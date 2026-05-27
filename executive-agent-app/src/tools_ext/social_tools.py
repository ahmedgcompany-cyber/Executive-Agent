"""Social media tools — browser-based login, OAuth, and posting for all platforms."""

import asyncio
import json
import logging
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlencode, parse_qs, urlparse

_log = logging.getLogger("megav.social")

# Storage path for tokens / cookies
_ACCOUNTS_PATH = Path(__file__).parent.parent.parent / "profiles" / "social_accounts.json"
_CALLBACK_PORT = 8847

# ── Platform definitions ──────────────────────────────────────────────────────

PLATFORMS: dict[str, dict] = {
    "linkedin": {
        "name": "LinkedIn",
        "color": "#0077B5",
        "icon": "in",
        "login_url": "https://www.linkedin.com/login",
        "home_url":  "https://www.linkedin.com/feed/",
        "success_patterns": ["/feed", "/in/", "/mynetwork", "/jobs"],
        "compose_url": "https://www.linkedin.com/feed/",
        "scopes": ["r_liteprofile", "w_member_social"],
        "auth_url":  "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "api_base":  "https://api.linkedin.com/v2",
    },
    "facebook": {
        "name": "Facebook",
        "color": "#1877F2",
        "icon": "f",
        "login_url": "https://www.facebook.com/login",
        "home_url":  "https://www.facebook.com/",
        "success_patterns": ["facebook.com/?", "facebook.com/home", "facebook.com/feed"],
        "compose_url": "https://www.facebook.com/",
        "scopes": ["pages_manage_posts", "public_profile"],
        "auth_url":  "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "api_base":  "https://graph.facebook.com/v19.0",
    },
    "instagram": {
        "name": "Instagram",
        "color": "#E4405F",
        "icon": "ig",
        "login_url": "https://www.instagram.com/accounts/login/",
        "home_url":  "https://www.instagram.com/",
        "success_patterns": ["/direct/", "/explore/", "instagram.com/?"],
        "compose_url": "https://www.instagram.com/",
        "scopes": ["instagram_basic", "instagram_content_publish"],
        "auth_url":  "https://api.instagram.com/oauth/authorize",
        "token_url": "https://api.instagram.com/oauth/access_token",
        "api_base":  "https://graph.instagram.com",
    },
    "google_business": {
        "name": "Google Business",
        "color": "#4285F4",
        "icon": "G",
        "login_url": "https://accounts.google.com/signin",
        "home_url":  "https://business.google.com/",
        "success_patterns": ["business.google.com", "myaccount.google.com"],
        "compose_url": "https://business.google.com/",
        "scopes": ["https://www.googleapis.com/auth/business.manage"],
        "auth_url":  "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "api_base":  "https://mybusiness.googleapis.com/v4",
    },
    "tiktok": {
        "name": "TikTok",
        "color": "#010101",
        "icon": "tt",
        "login_url": "https://www.tiktok.com/login/phone-or-email/email",
        "home_url":  "https://www.tiktok.com/foryou",
        "success_patterns": ["/foryou", "/following", "tiktok.com/@"],
        "compose_url": "https://www.tiktok.com/upload",
        "scopes": ["user.info.basic", "video.upload"],
        "auth_url":  "https://www.tiktok.com/v2/auth/authorize/",
        "token_url": "https://open.tiktokapis.com/v2/oauth/token/",
        "api_base":  "https://open.tiktokapis.com/v2",
    },
    "twitter": {
        "name": "X (Twitter)",
        "color": "#1DA1F2",
        "icon": "X",
        "login_url": "https://twitter.com/i/flow/login",
        "home_url":  "https://twitter.com/home",
        "success_patterns": ["/home", "x.com/home", "twitter.com/home"],
        "compose_url": "https://twitter.com/compose/tweet",
        "scopes": ["tweet.read", "tweet.write"],
        "auth_url":  "https://twitter.com/i/oauth2/authorize",
        "token_url": "https://api.twitter.com/2/oauth2/token",
        "api_base":  "https://api.twitter.com/2",
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_accounts() -> dict:
    if _ACCOUNTS_PATH.exists():
        try:
            return json.loads(_ACCOUNTS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_accounts(data: dict):
    _ACCOUNTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _ACCOUNTS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_success_url(platform: str, url: str) -> bool:
    """Return True if the URL indicates successful login."""
    patterns = PLATFORMS[platform]["success_patterns"]
    return any(p in url for p in patterns)


# ── Local OAuth callback server ───────────────────────────────────────────────

class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            _OAuthCallbackHandler.code = params["code"][0]
        if "error" in params:
            _OAuthCallbackHandler.error = params["error"][0]

        html = (
            b"<!DOCTYPE html><html><body style='font-family:sans-serif;background:#0d1117;"
            b"color:#e6edf3;text-align:center;padding:60px'>"
            b"<h2 style='color:#58a6ff'>Authorisation Received!</h2>"
            b"<p>You can close this tab and return to MegaV.</p>"
            b"</body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, *args):
        pass


def _run_callback_server(timeout: int = 120) -> Optional[str]:
    _OAuthCallbackHandler.code = None
    _OAuthCallbackHandler.error = None
    server = HTTPServer(("localhost", _CALLBACK_PORT), _OAuthCallbackHandler)
    server.timeout = timeout
    deadline = time.time() + timeout
    while time.time() < deadline:
        server.handle_request()
        if _OAuthCallbackHandler.code:
            server.server_close()
            return _OAuthCallbackHandler.code
        if _OAuthCallbackHandler.error:
            break
    server.server_close()
    return None


# ── Playwright browser helpers ────────────────────────────────────────────────

async def _open_browser(url: str, cookies: list = None, headless: bool = False):
    """Open a Playwright browser (real Chrome preferred). Returns (playwright, browser, page)."""
    from playwright.async_api import async_playwright
    p = await async_playwright().start()
    try:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-notifications",
                "--start-maximized",
            ],
        )
    except Exception:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--disable-notifications"],
        )

    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
    )

    if cookies:
        await context.add_cookies(cookies)

    page = await context.new_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    return p, browser, context, page


async def _wait_for_login(page, platform: str, timeout: int = 180) -> bool:
    """Poll every second until the URL matches a success pattern or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            url = page.url
            if _is_success_url(platform, url):
                return True
        except Exception:
            return False
        await asyncio.sleep(1)
    return False


# ── Post via browser helpers ──────────────────────────────────────────────────

async def _post_linkedin_browser(page, text: str) -> dict:
    """Post a LinkedIn update via browser UI."""
    try:
        # Click "Start a post" button
        await page.wait_for_selector(
            '[data-control-name="share.sharebox_feed_prompt"], '
            '.share-box-feed-entry__trigger, '
            'button.artdeco-button--primary[data-artdeco-is-focused]',
            timeout=10_000
        )
        # Try multiple selectors for the compose button
        for sel in [
            'div.share-box-feed-entry__closed-share-box',
            'button[aria-label="Start a post"]',
            '.share-box-feed-entry__trigger',
            'div[data-control-name="share.sharebox_feed_prompt"]',
        ]:
            try:
                el = await page.query_selector(sel)
                if el:
                    await el.click()
                    break
            except Exception:
                continue

        await asyncio.sleep(1.5)

        # Type the post text
        editor = await page.wait_for_selector(
            'div[contenteditable=true], div[role=textbox], .ql-editor',
            timeout=8_000
        )
        await editor.click()
        await page.keyboard.type(text, delay=20)
        await asyncio.sleep(0.5)

        # Click Post button
        for sel in [
            'button.share-actions__primary-action',
            'button[class*="share-actions__primary"]',
            'button:has-text("Post")',
        ]:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await asyncio.sleep(2)
                    return {"success": True, "summary": "Posted to LinkedIn via browser."}
            except Exception:
                continue

        return {"success": False, "error": "Could not find LinkedIn Post button."}
    except Exception as e:
        return {"success": False, "error": f"LinkedIn browser post failed: {e}"}


async def _post_facebook_browser(page, text: str) -> dict:
    """Post a Facebook update via browser UI."""
    try:
        for sel in [
            "div[aria-label=\"What's on your mind?\"]",
            "div[data-lexical-editor]",
            "span[data-text]",
        ]:
            try:
                box = await page.wait_for_selector(sel, timeout=8_000)
                if box:
                    await box.click()
                    await asyncio.sleep(1)
                    await page.keyboard.type(text, delay=20)
                    break
            except Exception:
                continue

        await asyncio.sleep(0.5)
        # Click Post
        for sel in ["div[aria-label='Post']", "button:has-text('Post')"]:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await asyncio.sleep(2)
                    return {"success": True, "summary": "Posted to Facebook via browser."}
            except Exception:
                continue
        return {"success": False, "error": "Could not find Facebook Post button."}
    except Exception as e:
        return {"success": False, "error": f"Facebook browser post failed: {e}"}


async def _post_twitter_browser(page, text: str) -> dict:
    """Post a tweet via browser UI."""
    try:
        await page.goto("https://twitter.com/compose/tweet", wait_until="domcontentloaded", timeout=15_000)
        await asyncio.sleep(1.5)

        editor = await page.wait_for_selector(
            'div[contenteditable=true][data-testid="tweetTextarea_0"],'
            'div[role=textbox][contenteditable=true]',
            timeout=10_000
        )
        await editor.click()
        await page.keyboard.type(text[:280], delay=20)
        await asyncio.sleep(0.5)

        btn = await page.wait_for_selector(
            'button[data-testid="tweetButtonInline"], button:has-text("Post"), '
            'button[data-testid="tweetButton"]',
            timeout=8_000
        )
        await btn.click()
        await asyncio.sleep(2)
        return {"success": True, "summary": "Tweeted via browser."}
    except Exception as e:
        return {"success": False, "error": f"Twitter browser post failed: {e}"}


async def _post_instagram_browser(page, text: str, image_path: Optional[str] = None) -> dict:
    """Instagram requires mobile API for posting — guide user."""
    return {
        "success": False,
        "error": (
            "Instagram does not allow automated text-only posts from desktop browsers. "
            "To post on Instagram:\n"
            "  1. Save your caption to clipboard\n"
            "  2. Open Instagram on your phone and paste it\n"
            "Or use an image: attach a photo and I'll try the upload flow."
        ),
    }


async def _post_tiktok_browser(page, text: str, image_path: Optional[str] = None) -> dict:
    """TikTok requires a video — provide guidance."""
    return {
        "success": False,
        "error": (
            "TikTok requires a video file for posting. "
            "Please attach a video file using the 📎 button and I'll handle the upload."
        ),
    }


# ── Main SocialTools class ────────────────────────────────────────────────────

class SocialTools:
    """Social media tools — browser login + API posting for all platforms."""

    def __init__(self):
        self.accounts: dict = _load_accounts()

    def reload(self):
        self.accounts = _load_accounts()

    # ── Connection status ──────────────────────────────────────────────

    def get_connection_status(self) -> dict[str, dict]:
        self.reload()
        status = {}
        for pid, pinfo in PLATFORMS.items():
            acc = self.accounts.get(pid, {})
            connected = bool(
                acc.get("access_token")
                or acc.get("cookies")
                or acc.get("session_cookie")
            )
            status[pid] = {
                "connected":     connected,
                "platform_name": pinfo["name"],
                "color":         pinfo["color"],
                "icon":          pinfo["icon"],
                "account_name":  acc.get("account_name", ""),
                "account_id":    acc.get("account_id", ""),
                "connected_at":  acc.get("connected_at", ""),
                "method":        acc.get("method", ""),
            }
        return status

    def is_connected(self, platform: str) -> bool:
        self.reload()
        acc = self.accounts.get(platform, {})
        return bool(acc.get("access_token") or acc.get("cookies") or acc.get("session_cookie"))

    # ── Browser-based login (visible browser, user logs in normally) ───

    def login_via_browser(
        self,
        platform: str,
        email: str = "",
        password: str = "",
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> dict[str, Any]:
        """Open a real browser window for the user to log into the platform.

        The browser is visible — the user can handle 2FA, CAPTCHAs, etc.
        After successful login, session cookies are saved locally.

        Args:
            platform: Platform ID (linkedin, facebook, etc.)
            email: Optional — pre-fill the email/username field
            password: Optional — pre-fill the password field
            progress_cb: Optional callable(str) for progress updates

        Returns:
            dict with success, account_name, message
        """
        if platform not in PLATFORMS:
            return {"success": False, "error": f"Unknown platform: {platform}"}

        def _emit(msg: str):
            if progress_cb:
                progress_cb(msg)

        try:
            return asyncio.run(
                self._login_via_browser_async(platform, email, password, _emit)
            )
        except RuntimeError:
            # Already in an event loop — run in new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self._login_via_browser_async(platform, email, password, _emit)
                )
                return future.result(timeout=240)

    async def _login_via_browser_async(
        self,
        platform: str,
        email: str,
        password: str,
        emit: Callable[[str], None],
    ) -> dict:
        pinfo = PLATFORMS[platform]
        emit(f"Opening {pinfo['name']} login page in your browser…")
        emit("Complete the login in the browser window that just opened.")
        emit("(Handles 2FA, CAPTCHA, etc. automatically)")

        try:
            p, browser, context, page = await _open_browser(
                pinfo["login_url"],
                headless=False,
            )
        except ImportError:
            return {
                "success": False,
                "error": "Playwright not installed. Run: pip install playwright && python -m playwright install chromium",
            }
        except Exception as e:
            return {"success": False, "error": f"Could not open browser: {e}"}

        try:
            # Auto-fill credentials if provided
            if email and password:
                await asyncio.sleep(2)
                await self._autofill_credentials(platform, page, email, password, emit)

            emit("Waiting for you to complete login… (up to 3 minutes)")
            logged_in = await _wait_for_login(page, platform, timeout=180)

            if not logged_in:
                await browser.close()
                await p.stop()
                return {
                    "success": False,
                    "error": f"Login timeout — did not detect successful login to {pinfo['name']}.",
                }

            emit("Login detected! Saving session…")

            # Extract profile name from page
            account_name = await self._extract_account_name(platform, page)

            # Save cookies for future sessions
            cookies = await context.cookies()
            acc_data = {
                "cookies":      cookies,
                "method":       "browser",
                "account_name": account_name,
                "connected_at": time.strftime("%Y-%m-%d %H:%M"),
            }
            self.accounts[platform] = acc_data
            _save_accounts(self.accounts)

            await browser.close()
            await p.stop()

            emit(f"{pinfo['name']} connected as {account_name}!")
            return {
                "success": True,
                "platform": platform,
                "account_name": account_name,
                "summary": f"Connected to {pinfo['name']} as {account_name}",
            }

        except Exception as e:
            _log.error("Browser login failed for %s: %s", platform if 'platform' in dir() else '?', e)
            try:
                await browser.close()
                await p.stop()
            except Exception:
                pass
            return {"success": False, "error": f"Login error: {e}"}

    async def _autofill_credentials(
        self, platform: str, page, email: str, password: str, emit: Callable
    ):
        """Attempt to auto-fill login form. Safe — leaves manual control if it fails."""
        try:
            emit("Auto-filling credentials…")
            # Common email/username selectors
            email_sels = [
                'input[type=email]', 'input[name=email]', 'input[name=username]',
                'input[id*=email]', 'input[id*=username]', 'input[id*=login]',
                '#email', '#username', '#login_email',
                'input[autocomplete=email]', 'input[autocomplete=username]',
            ]
            for sel in email_sels:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.fill(email)
                        await asyncio.sleep(0.3)
                        break
                except Exception:
                    continue

            # Password selectors
            pw_sels = [
                'input[type=password]', 'input[name=password]',
                '#password', 'input[id*=password]',
                'input[autocomplete=current-password]',
            ]
            for sel in pw_sels:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.fill(password)
                        await asyncio.sleep(0.3)
                        break
                except Exception:
                    continue

            # Submit
            submit_sels = [
                'button[type=submit]', 'input[type=submit]',
                'button:has-text("Sign in")', 'button:has-text("Log in")',
                'button:has-text("Login")', 'button:has-text("Continue")',
            ]
            for sel in submit_sels:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        break
                except Exception:
                    continue

        except Exception as _e:
            _log.debug("Auto-fill skipped: %s", _e)
            emit("Auto-fill skipped — please complete login manually.")

    async def _extract_account_name(self, platform: str, page) -> str:
        """Try to extract the logged-in account name from the page."""
        try:
            if platform == "linkedin":
                el = await page.query_selector('.nav-item__profile-member-photo img, .profile-nav-item__name')
                if el:
                    return (await el.get_attribute("alt") or await el.inner_text() or "").strip()
            elif platform in ("facebook", "instagram"):
                el = await page.query_selector('[data-testid="blue_bar_profile_link"], a[aria-label]')
                if el:
                    return (await el.inner_text() or "").strip()
            elif platform == "twitter":
                el = await page.query_selector('div[data-testid="UserName"] span')
                if el:
                    return (await el.inner_text() or "").strip()
        except Exception as _e:
            _log.debug("Could not extract account name for %s: %s", platform, _e)
        return "Connected Account"

    # ── Direct token connection ────────────────────────────────────────

    def connect_with_token(
        self,
        platform: str,
        access_token: str,
        account_name: str = "",
    ) -> dict[str, Any]:
        if platform not in PLATFORMS:
            return {"success": False, "error": f"Unknown platform: {platform}"}
        self.accounts[platform] = {
            "access_token": access_token,
            "method":       "token",
            "account_name": account_name or "Connected Account",
            "connected_at": time.strftime("%Y-%m-%d %H:%M"),
        }
        _save_accounts(self.accounts)
        return {"success": True, "platform": platform,
                "summary": f"Token saved for {PLATFORMS[platform]['name']}"}

    # ── OAuth connect (for platforms supporting it) ────────────────────

    def start_oauth_connect(
        self,
        platform: str,
        client_id: str,
        client_secret: str,
        progress_cb: Optional[Callable] = None,
    ) -> dict[str, Any]:
        """Standard OAuth 2.0 flow. Requires developer app credentials."""
        if platform not in PLATFORMS:
            return {"success": False, "error": f"Unknown platform: {platform}"}
        pinfo = PLATFORMS[platform]

        def _emit(msg):
            if progress_cb:
                progress_cb(msg)

        redirect_uri = f"http://localhost:{_CALLBACK_PORT}/callback"
        scope = " ".join(pinfo["scopes"])
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": f"exec_agent_{platform}",
        }
        auth_url = pinfo["auth_url"] + "?" + urlencode(params)

        _emit(f"Opening {pinfo['name']} OAuth in browser…")
        webbrowser.open(auth_url)
        _emit("Waiting for authorisation (up to 2 min)…")
        code = _run_callback_server(timeout=120)

        if not code:
            return {"success": False, "error": "No authorisation code received."}

        # Exchange code
        _emit("Exchanging code for token…")
        token_result = self._exchange_code(platform, code, client_id, client_secret, redirect_uri)
        if not token_result.get("success"):
            return token_result

        access_token = token_result["access_token"]
        account_info = self._fetch_account_info_sync(platform, access_token)

        self.accounts[platform] = {
            "access_token":  access_token,
            "refresh_token": token_result.get("refresh_token", ""),
            "client_id":     client_id,
            "client_secret": client_secret,
            "method":        "oauth",
            "account_name":  account_info.get("name", ""),
            "account_id":    account_info.get("id", ""),
            "connected_at":  time.strftime("%Y-%m-%d %H:%M"),
        }
        _save_accounts(self.accounts)

        name = self.accounts[platform]["account_name"]
        _emit(f"{pinfo['name']} connected as {name}!")
        return {
            "success": True,
            "platform": platform,
            "account_name": name,
            "summary": f"Connected to {pinfo['name']} as {name}",
        }

    def disconnect(self, platform: str) -> dict[str, Any]:
        if platform in self.accounts:
            self.accounts.pop(platform)
            _save_accounts(self.accounts)
        pinfo = PLATFORMS.get(platform, {})
        return {"success": True, "summary": f"Disconnected from {pinfo.get('name', platform)}"}

    # ── Posting ────────────────────────────────────────────────────────

    def post(
        self,
        platform: str,
        text: str,
        image_path: Optional[str] = None,
        link: Optional[str] = None,
    ) -> dict[str, Any]:
        """Post content to a connected platform."""
        if not self.is_connected(platform):
            pname = PLATFORMS.get(platform, {}).get("name", platform)
            return {
                "success": False,
                "error": f"Not connected to {pname}. Open the Social Accounts tab to connect.",
            }

        acc = self.accounts.get(platform, {})
        method = acc.get("method", "token")
        full_text = text + (f"\n\n{link}" if link else "")

        # Browser-session posting
        if method == "browser" and acc.get("cookies"):
            try:
                return asyncio.run(self._post_via_browser_async(platform, full_text, image_path))
            except RuntimeError:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(
                        asyncio.run,
                        self._post_via_browser_async(platform, full_text, image_path)
                    ).result(timeout=120)

        # API token posting
        api_method = {
            "linkedin": self._post_linkedin_api,
            "facebook": self._post_facebook_api,
            "twitter":  self._post_twitter_api,
        }.get(platform)

        if api_method:
            return api_method(text=full_text, image_path=image_path)

        return {
            "success": False,
            "error": f"No posting method available for {platform}. Connect via browser login.",
        }

    def post_to_all(
        self,
        text: str,
        platforms: Optional[list] = None,
        image_path: Optional[str] = None,
    ) -> dict[str, Any]:
        if platforms is None:
            platforms = [p for p in PLATFORMS if self.is_connected(p)]

        results = {}
        for p in platforms:
            results[p] = self.post(p, text, image_path=image_path)

        succeeded = [p for p, r in results.items() if r.get("success")]
        failed    = [p for p, r in results.items() if not r.get("success")]

        return {
            "success": bool(succeeded),
            "results": results,
            "succeeded": succeeded,
            "failed": failed,
            "summary": (
                f"Posted to: {', '.join(PLATFORMS[p]['name'] for p in succeeded)}."
                + (f"  Failed: {', '.join(PLATFORMS[p]['name'] for p in failed)}." if failed else "")
            ) if succeeded else (
                results[failed[0]].get("error", "Post failed") if failed else "Nothing to post."
            ),
        }

    # ── Browser posting ────────────────────────────────────────────────

    async def _post_via_browser_async(
        self, platform: str, text: str, image_path: Optional[str]
    ) -> dict:
        pinfo = PLATFORMS[platform]
        acc = self.accounts.get(platform, {})
        cookies = acc.get("cookies", [])

        p, browser, context, page = await _open_browser(
            pinfo["compose_url"],
            cookies=cookies,
            headless=False,
        )
        await asyncio.sleep(2)

        try:
            dispatchers = {
                "linkedin": _post_linkedin_browser,
                "facebook": _post_facebook_browser,
                "twitter":  _post_twitter_browser,
                "instagram": _post_instagram_browser,
                "tiktok":   _post_tiktok_browser,
                "google_business": self._post_google_business_browser,
            }
            fn = dispatchers.get(platform)
            if fn:
                result = await fn(page, text) if platform not in ("instagram", "tiktok") \
                    else await fn(page, text, image_path)
            else:
                result = {"success": False, "error": f"Browser posting not implemented for {platform}"}
        except Exception as e:
            result = {"success": False, "error": str(e)}
        finally:
            await asyncio.sleep(1)
            await browser.close()
            await p.stop()

        return result

    async def _post_google_business_browser(self, page, text: str) -> dict:
        """Post a Google Business update via browser."""
        try:
            await page.goto("https://business.google.com/", wait_until="domcontentloaded", timeout=15_000)
            await asyncio.sleep(2)
            return {
                "success": False,
                "error": "Google Business posting via browser requires manual interaction. "
                         "The browser is open — please compose and post manually.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── API posting (token-based) ──────────────────────────────────────

    def _post_linkedin_api(self, text: str, image_path=None, **_) -> dict:
        try:
            import urllib.request as _req
            acc = self.accounts.get("linkedin", {})
            token = acc.get("access_token", "")
            person_id = acc.get("account_id", "")

            if not person_id:
                info = self._fetch_account_info_sync("linkedin", token)
                person_id = info.get("id", "")
                self.accounts["linkedin"]["account_id"] = person_id
                _save_accounts(self.accounts)

            payload = {
                "author": f"urn:li:person:{person_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }
            data = json.dumps(payload).encode()
            req = _req.Request("https://api.linkedin.com/v2/ugcPosts", data=data, method="POST")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")
            req.add_header("X-Restli-Protocol-Version", "2.0.0")
            with _req.urlopen(req, timeout=20) as resp:
                result = json.loads(resp.read())
            return {"success": True, "post_id": result.get("id", ""),
                    "summary": "Posted to LinkedIn via API."}
        except Exception as e:
            return {"success": False, "error": f"LinkedIn API post failed: {e}"}

    def _post_facebook_api(self, text: str, **_) -> dict:
        try:
            import urllib.request as _req
            acc = self.accounts.get("facebook", {})
            token = acc.get("access_token", "")
            page_id = acc.get("account_id", "me")
            data = urlencode({"message": text, "access_token": token}).encode()
            req = _req.Request(
                f"https://graph.facebook.com/v19.0/{page_id}/feed",
                data=data, method="POST"
            )
            with _req.urlopen(req, timeout=20) as resp:
                result = json.loads(resp.read())
            return {"success": True, "post_id": result.get("id", ""),
                    "summary": "Posted to Facebook via API."}
        except Exception as e:
            return {"success": False, "error": f"Facebook API post failed: {e}"}

    def _post_twitter_api(self, text: str, **_) -> dict:
        try:
            import urllib.request as _req
            acc = self.accounts.get("twitter", {})
            token = acc.get("access_token", "")
            payload = json.dumps({"text": text[:280]}).encode()
            req = _req.Request("https://api.twitter.com/2/tweets", data=payload, method="POST")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")
            with _req.urlopen(req, timeout=20) as resp:
                result = json.loads(resp.read())
            tweet_id = result.get("data", {}).get("id", "")
            return {"success": True, "post_id": tweet_id, "summary": "Tweet posted via API."}
        except Exception as e:
            return {"success": False, "error": f"Twitter API post failed: {e}"}

    # ── Read posts ─────────────────────────────────────────────────────

    def get_recent_posts(self, platform: str, count: int = 5) -> dict[str, Any]:
        if not self.is_connected(platform):
            return {"success": False, "error": f"Not connected to {platform}"}
        acc = self.accounts.get(platform, {})
        token = acc.get("access_token", "")
        if not token:
            return {"success": True, "summary": f"Session connected to {platform} via browser. "
                    "Reading posts requires an API token for this platform."}
        try:
            return self._api_get_posts(platform, token, count)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _api_get_posts(self, platform: str, token: str, count: int) -> dict:
        try:
            import urllib.request as _req
            url_map = {
                "linkedin": f"https://api.linkedin.com/v2/ugcPosts?q=authors&count={count}",
                "facebook": f"https://graph.facebook.com/v19.0/me/posts?limit={count}&access_token={token}",
                "twitter":  f"https://api.twitter.com/2/users/me/tweets?max_results={min(count,100)}",
            }
            url = url_map.get(platform)
            if not url:
                return {"success": False, "error": f"Reading posts not available for {platform}"}
            req = _req.Request(url)
            req.add_header("Authorization", f"Bearer {token}")
            with _req.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            return {"success": True, "posts": data, "platform": platform}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Internal helpers ───────────────────────────────────────────────

    def _exchange_code(self, platform, code, client_id, client_secret, redirect_uri) -> dict:
        try:
            import urllib.request as _req
            pinfo = PLATFORMS[platform]
            data = urlencode({
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            }).encode()
            req = _req.Request(pinfo["token_url"], data=data, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            req.add_header("Accept", "application/json")
            with _req.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
            return {"success": True,
                    "access_token": body.get("access_token", ""),
                    "refresh_token": body.get("refresh_token", "")}
        except Exception as e:
            return {"success": False, "error": f"Token exchange failed: {e}"}

    def _fetch_account_info_sync(self, platform: str, token: str) -> dict:
        try:
            import urllib.request as _req
            urls = {
                "linkedin": "https://api.linkedin.com/v2/me",
                "facebook": f"https://graph.facebook.com/v19.0/me?access_token={token}",
                "twitter":  "https://api.twitter.com/2/users/me",
                "google_business": "https://www.googleapis.com/oauth2/v1/userinfo",
            }
            url = urls.get(platform)
            if not url:
                return {"name": "", "id": ""}
            req = _req.Request(url)
            req.add_header("Authorization", f"Bearer {token}")
            with _req.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            name = (data.get("name") or
                    (data.get("localizedFirstName", "") + " " + data.get("localizedLastName", "")).strip() or
                    data.get("username", "") or data.get("email", ""))
            return {"name": name.strip(), "id": str(data.get("id", ""))}
        except Exception:
            return {"name": "Connected Account", "id": ""}

    # ── Agent task handler ─────────────────────────────────────────────

    def handle_social_task(self, action: str, context) -> dict[str, Any]:
        goal = getattr(context, "goal", "") or getattr(context, "current_goal", "") or ""

        if action in ("post", "share", "publish", "execute_goal", "execute_task", "create"):
            return self._execute_from_goal(goal)
        elif action in ("get_status", "status", "analyze"):
            return self._status_summary()
        elif action == "disconnect":
            platform = getattr(context, "platform", "") or ""
            return self.disconnect(platform) if platform else {"success": False, "error": "No platform specified"}
        return self._execute_from_goal(goal)

    def _execute_from_goal(self, goal: str) -> dict[str, Any]:
        import re
        if not goal:
            return {"success": False, "error": "No goal provided."}

        g = goal.lower()
        if any(x in g for x in ["connect", "login", "link", "authoris", "authoriz"]):
            return self._guide_connect(goal)
        if any(x in g for x in ["read", "show", "get", "fetch", "my post", "recent"]):
            return self._read_posts_summary(goal)
        if any(x in g for x in ["disconnect", "unlink", "remove account"]):
            return self._disconnect_from_goal(goal)
        if any(x in g for x in ["status", "connected", "which accounts", "what platforms"]):
            return self._status_summary()

        # Default: post
        targets = [pid for pid, pinfo in PLATFORMS.items()
                   if pinfo["name"].lower().split()[0] in g or pid in g]
        quoted = re.findall(r'"([^"]{4,500})"', goal)
        text = quoted[0] if quoted else ""
        if not text:
            m = re.search(
                r'(?:post|share|publish|say|write|tweet|caption)\s*:?\s*["\']?(.{10,500}?)["\']?'
                r'(?:$|on\s|to\s|for\s)',
                goal, re.IGNORECASE
            )
            text = m.group(1).strip() if m else goal

        if not text or len(text) < 5:
            text = goal

        connected = [p for p in PLATFORMS if self.is_connected(p)]
        if not connected:
            return {"success": False, "error": "No social media accounts connected.",
                    "summary": "No platforms connected. Open the Social Accounts tab to connect."}

        if not targets:
            targets = connected

        return self.post_to_all(text, platforms=targets)

    def _status_summary(self) -> dict:
        status = self.get_connection_status()
        lines = ["Social Media Account Status:\n"]
        for pid, info in status.items():
            icon = "Connected" if info["connected"] else "Not connected"
            name = f" ({info['account_name']})" if info["account_name"] else ""
            method = f" [via {info['method']}]" if info.get("method") else ""
            lines.append(f"  {'[OK]' if info['connected'] else '[ ]'}  {info['platform_name']}{name}{method}")
        connected = sum(1 for v in status.values() if v["connected"])
        lines.append(f"\n{connected}/{len(PLATFORMS)} platforms connected.")
        return {"success": True, "summary": "\n".join(lines), "status": status}

    def _guide_connect(self, goal: str) -> dict:
        for pid, pinfo in PLATFORMS.items():
            if pinfo["name"].lower().split()[0] in goal.lower() or pid in goal.lower():
                return {"success": True,
                        "summary": f"To connect {pinfo['name']}, open the Social Accounts tab and click 'Connect'."}
        return {"success": True,
                "summary": "Open the Social Accounts tab to connect your platforms."}

    def _disconnect_from_goal(self, goal: str) -> dict:
        for pid, pinfo in PLATFORMS.items():
            if pinfo["name"].lower().split()[0] in goal.lower() or pid in goal.lower():
                return self.disconnect(pid)
        return {"success": False, "error": "Specify which platform to disconnect."}

    def _read_posts_summary(self, goal: str) -> dict:
        for pid in PLATFORMS:
            if pid in goal.lower() or PLATFORMS[pid]["name"].lower().split()[0] in goal.lower():
                if self.is_connected(pid):
                    return self.get_recent_posts(pid)
        connected = [p for p in PLATFORMS if self.is_connected(p)]
        if connected:
            return self.get_recent_posts(connected[0])
        return {"success": False, "error": "No connected platforms to read from."}
