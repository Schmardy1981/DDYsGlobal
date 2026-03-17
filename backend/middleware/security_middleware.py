"""Security middleware: rate limiting, security headers, input sanitization."""
import html
import re
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time
import os
from collections import defaultdict
import asyncio


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token bucket rate limiter per IP address."""

    def __init__(self, app, default_limit: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

        # Route-specific limits
        self.route_limits = {
            "/api/auth/login": 10,
            "/api/auth/mfa/verify": 10,
            "/api/auth/customer/otp": 10,
            "/api/documents/upload": 20,
            "/api/seed": 5,
            "/api/intake/submit": 20,
        }

    def _get_limit(self, path: str) -> int:
        for route, limit in self.route_limits.items():
            if path.startswith(route):
                return limit
        return self.default_limit

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        limit = self._get_limit(path)
        now = time.time()

        key = f"{client_ip}:{path}"

        async with self._lock:
            # Clean old entries
            self.requests[key] = [
                t for t in self.requests[key]
                if now - t < self.window_seconds
            ]

            if len(self.requests[key]) >= limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many requests",
                        "retry_after": self.window_seconds,
                    },
                    headers={"Retry-After": str(self.window_seconds)},
                )

            self.requests[key].append(now)

        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(self), microphone=(self), geolocation=(), payment=()"
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"

        if os.environ.get("ENVIRONMENT") == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        return response


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Sanitize request inputs to prevent XSS and injection attacks."""

    # Patterns that indicate potential injection
    DANGEROUS_PATTERNS = [
        re.compile(r"<script", re.IGNORECASE),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
        re.compile(r"\{\{.*\}\}"),  # Template injection
    ]

    async def dispatch(self, request: Request, call_next):
        # Only check body for mutation requests
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body = await request.body()
                    body_str = body.decode("utf-8")
                    for pattern in self.DANGEROUS_PATTERNS:
                        if pattern.search(body_str):
                            return JSONResponse(
                                status_code=400,
                                content={"detail": "Potentially dangerous input detected"},
                            )
                except Exception:
                    pass

        # Check query params
        for key, value in request.query_params.items():
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern.search(value):
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Potentially dangerous input detected"},
                    )

        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Structured request logging for monitoring."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time
        import logging
        import json

        logger = logging.getLogger("ddys.access")

        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", ""),
        }

        if os.environ.get("LOG_FORMAT") == "json":
            logger.info(json.dumps(log_data))
        else:
            logger.info(
                f"{log_data['method']} {log_data['path']} "
                f"{log_data['status']} {log_data['duration_ms']}ms"
            )

        return response
