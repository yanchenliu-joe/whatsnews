"""Shared admin-key gating dependency for every /admin/* route."""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import HTTPException


def require_admin_key(x_admin_key: Optional[str]) -> None:
    """Raise 401 if ADMIN_API_KEY is configured and the provided key does not match."""
    required = os.getenv("ADMIN_API_KEY")
    if required and not hmac.compare_digest(x_admin_key or "", required):
        raise HTTPException(status_code=401, detail="Missing or invalid x-admin-key header.")
