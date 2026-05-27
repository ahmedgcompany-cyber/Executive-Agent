"""Browser automation tools using Playwright.

Browser priority order (enforced by this module):
  1. Playwright / Chromium        — PRIMARY for all automation, headless, scraping, form-filling
  2. DuckDuckGo Desktop Browser   — OPTIONAL: user-visible browsing only (prefer_ddg=True)
  3. System default browser       — last resort fallback
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# DuckDuckGo Desktop Browser — detection, install, launch
# ---------------------------------------------------------------------------

# Candidate install paths on Windows
_DDG_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\DuckDuckGo\DuckDuckGo.exe"),
    r"C:\Program Files\DuckDuckGo\DuckDuckGo.exe",
    r"C:\Program Files (x86)\DuckDuckGo\DuckDuckGo.exe",
    os.path.expandvars(r"%APPDATA%\DuckDuckGo\DuckDuckGo.exe"),
]


def find_ddg_browser() -> Optional[str]:
    """Return the path to DuckDuckGo Desktop Browser, or None if not installed."""
    for path in _DDG_PATHS:
        if os.path.isfile(path):
            return path
    # Also check via winget list (silently)
    try:
        r = subprocess.run(
            ["winget", "list", "--id", "DuckDuckGo.DesktopBrowser", "-q"],
            capture_output=True, text=True, timeout=10,
        )
        if "DuckDuckGo" in r.stdout:
            for path in _DDG_PATHS:
                if os.path.isfile(path):
                    return path
    except Exception:
        pass
    return None


def install_ddg_browser() -> dict:
    """
    Install DuckDuckGo Desktop Browser on Windows.

    Tries winget first, then PowerShell direct download.
    Returns {"success": bool, "message": str, "method": str}.
    """
    # ── Strategy 1: winget ────────────────────────────────────────────
    try:
        r = subprocess.run(
            [
                "winget", "install",
                "--id", "DuckDuckGo.DesktopBrowser",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            capture_output=True, text=True, timeout=180,
        )
        if r.returncode == 0 or "Successfully installed" in r.stdout:
            exe = find_ddg_browser()
            return {
                "success": bool(exe),
                "message": f"Installed via winget. Exe: {exe or 'not found yet'}",
                "method": "winget",
            }
    except FileNotFoundError:
        pass  # winget not available
    except Exception as exc:
        pass

    # ── Strategy 2: PowerShell direct download ────────────────────────
    ps_script = r"""
$ErrorActionPreference = "Stop"
$url = "https://staticcdn.duckduckgo.com/windows/release/latest/DuckDuckGo-Windows.exe"
$out = "$env:TEMP\DuckDuckGo-Setup.exe"
Write-Host "Downloading DuckDuckGo Browser..."
Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
Write-Host "Installing..."
Start-Process -FilePath $out -ArgumentList "/S" -Wait
Write-Host "Done."
"""
    try:
        r = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=300,
        )
        if r.returncode == 0:
            exe = find_ddg_browser()
            return {
                "success": bool(exe),
                "message": f"Installed via PowerShell. Exe: {exe or 'not yet visible'}",
                "method": "powershell",
            }
        return {
            "success": False,
            "message": f"PowerShell install failed: {r.stderr[:300]}",
            "method": "powershell",
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"Install failed: {exc}",
            "method": "none",
        }


def open_url_in_ddg_browser(url: str) -> dict:
    """
    Open a URL in the DuckDuckGo Desktop Browser.

    If DDG browser is not installed, attempts to install it first.
    Returns {"success": bool, "message": str, "exe": str}.
    """
    exe = find_ddg_browser()

    if not exe:
        # Try to auto-install
        install_result = install_ddg_browser()
        if install_result.get("success"):
            exe = find_ddg_browser()
        if not exe:
            return {
                "success": False,
                "message": (
                    "DuckDuckGo Browser not installed and auto-install failed.\n"
                    + install_result.get("message", "")
                    + "\nManual install: https://duckduckgo.com/windows"
                ),
                "exe": None,
            }

    try:
        subprocess.Popen([exe, url])
        return {
            "success": True,
            "message": f"Opened {url} in DuckDuckGo Browser",
            "exe": exe,
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"Failed to launch DDG browser: {exc}",
            "exe": exe,
        }


@dataclass
class BrowserSession:
    """Browser session state."""
    playwright: Any = None
    browser: Any = None
    context: Any = None
    page: Any = None
    session_id: str = ""


class BrowserTools:
    """Web browser automation tools."""

    def __init__(self):
        """Initialize browser tools."""
        self.session: Optional[BrowserSession] = None
        self._playwright = None

    async def _ensure_playwright(self) -> Any:
        """Ensure playwright is imported."""
        if self._playwright is None:
            try:
                from playwright.async_api import async_playwright
                self._playwright = async_playwright
            except ImportError:
                raise ImportError("Playwright not installed. Run: pip install playwright")
        return self._playwright

    async def browser_open(self, url: str, headless: bool = False,
                           stealth: bool = False,
                           prefer_ddg: bool = False) -> dict[str, Any]:
        """Open a browser and navigate to URL.  Browser stays open after this call.

        Args:
            url:        URL to navigate to
            headless:   Whether to run in headless mode
            stealth:    Apply anti-detection measures (realistic UA, hide webdriver flag)
            prefer_ddg: Open in DuckDuckGo Desktop Browser (visual only — no automation API).
                        Only set True when the user explicitly wants to *view* a page.
                        For scraping, form-filling, or headless work use the default (False).

        Browser priority:
          1. Playwright / Chromium    — PRIMARY (automation, scraping, headless, form-filling)
          2. DuckDuckGo Desktop       — OPTIONAL visual fallback (prefer_ddg=True, non-headless)
          3. Windows default browser  — last resort

        Returns:
            Result with session info
        """
        # Validate URL before even starting a browser
        if not url or not url.startswith(("http://", "https://")):
            return {"success": False, "error": f"Invalid URL: '{url}' — must start with http:// or https://"}

        # ── Priority 1: Playwright / Chromium (PRIMARY execution engine) ──────
        try:
            playwright_factory = await self._ensure_playwright()

            # Use .start() NOT async-with so the playwright process stays alive
            # after this coroutine returns and the browser window stays visible.
            p = await playwright_factory().start()

            # Anti-detection launch args
            _stealth_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ] if stealth else []

            # Prefer the user's real installed Chrome (avoids "not secure" blocks).
            # Falls back to bundled Chromium if Chrome is not found.
            try:
                browser = await p.chromium.launch(
                    channel="chrome",
                    headless=headless,
                    args=_stealth_args,
                )
            except Exception:
                browser = await p.chromium.launch(
                    headless=headless,
                    args=_stealth_args,
                )

            # Stealth context: realistic user-agent, viewport, locale, no automation flag
            _ua = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
            context_kwargs: dict = {
                "viewport": {"width": 1920, "height": 1080},
            }
            if stealth:
                context_kwargs.update({
                    "user_agent": _ua,
                    "locale": "en-US",
                    "timezone_id": "America/New_York",
                    "java_script_enabled": True,
                    "bypass_csp": False,
                })
            context = await browser.new_context(**context_kwargs)

            # Hide navigator.webdriver when in stealth mode
            if stealth:
                await context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )

            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # Wait a moment for dynamic content (JS-rendered pages like LinkedIn)
            import asyncio as _aio
            await _aio.sleep(2)

            self.session = BrowserSession(
                playwright=p,
                browser=browser,
                context=context,
                page=page,
                session_id=f"session_{id(page)}",
            )

            # Extract visible page text so agents can read and act on the content
            try:
                page_text = await page.evaluate("() => document.body.innerText")
            except Exception:
                page_text = ""

            return {
                "success": True,
                "session_id": self.session.session_id,
                "url": page.url,
                "title": await page.title(),
                "page_text": page_text[:6000],   # first 6 KB of visible text
            }
        except ImportError:
            # Playwright not installed — try DDG visual mode if requested, else system browser
            if prefer_ddg and not headless:
                ddg_result = open_url_in_ddg_browser(url)
                if ddg_result.get("success"):
                    return {
                        "success": True,
                        "session_id": "ddg_browser",
                        "url": url,
                        "title": url,
                        "page_text": "",
                        "browser": "duckduckgo",
                        "note": ddg_result["message"],
                    }
            return await self._open_in_system_browser(url)
        except Exception as e:
            # Playwright error — try DDG visual mode if requested, then system browser
            if prefer_ddg and not headless:
                ddg_result = open_url_in_ddg_browser(url)
                if ddg_result.get("success"):
                    return {
                        "success": True,
                        "session_id": "ddg_browser",
                        "url": url,
                        "title": url,
                        "page_text": "",
                        "browser": "duckduckgo",
                        "note": ddg_result["message"],
                    }
            fallback = await self._open_in_system_browser(url)
            if fallback.get("success"):
                return fallback
            return {"success": False, "error": str(e)}

    async def browser_get_page_content(self) -> dict[str, Any]:
        """Return the visible text of the currently open page."""
        if not self.session or not self.session.page:
            return {"success": False, "error": "No active browser session"}
        try:
            title = await self.session.page.title()
            url   = self.session.page.url
            text  = await self.session.page.evaluate("() => document.body.innerText")
            return {"success": True, "title": title, "url": url, "content": text[:8000]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_extract_jobs(self) -> dict[str, Any]:
        """Extract job listings from the currently open job-search page."""
        if not self.session or not self.session.page:
            return {"success": False, "error": "No active browser session"}
        try:
            import asyncio as _aio
            # Wait up to 5s for job cards to appear (JS-rendered pages need this)
            for _sel in (
                'li.jobs-search-results__list-item',
                '.job_seen_beacon',
                '[data-job-id]',
                'h2.jobTitle',
            ):
                try:
                    await self.session.page.wait_for_selector(_sel, timeout=5000)
                    break
                except Exception:
                    pass
            await _aio.sleep(1)

            jobs = await self.session.page.evaluate("""() => {
                const results = [];

                // LinkedIn — logged-in job search (2024/2025 selectors)
                document.querySelectorAll(
                    'li.jobs-search-results__list-item, .scaffold-layout__list-item'
                ).forEach(card => {
                    const titleEl = card.querySelector(
                        '.job-card-list__title--link, .job-card-container__link, ' +
                        'strong, .job-card-list__title, a[data-control-name="jobcard_title"]'
                    );
                    const compEl = card.querySelector(
                        '.job-card-container__primary-description, ' +
                        '.job-card-container__company-name, ' +
                        '.artdeco-entity-lockup__subtitle span'
                    );
                    const locEl = card.querySelector(
                        '.job-card-container__metadata-item, ' +
                        '.job-card-list__footer-wrapper li'
                    );
                    const linkEl = card.querySelector('a[href*="/jobs/view/"]');
                    const title = (titleEl || {}).innerText || '';
                    if (title.trim()) {
                        results.push({
                            title: title.trim(),
                            company: ((compEl || {}).innerText || '').trim(),
                            location: ((locEl || {}).innerText || '').trim(),
                            url: linkEl ? (linkEl.href || '') : '',
                        });
                    }
                });

                // LinkedIn — public/guest job search
                if (!results.length) {
                    document.querySelectorAll('.base-search-card, .job-search-card').forEach(card => {
                        const title   = ((card.querySelector('.base-search-card__title, h3') || {}).innerText || '').trim();
                        const company = ((card.querySelector('.base-search-card__subtitle, h4') || {}).innerText || '').trim();
                        const loc     = ((card.querySelector('.job-search-card__location') || {}).innerText || '').trim();
                        const linkEl  = card.querySelector('a[href*="/jobs/"]');
                        if (title) results.push({title, company, location: loc, url: linkEl ? linkEl.href : ''});
                    });
                }

                // Indeed (2024/2025)
                if (!results.length) {
                    document.querySelectorAll('[data-jk], .job_seen_beacon, .resultContent').forEach(card => {
                        const title   = ((card.querySelector('h2.jobTitle span[title], h2.jobTitle a span, .jobTitle') || {}).innerText || '').trim();
                        const company = ((card.querySelector('.companyName, [data-testid="company-name"]') || {}).innerText || '').trim();
                        const loc     = ((card.querySelector('.companyLocation, [data-testid="text-location"]') || {}).innerText || '').trim();
                        const linkEl  = card.querySelector('a[data-jk], a[id*="job_"]');
                        if (title) results.push({title, company, location: loc, url: linkEl ? 'https://www.indeed.com' + (linkEl.getAttribute('href') || '') : ''});
                    });
                }

                // Glassdoor
                if (!results.length) {
                    document.querySelectorAll('[data-test="jobListing"], .react-job-listing').forEach(card => {
                        const title   = ((card.querySelector('[data-test="job-title"], .job-title') || {}).innerText || '').trim();
                        const company = ((card.querySelector('[data-test="employer-name"], .employer-name') || {}).innerText || '').trim();
                        if (title) results.push({title, company, location: '', url: ''});
                    });
                }

                // Generic fallback — any visible link whose text looks like a job title
                if (!results.length) {
                    document.querySelectorAll('a[href]').forEach(a => {
                        const text = (a.innerText || '').trim();
                        if (text.length > 8 && text.length < 100 && !text.includes('\\n')) {
                            results.push({title: text, company: '', location: '', url: a.href || ''});
                        }
                    });
                }

                return results.slice(0, 20);
            }""")
            return {"success": True, "jobs": jobs, "count": len(jobs)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_navigate(self, url: str) -> dict[str, Any]:
        """Navigate the current session to a new URL."""
        if not self.session or not self.session.page:
            return await self.browser_open(url, headless=False)
        try:
            await self.session.page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            import asyncio as _aio; await _aio.sleep(1)
            text = await self.session.page.evaluate("() => document.body.innerText")
            return {
                "success": True,
                "url": self.session.page.url,
                "title": await self.session.page.title(),
                "page_text": text[:6000],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _open_in_system_browser(self, url: str) -> dict[str, Any]:
        """Open URL in the user's default system browser (Windows fallback)."""
        try:
            import subprocess
            subprocess.Popen(f'start "" "{url}"', shell=True)
            return {
                "success": True,
                "url": url,
                "title": url,
                "note": "Opened in system browser (Playwright unavailable)",
            }
        except Exception as e:
            return {"success": False, "error": f"System browser fallback failed: {e}"}

    async def browser_click(self, selector: str) -> dict[str, Any]:
        """Click an element on the page.

        Args:
            selector: CSS selector for the element

        Returns:
            Click result
        """
        if not self.session or not self.session.page:
            return {"success": False, "error": "No active browser session"}

        try:
            await self.session.page.click(selector)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_type(self, selector: str, text: str, clear_first: bool = True) -> dict[str, Any]:
        """Type text into an input field.

        Args:
            selector: CSS selector for the input
            text: Text to type
            clear_first: Whether to clear field first

        Returns:
            Type result
        """
        if not self.session or not self.session.page:
            return {"success": False, "error": "No active browser session"}

        try:
            if clear_first:
                await self.session.page.fill(selector, "")
            await self.session.page.type(selector, text)
            return {"success": True, "selector": selector, "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_select(self, selector: str, value: str) -> dict[str, Any]:
        """Select an option from a dropdown.

        Args:
            selector: CSS selector for the select element
            value: Value to select

        Returns:
            Select result
        """
        if not self.session or not self.session.page:
            return {"success": False, "error": "No active browser session"}

        try:
            await self.session.page.select_option(selector, value)
            return {"success": True, "selector": selector, "value": value}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_upload(self, selector: str, file_path: str) -> dict[str, Any]:
        """Upload a file.

        Args:
            selector: CSS selector for the file input
            file_path: Path to the file to upload

        Returns:
            Upload result
        """
        if not self.session or not self.session.page:
            return {"success": False, "error": "No active browser session"}

        try:
            path = Path(file_path)
            if not path.exists():
                return {"success": False, "error": f"File not found: {file_path}"}

            input_element = await self.session.page.query_selector(selector)
            if not input_element:
                return {"success": False, "error": f"Element not found: {selector}"}

            await input_element.set_input_files(str(path.absolute()))
            return {"success": True, "selector": selector, "file": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_extract_fields(self) -> dict[str, Any]:
        """Extract form fields from the current page.

        Returns:
            List of form fields with their properties
        """
        if not self.session or not self.session.page:
            return {"success": False, "error": "No active browser session"}

        try:
            fields = await self.session.page.evaluate("""
                () => {
                    const inputs = document.querySelectorAll('input, select, textarea');
                    return Array.from(inputs).map(input => ({
                        tag: input.tagName.toLowerCase(),
                        type: input.type || 'text',
                        name: input.name || '',
                        id: input.id || '',
                        placeholder: input.placeholder || '',
                        label: input.labels?.[0]?.textContent?.trim() || '',
                        required: input.required || false,
                        selector: input.id ? `#${input.id}` : 
                                  input.name ? `[name="${input.name}"]` : 
                                  input.className ? `.${input.className.split(' ')[0]}` : 
                                  input.tagName.toLowerCase()
                    }));
                }
            """)
            return {"success": True, "fields": fields}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_screenshot(self, output_path: Optional[str] = None) -> dict[str, Any]:
        """Take a screenshot of the current page.

        Args:
            output_path: Optional path to save screenshot

        Returns:
            Screenshot result with path
        """
        if not self.session or not self.session.page:
            return {"success": False, "error": "No active browser session"}

        try:
            if output_path is None:
                output_path = f"screenshot_{self.session.session_id}.png"

            await self.session.page.screenshot(path=output_path, full_page=True)
            return {"success": True, "path": output_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_wait_for(self, selector: str, timeout: int = 30000) -> dict[str, Any]:
        """Wait for an element to appear.

        Args:
            selector: CSS selector to wait for
            timeout: Timeout in milliseconds

        Returns:
            Wait result
        """
        if not self.session or not self.session.page:
            return {"success": False, "error": "No active browser session"}

        try:
            await self.session.page.wait_for_selector(selector, timeout=timeout)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_get_html(self) -> dict[str, Any]:
        """Get the current page HTML.

        Returns:
            Page HTML content
        """
        if not self.session or not self.session.page:
            return {"success": False, "error": "No active browser session"}

        try:
            html = await self.session.page.content()
            return {"success": True, "html": html}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_close(self) -> dict[str, Any]:
        """Close the browser session.

        Returns:
            Close result
        """
        if not self.session:
            return {"success": True, "message": "No session to close"}

        try:
            if self.session.browser:
                await self.session.browser.close()
            self.session = None
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_navigate(self, url: str) -> dict[str, Any]:
        """Navigate to a new URL in the current session.

        Args:
            url: URL to navigate to

        Returns:
            Navigation result
        """
        if not self.session or not self.session.page:
            return {"success": False, "error": "No active browser session"}

        try:
            await self.session.page.goto(url, wait_until="networkidle")
            return {
                "success": True,
                "url": self.session.page.url,
                "title": await self.session.page.title(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_get_text(self, selector: str) -> dict[str, Any]:
        """Get text content of an element.

        Args:
            selector: CSS selector

        Returns:
            Text content
        """
        if not self.session or not self.session.page:
            return {"success": False, "error": "No active browser session"}

        try:
            element = await self.session.page.query_selector(selector)
            if not element:
                return {"success": False, "error": f"Element not found: {selector}"}
            text = await element.text_content()
            return {"success": True, "text": text or ""}
        except Exception as e:
            return {"success": False, "error": str(e)}
