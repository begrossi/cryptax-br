"""
Backend API authentication.

The FastAPI backend is a separate process from the Next.js frontend. Without
this guard, anyone who can reach port 8000 could read/write wallets and
credentials directly, bypassing the frontend password entirely.

A shared secret (`API_TOKEN`) is sent by the frontend proxy on every request via
the `X-API-Token` header and verified here with a constant-time comparison.

If `API_TOKEN` is unset the guard is a no-op — intended for local single-user
dev only. In that mode the backend is fully open, so a startup warning is logged.
"""

import hmac

from fastapi import Header, HTTPException

from app.config import settings


async def require_api_token(x_api_token: str | None = Header(default=None)) -> None:
    expected = settings.api_token
    if not expected:
        # Auth disabled (no token configured). Open backend — dev only.
        return
    if x_api_token is None or not hmac.compare_digest(x_api_token, expected):
        raise HTTPException(status_code=401, detail="Token de API inválido ou ausente")
