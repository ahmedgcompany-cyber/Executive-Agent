"""Secret resolution helpers.

Resolution order for any secret:
  1. Environment variable (e.g. STRIPE_API_KEY)
  2. CredentialStore service entry
  3. Empty string

Secrets are NEVER read from settings.yaml or any file under the project tree.
"""

from __future__ import annotations

import os
from typing import Optional


def get_secret(env_var: str, service: str, key: str = "api_key") -> str:
    """Return a secret by checking env then CredentialStore."""
    val = os.environ.get(env_var, "").strip()
    if val:
        return val
    try:
        from .credential_store import get_credential_store
        store = get_credential_store()
        loaded = store.load(service, key)
        return (loaded or "").strip()
    except Exception:
        return ""


def get_stripe_key() -> str:
    return get_secret("STRIPE_API_KEY", "stripe", "api_key")


def set_stripe_key(value: str) -> None:
    from .credential_store import get_credential_store
    get_credential_store().save("stripe", "api_key", value)
