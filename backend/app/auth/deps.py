"""FastAPI dependencies for authenticated routes."""

from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from app.auth.config import auth_enabled
from app.auth.jwt import decode_supabase_access_token
from app.auth.models import AuthUser


def require_auth_enabled() -> None:
    if not auth_enabled():
        raise HTTPException(status_code=503, detail="Auth disabled")


def extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")

    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Invalid Authorization header.")

    return parts[1].strip()


def get_current_user(authorization: Optional[str] = Header(default=None)) -> AuthUser:
    require_auth_enabled()
    token = extract_bearer_token(authorization)
    return decode_supabase_access_token(token)
