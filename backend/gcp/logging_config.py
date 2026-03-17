"""
Cloud Logging Configuration for DDYs Compliance Platform.

Produces structured JSON logs compatible with Google Cloud Logging.
Includes request ID propagation and tenant context in all log entries.
"""

import json
import logging
import os
import sys
import traceback
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Context variables for request-scoped metadata
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")

# GCP severity mapping
SEVERITY_MAP = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL",
}


class CloudLoggingFormatter(logging.Formatter):
    """
    Formats log records as structured JSON for Google Cloud Logging.

    Fields follow the GCP structured logging specification:
    https://cloud.google.com/logging/docs/structured-logging
    """

    def __init__(self, service_name: str = "ddys-compliance", environment: str = "dev"):
        super().__init__()
        self.service_name = service_name
        self.environment = environment
        self.project_id = os.environ.get("GCP_PROJECT_ID", "")

    def format(self, record: logging.LogRecord) -> str:
        # Build the structured log entry
        entry: dict[str, Any] = {
            "severity": SEVERITY_MAP.get(record.levelno, "DEFAULT"),
            "message": record.getMessage(),
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "logging.googleapis.com/sourceLocation": {
                "file": record.pathname,
                "line": str(record.lineno),
                "function": record.funcName,
            },
            "serviceContext": {
                "service": self.service_name,
                "version": os.environ.get("K_REVISION", "local"),
            },
            "labels": {
                "environment": self.environment,
                "logger": record.name,
            },
        }

        # Add trace context if available (for Cloud Trace correlation)
        trace_header = getattr(record, "trace_header", None)
        if trace_header and self.project_id:
            trace_id = trace_header.split("/")[0]
            entry["logging.googleapis.com/trace"] = (
                f"projects/{self.project_id}/traces/{trace_id}"
            )

        # Add request context from ContextVars
        req_id = request_id_var.get("")
        if req_id:
            entry["httpRequest"] = {"requestId": req_id}
            entry["labels"]["request_id"] = req_id

        tenant = tenant_id_var.get("")
        if tenant:
            entry["labels"]["tenant_id"] = tenant

        user = user_id_var.get("")
        if user:
            entry["labels"]["user_id"] = user

        # Add exception info
        if record.exc_info and record.exc_info[0] is not None:
            entry["stack_trace"] = "".join(traceback.format_exception(*record.exc_info))
            entry["@type"] = (
                "type.googleapis.com/google.devtools.clouderrorreporting.v1beta1.ReportedErrorEvent"
            )

        # Add any extra fields
        if hasattr(record, "extra_fields"):
            entry.update(record.extra_fields)

        return json.dumps(entry, ensure_ascii=False, default=str)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that sets request context (ID, tenant, user) for structured logging.
    """

    async def dispatch(self, request: Request, call_next):
        # Generate or extract request ID
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_var.set(req_id)

        # Extract trace header for Cloud Trace
        trace_header = request.headers.get("X-Cloud-Trace-Context", "")

        # Extract tenant from various sources
        tenant = (
            request.headers.get("X-Tenant-ID")
            or request.query_params.get("tenant_id")
            or ""
        )
        tenant_id_var.set(tenant)

        # User ID will be set by auth middleware after JWT validation
        user_id_var.set("")

        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = req_id

        return response


def setup_cloud_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    service_name: str = "ddys-compliance",
    environment: str = "dev",
):
    """
    Configure logging for GCP Cloud Logging or local development.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: "json" for structured Cloud Logging, "text" for local dev.
        service_name: Service name to include in log entries.
        environment: Environment name (dev, staging, prod).
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if log_format == "json":
        formatter = CloudLoggingFormatter(
            service_name=service_name,
            environment=environment,
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (req=%(request_id)s tenant=%(tenant_id)s): %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # Add filter to inject context vars into text formatter
        handler.addFilter(_ContextFilter())

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Suppress noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("google.auth").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured: level=%s format=%s service=%s env=%s",
        log_level,
        log_format,
        service_name,
        environment,
    )


class _ContextFilter(logging.Filter):
    """Injects context vars into log records for text formatter."""

    def filter(self, record):
        record.request_id = request_id_var.get("none")
        record.tenant_id = tenant_id_var.get("none")
        record.user_id = user_id_var.get("none")
        return True


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **extra_fields,
):
    """
    Log a message with additional structured context fields.

    Usage:
        log_with_context(logger, logging.INFO, "Document uploaded",
                         tenant_id="t-123", doc_id="d-456", size=1024)
    """
    if tenant_id:
        tenant_id_var.set(tenant_id)
    if user_id:
        user_id_var.set(user_id)

    record = logger.makeRecord(
        logger.name, level, "(unknown)", 0, message, (), None
    )
    record.extra_fields = extra_fields  # type: ignore
    logger.handle(record)
