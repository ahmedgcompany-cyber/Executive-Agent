"""
Web Research Tools — multi-layer fallback scraper.

Uses Python stdlib ONLY (urllib, html.parser, re) as primary backend.
requests + BeautifulSoup4 are loaded as optional upgrades if installed.

Fallback chain (each layer tried if previous fails or returns nothing):
  L1  DuckDuckGo HTML POST   — no JS, no CAPTCHA, stdlib urllib
  L2  Bing HTML GET          — browser-like headers, stdlib urllib
  L3  DuckDuckGo Instant API — JSON endpoint, no CAPTCHA
  L4  Direct HTTP fetch      — fetch a specific URL
  L5  PowerShell             — Windows last-resort

All methods return:
  {"success": bool, "results": [...], "raw_text": str, "source": str, "error": str}

Each result item:
  {"title": str, "url": str, "snippet": str}
"""

from __future__ import annotations

import base64
import gzip
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# User-agent rotation
# ---------------------------------------------------------------------------

_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0"
    ),
]
_UA_IDX = 0


def _next_ua() -> str:
    global _UA_IDX
    ua = _USER_AGENTS[_UA_IDX % len(_USER_AGENTS)]
    _UA_IDX += 1
    return ua


def _make_request(url: str, data: bytes | None = None,
                  extra_headers: dict | None = None,
                  timeout: int = 15) -> str:
    """
    Perform an HTTP GET or POST using urllib (stdlib).
    Handles gzip decompression automatically.
    Returns the decoded response body or raises.
    """
    headers = {
        "User-Agent": _next_ua(),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        encoding = resp.headers.get("Content-Encoding", "")
        if encoding == "gzip":
            raw = gzip.decompress(raw)
        charset = "utf-8"
        ct = resp.headers.get("Content-Type", "")
        if "charset=" in ct:
            charset = ct.split("charset=")[-1].strip().split(";")[0].strip()
        try:
            return raw.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Minimal HTML text extractor (stdlib html.parser)
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Extract visible text and <a href> links from HTML."""

    SKIP_TAGS = {"script", "style", "noscript", "head", "meta",
                 "link", "input", "button", "svg", "path"}

    def __init__(self):
        super().__init__()
        self._skip = 0
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []   # (href, text)
        self._in_a = False
        self._a_href = ""
        self._a_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip += 1
        if tag == "a":
            self._in_a = True
            self._a_href = dict(attrs).get("href", "")
            self._a_text = []

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip > 0:
            self._skip -= 1
        if tag == "a" and self._in_a:
            text = " ".join(self._a_text).strip()
            if self._a_href and text:
                self.links.append((self._a_href, text))
            self._in_a = False
            self._a_href = ""

    def handle_data(self, data):
        if self._skip:
            return
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)
            if self._in_a:
                self._a_text.append(stripped)

    def get_text(self) -> str:
        return " ".join(self.text_parts)


def _parse_html(html: str) -> _TextExtractor:
    p = _TextExtractor()
    try:
        p.feed(html)
    except Exception:
        pass
    return p


def _strip_html(html: str) -> str:
    """Quick regex-only tag stripper (fallback)."""
    text = re.sub(r"<[^>]+>", " ", html)
    for ent, ch in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")]:
        text = text.replace(ent, ch)
    return re.sub(r"\s{2,}", " ", text).strip()


# ---------------------------------------------------------------------------
# Optional: try to use requests + bs4 for better parsing
# ---------------------------------------------------------------------------

def _try_bs4(html: str):
    """Return BeautifulSoup object if bs4 is installed, else None."""
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "html.parser")
    except ImportError:
        return None


def _try_requests_get(url: str, headers: dict, timeout: int = 15, data=None):
    """Use requests if available, else fall back to urllib."""
    try:
        import requests as _req
        if data:
            r = _req.post(url, data=data, headers=headers, timeout=timeout)
        else:
            r = _req.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.text
    except ImportError:
        # requests not installed — use stdlib
        enc_data = None
        if data:
            if isinstance(data, dict):
                enc_data = urllib.parse.urlencode(data).encode()
            elif isinstance(data, str):
                enc_data = data.encode()
            else:
                enc_data = data
        return _make_request(url, data=enc_data, extra_headers=headers, timeout=timeout)


# ---------------------------------------------------------------------------
# Layer 1 — DuckDuckGo HTML search (POST, no CAPTCHA)
# ---------------------------------------------------------------------------

def search_duckduckgo(query: str, max_results: int = 10) -> dict:
    """DuckDuckGo HTML endpoint — works with urllib, no CAPTCHA."""
    url = "https://html.duckduckgo.com/html/"
    payload = urllib.parse.urlencode({"q": query, "b": "", "kl": "us-en"}).encode()
    extra = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://duckduckgo.com/",
    }
    try:
        html = _make_request(url, data=payload, extra_headers=extra)
    except Exception as exc:
        return {"success": False, "results": [], "raw_text": "",
                "source": "ddg", "error": str(exc)}

    results: list[dict] = []

    # Try bs4 first — DDG uses multi-class "links_main links_deep result__body"
    soup = _try_bs4(html)
    if soup:
        # Select by the result__body class (BS4 matches even with multiple classes)
        blocks = soup.select(".result__body") or soup.select(".links_main")
        for r in blocks[:max_results]:
            # Title: in <a class="result__a">
            a_el    = r.select_one("a.result__a") or r.select_one(".result__a")
            title   = a_el.get_text(strip=True) if a_el else ""
            # URL: prefer href from the link, fall back to result__extras__url display text
            href    = a_el["href"] if a_el and a_el.has_attr("href") else ""
            url_el  = r.select_one(".result__extras__url") or r.select_one(".result__url")
            raw_url = href or (url_el.get_text(strip=True) if url_el else "")
            # Make display URL into absolute if needed
            if raw_url and not raw_url.startswith("http"):
                raw_url = "https://" + raw_url.lstrip("/")
            snip_el = r.select_one(".result__snippet")
            snippet = snip_el.get_text(strip=True) if snip_el else ""
            if title:
                results.append({"title": title, "url": raw_url, "snippet": snippet})

    # Always run regex fallback to fill gaps (DDG HTML changes frequently)
    if len(results) < max_results:
        pat_block = re.compile(
            r'class="[^"]*result__a[^"]*"\s+href="([^"]+)"[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        pat_snip = re.compile(
            r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:span|div|a)',
            re.IGNORECASE | re.DOTALL,
        )
        snippets_raw = [_strip_html(m.group(1)) for m in pat_snip.finditer(html)]
        seen_titles = {r["title"] for r in results}
        snip_idx = 0
        for m in pat_block.finditer(html):
            if len(results) >= max_results:
                break
            href  = m.group(1)
            title = _strip_html(m.group(2))
            if not title or len(title) <= 3 or title in seen_titles:
                continue
            # Skip DDG internal links
            if "duckduckgo.com" in href or href.startswith("//duckduckgo"):
                continue
            snip = snippets_raw[snip_idx] if snip_idx < len(snippets_raw) else ""
            snip_idx += 1
            # Normalise relative URLs
            if href.startswith("//"):
                href = "https:" + href
            results.append({"title": title, "url": href, "snippet": snip})
            seen_titles.add(title)

    if not results:
        # Last resort: extract any <a href> with a clean external URL
        for href, text in _parse_html(html).links:
            if len(results) >= max_results:
                break
            if (href.startswith("http") and "duckduckgo.com" not in href
                    and len(text) > 5 and len(text) < 120):
                results.append({"title": text, "url": href, "snippet": ""})

    return {
        "success": bool(results),
        "results": results[:max_results],
        "raw_text": _strip_html(html)[:3000],
        "source": "duckduckgo",
        "error": "" if results else "No results parsed from DDG",
    }


# ---------------------------------------------------------------------------
# Bing redirect URL decoder
# ---------------------------------------------------------------------------

def _decode_bing_url(url: str) -> str:
    """
    Decode Bing's ck/a redirect URL to the real destination.
    Format: https://www.bing.com/ck/a?!&&p=...&u=a1<base64url>
    The base64url portion after 'a1' encodes the real URL.
    """
    if "bing.com/ck/a" not in url:
        return url
    m = re.search(r"[?&]u=a1([A-Za-z0-9_=-]+)", url)
    if not m:
        return url
    try:
        # base64url padding
        encoded = m.group(1)
        padding = 4 - (len(encoded) % 4)
        if padding != 4:
            encoded += "=" * padding
        decoded = base64.urlsafe_b64decode(encoded).decode("utf-8", errors="replace")
        if decoded.startswith("http"):
            return decoded
    except Exception:
        pass
    return url


# ---------------------------------------------------------------------------
# Layer 2 — Bing HTML search (GET, browser headers)
# ---------------------------------------------------------------------------

def search_bing(query: str, max_results: int = 10) -> dict:
    """Bing HTML search with realistic browser headers."""
    enc = urllib.parse.quote_plus(query)
    url = (
        f"https://www.bing.com/search?q={enc}&count={max_results}"
        f"&form=QBLH&mkt=en-US&setLang=en&cc=US"
    )
    extra = {"Referer": "https://www.bing.com/"}

    try:
        time.sleep(0.4)
        html = _make_request(url, extra_headers=extra)
    except Exception as exc:
        return {"success": False, "results": [], "raw_text": "",
                "source": "bing", "error": str(exc)}

    results: list[dict] = []
    soup = _try_bs4(html)
    if soup:
        for li in soup.select("li.b_algo")[:max_results]:
            h2 = li.select_one("h2")
            a  = h2.select_one("a") if h2 else None
            p  = li.select_one("p, .b_caption p")
            title   = a.get_text(strip=True)   if a else ""
            href    = _decode_bing_url(a["href"]) if a and a.has_attr("href") else ""
            snippet = p.get_text(strip=True)   if p else ""
            if title and href:
                results.append({"title": title, "url": href, "snippet": snippet})
    else:
        # Regex fallback for Bing — also decode redirect URLs
        pat = re.compile(
            r'<h2>\s*<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for m in pat.finditer(html):
            href  = _decode_bing_url(m.group(1))
            title = _strip_html(m.group(2))
            if title and "bing.com" not in href:
                results.append({"title": title, "url": href, "snippet": ""})
            if len(results) >= max_results:
                break

    return {
        "success": bool(results),
        "results": results[:max_results],
        "raw_text": _strip_html(html)[:3000],
        "source": "bing",
        "error": "" if results else "No results parsed from Bing",
    }


# ---------------------------------------------------------------------------
# Layer 3 — DuckDuckGo Instant Answer API (JSON, never CAPTCHA)
# ---------------------------------------------------------------------------

def ddg_instant_answer(query: str) -> dict:
    """DuckDuckGo Instant Answers — pure JSON, no blocks."""
    import json
    params = urllib.parse.urlencode({
        "q": query, "format": "json",
        "no_html": "1", "skip_disambig": "1", "no_redirect": "1",
    })
    url = f"https://api.duckduckgo.com/?{params}"
    try:
        raw = _make_request(url)
        data = json.loads(raw)
    except Exception as exc:
        return {"success": False, "results": [], "raw_text": "",
                "source": "ddg_api", "error": str(exc)}

    results = []
    abstract = data.get("AbstractText", "")
    if abstract:
        results.append({
            "title":   data.get("Heading", query),
            "url":     data.get("AbstractURL", ""),
            "snippet": abstract[:500],
        })
    for topic in data.get("RelatedTopics", [])[:8]:
        if isinstance(topic, dict) and topic.get("Text"):
            results.append({
                "title":   topic["Text"][:80],
                "url":     topic.get("FirstURL", ""),
                "snippet": topic["Text"],
            })

    return {
        "success": bool(results),
        "results": results,
        "raw_text": abstract[:2000] or str(data)[:1000],
        "source": "ddg_instant",
        "error": "" if results else "No instant answer",
    }


# ---------------------------------------------------------------------------
# Layer 4 — Direct HTTP fetch of a specific URL
# ---------------------------------------------------------------------------

def fetch_url(url: str, timeout: int = 15) -> dict:
    """Fetch a URL and return visible text."""
    try:
        html = _make_request(url, timeout=timeout)
    except Exception as exc:
        return {"success": False, "results": [], "raw_text": "",
                "source": "http_fetch", "error": str(exc)}

    # Title
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = _strip_html(title_m.group(1)) if title_m else url

    # Text
    soup = _try_bs4(html)
    if soup:
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        main = soup.find("main") or soup.find("article") or soup.body
        text = main.get_text(separator="\n", strip=True) if main else soup.get_text()
        text = re.sub(r"\n{3,}", "\n\n", text)[:5000]
    else:
        parser = _parse_html(html)
        text = " ".join(parser.text_parts)[:5000]

    return {
        "success": True,
        "results": [{"title": title, "url": url, "snippet": text[:300]}],
        "raw_text": text,
        "source": "http_fetch",
        "error": "",
    }


# ---------------------------------------------------------------------------
# Layer 5 — PowerShell Invoke-WebRequest (Windows only)
# ---------------------------------------------------------------------------

def fetch_via_powershell(url: str) -> dict:
    """PowerShell fallback — Windows only."""
    if sys.platform != "win32":
        return {"success": False, "results": [], "raw_text": "",
                "source": "powershell", "error": "Not Windows"}
    ua = _next_ua()
    ps_script = (
        f"[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; "
        f"$r = Invoke-WebRequest -Uri '{url}' "
        f"-UserAgent '{ua}' -UseBasicParsing -TimeoutSec 15; "
        f"Write-Output $r.Content"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=25,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = (proc.stdout or "").strip()
        if not output:
            return {"success": False, "results": [], "raw_text": "",
                    "source": "powershell",
                    "error": proc.stderr.strip() or "Empty response"}
        text = _strip_html(output)[:5000]
        return {
            "success": True,
            "results": [{"title": url, "url": url, "snippet": text[:300]}],
            "raw_text": text,
            "source": "powershell",
            "error": "",
        }
    except Exception as exc:
        return {"success": False, "results": [], "raw_text": "",
                "source": "powershell", "error": str(exc)}


# ---------------------------------------------------------------------------
# Master search — try all layers
# ---------------------------------------------------------------------------

def web_search(query: str, max_results: int = 10) -> dict:
    """
    Try each search layer in order, return the first success.

    Pure stdlib — no external packages required.
    """
    layers = [
        ("DuckDuckGo HTML", lambda: search_duckduckgo(query, max_results)),
        ("Bing",            lambda: search_bing(query, max_results)),
        ("DDG Instant",     lambda: ddg_instant_answer(query)),
    ]

    last_error = "All layers failed"
    for name, fn in layers:
        try:
            result = fn()
            if result.get("success") and result.get("results"):
                result["query"] = query
                return result
            last_error = f"{name}: {result.get('error', 'no results')}"
        except Exception as exc:
            last_error = f"{name} exception: {exc}"

    return {
        "success": False, "results": [], "raw_text": "",
        "source": "none", "query": query, "error": last_error,
    }


# ---------------------------------------------------------------------------
# Research a specific company
# ---------------------------------------------------------------------------

def research_business(name: str, industry: str = "") -> dict:
    """Find a company's website, emails, LinkedIn URL."""
    query = f"{name} {industry} official website contact email".strip()
    sr = web_search(query, max_results=5)

    company_url = ""
    description = ""
    if sr.get("results"):
        for r in sr["results"]:
            u = r.get("url", "")
            skip = ("wikipedia.", "yelp.", "facebook.", "twitter.", "instagram.",
                    "google.", "bing.", "duckduckgo.", "linkedin.com/jobs",
                    "indeed.", "glassdoor.")
            if u and not any(s in u for s in skip):
                company_url = u
                description = r.get("snippet", "")
                break

    email_hints: list[str] = []
    linkedin_url = ""
    site_text = ""

    if company_url:
        fetch = fetch_url(company_url)
        if fetch.get("success"):
            site_text = fetch.get("raw_text", "")
            emails = re.findall(
                r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}",
                site_text,
            )
            email_hints = list(dict.fromkeys(
                e for e in emails
                if not re.search(r"\.(png|jpg|gif|svg|css|js)$", e, re.I)
            ))[:3]
            li_m = re.search(
                r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[^\s\"'<>]+",
                site_text,
            )
            if li_m:
                linkedin_url = li_m.group(0).rstrip("/.,)")

    return {
        "company": name,
        "website": company_url,
        "description": description[:400],
        "email_hints": email_hints,
        "linkedin": linkedin_url,
        "raw": site_text[:2000],
    }


# ---------------------------------------------------------------------------
# Discover businesses in a niche
# ---------------------------------------------------------------------------

_SKIP_DOMAINS = (
    "yelp.", "yellowpages.", "tripadvisor.", "bbb.org",
    "google.com", "duckduckgo.", "bing.com/search", "bing.com/ck/a",
    "facebook.com", "twitter.com", "instagram.com",
    "indeed.", "glassdoor.", "linkedin.com/jobs",
    "wikipedia.", "reddit.", "quora.",
)


def discover_businesses(niche: str, location: str = "", count: int = 10) -> list[dict]:
    """
    Discover real businesses in a niche via multi-layer web search.

    Pipeline:
      1. Generate 5 diverse query variants
      2. Multi-retry: if results stay sparse after 3 queries, add 2 more variants
      3. Validate each result (ExtractionEngine if available, else _SKIP_DOMAINS)
      4. Deduplicate by domain
      5. Enrich top candidates (fetch site to extract emails + LinkedIn)

    Returns list of dicts: company / website / description / email_hints / linkedin.
    """
    # Load ExtractionEngine for validation + dedup (graceful fallback if unavailable)
    try:
        from .extraction_engine import get_extraction_engine
        extractor = get_extraction_engine()
    except Exception:
        extractor = None

    loc_part = f" {location}" if location else ""

    # 5 diverse query variants covering different search intents
    queries: list[str] = [
        f"{niche}{loc_part} companies contact email",
        f"top {niche}{loc_part} businesses website",
        f"{niche}{loc_part} agency services contact",
        f"best {niche}{loc_part} list directory",
        f"{niche}{loc_part} firm services official site",
    ]

    seen: dict[str, dict] = {}   # domain → record

    for q_idx, q in enumerate(queries):
        if len(seen) >= count:
            break

        # Multi-retry: if still sparse halfway through, inject two extra variants
        if q_idx == 3 and len(seen) < max(count // 2, 3):
            extra: list[str] = [
                f'"{niche}" {location} email contact'.strip(),
                (
                    f"{niche} near {location} services"
                    if location else
                    f"{niche} services provider website"
                ),
            ]
            queries.extend(extra)

        sr = web_search(q, max_results=max(count * 2, 20))

        for r in sr.get("results", []):
            if len(seen) >= count * 2:   # collect extras for scoring
                break
            url   = r.get("url", "")
            title = r.get("title", "")
            snip  = r.get("snippet", "")
            if not url or not title:
                continue

            # Validate: ExtractionEngine is authoritative; fallback to _SKIP_DOMAINS
            if extractor:
                if not extractor.is_valid_lead(url, title, snip):
                    continue
            else:
                if any(d in url for d in _SKIP_DOMAINS):
                    continue

            dm = re.match(r"https?://(?:www\.)?([^/]+)", url)
            domain = dm.group(1) if dm else url
            if domain not in seen:
                seen[domain] = {
                    "company":     title.split(" - ")[0].split(" | ")[0][:80],
                    "website":     url,
                    "description": snip[:300],
                    "email_hints": [],
                    "linkedin":    "",
                }

        if len(seen) < max(count // 2, 3):
            time.sleep(0.5)

    # Deduplicate (ExtractionEngine handles domain normalisation if available)
    candidates = list(seen.values())
    if extractor and candidates:
        candidates = extractor.deduplicate(candidates, key="website")

    # Enrich top candidates: visit their sites to extract real emails + LinkedIn
    enriched: list[dict] = []
    for biz in candidates[:count]:
        try:
            fetch = fetch_url(biz["website"], timeout=10)
            if fetch.get("success") and fetch.get("raw_text"):
                site_text = fetch["raw_text"]
                emails = re.findall(
                    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}",
                    site_text,
                )
                biz["email_hints"] = list(dict.fromkeys(
                    e for e in emails
                    if not re.search(r"\.(png|jpg|gif|svg|css|js)$", e, re.I)
                ))[:3]
                li_m = re.search(
                    r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[^\s\"'<>]+",
                    site_text,
                )
                if li_m:
                    biz["linkedin"] = li_m.group(0).rstrip("/.,)")
        except Exception:
            pass
        enriched.append(biz)

    return enriched[:count]


# ---------------------------------------------------------------------------
# Niche extraction — shared by sales agent and browser agent
# ---------------------------------------------------------------------------

# Words that indicate meta-instructions in a goal, not the actual niche
_META_WORDS = re.compile(
    r"\b(build|create|find|generate|autonomous|system|agent|outreach|lead|leads|"
    r"list|top|best|with|for|the|and|or|task|objective|mission|please|should|must|"
    r"fully|complete|target|discovery|identify|extract|niche|research|analysis|"
    r"search|report|data|business|businesses|company|companies|each|their|"
    r"from|into|have|will|would|that|this|your|manual|intervention|without|step|"
    r"also|then|after|before|when|where|which|some|many|more|most|all|any|"
    r"generation|automation|pipeline|funnel|sequence|outbound|inbound|"
    r"discover|prospects?|fully|automated|goal|using|via|through|based)\b",
    re.IGNORECASE,
)

_DEFAULT_NICHES = [
    "digital marketing agencies",
    "e-commerce businesses",
    "SaaS companies",
    "real estate agencies",
    "gym owners",
]


def extract_niche_from_goal(goal: str, fallback: str = "") -> tuple[str, str]:
    """
    Extract the target niche and optional location from a goal string.

    Returns (niche, location).

    Strategy (in priority order):
    1. Explicit label:  "niche: X", "industry: X", "targeting: X", "sector: X"
    2. Parenthetical examples: "(e.g., real estate agents in Dubai, gym owners)"
       → use the first example (strip "in <location>" into the location field)
    3. "for [niche] companies/businesses/owners" pattern
    4. Strip meta-instruction words and take first meaningful noun phrase
    5. Use fallback or a sensible default
    """
    # 1. Explicit label — must have a colon to avoid "Target Discovery" false matches
    explicit = re.search(
        r"(?:niche|industry|sector|targeting|target)\s*:\s*([^\n,.(]{5,60})",
        goal, re.IGNORECASE,
    )
    if explicit:
        val = explicit.group(1).strip()
        # Don't accept obviously meta values; strip trailing punctuation before check
        first_word = (val.split()[0] if val.split() else val).rstrip(":.,;!?")
        if not _META_WORDS.fullmatch(first_word):
            return _split_loc(val)

    # 2. Parenthetical "(e.g., X, Y, Z)" — pick first example
    eg_match = re.search(r"\(e\.?g\.?,?\s*([^)]{5,120})\)", goal, re.IGNORECASE)
    if eg_match:
        examples = eg_match.group(1).split(",")
        first = examples[0].strip()
        if first:
            return _split_loc(first)

    # 3a. "for [qualifier] companies/businesses/owners/agencies [in X]"
    # Capture the noun AND any trailing "in <location>"
    for_match = re.search(
        r"\bfor\s+([a-zA-Z0-9\-][a-zA-Z0-9\-\s]{2,40}?)\s+(companies|businesses|owners?|agencies|brands|clients|leads?|firms|studios|clinics|shops?)\b",
        goal, re.IGNORECASE,
    )
    if for_match:
        qualifier = for_match.group(1).strip()
        noun = for_match.group(2).strip()
        # Include any "in <location>" that follows the noun
        rest = goal[for_match.end():].strip().rstrip(".,;:!?")
        val = qualifier + " " + noun + (" " + rest if rest else "")
        if len(qualifier.split()) <= 5:
            return _split_loc(val)

    # 3b. "find/research/discover N? [niche phrase]" — capture full phrase then split location
    action_match = re.search(
        r"\b(?:find|research|discover|identify|target|search\s+for)\s+(?:\d+\s+)?(.+?)(?:\.|$)",
        goal, re.IGNORECASE,
    )
    if action_match:
        candidate = action_match.group(1).strip()
        # Split location FIRST (preserves "in" for location detection)
        raw_niche, loc = _split_loc(candidate)
        # Accept if first word is not a pure meta/verb word (e.g. not "lead", "data")
        # Don't strip noun-class words like "companies"/"agencies" — they're part of the niche
        words = raw_niche.split()
        if words and not _META_WORDS.fullmatch(words[0].rstrip(".,;:!?").lower()):
            return raw_niche.strip(), loc

    # 4. Strip meta words and take first noun phrase (2–4 words)
    clean = _META_WORDS.sub(" ", goal[:400])
    # Also remove pure instruction fragments
    clean = re.sub(r"\d+[.)]\s*", " ", clean)
    words = [w for w in re.findall(r"[a-zA-Z]{3,}", clean)
             if len(w) >= 3 and w.lower() not in
             {"that", "this", "your", "their", "into", "have", "owner", "name",
              "email", "phone", "site", "page", "step", "find", "each"}]
    if words:
        phrase = " ".join(words[:3])
        if phrase:
            return phrase, ""

    # 5. Fallback
    return (fallback or _DEFAULT_NICHES[0], "")


def _split_loc(phrase: str) -> tuple[str, str]:
    """Split 'real estate agents in Dubai' → ('real estate agents', 'Dubai').
    Handles: multi-word cities (up to 3 words), articles ('in the USA'),
    uppercase abbreviations (USA, UK, NYC).
    """
    # Case-sensitive: title-case cities (New York) or all-uppercase abbreviations (USA, UK)
    m = re.search(
        r"\bin\s+(?:the\s+)?((?:[A-Z]{2,5}|[A-Z][a-z]+)(?:\s+(?:[A-Z]{2,5}|[A-Z][a-z]+)){0,2})\s*$",
        phrase,
    )
    if m:
        loc = m.group(1)
        niche = phrase[: m.start()].strip().rstrip(",")
        if niche:
            return niche, loc
    # Case-insensitive fallback: "in dubai", "in new york"
    m = re.search(
        r"\bin\s+(?:the\s+)?([a-zA-Z][a-z]+(?:\s+[a-zA-Z][a-z]+){0,2})\s*$",
        phrase, re.IGNORECASE,
    )
    if m:
        loc = m.group(1).title()
        niche = phrase[: m.start()].strip().rstrip(",")
        if niche:
            return niche, loc
    return phrase.strip(), ""


# ---------------------------------------------------------------------------
# WebResearcher — stateless facade used by agents
# ---------------------------------------------------------------------------

class WebResearcher:
    def search(self, query: str, max_results: int = 10) -> dict:
        return web_search(query, max_results)

    def discover(self, niche: str, location: str = "", count: int = 10) -> list[dict]:
        return discover_businesses(niche, location, count)

    def profile(self, company_name: str, industry: str = "") -> dict:
        return research_business(company_name, industry)

    def fetch(self, url: str) -> dict:
        return fetch_url(url)


_instance: WebResearcher | None = None


def get_web_researcher() -> WebResearcher:
    global _instance
    if _instance is None:
        _instance = WebResearcher()
    return _instance
