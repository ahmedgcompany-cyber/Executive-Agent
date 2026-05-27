"""
Secure local credential storage for MegaV.

Encrypts all secrets before writing to disk using Fernet (AES-128-CBC + HMAC).
The `cryptography` package is REQUIRED — there is no insecure fallback.

Credentials are stored per-service as JSON files in profiles/credentials/.
Plain-text passwords are NEVER persisted or logged.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
from pathlib import Path
from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError as exc:
    raise SystemExit(
        "FATAL: 'cryptography' package is required for CredentialStore.\n"
        "Install it with:  pip install cryptography\n"
        f"Original error: {exc}"
    )


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

def _machine_key() -> bytes:
    """Derive a 32-byte machine-specific key from stable hardware identifiers."""
    node    = platform.node() or "megav-node"
    user    = os.environ.get("USERNAME", "") or os.environ.get("USER", "") or "megav"
    machine = platform.machine() or "x86"
    seed    = f"megav-cred-store::{node}::{user}::{machine}::v1"
    return hashlib.sha256(seed.encode("utf-8")).digest()


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_machine_key()))


def _encrypt(plaintext: str) -> str:
    """Encrypt a string with Fernet, return tagged ciphertext."""
    ct = _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"fernet:{ct}"


def _decrypt(ciphertext: str) -> str:
    """Decrypt a tagged ciphertext string. Returns "" on failure."""
    if not ciphertext:
        return ""
    if ciphertext.startswith("fernet:"):
        try:
            return _fernet().decrypt(ciphertext[7:].encode("ascii")).decode("utf-8")
        except InvalidToken:
            return ""
    if ciphertext.startswith("xor:"):
        # Legacy XOR-encoded values — refuse to decrypt; force user to re-enter.
        return ""
    # Unrecognised format — assume legacy plaintext (do not log).
    return ciphertext


# ---------------------------------------------------------------------------
# CredentialStore class
# ---------------------------------------------------------------------------

class CredentialStore:
    """Encrypted local credential store backed by per-service JSON files.

    Usage::

        store = CredentialStore()
        store.save("gmail_john@example.com", "password", "my-app-password")
        pw = store.load("gmail_john@example.com", "password")
        store.delete("gmail_john@example.com")
    """

    DEFAULT_DIR = Path("profiles") / "credentials"  # legacy fallback (repo-relative)

    def __init__(self, store_dir: Optional[str] = None):
        if store_dir:
            self._dir = Path(store_dir)
        else:
            try:
                from .profile_paths import credentials_dir
                self._dir = credentials_dir()
            except Exception:
                self._dir = self.DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def save(self, service: str, key: str, value: str) -> None:
        """Encrypt and persist a credential field."""
        data = self._load_raw(service)
        data[key] = _encrypt(value)
        self._write_raw(service, data)

    def save_many(self, service: str, fields: dict[str, str]) -> None:
        """Encrypt and persist multiple fields atomically."""
        data = self._load_raw(service)
        for k, v in fields.items():
            data[k] = _encrypt(v)
        self._write_raw(service, data)

    def load(self, service: str, key: str) -> Optional[str]:
        """Load and decrypt a single credential field."""
        data = self._load_raw(service)
        raw  = data.get(key)
        return _decrypt(raw) if raw else None

    def load_all(self, service: str) -> dict[str, str]:
        """Load and decrypt all fields for a service."""
        data = self._load_raw(service)
        return {k: _decrypt(v) for k, v in data.items()}

    def delete(self, service: str) -> None:
        """Remove all credentials for a service."""
        p = self._service_path(service)
        if p.exists():
            p.unlink()

    def delete_field(self, service: str, key: str) -> None:
        """Remove a single field from a service credential."""
        data = self._load_raw(service)
        if key in data:
            del data[key]
            self._write_raw(service, data)

    def exists(self, service: str) -> bool:
        """Return True if credentials exist for this service."""
        return self._service_path(service).exists()

    def list_services(self) -> list[str]:
        """Return all stored service names."""
        return [p.stem for p in self._dir.glob("*.json")]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _service_path(self, service: str) -> Path:
        # Sanitise service name for use as filename
        safe = "".join(c if c.isalnum() or c in "-_.@+" else "_" for c in service)
        return self._dir / f"{safe}.json"

    def _load_raw(self, service: str) -> dict:
        p = self._service_path(service)
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_raw(self, service: str, data: dict) -> None:
        p = self._service_path(service)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store: Optional[CredentialStore] = None


def get_credential_store() -> CredentialStore:
    """Return the shared CredentialStore singleton."""
    global _store
    if _store is None:
        _store = CredentialStore()
    return _store
