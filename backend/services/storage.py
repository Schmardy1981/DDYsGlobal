"""Unified document-storage facade.

The platform supports two backends:

* ``local`` — writes files to ``LOCAL_STORAGE_DIR`` (default ``/app/backend/uploads``).
  Suitable for development and tests only.
* ``gcs``   — delegates to :class:`backend.gcp.storage.GCSStorageService`. This is
  the production backend; data lives in a Swiss-region GCS bucket with
  per-tenant prefixes.

The active backend is chosen by the ``STORAGE_TYPE`` environment variable.

Callers should not import GCS or local-filesystem code directly; they should
always go through :func:`get_storage` and use the metadata dict it returns. The
dict format is stable::

    {
        "storage_type": "local" | "gcs",
        "storage_path": str,          # opaque reference for download/delete
        "blob_path":   str | None,    # gcs-only convenience
        "bucket":      str | None,    # gcs-only convenience
        "file_hash":   str,
        "file_size":   int,
        "content_type": str,
        "original_filename": str,
    }
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import aiofiles

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Common interface for document storage backends."""

    storage_type: str = "base"

    @abstractmethod
    async def upload(
        self,
        tenant_id: str,
        case_id: str,
        filename: str,
        content: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict: ...

    @abstractmethod
    async def download(self, tenant_id: str, storage_ref: str) -> tuple[bytes, str]: ...

    @abstractmethod
    async def delete(self, tenant_id: str, storage_ref: str) -> bool: ...

    async def generate_view_url(
        self, tenant_id: str, storage_ref: str, expiration_minutes: int = 15
    ) -> Optional[str]:
        """Return a signed URL where the backend supports it; None otherwise."""
        return None


class LocalStorageBackend(StorageBackend):
    """Filesystem backend. Files are stored under ``base_dir/<tenant_id>/<case_id>/``."""

    storage_type = "local"

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _tenant_dir(self, tenant_id: str, case_id: str) -> Path:
        # Tenant isolation: never allow path traversal via the IDs.
        safe_tenant = (tenant_id or "_unscoped").replace("/", "_").replace("..", "_")
        safe_case = (case_id or "_uncased").replace("/", "_").replace("..", "_")
        path = self.base_dir / safe_tenant / safe_case
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def upload(
        self,
        tenant_id: str,
        case_id: str,
        filename: str,
        content: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        ext = os.path.splitext(filename or "")[1] or ".bin"
        storage_filename = f"{uuid.uuid4().hex}{ext}"
        path = self._tenant_dir(tenant_id, case_id) / storage_filename

        async with aiofiles.open(path, "wb") as f:
            await f.write(content)

        if not content_type:
            content_type, _ = mimetypes.guess_type(filename or "")
            content_type = content_type or "application/octet-stream"

        return {
            "storage_type": self.storage_type,
            "storage_path": str(path),
            "blob_path": None,
            "bucket": None,
            "file_hash": hashlib.sha256(content).hexdigest(),
            "file_size": len(content),
            "content_type": content_type,
            "original_filename": filename,
        }

    async def download(self, tenant_id: str, storage_ref: str) -> tuple[bytes, str]:
        path = Path(storage_ref)
        # Enforce tenant isolation: the path must live under our base_dir, and
        # if a tenant prefix is in use, under the matching subdir.
        try:
            path.resolve().relative_to(self.base_dir.resolve())
        except ValueError as exc:
            raise PermissionError(
                f"Refusing to read file outside storage dir: {storage_ref}"
            ) from exc

        if tenant_id:
            expected_prefix = self.base_dir.resolve() / tenant_id
            try:
                path.resolve().relative_to(expected_prefix)
            except ValueError:
                # Legacy uploads predate per-tenant subdirs — allow but log.
                logger.warning(
                    "Legacy local document outside tenant prefix: tenant=%s path=%s",
                    tenant_id,
                    storage_ref,
                )

        async with aiofiles.open(path, "rb") as f:
            content = await f.read()

        mime, _ = mimetypes.guess_type(str(path))
        return content, mime or "application/octet-stream"

    async def delete(self, tenant_id: str, storage_ref: str) -> bool:
        path = Path(storage_ref)
        try:
            path.resolve().relative_to(self.base_dir.resolve())
        except ValueError:
            return False
        try:
            os.remove(path)
            return True
        except FileNotFoundError:
            return False


class GCSStorageBackend(StorageBackend):
    """Google Cloud Storage backend (production)."""

    storage_type = "gcs"

    def __init__(self):
        from gcp.storage import get_gcs_storage

        self._svc = get_gcs_storage()

    async def upload(
        self,
        tenant_id: str,
        case_id: str,
        filename: str,
        content: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        result = await self._svc.upload_document(
            tenant_id=tenant_id,
            case_id=case_id,
            filename=filename,
            content=content,
            content_type=content_type,
            metadata=metadata,
        )
        return {
            "storage_type": "gcs",
            # canonical reference used by download/delete
            "storage_path": result["blob_path"],
            "blob_path": result["blob_path"],
            "bucket": result["bucket"],
            "file_hash": result["file_hash"],
            "file_size": result["file_size"],
            "content_type": result["content_type"],
            "original_filename": result["original_filename"],
        }

    async def download(self, tenant_id: str, storage_ref: str) -> tuple[bytes, str]:
        return await self._svc.download_document(tenant_id, storage_ref)

    async def delete(self, tenant_id: str, storage_ref: str) -> bool:
        return await self._svc.delete_document(tenant_id, storage_ref)

    async def generate_view_url(
        self, tenant_id: str, storage_ref: str, expiration_minutes: int = 15
    ) -> Optional[str]:
        return await self._svc.generate_signed_url(
            tenant_id=tenant_id,
            blob_path=storage_ref,
            expiration_minutes=expiration_minutes,
            method="GET",
        )


# --- Factory ---------------------------------------------------------------

_BACKEND: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    """Return the configured storage backend (singleton)."""
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND

    storage_type = os.environ.get("STORAGE_TYPE", "local").lower()
    if storage_type == "gcs":
        try:
            _BACKEND = GCSStorageBackend()
            logger.info("Using GCS storage backend")
            return _BACKEND
        except Exception:
            logger.exception("GCS backend init failed; falling back to local storage")

    base_dir = os.environ.get("LOCAL_STORAGE_DIR", "/app/backend/uploads")
    _BACKEND = LocalStorageBackend(base_dir)
    logger.info("Using local storage backend at %s", base_dir)
    return _BACKEND


async def resolve_document_storage(doc: dict) -> tuple[str, str]:
    """Return ``(tenant_id, storage_ref)`` for a document record.

    Older documents may only have ``storage_path``. New ones store the canonical
    reference under ``storage_path`` regardless of backend, plus ``storage_type``
    for routing.
    """
    tenant_id = doc.get("tenant_id", "") or ""
    storage_ref = doc.get("blob_path") or doc.get("storage_path") or ""
    return tenant_id, storage_ref


def backend_for(doc: dict) -> StorageBackend:
    """Return the right backend for a given document record.

    If the document has ``storage_type == "local"`` we always use a local backend
    even when the platform is configured for GCS — this keeps legacy uploads
    readable while new ones go to GCS.
    """
    storage_type = (doc.get("storage_type") or "local").lower()
    if storage_type == "local":
        base_dir = os.environ.get("LOCAL_STORAGE_DIR", "/app/backend/uploads")
        return LocalStorageBackend(base_dir)
    return get_storage()
