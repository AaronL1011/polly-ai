import os
import time
from collections.abc import Callable

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from democrata_server.api.http.deps import get_session_id


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting for MVP. Use Redis for production."""

    def __init__(
        self,
        app,
        requests_per_minute: int = 30,
        protected_prefixes: list[str] | None = None,
    ):
        super().__init__(app)
        self.requests_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", str(requests_per_minute)))
        self.protected_prefixes = protected_prefixes or ["/rag", "/ingestion"]
        self._requests: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        is_protected = any(path.startswith(prefix) for prefix in self.protected_prefixes)

        if not is_protected:
            return await call_next(request)

        session_id = get_session_id(request)
        now = time.time()
        window_start = now - 60

        # Clean old entries and get current count
        if session_id in self._requests:
            self._requests[session_id] = [
                ts for ts in self._requests[session_id] if ts > window_start
            ]
        else:
            self._requests[session_id] = []

        if len(self._requests[session_id]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please wait before making more requests.",
            )

        self._requests[session_id].append(now)
        return await call_next(request)
