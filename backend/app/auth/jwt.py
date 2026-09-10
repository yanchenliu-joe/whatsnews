"""Supabase access token verification.

Primary path: JWKS-based asymmetric verification (ES256/RS256) — this is
Supabase's current default for new projects (see "JWT Signing Keys" in the
Supabase dashboard). Fallback: legacy shared HS256 secret
(SUPABASE_JWT_SECRET), for projects that haven't migrated off it.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException
import jwt
from jwt import PyJWKClient
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, PyJWKClientError, PyJWTError

from app.auth.config import supabase_jwt_secret, supabase_url
from app.auth.models import AuthUser

SUPABASE_AUDIENCE = "authenticated"


@lru_cache(maxsize=4)
def _jwks_client_for(jwks_url: str) -> PyJWKClient:
    # PyJWKClient caches fetched signing keys internally (default lifespan
    # 300s), so this only needs to avoid recreating the client per-request.
    return PyJWKClient(jwks_url)


def _decode_kwargs(project_url: str | None) -> dict:
    kwargs: dict = {
        "audience": SUPABASE_AUDIENCE,
        "options": {"require": ["exp", "sub"]},
    }
    if project_url:
        kwargs["issuer"] = f"{project_url.rstrip('/')}/auth/v1"
    return kwargs


def decode_supabase_access_token(token: str) -> AuthUser:
    """
    Verify a Supabase Auth access token from Authorization: Bearer.
    Never log token contents.
    """
    project_url = supabase_url()
    payload = None

    if project_url:
        jwks_url = f"{project_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        try:
            signing_key = _jwks_client_for(jwks_url).get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                **_decode_kwargs(project_url),
            )
        except ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired.")
        except (PyJWKClientError, InvalidTokenError, PyJWTError) as exc:
            print(
                f"[whatsnews] event=jwt_verify_failed stage=jwks "
                f"reason={type(exc).__name__} detail={exc}"
            )

    if payload is None:
        secret = supabase_jwt_secret()
        if not secret:
            raise HTTPException(status_code=401, detail="Invalid or expired token.")

        try:
            payload = jwt.decode(
                token, secret, algorithms=["HS256"], **_decode_kwargs(project_url)
            )
        except ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired.")
        except (InvalidTokenError, PyJWTError) as exc:
            print(
                f"[whatsnews] event=jwt_verify_failed stage=hs256 "
                f"reason={type(exc).__name__} detail={exc}"
            )
            raise HTTPException(status_code=401, detail="Invalid or expired token.")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    email = payload.get("email")
    if email is not None and not isinstance(email, str):
        email = str(email)

    return AuthUser(
        id=str(sub),
        email=email,
        role=payload.get("role") if isinstance(payload.get("role"), str) else None,
        app_metadata=payload.get("app_metadata")
        if isinstance(payload.get("app_metadata"), dict)
        else None,
        user_metadata=payload.get("user_metadata")
        if isinstance(payload.get("user_metadata"), dict)
        else None,
    )
