"""
Rate limiting
=============
Who a request counts against, and whether it is allowed through.

Two independent bugs made the configured limit a no-op in production:

1. **Nothing counted.** ``RATE_LIMIT_PER_MINUTE`` was passed to slowapi as a
   default limit, but slowapi only applies default limits from
   ``SlowAPIMiddleware``, which was never installed. Adding it does not help
   either: slowapi resolves the route by walking ``app.routes`` for an object
   with an ``.endpoint``, and this Starlette version nests included routers
   inside ``_IncludedRouter`` entries instead of flattening them. The lookup
   returns ``None``, ``_should_exempt`` treats an unresolved route as exempt,
   and every API route is skipped. That is why this module counts requests
   itself rather than going through slowapi's middleware — the limiting is done
   with the same underlying ``limits`` library slowapi uses, keyed off the
   request path, which needs no route resolution.

2. **Everyone shared one bucket.** The key was the client address, which behind
   the production reverse proxy is the proxy's address — so the per-client
   limit behaved as a single global cap. Authenticated traffic is now keyed on
   the user, which is the unit the limit is actually about and is immune to
   proxies and NAT alike. Anonymous traffic still falls back to the address,
   which is only meaningful when the app runs with forwarded headers enabled
   (see ``--forwarded-allow-ips`` on the gunicorn command in
   ``docker-compose.prod.yml``).
"""

import logging
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from limits import parse
from limits.storage import storage_from_string
from limits.strategies import MovingWindowRateLimiter
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .security import decode_access_token

logger = logging.getLogger("stock_analyzer.rate_limit")

# Paths that must not consume anyone's budget.
#
# The health checks are polled by infrastructure, and would otherwise exhaust
# the anonymous bucket for the proxy's address and lock out every user behind
# it. Stripe's webhook deliveries carry no user token and originate from a
# handful of shared addresses, so they would pile into one bucket and be
# dropped under load; that endpoint establishes authenticity with a signature
# check instead.
EXEMPT_PATHS = frozenset(
    {
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/docs/oauth2-redirect",
        "/api/v1/stripe/webhook",
    }
)


def _bearer_subject(request: Request) -> Optional[str]:
    """
    The email claim of a valid access token on this request, if there is one.

    Every failure mode — no header, wrong scheme, malformed, expired, or a
    refresh token used where an access token belongs — returns ``None`` so the
    caller falls back to address keying. Nothing here rejects a request; that
    stays the job of ``get_current_user``, which reports a proper 401.
    """
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None

    try:
        payload = decode_access_token(token)
    except Exception:  # noqa: BLE001
        # A key function that raises would turn every request into a 500, so an
        # unreadable token degrades to address keying instead of propagating.
        return None

    # A refresh token would otherwise open a second bucket for the same person.
    if payload.get("type") != "access":
        return None

    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None


def client_key(request: Request) -> str:
    """Identify the caller: the user when known, else the client address."""
    subject = _bearer_subject(request)
    if subject:
        return f"user:{subject.lower()}"
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


class RateLimiter:
    """
    A fixed budget of requests per caller per minute.

    Storage is in-process by default and shared through Redis when ``REDIS_URL``
    is set — which is what makes the limit meaningful across gunicorn workers,
    since otherwise each worker grants the full budget independently.
    """

    def __init__(self) -> None:
        self.enabled = settings.RATE_LIMIT_ENABLED
        self._limit = parse(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
        self._storage = storage_from_string(settings.REDIS_URL or "memory://")
        self._strategy = MovingWindowRateLimiter(self._storage)

    def allow(self, key: str) -> bool:
        """Consume one request from ``key``'s budget; False when it is spent."""
        try:
            return self._strategy.hit(self._limit, key)
        except Exception as e:  # noqa: BLE001
            # Fail open. A limiter that rejects traffic when its storage is
            # unreachable converts a Redis blip into a full outage.
            logger.error("Rate limit storage unavailable, allowing request: %s", e)
            return True

    def retry_after(self, key: str) -> int:
        """Whole seconds until ``key`` may retry, for the Retry-After header."""
        import time

        try:
            stats = self._strategy.get_window_stats(self._limit, key)
            return max(1, int(stats.reset_time - time.time()))
        except Exception:  # noqa: BLE001
            return 60

    def reset(self) -> None:
        """Clear all counts. Used by tests."""
        self._storage.reset()


limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce the per-caller limit on every request that is not exempt."""

    async def dispatch(self, request: Request, call_next):
        if not limiter.enabled or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        key = client_key(request)
        if not limiter.allow(key):
            logger.info("Rate limit exceeded for %s on %s", key, request.url.path)
            retry_after = limiter.retry_after(key)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Too many requests. Please slow down and try again in "
                        f"{retry_after} second(s)."
                    )
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
