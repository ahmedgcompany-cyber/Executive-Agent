"""
GitHub Integration Service — MegaV

Provides full GitHub API access via Personal Access Token (PAT).
All API calls are real (PyGitHub + raw REST fallback).

Usage::

    from src.integrations.github_service import GitHubService

    gh = GitHubService()
    gh.set_token("ghp_xxxxxxxxxxxx")

    repos = gh.get_repositories()
    gh.create_issue("owner/my-repo", "Bug: login fails", "Steps to reproduce...")
    gh.create_file("owner/my-repo", "README.md", "# Hello World", "Add README")
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Optional
from urllib import request, error as url_error

# ── Token storage path (user-scoped, never inside the repo) ─────────────────
from .profile_paths import profile_file as _profile_file

def _creds_file() -> Path:
    return _profile_file("github_credentials.json")

# ── GitHub REST API base ───────────────────────────────────────────────────────
_API = "https://api.github.com"


class GitHubError(Exception):
    """Raised for GitHub API errors."""
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class GitHubService:
    """Full GitHub integration service using the REST API."""

    def __init__(self):
        self._token:    Optional[str] = None
        self._username: Optional[str] = None
        self._load_stored_credentials()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def set_token(self, token: str, username: str = "") -> dict:
        """Set and validate a Personal Access Token.

        Args:
            token:    GitHub PAT (starts with ghp_ or github_pat_).
            username: Optional username hint (auto-detected if blank).

        Returns:
            dict with success, username, message.
        """
        token = token.strip()
        if not token:
            return {"success": False, "error": "Token is empty"}

        # Validate by calling /user
        self._token = token
        try:
            user = self._get("/user")
            self._username = user.get("login", username or "")
            self._save_credentials(token, self._username)
            return {
                "success":  True,
                "username": self._username,
                "message":  f"Connected as {self._username}",
                "avatar":   user.get("avatar_url", ""),
                "name":     user.get("name", self._username),
            }
        except GitHubError as e:
            self._token = None
            return {"success": False, "error": str(e)}
        except Exception as e:
            self._token = None
            return {"success": False, "error": f"Connection failed: {e}"}

    def disconnect(self) -> dict:
        """Remove stored token and disconnect."""
        self._token    = None
        self._username = None
        f = _creds_file()
        if f.exists():
            f.unlink()
        return {"success": True, "message": "Disconnected from GitHub"}

    def is_connected(self) -> bool:
        return bool(self._token)

    def get_username(self) -> str:
        return self._username or ""

    def connection_status(self) -> dict:
        if not self._token:
            return {"connected": False, "username": ""}
        return {"connected": True, "username": self._username or ""}

    # ------------------------------------------------------------------
    # Repository management
    # ------------------------------------------------------------------

    def get_repositories(self, visibility: str = "all", limit: int = 50) -> dict:
        """List authenticated user's repositories.

        Args:
            visibility: "all" | "public" | "private"
            limit:      Max repos to return.

        Returns:
            dict with success, repos (list), count.
        """
        self._require_auth()
        try:
            data = self._get(f"/user/repos?visibility={visibility}&per_page={limit}&sort=updated")
            repos = [
                {
                    "id":          r["id"],
                    "name":        r["name"],
                    "full_name":   r["full_name"],
                    "description": r.get("description", "") or "",
                    "url":         r["html_url"],
                    "private":     r["private"],
                    "language":    r.get("language", "") or "",
                    "stars":       r.get("stargazers_count", 0),
                    "updated_at":  r.get("updated_at", ""),
                    "default_branch": r.get("default_branch", "main"),
                }
                for r in data
            ]
            return {"success": True, "repos": repos, "count": len(repos)}
        except GitHubError as e:
            return {"success": False, "error": str(e), "repos": []}

    def create_repository(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = True,
    ) -> dict:
        """Create a new GitHub repository.

        Args:
            name:        Repository name (slug).
            description: Short description.
            private:     True for private repo.
            auto_init:   Add initial README commit.

        Returns:
            dict with success, repo_url, full_name.
        """
        self._require_auth()
        payload = {
            "name":        name,
            "description": description,
            "private":     private,
            "auto_init":   auto_init,
        }
        try:
            data = self._post("/user/repos", payload)
            return {
                "success":   True,
                "full_name": data["full_name"],
                "repo_url":  data["html_url"],
                "clone_url": data["clone_url"],
                "message":   f"Repository '{data['full_name']}' created.",
            }
        except GitHubError as e:
            return {"success": False, "error": str(e)}

    def get_repo_details(self, repo: str) -> dict:
        """Get details for one repository (owner/name or just name for auth user).

        Args:
            repo: Full name "owner/repo" or just "repo" (uses authenticated user).

        Returns:
            dict with success and repo metadata.
        """
        self._require_auth()
        full_name = repo if "/" in repo else f"{self._username}/{repo}"
        try:
            data = self._get(f"/repos/{full_name}")
            return {
                "success":     True,
                "full_name":   data["full_name"],
                "description": data.get("description", "") or "",
                "url":         data["html_url"],
                "private":     data["private"],
                "language":    data.get("language", "") or "",
                "stars":       data.get("stargazers_count", 0),
                "forks":       data.get("forks_count", 0),
                "open_issues": data.get("open_issues_count", 0),
                "default_branch": data.get("default_branch", "main"),
            }
        except GitHubError as e:
            return {"success": False, "error": str(e)}

    def delete_repository(self, repo: str) -> dict:
        """Delete a repository (requires admin scope on token)."""
        self._require_auth()
        full_name = repo if "/" in repo else f"{self._username}/{repo}"
        try:
            self._delete(f"/repos/{full_name}")
            return {"success": True, "message": f"Repository '{full_name}' deleted."}
        except GitHubError as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # File / commit operations
    # ------------------------------------------------------------------

    def get_file(self, repo: str, path: str, branch: str = "") -> dict:
        """Get a file's content and SHA from a repository.

        Returns:
            dict with success, content (decoded text), sha, encoding.
        """
        self._require_auth()
        full_name = repo if "/" in repo else f"{self._username}/{repo}"
        url = f"/repos/{full_name}/contents/{path}"
        if branch:
            url += f"?ref={branch}"
        try:
            data = self._get(url)
            raw = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return {
                "success": True,
                "content": raw,
                "sha":     data["sha"],
                "path":    data["path"],
            }
        except GitHubError as e:
            return {"success": False, "error": str(e)}

    def create_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str = "Add file via MegaV",
        branch: str = "",
    ) -> dict:
        """Create a new file in a repository.

        Args:
            repo:    Full "owner/repo" or just "repo".
            path:    File path inside the repo (e.g. "src/main.py").
            content: File content as plain text.
            message: Commit message.
            branch:  Branch name (uses repo default if blank).

        Returns:
            dict with success, commit_sha, file_url, message.
        """
        self._require_auth()
        full_name = repo if "/" in repo else f"{self._username}/{repo}"
        payload: dict = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
        }
        if branch:
            payload["branch"] = branch
        try:
            data = self._put(f"/repos/{full_name}/contents/{path}", payload)
            commit = data.get("commit", {})
            return {
                "success":    True,
                "commit_sha": commit.get("sha", ""),
                "file_url":   data.get("content", {}).get("html_url", ""),
                "message":    f"File '{path}' created in {full_name}.",
            }
        except GitHubError as e:
            return {"success": False, "error": str(e)}

    def update_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str = "Update file via MegaV",
        branch: str = "",
    ) -> dict:
        """Update an existing file (automatically fetches current SHA).

        Args:
            repo:    Full "owner/repo".
            path:    File path inside the repo.
            content: New file content.
            message: Commit message.
            branch:  Branch name (optional).

        Returns:
            dict with success, commit_sha, message.
        """
        self._require_auth()
        full_name = repo if "/" in repo else f"{self._username}/{repo}"

        # Get current file SHA
        existing = self.get_file(full_name, path, branch)
        if not existing.get("success"):
            # File doesn't exist — create it
            return self.create_file(repo, path, content, message, branch)

        payload: dict = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "sha":     existing["sha"],
        }
        if branch:
            payload["branch"] = branch
        try:
            data = self._put(f"/repos/{full_name}/contents/{path}", payload)
            commit = data.get("commit", {})
            return {
                "success":    True,
                "commit_sha": commit.get("sha", ""),
                "message":    f"File '{path}' updated in {full_name}.",
            }
        except GitHubError as e:
            return {"success": False, "error": str(e)}

    def commit_changes(
        self,
        repo: str,
        files: dict[str, str],
        message: str = "Commit via MegaV",
        branch: str = "",
    ) -> dict:
        """Create or update multiple files in one logical commit.

        Args:
            repo:    Repository identifier.
            files:   dict of {path: content}.
            message: Commit message.
            branch:  Branch name.

        Returns:
            dict with success, committed_files, message.
        """
        self._require_auth()
        committed: list[str] = []
        errors:    list[str] = []

        for path, content in files.items():
            result = self.update_file(repo, path, content, message, branch)
            if result.get("success"):
                committed.append(path)
            else:
                errors.append(f"{path}: {result.get('error', '?')}")

        success = len(committed) > 0
        return {
            "success":        success,
            "committed_files": committed,
            "errors":          errors,
            "message":         f"Committed {len(committed)} file(s) to {repo}.",
        }

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------

    def create_issue(
        self,
        repo: str,
        title: str,
        body: str = "",
        labels: Optional[list[str]] = None,
    ) -> dict:
        """Open a new issue.

        Args:
            repo:   Repository identifier.
            title:  Issue title.
            body:   Issue body (markdown supported).
            labels: Optional list of label names.

        Returns:
            dict with success, issue_number, url, message.
        """
        self._require_auth()
        full_name = repo if "/" in repo else f"{self._username}/{repo}"
        payload: dict = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        try:
            data = self._post(f"/repos/{full_name}/issues", payload)
            return {
                "success":      True,
                "issue_number": data["number"],
                "url":          data["html_url"],
                "message":      f"Issue #{data['number']} created: '{title}'",
            }
        except GitHubError as e:
            return {"success": False, "error": str(e)}

    def list_issues(
        self,
        repo: str,
        state: str = "open",
        limit: int = 20,
    ) -> dict:
        """List issues for a repository.

        Args:
            repo:  Repository identifier.
            state: "open" | "closed" | "all".
            limit: Max issues to return.

        Returns:
            dict with success, issues (list), count.
        """
        self._require_auth()
        full_name = repo if "/" in repo else f"{self._username}/{repo}"
        try:
            data = self._get(
                f"/repos/{full_name}/issues?state={state}&per_page={limit}"
            )
            issues = [
                {
                    "number":    i["number"],
                    "title":     i["title"],
                    "state":     i["state"],
                    "url":       i["html_url"],
                    "created":   i.get("created_at", "")[:10],
                    "body":      (i.get("body") or "")[:200],
                    "labels":    [lb["name"] for lb in i.get("labels", [])],
                }
                for i in data
                if "pull_request" not in i   # exclude PRs
            ]
            return {"success": True, "issues": issues, "count": len(issues)}
        except GitHubError as e:
            return {"success": False, "error": str(e), "issues": []}

    def comment_on_issue(
        self,
        repo: str,
        issue_number: int,
        comment: str,
    ) -> dict:
        """Add a comment to an issue.

        Returns:
            dict with success, comment_id, url, message.
        """
        self._require_auth()
        full_name = repo if "/" in repo else f"{self._username}/{repo}"
        try:
            data = self._post(
                f"/repos/{full_name}/issues/{issue_number}/comments",
                {"body": comment},
            )
            return {
                "success":    True,
                "comment_id": data["id"],
                "url":        data["html_url"],
                "message":    f"Comment added to issue #{issue_number}.",
            }
        except GitHubError as e:
            return {"success": False, "error": str(e)}

    def close_issue(self, repo: str, issue_number: int) -> dict:
        """Close an open issue.

        Returns:
            dict with success, message.
        """
        self._require_auth()
        full_name = repo if "/" in repo else f"{self._username}/{repo}"
        try:
            data = self._patch(
                f"/repos/{full_name}/issues/{issue_number}",
                {"state": "closed"},
            )
            return {
                "success": True,
                "message": f"Issue #{issue_number} closed.",
                "url":     data["html_url"],
            }
        except GitHubError as e:
            return {"success": False, "error": str(e)}

    def reopen_issue(self, repo: str, issue_number: int) -> dict:
        """Reopen a closed issue."""
        self._require_auth()
        full_name = repo if "/" in repo else f"{self._username}/{repo}"
        try:
            data = self._patch(
                f"/repos/{full_name}/issues/{issue_number}",
                {"state": "open"},
            )
            return {"success": True, "message": f"Issue #{issue_number} reopened.", "url": data["html_url"]}
        except GitHubError as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Convenience: prompt-driven auto actions
    # ------------------------------------------------------------------

    def handle_prompt(self, prompt: str, default_repo: str = "") -> dict:
        """Parse a natural-language prompt and execute the right GitHub action.

        Examples:
          "Create a repo called my-project for AI experiments"
          "Open an issue: bug in login system"
          "Push README.md to my-project"
          "List my repos"
          "Close issue 5 in my-project"
        """
        import re
        p = prompt.lower()

        # Create repo
        m = re.search(r"create\s+(?:a\s+)?repo(?:sitory)?\s+(?:called|named)?\s+([a-z0-9_\-]+)", p)
        if m:
            name = m.group(1)
            desc_m = re.search(r"(?:for|about|description)[:\s]+(.+?)(?:\.|$)", prompt, re.I)
            desc = desc_m.group(1).strip() if desc_m else ""
            return self.create_repository(name, desc)

        # List repos
        if any(kw in p for kw in ("list repos", "my repos", "show repos", "all repos")):
            return self.get_repositories()

        # Create issue
        m = re.search(r"(?:open|create|add)\s+(?:an?\s+)?issue[:\s]+(.+)", prompt, re.I)
        if m:
            title = m.group(1).strip()
            repo = default_repo or self._infer_repo(prompt)
            if not repo:
                return {"success": False, "error": "Please specify a repository name"}
            return self.create_issue(repo, title)

        # Close issue
        m = re.search(r"close\s+issue\s+#?(\d+)", p)
        if m:
            num = int(m.group(1))
            repo = default_repo or self._infer_repo(prompt)
            if not repo:
                return {"success": False, "error": "Please specify a repository name"}
            return self.close_issue(repo, num)

        # List issues
        if "list issues" in p or "show issues" in p or "open issues" in p:
            repo = default_repo or self._infer_repo(prompt)
            if not repo:
                return self.list_issues(f"{self._username}/{self._username}.github.io")
            return self.list_issues(repo)

        return {"success": False, "error": "Could not determine GitHub action from prompt"}

    def _infer_repo(self, prompt: str) -> str:
        """Try to extract a repo name from a prompt string."""
        import re
        # "in my-project" / "to my-project" / "for my-project"
        m = re.search(r"(?:in|to|for|of|on)\s+([a-zA-Z0-9_\-]+)", prompt)
        if m:
            candidate = m.group(1)
            if candidate not in ("my", "a", "an", "the", "github", "repo", "issue"):
                return candidate
        return ""

    # ------------------------------------------------------------------
    # Credential persistence (plain JSON — no external crypto needed)
    # ------------------------------------------------------------------

    def _save_credentials(self, token: str, username: str):
        # Persist via Fernet-backed CredentialStore (keychain-grade encryption).
        try:
            from .credential_store import get_credential_store
            store = get_credential_store()
            store.save_many("github", {"token": token, "username": username})
        except Exception:
            pass
        # Mirror username + saved_at (no token) into the legacy JSON for UI display.
        f = _creds_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        data = {"enc_token": "", "username": username, "saved_at": time.time()}
        f.write_text(json.dumps(data), encoding="utf-8")

    def _load_stored_credentials(self):
        try:
            from .credential_store import get_credential_store
            store = get_credential_store()
            tok = store.load("github", "token") or ""
            user = store.load("github", "username") or ""
            if tok:
                self._token = tok
                self._username = user
                return
        except Exception:
            pass
        # Legacy fallback: base64-encoded token in profile JSON (pre-Fernet).
        f = _creds_file()
        if not f.exists():
            return
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            enc = data.get("enc_token") or ""
            if enc:
                self._token = base64.b64decode(enc).decode()
                self._username = data.get("username", "")
        except Exception:
            self._token = None
            self._username = None

    # ------------------------------------------------------------------
    # HTTP helpers (uses only stdlib urllib — no requests/httpx needed)
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        return {
            "Authorization":        f"Bearer {self._token}",
            "Accept":               "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type":         "application/json",
            "User-Agent":           "MegaV-Agent/1.0",
        }

    def _get(self, path: str) -> Any:
        return self._call("GET", path)

    def _post(self, path: str, body: dict) -> Any:
        return self._call("POST", path, body)

    def _put(self, path: str, body: dict) -> Any:
        return self._call("PUT", path, body)

    def _patch(self, path: str, body: dict) -> Any:
        return self._call("PATCH", path, body)

    def _delete(self, path: str) -> Any:
        return self._call("DELETE", path)

    def _call(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        url = _API + path
        data = json.dumps(body).encode() if body else None
        req = request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                return json.loads(raw)
        except url_error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="ignore")
            try:
                msg = json.loads(body_text).get("message", body_text)
            except Exception:
                msg = body_text[:200]
            raise GitHubError(f"GitHub API {e.code}: {msg}", e.code) from e
        except url_error.URLError as e:
            raise GitHubError(f"Network error: {e.reason}") from e

    def _require_auth(self):
        if not self._token:
            raise GitHubError(
                "Not authenticated. Set a Personal Access Token first.",
                401,
            )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_SERVICE: Optional[GitHubService] = None


def get_github_service() -> GitHubService:
    """Return the shared GitHubService instance (lazy-created)."""
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = GitHubService()
    return _SERVICE
