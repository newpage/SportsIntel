from __future__ import annotations

from hmac import compare_digest

from fastapi import Header, HTTPException, Request


def require_admin_api_key(
    request: Request,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> None:
    configured_key = request.app.state.settings.admin_key
    if (
        configured_key is None
        or x_admin_key is None
        or not compare_digest(x_admin_key, configured_key)
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "ApiKey"},
        )
