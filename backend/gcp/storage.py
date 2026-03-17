"""
GCS Document Storage Service - Multi-tenant document management on Google Cloud Storage.

Provides upload, download, delete, and signed URL generation with strict tenant isolation.
Each tenant's documents are stored under a tenant-specific prefix within the shared bucket,
or optionally in a dedicated per-tenant bucket.

Swiss data residency: All buckets MUST be in europe-west6 (Zurich).
"""

import hashlib
import logging
import mimetypes
import os
import uuid
from datetime import timedelta
from typing import Optional

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError, NotFound

logger = logging.getLogger(__name__)

# Maximum upload size: 20 MB
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

# Allowed MIME types for compliance documents
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
    "image/gif",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
    "application/zip",
    "application/json",
}


class GCSStorageService:
    """Google Cloud Storage service with multi-tenant isolation."""

    def __init__(
        self,
        project_id: str,
        bucket_prefix: str = "ddys",
        default_bucket: Optional[str] = None,
        use_per_tenant_buckets: bool = False,
        region: str = "europe-west6",
    ):
        """
        Initialize GCS storage service.

        Args:
            project_id: GCP project ID.
            bucket_prefix: Prefix for bucket names (e.g., "ddys-prod").
            default_bucket: Override default bucket name. If not set, uses "{bucket_prefix}-documents-*".
            use_per_tenant_buckets: If True, each tenant gets their own bucket.
            region: GCS bucket location (must be europe-west6 for Swiss data residency).
        """
        self.client = storage.Client(project=project_id)
        self.project_id = project_id
        self.bucket_prefix = bucket_prefix
        self.default_bucket_name = default_bucket
        self.use_per_tenant_buckets = use_per_tenant_buckets
        self.region = region
        self._bucket_cache: dict[str, storage.Bucket] = {}

        if region != "europe-west6":
            logger.warning(
                "GCS region is '%s', not europe-west6. This may violate Swiss data residency requirements!",
                region,
            )

    def _get_bucket(self, tenant_id: str) -> storage.Bucket:
        """Get the GCS bucket for a given tenant. Caches bucket references."""
        if self.use_per_tenant_buckets:
            bucket_name = f"{self.bucket_prefix}-{tenant_id}-documents"
        elif self.default_bucket_name:
            bucket_name = self.default_bucket_name
        else:
            # Find the shared documents bucket (created by Terraform with random suffix)
            bucket_name = self._find_shared_bucket()

        if bucket_name not in self._bucket_cache:
            bucket = self.client.bucket(bucket_name)
            if not bucket.exists():
                raise ValueError(
                    f"Bucket '{bucket_name}' does not exist. "
                    f"Ensure Terraform has been applied or run setup-tenant.sh."
                )
            self._bucket_cache[bucket_name] = bucket

        return self._bucket_cache[bucket_name]

    def _find_shared_bucket(self) -> str:
        """Find the shared documents bucket by prefix."""
        if hasattr(self, "_shared_bucket_name"):
            return self._shared_bucket_name

        prefix = f"{self.bucket_prefix}-documents-"
        for bucket in self.client.list_buckets(prefix=prefix, project=self.project_id):
            if bucket.location.upper() == self.region.upper().replace("-", "_"):
                self._shared_bucket_name = bucket.name
                return bucket.name

        # Fallback: use deterministic name
        self._shared_bucket_name = f"{self.bucket_prefix}-documents"
        return self._shared_bucket_name

    def _build_blob_path(self, tenant_id: str, case_id: str, filename: str) -> str:
        """
        Build the GCS object path with tenant isolation.

        Format: tenants/{tenant_id}/cases/{case_id}/{uuid}_{filename}
        """
        safe_filename = filename.replace("/", "_").replace("\\", "_")
        unique_name = f"{uuid.uuid4().hex[:12]}_{safe_filename}"
        return f"tenants/{tenant_id}/cases/{case_id}/{unique_name}"

    def _detect_content_type(self, filename: str, content: bytes) -> str:
        """Detect MIME type from filename, falling back to magic bytes."""
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            return mime_type

        # Check magic bytes for common formats
        if content[:4] == b"%PDF":
            return "application/pdf"
        if content[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if content[:2] == b"\xff\xd8":
            return "image/jpeg"
        if content[:4] in (b"PK\x03\x04", b"PK\x05\x06"):
            return "application/zip"

        return "application/octet-stream"

    async def upload_document(
        self,
        tenant_id: str,
        case_id: str,
        filename: str,
        content: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Upload a document to GCS with tenant isolation.

        Args:
            tenant_id: Tenant identifier for isolation.
            case_id: Case this document belongs to.
            filename: Original filename.
            content: File content bytes.
            content_type: MIME type (auto-detected if not provided).
            metadata: Additional metadata to store on the blob.

        Returns:
            dict with storage metadata (path, hash, size, etc.)

        Raises:
            ValueError: If file exceeds size limit or has disallowed type.
            GoogleCloudError: On GCS upload failure.
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for document upload")

        # Enforce file size limit
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File size {len(content)} bytes exceeds maximum of {MAX_FILE_SIZE_BYTES} bytes (20 MB)"
            )

        # Detect and validate content type
        if not content_type:
            content_type = self._detect_content_type(filename, content)

        if content_type not in ALLOWED_MIME_TYPES:
            logger.warning(
                "Upload attempted with disallowed MIME type '%s' by tenant '%s'",
                content_type,
                tenant_id,
            )
            raise ValueError(
                f"File type '{content_type}' is not allowed. "
                f"Allowed types: PDF, images, Office documents, text, CSV, ZIP."
            )

        # Compute file hash for integrity verification
        file_hash = hashlib.sha256(content).hexdigest()

        # Build storage path
        blob_path = self._build_blob_path(tenant_id, case_id, filename)

        try:
            bucket = self._get_bucket(tenant_id)
            blob = bucket.blob(blob_path)

            # Set metadata
            blob_metadata = {
                "tenant_id": tenant_id,
                "case_id": case_id,
                "original_filename": filename,
                "file_hash_sha256": file_hash,
                "uploaded_by": "ddys-compliance-platform",
            }
            if metadata:
                blob_metadata.update(metadata)
            blob.metadata = blob_metadata

            # Upload with content type
            blob.upload_from_string(content, content_type=content_type)

            logger.info(
                "Document uploaded: bucket=%s path=%s tenant=%s case=%s size=%d hash=%s",
                bucket.name,
                blob_path,
                tenant_id,
                case_id,
                len(content),
                file_hash[:16],
            )

            return {
                "storage_type": "gcs",
                "bucket": bucket.name,
                "blob_path": blob_path,
                "gcs_uri": f"gs://{bucket.name}/{blob_path}",
                "file_hash": file_hash,
                "file_size": len(content),
                "content_type": content_type,
                "original_filename": filename,
            }

        except GoogleCloudError as e:
            logger.error(
                "GCS upload failed: tenant=%s case=%s error=%s",
                tenant_id,
                case_id,
                str(e),
            )
            raise

    async def download_document(
        self, tenant_id: str, blob_path: str
    ) -> tuple[bytes, str]:
        """
        Download a document from GCS with tenant isolation check.

        Args:
            tenant_id: Tenant requesting the download (for isolation verification).
            blob_path: GCS blob path.

        Returns:
            Tuple of (content_bytes, content_type).

        Raises:
            PermissionError: If tenant tries to access another tenant's document.
            NotFound: If document doesn't exist.
        """
        # Verify tenant isolation
        if not blob_path.startswith(f"tenants/{tenant_id}/"):
            logger.error(
                "Cross-tenant access attempt: tenant '%s' tried to access '%s'",
                tenant_id,
                blob_path,
            )
            raise PermissionError(
                f"Access denied: document does not belong to tenant '{tenant_id}'"
            )

        try:
            bucket = self._get_bucket(tenant_id)
            blob = bucket.blob(blob_path)

            if not blob.exists():
                raise NotFound(f"Document not found: {blob_path}")

            content = blob.download_as_bytes()
            content_type = blob.content_type or "application/octet-stream"

            logger.info(
                "Document downloaded: tenant=%s path=%s size=%d",
                tenant_id,
                blob_path,
                len(content),
            )

            return content, content_type

        except GoogleCloudError as e:
            logger.error(
                "GCS download failed: tenant=%s path=%s error=%s",
                tenant_id,
                blob_path,
                str(e),
            )
            raise

    async def delete_document(self, tenant_id: str, blob_path: str) -> bool:
        """
        Delete a document from GCS with tenant isolation check.

        Returns True if deleted, False if not found.
        """
        if not blob_path.startswith(f"tenants/{tenant_id}/"):
            logger.error(
                "Cross-tenant delete attempt: tenant '%s' tried to delete '%s'",
                tenant_id,
                blob_path,
            )
            raise PermissionError(
                f"Access denied: document does not belong to tenant '{tenant_id}'"
            )

        try:
            bucket = self._get_bucket(tenant_id)
            blob = bucket.blob(blob_path)

            if not blob.exists():
                return False

            blob.delete()
            logger.info(
                "Document deleted: tenant=%s path=%s", tenant_id, blob_path
            )
            return True

        except NotFound:
            return False
        except GoogleCloudError as e:
            logger.error(
                "GCS delete failed: tenant=%s path=%s error=%s",
                tenant_id,
                blob_path,
                str(e),
            )
            raise

    async def generate_signed_url(
        self,
        tenant_id: str,
        blob_path: str,
        expiration_minutes: int = 15,
        method: str = "GET",
        content_type: Optional[str] = None,
    ) -> str:
        """
        Generate a signed URL for secure, time-limited access to a document.

        Args:
            tenant_id: Tenant for isolation verification.
            blob_path: GCS blob path.
            expiration_minutes: URL validity in minutes (default 15).
            method: HTTP method (GET for download, PUT for upload).
            content_type: Required content type for PUT URLs.

        Returns:
            Signed URL string.
        """
        if not blob_path.startswith(f"tenants/{tenant_id}/"):
            logger.error(
                "Cross-tenant signed URL attempt: tenant '%s' for path '%s'",
                tenant_id,
                blob_path,
            )
            raise PermissionError(
                f"Access denied: document does not belong to tenant '{tenant_id}'"
            )

        bucket = self._get_bucket(tenant_id)
        blob = bucket.blob(blob_path)

        kwargs = {
            "expiration": timedelta(minutes=expiration_minutes),
            "method": method,
            "version": "v4",
        }

        if method == "PUT" and content_type:
            kwargs["content_type"] = content_type

        url = blob.generate_signed_url(**kwargs)

        logger.info(
            "Signed URL generated: tenant=%s path=%s method=%s expires=%dm",
            tenant_id,
            blob_path,
            method,
            expiration_minutes,
        )

        return url

    async def generate_upload_signed_url(
        self,
        tenant_id: str,
        case_id: str,
        filename: str,
        content_type: str,
        expiration_minutes: int = 30,
    ) -> dict:
        """
        Generate a signed URL for direct browser-to-GCS upload.

        Returns:
            dict with signed_url, blob_path, and headers to include.
        """
        blob_path = self._build_blob_path(tenant_id, case_id, filename)

        if content_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"File type '{content_type}' is not allowed.")

        url = await self.generate_signed_url(
            tenant_id=tenant_id,
            blob_path=blob_path,
            expiration_minutes=expiration_minutes,
            method="PUT",
            content_type=content_type,
        )

        return {
            "signed_url": url,
            "blob_path": blob_path,
            "content_type": content_type,
            "method": "PUT",
            "expires_in_minutes": expiration_minutes,
            "headers": {
                "Content-Type": content_type,
            },
        }

    async def list_tenant_documents(
        self, tenant_id: str, case_id: Optional[str] = None, max_results: int = 500
    ) -> list[dict]:
        """List all documents for a tenant, optionally filtered by case."""
        prefix = f"tenants/{tenant_id}/"
        if case_id:
            prefix = f"tenants/{tenant_id}/cases/{case_id}/"

        bucket = self._get_bucket(tenant_id)
        blobs = bucket.list_blobs(prefix=prefix, max_results=max_results)

        documents = []
        for blob in blobs:
            documents.append(
                {
                    "blob_path": blob.name,
                    "size": blob.size,
                    "content_type": blob.content_type,
                    "created": blob.time_created.isoformat() if blob.time_created else None,
                    "updated": blob.updated.isoformat() if blob.updated else None,
                    "metadata": blob.metadata or {},
                }
            )

        return documents

    async def copy_document(
        self,
        source_tenant_id: str,
        source_blob_path: str,
        dest_tenant_id: str,
        dest_case_id: str,
        dest_filename: str,
    ) -> dict:
        """
        Copy a document between tenants or cases.
        Requires explicit authorization (not checked here - caller must verify).
        """
        source_bucket = self._get_bucket(source_tenant_id)
        dest_bucket = self._get_bucket(dest_tenant_id)

        source_blob = source_bucket.blob(source_blob_path)
        if not source_blob.exists():
            raise NotFound(f"Source document not found: {source_blob_path}")

        dest_blob_path = self._build_blob_path(dest_tenant_id, dest_case_id, dest_filename)
        dest_blob = dest_bucket.blob(dest_blob_path)

        source_bucket.copy_blob(source_blob, dest_bucket, dest_blob_path)

        logger.info(
            "Document copied: %s/%s -> %s/%s",
            source_bucket.name,
            source_blob_path,
            dest_bucket.name,
            dest_blob_path,
        )

        return {
            "storage_type": "gcs",
            "bucket": dest_bucket.name,
            "blob_path": dest_blob_path,
            "gcs_uri": f"gs://{dest_bucket.name}/{dest_blob_path}",
        }


# --- Factory ---

_storage_instance: Optional[GCSStorageService] = None


def get_gcs_storage() -> GCSStorageService:
    """Get or create a singleton GCS storage service instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = GCSStorageService(
            project_id=os.environ.get("GCP_PROJECT_ID", ""),
            bucket_prefix=os.environ.get("GCS_BUCKET_PREFIX", "ddys"),
            default_bucket=os.environ.get("GCS_DEFAULT_BUCKET", None),
            use_per_tenant_buckets=os.environ.get("GCS_PER_TENANT_BUCKETS", "false").lower() == "true",
            region=os.environ.get("GCP_REGION", "europe-west6"),
        )
    return _storage_instance
