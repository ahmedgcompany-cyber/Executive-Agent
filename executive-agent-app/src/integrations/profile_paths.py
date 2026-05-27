"""User-scoped profile path resolution.

User data (profile JSON, GitHub credential file, resumes) lives outside
the application tree so it is never bundled into a distribution ZIP.

Resolution order for `user_profile.json`, `github_credentials.json`, etc.:
  1. Environment override:  $MEGAV_PROFILES_DIR
  2. Per-user data dir:     %APPDATA%\\MegaV\\profiles  (Windows)
                            ~/Library/Application Support/MegaV/profiles  (macOS)
                            ~/.local/share/megav/profiles  (Linux)
  3. Repo template:         <project>/profiles/

On first access the user-scoped directory is created and missing files
are copied from the repo template (so the template ships sanitised but
the running app behaves as before).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_REPO_PROFILES = _PROJECT_ROOT / "profiles"
_TEMPLATE_FILES = ("user_profile.json", "github_credentials.json", "job_answers.json")


def _user_data_root() -> Path:
    override = os.environ.get("MEGAV_PROFILES_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "MegaV" / "profiles"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MegaV" / "profiles"
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(xdg) if xdg else (Path.home() / ".local" / "share")
    return base / "megav" / "profiles"


def profiles_dir() -> Path:
    """Return user-scoped profiles directory, creating it on first call."""
    target = _user_data_root()
    target.mkdir(parents=True, exist_ok=True)
    _seed_from_template(target)
    return target


def profile_file(name: str) -> Path:
    """Return absolute path to a user-scoped profile file."""
    return profiles_dir() / name


def resumes_dir() -> Path:
    d = profiles_dir() / "resumes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def credentials_dir() -> Path:
    d = profiles_dir() / "credentials"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _seed_from_template(target: Path) -> None:
    """Copy repo template files into the user dir if they are missing."""
    if not _REPO_PROFILES.exists():
        return
    for name in _TEMPLATE_FILES:
        src = _REPO_PROFILES / name
        dst = target / name
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass
