#!/usr/bin/env python3
"""
prepare_distribution.py
=======================
Creates a clean, shareable ZIP of the MegaV app.

Run from the "MegaV" folder:
    python prepare_distribution.py

What it does:
  1. Copies executive-agent-app/ to a temp staging directory
  2. Strips all personal data (name, location, phone, email, UAE details)
  3. Deletes cache, logs, screenshots, old outputs, __pycache__
  4. Removes first_run_complete.json so the wizard fires on first launch
  5. Removes any recorded workflows that may reveal personal tasks
  6. Zips the staging directory into Executive_Agent_v1.0.zip
"""

import json
import os
import re
import shutil
import stat
import sys
import zipfile
from pathlib import Path


def _force_remove(func, path, exc_info):
    """rmtree onerror handler — clears Windows ReadOnly attribute and retries."""
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    except Exception:
        pass


def _rmtree(path: Path) -> None:
    if not path.exists():
        return
    shutil.rmtree(path, onerror=_force_remove)

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent.resolve()
SOURCE_DIR  = SCRIPT_DIR / "executive-agent-app"
STAGE_DIR   = SCRIPT_DIR / "_dist_staging" / "MegaV_v2.7"
OUTPUT_ZIP  = SCRIPT_DIR / "MegaV_v2.7.0.zip"

# Launcher files in the parent folder to copy alongside the app
LAUNCHER_FILES = [
    "Launch MegaV.bat",
    "Install Dependencies.bat",
    "Setup Local AI (Ollama).bat",
]

# ── Personal-data tokens to scrub from JSON/YAML/TXT ──────────────────────
PERSONAL_TOKENS = [
    "Ahmed Alghoul", "ahmed alghoul",
    "Abu Dhabi", "abu dhabi",
    "UAE", "U.A.E",
    "+971", "AED",
    "UAE Resident", "Valid work permit",
]

# Files/dirs to delete from the staging copy
JUNK_PATTERNS = [
    "**/__pycache__",
    "**/.pytest_cache",
    "**/.mypy_cache",
    "**/.ruff_cache",
    "**/*.pyc",
    "**/*.pyo",
    "**/*.log",
    "**/*.png",      # screenshots
    "**/*.jpg",
    "TRANSFORMATION_SUMMARY.md",
    "out.log",
    "output.py",
    "output.txt",
    "test_output.txt",
    "screenshot_*.png",
    "window_capture_*.png",
    "region_capture_*.png",
]

# Sensitive credential files: ALWAYS reset to empty templates in the ZIP.
SENSITIVE_FILES = [
    "profiles/github_credentials.json",
    "profiles/credentials",  # whole encrypted credential dir, if it exists
]

# Dirs to wipe completely (recreate empty)
WIPE_DIRS = [
    "logs",
    "workflows",   # clear recorded workflows — may contain personal task text
]

# Files to reset/remove entirely
RESET_FILES = [
    "config/first_run_complete.json",   # force wizard on first launch
]


def reset_sensitive_files(app_stage: Path):
    """Wipe credentials and stripe-key residue before zipping."""
    # github_credentials.json -> empty template
    creds_json = app_stage / "profiles" / "github_credentials.json"
    if creds_json.exists():
        creds_json.write_text(
            json.dumps({"enc_token": "", "username": "", "saved_at": 0}),
            encoding="utf-8",
        )
    # Encrypted credential store directory -> remove entirely
    creds_dir = app_stage / "profiles" / "credentials"
    if creds_dir.exists():
        _rmtree(creds_dir)
    # Belt-and-suspenders: scrub any leftover stripe_api_key from settings.yaml
    settings = app_stage / "config" / "settings.yaml"
    if settings.exists():
        try:
            text = settings.read_text(encoding="utf-8")
            scrubbed = re.sub(
                r'^\s*stripe_api_key\s*:.*$',
                '# stripe_api_key removed — set STRIPE_API_KEY env var or use the GUI.',
                text,
                flags=re.MULTILINE,
            )
            if scrubbed != text:
                settings.write_text(scrubbed, encoding="utf-8")
        except Exception:
            pass


def copy_source():
    """Copy source directory and launcher files to staging."""
    _rmtree(STAGE_DIR)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Copy the app folder
    app_stage = STAGE_DIR / "executive-agent-app"
    print(f"  Copying app -> {app_stage} ...")
    shutil.copytree(SOURCE_DIR, app_stage, dirs_exist_ok=True)

    # Copy launcher batch files
    for fname in LAUNCHER_FILES:
        src = SCRIPT_DIR / fname
        if src.exists():
            shutil.copy2(src, STAGE_DIR / fname)
            print(f"  Copied launcher: {fname}")


def strip_personal_data():
    """Replace personal tokens in text files."""
    text_extensions = {".json", ".yaml", ".yml", ".txt", ".md", ".py", ".bat", ".sh", ".cfg", ".ini", ".toml"}
    scrubbed_count = 0
    app_stage = STAGE_DIR / "executive-agent-app"

    for fpath in app_stage.rglob("*"):
        if not fpath.is_file():
            continue
        if fpath.suffix.lower() not in text_extensions:
            continue

        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        original = content
        for token in PERSONAL_TOKENS:
            content = content.replace(token, "")

        # Also blank out the 'author' field in settings.yaml
        content = re.sub(r'(author:\s*")[^"]*(")', r'\1\2', content)
        # Blank "name" in user_profile.json
        if fpath.name == "user_profile.json":
            try:
                data = json.loads(content)
                data["name"] = ""
                data["location"] = ""
                data["emails"] = []
                data["phones"] = []
                data["linkedin"] = ""
                data["portfolio"] = ""
                data["website"] = ""
                data["skills"] = []
                data["job_titles"] = []
                data["preferences"]["salary_currency"] = "USD"
                data["preferences"]["industries"] = []
                data["languages"] = ["English"]
                content = json.dumps(data, indent=2)
            except Exception:
                pass

        if fpath.name == "job_answers.json":
            try:
                data = json.loads(content)
                data["work_authorization"] = ""
                data["years_of_experience"] = ""
                data["relocation"] = "Open to discussion."
                content = json.dumps(data, indent=2)
            except Exception:
                pass

        if content != original:
            fpath.write_text(content, encoding="utf-8")
            scrubbed_count += 1

    print(f"  Scrubbed personal data from {scrubbed_count} file(s).")


def delete_junk():
    """Remove cache, logs, screenshots, and other junk files."""
    app_stage = STAGE_DIR / "executive-agent-app"
    removed = 0
    for pattern in JUNK_PATTERNS:
        for fpath in app_stage.glob(pattern):
            if fpath.is_dir():
                _rmtree(fpath)
            elif fpath.is_file():
                fpath.unlink()
            removed += 1

    # Remove __pycache__ dirs recursively (glob pattern didn't catch nested ones)
    for pycache in app_stage.rglob("__pycache__"):
        if pycache.is_dir():
            _rmtree(pycache)
            removed += 1

    print(f"  Deleted {removed} junk file(s)/dir(s).")


def wipe_dirs():
    """Wipe content of logs/ and workflows/, keep the directory."""
    app_stage = STAGE_DIR / "executive-agent-app"
    for dname in WIPE_DIRS:
        target = app_stage / dname
        if target.exists():
            _rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        # Add a .gitkeep so the folder is not completely empty
        (target / ".gitkeep").write_text("", encoding="utf-8")
    print(f"  Wiped: {', '.join(WIPE_DIRS)}")


def reset_files():
    """Remove files that should not exist for a fresh install."""
    app_stage = STAGE_DIR / "executive-agent-app"
    for rel in RESET_FILES:
        f = app_stage / rel
        if f.exists():
            f.unlink()
            print(f"  Removed: {rel}")


def ensure_resumes_dir():
    """Create the resumes placeholder directory."""
    resumes = STAGE_DIR / "executive-agent-app" / "profiles" / "resumes"
    resumes.mkdir(parents=True, exist_ok=True)
    readme = resumes / "PUT_YOUR_RESUME_HERE.txt"
    if not readme.exists():
        readme.write_text(
            "Place your resume PDF here and update profiles/user_profile.json\n"
            "to point to the correct file name.\n",
            encoding="utf-8",
        )


def create_zip():
    """Zip the staging directory."""
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    print(f"  Creating ZIP: {OUTPUT_ZIP} ...")
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for fpath in STAGE_DIR.rglob("*"):
            arcname = fpath.relative_to(STAGE_DIR.parent)
            zf.write(fpath, arcname)

    size_mb = OUTPUT_ZIP.stat().st_size / (1024 * 1024)
    print(f"  Done!  {OUTPUT_ZIP.name}  ({size_mb:.1f} MB)")


def cleanup_staging():
    """Remove the temporary staging directory."""
    parent = STAGE_DIR.parent
    _rmtree(parent)
    print(f"  Cleaned up staging dir.")


def main():
    print("\n=== MegaV - Preparing Distribution Package ===\n")

    if not SOURCE_DIR.exists():
        print(f"[ERROR] Source not found: {SOURCE_DIR}")
        sys.exit(1)

    print("[1/6] Copying source files ...")
    copy_source()

    print("[2/6] Stripping personal data ...")
    strip_personal_data()

    print("[3/6] Deleting junk files ...")
    delete_junk()

    print("[4/6] Wiping logs and workflows ...")
    wipe_dirs()

    print("[5/7] Resetting first-run marker ...")
    reset_files()
    ensure_resumes_dir()

    print("[6/7] Resetting sensitive files (credentials, stripe key) ...")
    reset_sensitive_files(STAGE_DIR / "executive-agent-app")

    print("[7/7] Creating ZIP archive ...")
    create_zip()
    cleanup_staging()

    print(f"\n[OK]  Distribution package ready:")
    print(f"   {OUTPUT_ZIP}")
    print(f"\n   When clients unpack and double-click 'Launch MegaV.bat'")
    print(f"   the setup wizard will run automatically on their first launch.\n")


if __name__ == "__main__":
    main()
