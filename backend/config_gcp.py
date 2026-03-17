"""
GCP-specific configuration extension for DDYs Compliance Platform.

Extends the base Settings class with GCP service configuration.
Automatically detects whether running on GCP (Cloud Run) or locally.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings

from config import Settings


class GCPSettings(Settings):
    """Extended settings with GCP-specific configuration."""

    # --- GCP Core ---
    gcp_project_id: str = Field(default="", alias="GCP_PROJECT_ID")
    gcp_region: str = Field(default="europe-west6", alias="GCP_REGION")

    # --- Cloud Run detection ---
    k_service: str = Field(default="", alias="K_SERVICE")  # Set automatically by Cloud Run
    k_revision: str = Field(default="", alias="K_REVISION")
    k_configuration: str = Field(default="", alias="K_CONFIGURATION")

    # --- Storage ---
    gcs_bucket_prefix: str = Field(default="ddys", alias="GCS_BUCKET_PREFIX")
    gcs_default_bucket: Optional[str] = Field(default=None, alias="GCS_DEFAULT_BUCKET")
    gcs_per_tenant_buckets: bool = Field(default=False, alias="GCS_PER_TENANT_BUCKETS")

    # --- Feature Flags (GCP) ---
    feature_gcs_storage: bool = Field(default=False, alias="FEATURE_GCS_STORAGE")
    feature_secret_manager: bool = Field(default=False, alias="FEATURE_SECRET_MANAGER")
    feature_cloud_logging: bool = Field(default=False, alias="FEATURE_CLOUD_LOGGING")
    feature_cloud_monitoring: bool = Field(default=False, alias="FEATURE_CLOUD_MONITORING")
    feature_cloud_trace: bool = Field(default=False, alias="FEATURE_CLOUD_TRACE")
    feature_tenant_isolation: bool = Field(default=True, alias="FEATURE_TENANT_ISOLATION")

    @property
    def is_cloud_run(self) -> bool:
        """Detect if running on Google Cloud Run."""
        return bool(self.k_service)

    @property
    def use_gcs(self) -> bool:
        """Whether to use GCS for document storage."""
        return self.feature_gcs_storage or self.storage_type == "gcs"

    @property
    def use_secret_manager(self) -> bool:
        """Whether to load secrets from GCP Secret Manager."""
        return self.feature_secret_manager or self.is_cloud_run

    @property
    def use_cloud_logging(self) -> bool:
        """Whether to use structured Cloud Logging."""
        return self.feature_cloud_logging or self.is_cloud_run or self.log_format == "json"

    @property
    def use_cloud_monitoring(self) -> bool:
        """Whether to send custom metrics to Cloud Monitoring."""
        return self.feature_cloud_monitoring or (self.is_cloud_run and self.is_production)

    @property
    def storage_backend(self) -> str:
        """Determine which storage backend to use."""
        if self.use_gcs:
            return "gcs"
        if self.feature_s3_storage:
            return "s3"
        return "local"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_gcp_settings() -> GCPSettings:
    """Cached GCP settings instance."""
    return GCPSettings()


def initialize_gcp_services(settings: Optional[GCPSettings] = None):
    """
    Initialize all GCP services based on configuration.
    Call this at application startup.
    """
    if settings is None:
        settings = get_gcp_settings()

    initialized = []

    # 1. Set up structured logging first
    if settings.use_cloud_logging:
        from gcp.logging_config import setup_cloud_logging
        setup_cloud_logging(
            log_level=settings.log_level,
            log_format="json" if settings.use_cloud_logging else "text",
            service_name="ddys-compliance",
            environment=settings.environment,
        )
        initialized.append("Cloud Logging")

    # 2. Load secrets from Secret Manager
    if settings.use_secret_manager:
        from gcp.secrets import get_secret_manager
        sm = get_secret_manager()
        secrets = sm.load_all_app_secrets(settings.environment)
        # Inject secrets into environment (for downstream use)
        for key, value in secrets.items():
            if key not in os.environ:
                os.environ[key] = value
        initialized.append("Secret Manager")

    # 3. Initialize GCS storage
    if settings.use_gcs:
        from gcp.storage import get_gcs_storage
        get_gcs_storage()  # Initialize singleton
        initialized.append("GCS Storage")

    # 4. Initialize Cloud Monitoring
    if settings.use_cloud_monitoring:
        from gcp.monitoring import get_monitoring
        get_monitoring()  # Initialize singleton
        initialized.append("Cloud Monitoring")

    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        "GCP services initialized: %s (Cloud Run: %s, Environment: %s)",
        ", ".join(initialized) if initialized else "none",
        settings.is_cloud_run,
        settings.environment,
    )

    return initialized
