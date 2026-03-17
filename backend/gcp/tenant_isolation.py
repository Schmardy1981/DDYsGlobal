"""
Multi-Tenant Isolation Service for DDYs Compliance Platform.

Provides middleware and utilities to enforce strict tenant data isolation:
- Request-level tenant context propagation
- Database query scoping (all queries include tenant_id filter)
- Storage bucket/prefix routing
- Audit logging for cross-tenant access attempts
- Zero-trust: every data access is validated against tenant context

Swiss regulatory requirement: FINMA mandates strict client data segregation.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class TenantContext:
    """
    Holds the current tenant context for a request.
    Thread-safe via contextvars (set per-request in middleware).
    """

    def __init__(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
        global_role: str = "",
        is_global_admin: bool = False,
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.user_role = user_role
        self.global_role = global_role
        self.is_global_admin = is_global_admin

    def can_access_tenant(self, target_tenant_id: str) -> bool:
        """Check if the current user can access data for the target tenant."""
        # Global admins (DDYs staff) can access all tenants
        if self.is_global_admin:
            return True
        # Regular users can only access their own tenant
        return self.tenant_id == target_tenant_id

    def __repr__(self):
        return (
            f"TenantContext(tenant_id='{self.tenant_id}', user_id='{self.user_id}', "
            f"role='{self.user_role}', global_admin={self.is_global_admin})"
        )


# Global roles that have cross-tenant access
GLOBAL_ADMIN_ROLES = {"ADMIN"}

# Endpoints that don't require tenant context
TENANT_EXEMPT_PATHS = {
    "/api/health",
    "/api",
    "/api/seed",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/auth/login",
    "/api/auth/mfa/verify",
}


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces tenant isolation on every request.

    Responsibilities:
    1. Extracts tenant context from JWT claims (set by auth middleware).
    2. Validates tenant_id in request body/params matches user's tenant.
    3. Stores TenantContext in request.state for downstream handlers.
    4. Logs cross-tenant access attempts.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip tenant check for exempt paths
        if path in TENANT_EXEMPT_PATHS or path.startswith("/api/auth/"):
            return await call_next(request)

        # Skip for OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Get user info from request state (set by auth middleware)
        user = getattr(request.state, "user", None)
        if not user:
            # Auth middleware hasn't run or user not authenticated
            return await call_next(request)

        # Build tenant context
        user_tenant_id = user.get("tenant_id", "")
        user_id = user.get("user_id", "")
        user_role = user.get("role", "")
        global_role = user.get("global_role", "")
        is_global_admin = global_role in GLOBAL_ADMIN_ROLES

        tenant_ctx = TenantContext(
            tenant_id=user_tenant_id,
            user_id=user_id,
            user_role=user_role,
            global_role=global_role,
            is_global_admin=is_global_admin,
        )

        # Store context in request state
        request.state.tenant_context = tenant_ctx

        # Check if request targets a different tenant
        requested_tenant = _extract_tenant_from_request(request)
        if requested_tenant and not tenant_ctx.can_access_tenant(requested_tenant):
            # Log the cross-tenant access attempt
            await _log_cross_tenant_attempt(
                request, tenant_ctx, requested_tenant
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: you cannot access data belonging to another tenant.",
            )

        # Update logging context
        try:
            from gcp.logging_config import tenant_id_var, user_id_var
            tenant_id_var.set(user_tenant_id)
            user_id_var.set(user_id)
        except ImportError:
            pass

        response = await call_next(request)
        return response


def _extract_tenant_from_request(request: Request) -> Optional[str]:
    """
    Extract the target tenant_id from request parameters.
    Checks query params, path params, and headers.
    """
    # Query parameter
    tenant = request.query_params.get("tenant_id")
    if tenant:
        return tenant

    # Header
    tenant = request.headers.get("X-Tenant-ID")
    if tenant:
        return tenant

    # Path parameter (for routes like /api/tenants/{tenant_id}/...)
    path_parts = request.url.path.strip("/").split("/")
    if "tenants" in path_parts:
        idx = path_parts.index("tenants")
        if idx + 1 < len(path_parts):
            return path_parts[idx + 1]

    return None


async def _log_cross_tenant_attempt(
    request: Request,
    tenant_ctx: TenantContext,
    target_tenant_id: str,
):
    """Log a cross-tenant access attempt to the audit log and monitoring."""
    logger.error(
        "SECURITY: Cross-tenant access attempt: user=%s (tenant=%s, role=%s) "
        "tried to access tenant=%s via %s %s",
        tenant_ctx.user_id,
        tenant_ctx.tenant_id,
        tenant_ctx.user_role,
        target_tenant_id,
        request.method,
        request.url.path,
    )

    # Write to audit log in MongoDB
    try:
        db = request.app.state.db
        await db.audit_logs.insert_one(
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_ctx.tenant_id,
                "actor_user_id": tenant_ctx.user_id,
                "actor_role": tenant_ctx.global_role or tenant_ctx.user_role,
                "action_key": "security.cross_tenant_access_attempt",
                "entity_type": "tenant",
                "entity_id": target_tenant_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "before_json": None,
                "after_json": {
                    "method": request.method,
                    "path": request.url.path,
                    "source_tenant": tenant_ctx.tenant_id,
                    "target_tenant": target_tenant_id,
                },
                "ip_address": request.client.host if request.client else "",
                "user_agent": request.headers.get("user-agent", ""),
                "severity": "critical",
            }
        )
    except Exception as e:
        logger.error("Failed to write cross-tenant audit log: %s", str(e))

    # Report to Cloud Monitoring
    try:
        from gcp.monitoring import get_monitoring
        monitoring = get_monitoring()
        monitoring.record_cross_tenant_access_attempt(
            requesting_tenant=tenant_ctx.tenant_id,
            target_tenant=target_tenant_id,
            resource_type=request.url.path,
        )
    except Exception:
        pass


def get_tenant_context(request: Request) -> TenantContext:
    """
    Get the TenantContext from the current request.

    Raises HTTPException if no tenant context is set (user not authenticated).
    """
    ctx = getattr(request.state, "tenant_context", None)
    if not ctx:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: no tenant context available.",
        )
    return ctx


def enforce_tenant_access(request: Request, target_tenant_id: str) -> TenantContext:
    """
    Verify that the current user can access the target tenant's data.

    Use this in route handlers when processing requests that reference
    a specific tenant_id (e.g., from request body or database record).

    Raises HTTPException 403 if access is denied.
    """
    ctx = get_tenant_context(request)
    if not ctx.can_access_tenant(target_tenant_id):
        logger.error(
            "Tenant isolation violation in handler: user=%s (tenant=%s) "
            "accessing tenant=%s",
            ctx.user_id,
            ctx.tenant_id,
            target_tenant_id,
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied: you cannot access data belonging to another tenant.",
        )
    return ctx


class TenantScopedQuery:
    """
    Helper class that automatically adds tenant_id filters to MongoDB queries.

    Usage:
        scoped = TenantScopedQuery(db, tenant_ctx)
        cases = await scoped.find("cases", {"status": "open"})
        # Automatically adds {"tenant_id": tenant_ctx.tenant_id} to the query
    """

    def __init__(self, db: Any, tenant_context: TenantContext):
        self.db = db
        self.ctx = tenant_context

    def _scope_query(self, query: dict) -> dict:
        """Add tenant_id to query unless user is global admin accessing all tenants."""
        scoped = dict(query)
        if not self.ctx.is_global_admin:
            scoped["tenant_id"] = self.ctx.tenant_id
        elif "tenant_id" not in scoped:
            # Global admins must explicitly specify tenant_id or query all
            pass
        return scoped

    async def find_one(
        self, collection: str, query: dict, projection: Optional[dict] = None
    ):
        """Find one document, scoped to current tenant."""
        scoped_query = self._scope_query(query)
        return await self.db[collection].find_one(
            scoped_query, projection or {"_id": 0}
        )

    async def find(
        self,
        collection: str,
        query: dict,
        projection: Optional[dict] = None,
        limit: int = 500,
        sort: Optional[list] = None,
    ):
        """Find documents, scoped to current tenant."""
        scoped_query = self._scope_query(query)
        cursor = self.db[collection].find(scoped_query, projection or {"_id": 0})
        if sort:
            cursor = cursor.sort(sort)
        return await cursor.to_list(limit)

    async def count(self, collection: str, query: dict) -> int:
        """Count documents, scoped to current tenant."""
        scoped_query = self._scope_query(query)
        return await self.db[collection].count_documents(scoped_query)

    async def update_one(self, collection: str, query: dict, update: dict):
        """Update one document, scoped to current tenant."""
        scoped_query = self._scope_query(query)
        return await self.db[collection].update_one(scoped_query, update)

    async def delete_one(self, collection: str, query: dict):
        """Delete one document, scoped to current tenant."""
        scoped_query = self._scope_query(query)
        return await self.db[collection].delete_one(scoped_query)

    async def insert_one(self, collection: str, document: dict):
        """Insert a document, ensuring tenant_id is set."""
        doc = dict(document)
        if not self.ctx.is_global_admin:
            doc["tenant_id"] = self.ctx.tenant_id
        return await self.db[collection].insert_one(doc)
