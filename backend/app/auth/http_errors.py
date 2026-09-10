"""Map auth repository errors to HTTP responses."""

from __future__ import annotations

from fastapi import HTTPException


def raise_for_auth_repository_error(
    error: Exception,
    *,
    bad_request: bool = False,
) -> None:
    if isinstance(error, ValueError):
        status_code = 400 if bad_request else 503
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    if isinstance(error, RuntimeError):
        raise HTTPException(status_code=503, detail=str(error)) from error
    raise error
