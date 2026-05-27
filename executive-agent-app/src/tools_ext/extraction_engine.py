"""
Extraction Engine — structured data extraction from HTML and raw text.

Architecture position:
  Search (DDG/Bing) → Playwright → HTTP → [ExtractionEngine parses results]

Capabilities:
  - Search result page parsing (DDG, Bing, Google)
  - Business/lead data extraction from web pages
  - Email, phone, social link extraction
  - Structured JSON-LD parsing
  - Result validation and deduplication

Uses BeautifulSoup4 when available; falls back to stdlib html.parser.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import urljoin, urlparse


# ---------------------------------------------------------------------------
# Domains that are NOT valid business leads
# ---------------------------------------------------------------------------

_NOISE_DOMAINS = frozenset({
    "wikipedia.org", "wikimedia.org", "wikidata.org",
    "dictionary.com", "merriam-webster.com", "britannica.com",
    "investopedia.com", "cambridge.org",
    "reddit.com", "quora.com", "medium.com", "substack.com",
    "youtube.com", "vimeo.com", "tiktok.com",
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "pinterest.com",
    "amazon.com", "ebay.com", "etsy.com", "alibaba.com",
    "yelp.com", "yellowpages.com", "bbb.org", "tripadvisor.com",
    "indeed.com", "glassdoor.com", "ziprecruiter.com", "monster.com",
    "crunchbase.com", "owler.com", "zoominfo.com",
    "google.com", "bing.com", "yahoo.com", "duckduckgo.com",
    "gov", "edu",
})

_NOISE_PATTERNS = re.compile(
    r"\b(definition|meaning|dictionary|encyclopedia|wiki|"
    r"what is|how to|tutorial|guide|course|learn|study|"
    r"news|article|blog post|opinion)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Regex patterns for data extraction
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}\b"
)
_PHONE_RE = re.compile(
    r"(?:\+?1[\s\-.]?)?"
    r"(?:\(\d{3}\)|\d{3})"
    r"[\s\-.]?\d{3}[\s\-.]?\d{4}"
    r"(?!\d)"
)
_LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(?:company|in)/([a-zA-Z0-9\-_%.]+)"
)
_TWITTER_RE = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([a-zA-Z0-9_]{1,50})"
)
_INSTAGRAM_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.]{1,50})"
)
_FACEBOOK_RE = re.compile(
    r"https?://(?:www\.)?facebook\.com/([a-zA-Z0-9.]{1,80})"
)


# ---------------------------------------------------------------------------
# Minimal stdlib HTML text/link extractor
# ---------------------------------------------------------------------------

class _StdlibParser(HTMLParser):
    """Extract text, links, and meta tags using stdlib html.parser."""

    SKIP = {"script", "style", "noscript", "head", "link", "button", "input"}

    def __init__(self, base_url: str = ""):
        super().__init__()
        self._skip = 0
        self._base = base_url
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []   # (href, anchor_text)
        self.emails: list[str] = []
        self.meta: dict[str, str] = {}
        self.title: str = ""
        self._in_title = False
        self._cur_href = ""
        self._cur_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list):
        d = dict(attrs)
        if tag in self.SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            name = d.get("name", d.get("property", "")).lower()
            content = d.get("content", "")
            if name and content:
                self.meta[name] = content
        if tag == "a":
            href = d.get("href", "")
            if href.startswith("mailto:"):
                self.emails.append(href[7:].split("?")[0])
            elif href:
                if not href.startswith(("http", "//")):
                    href = urljoin(self._base, href)
                self._cur_href = href
        self._cur_text = []

    def handle_endtag(self, tag: str):
        if tag in self.SKIP:
            self._skip = max(self._skip - 1, 0)
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._cur_href:
            anchor = " ".join(self._cur_text).strip()
            self.links.append((self._cur_href, anchor))
            self._cur_href = ""
            self._cur_text = []

    def handle_data(self, data: str):
        if self._skip:
            return
        cleaned = data.strip()
        if not cleaned:
            return
        if self._in_title:
            self.title = cleaned
        if self._cur_href:
            self._cur_text.append(cleaned)
        self.text_parts.append(cleaned)

    def get_text(self) -> str:
        return " ".join(self.text_parts)


# ---------------------------------------------------------------------------
# Core extraction engine
# ---------------------------------------------------------------------------

class ExtractionEngine:
    """
    Structured data extractor for HTML pages and raw text.

    Uses BeautifulSoup4 when installed (richer selectors);
    falls back to stdlib html.parser transparently.
    """

    def __init__(self):
        self._bs4_available: Optional[bool] = None

    def _has_bs4(self) -> bool:
        if self._bs4_available is None:
            try:
                import bs4  # noqa: F401
                self._bs4_available = True
            except ImportError:
                self._bs4_available = False
        return self._bs4_available

    # ------------------------------------------------------------------
    # Search result page parsers
    # ------------------------------------------------------------------

    def parse_ddg_results(self, html: str) -> list[dict]:
        """
        Parse DuckDuckGo HTML search results page.
        Returns list of {title, url, snippet}.
        """
        results: list[dict] = []
        if self._has_bs4():
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for result in soup.select(".result"):
                title_el = result.select_one("a.result__a")
                url_el   = result.select_one(".result__extras__url, .result__url")
                snip_el  = result.select_one(".result__snippet")
                if not title_el:
                    continue
                href  = title_el.get("href", "")
                title = title_el.get_text(strip=True)
                url   = url_el.get_text(strip=True) if url_el else href
                snip  = snip_el.get_text(strip=True) if snip_el else ""
                if href and title:
                    results.append({"title": title, "url": href, "snippet": snip})
        else:
            # Regex fallback
            for m in re.finditer(
                r'<a[^>]+class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                html, re.DOTALL
            ):
                href  = m.group(1)
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                if href and title:
                    results.append({"title": title, "url": href, "snippet": ""})
        return results

    def parse_bing_results(self, html: str) -> list[dict]:
        """
        Parse Bing HTML search results page.
        Returns list of {title, url, snippet}.
        """
        results: list[dict] = []
        if self._has_bs4():
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for li in soup.select("li.b_algo"):
                title_el = li.select_one("h2 a")
                snip_el  = li.select_one(".b_caption p, .b_algoSlug")
                if not title_el:
                    continue
                href  = title_el.get("href", "")
                title = title_el.get_text(strip=True)
                snip  = snip_el.get_text(strip=True) if snip_el else ""
                if href and title:
                    results.append({"title": title, "url": href, "snippet": snip})
        else:
            for m in re.finditer(
                r'<h2[^>]*><a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
                html, re.DOTALL
            ):
                href  = m.group(1)
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                if href and title:
                    results.append({"title": title, "url": href, "snippet": ""})
        return results

    # ------------------------------------------------------------------
    # Business / lead extraction from a company web page
    # ------------------------------------------------------------------

    def extract_business_data(self, html: str, source_url: str = "") -> dict:
        """
        Extract structured business data from a company web page.

        Returns:
          {
            title, description, emails, phones,
            linkedin, twitter, instagram, facebook,
            address, structured_data (JSON-LD),
          }
        """
        data: dict[str, Any] = {
            "title": "", "description": "", "emails": [], "phones": [],
            "linkedin": "", "twitter": "", "instagram": "", "facebook": "",
            "address": "", "structured_data": [],
        }

        if self._has_bs4():
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Title
            title_tag = soup.find("title")
            data["title"] = title_tag.get_text(strip=True) if title_tag else ""

            # Meta description
            meta = (soup.find("meta", attrs={"name": "description"}) or
                    soup.find("meta", attrs={"property": "og:description"}))
            if meta:
                data["description"] = meta.get("content", "")[:400]

            # Emails from mailto links
            for a in soup.select("a[href^='mailto:']"):
                email = a["href"][7:].split("?")[0].strip()
                if email and email not in data["emails"]:
                    data["emails"].append(email)

            # Social links
            for a in soup.find_all("a", href=True):
                href = a["href"]
                m = _LINKEDIN_RE.search(href)
                if m and not data["linkedin"]:
                    data["linkedin"] = href
                m = _TWITTER_RE.search(href)
                if m and not data["twitter"]:
                    data["twitter"] = href
                m = _INSTAGRAM_RE.search(href)
                if m and not data["instagram"]:
                    data["instagram"] = href
                m = _FACEBOOK_RE.search(href)
                if m and not data["facebook"]:
                    data["facebook"] = href

            # JSON-LD structured data
            for script in soup.select("script[type='application/ld+json']"):
                try:
                    obj = json.loads(script.string or "")
                    data["structured_data"].append(obj)
                except Exception:
                    pass

            # Address from schema.org or itemprop
            addr_el = (soup.find(itemprop="address") or
                       soup.find(attrs={"class": re.compile(r"address", re.I)}))
            if addr_el:
                data["address"] = addr_el.get_text(separator=" ", strip=True)[:200]

            text = soup.get_text(separator=" ")
        else:
            parser = _StdlibParser(base_url=source_url)
            parser.feed(html)
            data["title"] = parser.title
            data["description"] = parser.meta.get("description", "")[:400]
            data["emails"] = parser.emails
            for href, _ in parser.links:
                if _LINKEDIN_RE.search(href) and not data["linkedin"]:
                    data["linkedin"] = href
                if _TWITTER_RE.search(href) and not data["twitter"]:
                    data["twitter"] = href
            text = parser.get_text()

        # Regex sweep on full text for extra emails/phones
        for e in _EMAIL_RE.findall(text):
            e = e.strip(".,;")
            if (e not in data["emails"]
                    and not re.search(r"\.(png|jpg|gif|svg|css|js|woff)$", e, re.I)):
                data["emails"].append(e)
        data["emails"] = data["emails"][:5]

        for p in _PHONE_RE.findall(text):
            cleaned = re.sub(r"[^\d+]", "", p)
            if len(cleaned) >= 7 and cleaned not in data["phones"]:
                data["phones"].append(p.strip())
        data["phones"] = data["phones"][:3]

        # LinkedIn from text sweep if not found in links
        if not data["linkedin"]:
            m = _LINKEDIN_RE.search(text)
            if m:
                data["linkedin"] = m.group(0)

        return data

    # ------------------------------------------------------------------
    # Page-level text extraction (for Playwright pages)
    # ------------------------------------------------------------------

    def extract_text_blocks(self, html: str) -> list[str]:
        """
        Extract meaningful text blocks (paragraphs, headings, list items)
        from HTML. Useful for summarisation or further NLP.
        """
        blocks: list[str] = []
        if self._has_bs4():
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "td", "th"]):
                t = tag.get_text(strip=True)
                if len(t) > 20:
                    blocks.append(t)
        else:
            parser = _StdlibParser()
            parser.feed(html)
            for part in parser.text_parts:
                if len(part) > 20:
                    blocks.append(part)
        return blocks

    def extract_tables(self, html: str) -> list[list[list[str]]]:
        """
        Extract all HTML tables as list of rows (each row = list of cell strings).
        """
        tables: list[list[list[str]]] = []
        if self._has_bs4():
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for table in soup.find_all("table"):
                rows: list[list[str]] = []
                for tr in table.find_all("tr"):
                    cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    if cells:
                        rows.append(cells)
                if rows:
                    tables.append(rows)
        return tables

    # ------------------------------------------------------------------
    # Validation and deduplication
    # ------------------------------------------------------------------

    def is_valid_lead(self, url: str, title: str, snippet: str = "") -> bool:
        """
        Return True if a search result looks like a real business lead.
        Filters out noise domains, Wikipedia, etc.
        """
        if not url or not title:
            return False
        try:
            domain = urlparse(url).netloc.lower().lstrip("www.")
        except Exception:
            return False

        # Check against noise domains
        for noise in _NOISE_DOMAINS:
            if domain.endswith(noise):
                return False

        # Check for obvious non-business title patterns
        if _NOISE_PATTERNS.search(title):
            return False

        # Require at least a minimal snippet or title length
        if len(title.strip()) < 4:
            return False

        return True

    def deduplicate(
        self,
        items: list[dict],
        key: str = "url",
        normalize_fn=None,
    ) -> list[dict]:
        """
        Remove duplicate items by a key field.

        normalize_fn: optional function(value) → canonical key.
        Default for URLs: extract domain only.
        """
        if normalize_fn is None and key in ("url", "website"):
            def normalize_fn(v):  # type: ignore[misc]
                try:
                    return urlparse(v).netloc.lower().lstrip("www.")
                except Exception:
                    return v

        seen: set[str] = set()
        result: list[dict] = []
        for item in items:
            raw = item.get(key, "")
            canon = normalize_fn(raw) if normalize_fn else raw
            if canon and canon not in seen:
                seen.add(canon)
                result.append(item)
        return result

    def score_lead(self, lead: dict) -> int:
        """
        Score a lead 0-10 based on data richness.
        Higher = more complete / reliable.
        """
        score = 0
        if lead.get("company"):   score += 2
        if lead.get("website"):   score += 2
        if lead.get("description") and len(lead["description"]) > 30: score += 1
        if lead.get("email_hints") or lead.get("emails"): score += 2
        if lead.get("linkedin"):  score += 1
        if lead.get("phones"):    score += 1
        if lead.get("address"):   score += 1
        return score

    # ------------------------------------------------------------------
    # Playwright page → structured lead
    # ------------------------------------------------------------------

    def page_html_to_lead(self, html: str, source_url: str, title_hint: str = "") -> dict:
        """
        Convert a full company web page HTML into a lead dict.
        """
        biz = self.extract_business_data(html, source_url)
        return {
            "company":     biz["title"] or title_hint,
            "website":     source_url,
            "description": biz["description"],
            "email_hints": biz["emails"],
            "phones":      biz["phones"],
            "linkedin":    biz["linkedin"],
            "twitter":     biz["twitter"],
            "instagram":   biz["instagram"],
            "address":     biz["address"],
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_engine: Optional[ExtractionEngine] = None


def get_extraction_engine() -> ExtractionEngine:
    """Return the shared ExtractionEngine instance."""
    global _engine
    if _engine is None:
        _engine = ExtractionEngine()
    return _engine
