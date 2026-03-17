"""
Cloud Monitoring Custom Metrics for DDYs Compliance Platform.

Tracks business-level metrics like cases created, documents processed,
screening results, and tenant-level activity.
"""

import logging
import os
import time
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class CloudMonitoringService:
    """
    Custom metrics reporting to Google Cloud Monitoring.

    Falls back to logging metrics when Cloud Monitoring client is unavailable
    (e.g., local development).
    """

    METRIC_PREFIX = "custom.googleapis.com/ddys"

    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID", "")
        self._client = None
        self._gcp_available = False

        if self.project_id:
            try:
                from google.cloud import monitoring_v3
                self._client = monitoring_v3.MetricServiceClient()
                self._project_name = f"projects/{self.project_id}"
                self._gcp_available = True
                logger.info("Cloud Monitoring client initialized for project '%s'", self.project_id)
            except ImportError:
                logger.info(
                    "google-cloud-monitoring not installed. Metrics will be logged only."
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize Cloud Monitoring client: %s. Metrics will be logged.",
                    str(e),
                )
        else:
            logger.info("No GCP_PROJECT_ID set. Metrics will be logged only.")

    def _write_time_series(
        self,
        metric_type: str,
        value: float,
        labels: dict[str, str],
        value_type: str = "int64",
    ):
        """Write a single time series data point to Cloud Monitoring."""
        if not self._gcp_available:
            logger.info(
                "METRIC: %s = %s | labels=%s",
                metric_type,
                value,
                labels,
            )
            return

        try:
            from google.api import metric_pb2, monitored_resource_pb2
            from google.cloud.monitoring_v3 import types
            from google.protobuf import timestamp_pb2

            now = time.time()
            seconds = int(now)
            nanos = int((now - seconds) * 10**9)

            interval = types.TimeInterval(
                end_time=timestamp_pb2.Timestamp(seconds=seconds, nanos=nanos),
            )

            if value_type == "int64":
                point_value = types.TypedValue(int64_value=int(value))
            else:
                point_value = types.TypedValue(double_value=float(value))

            point = types.Point(interval=interval, value=point_value)

            series = types.TimeSeries(
                metric=metric_pb2.Metric(
                    type=f"{self.METRIC_PREFIX}/{metric_type}",
                    labels=labels,
                ),
                resource=monitored_resource_pb2.MonitoredResource(
                    type="cloud_run_revision",
                    labels={
                        "project_id": self.project_id,
                        "service_name": os.environ.get("K_SERVICE", "ddys-backend"),
                        "revision_name": os.environ.get("K_REVISION", "local"),
                        "location": os.environ.get("GCP_REGION", "europe-west6"),
                        "configuration_name": "",
                    },
                ),
                points=[point],
            )

            self._client.create_time_series(
                request={
                    "name": self._project_name,
                    "time_series": [series],
                }
            )

        except Exception as e:
            logger.warning("Failed to write metric %s: %s", metric_type, str(e))

    # --- Business Metrics ---

    def record_case_created(self, tenant_id: str, case_type: str = "kyc"):
        """Record a new case creation."""
        self._write_time_series(
            "cases/created",
            1,
            {"tenant_id": tenant_id, "case_type": case_type},
        )

    def record_case_completed(self, tenant_id: str, case_type: str = "kyc"):
        """Record a case completion."""
        self._write_time_series(
            "cases/completed",
            1,
            {"tenant_id": tenant_id, "case_type": case_type},
        )

    def record_document_uploaded(self, tenant_id: str, doc_type: str, size_bytes: int):
        """Record a document upload."""
        self._write_time_series(
            "documents/uploaded",
            1,
            {"tenant_id": tenant_id, "doc_type": doc_type},
        )
        self._write_time_series(
            "documents/upload_size_bytes",
            size_bytes,
            {"tenant_id": tenant_id},
            value_type="int64",
        )

    def record_document_processed(
        self, tenant_id: str, doc_type: str, ai_decision: str
    ):
        """Record AI document processing result."""
        self._write_time_series(
            "documents/processed",
            1,
            {
                "tenant_id": tenant_id,
                "doc_type": doc_type,
                "ai_decision": ai_decision,
            },
        )

    def record_screening_result(
        self, tenant_id: str, screening_type: str, result: str
    ):
        """Record a screening result (sanctions, PEP, etc.)."""
        self._write_time_series(
            "screening/results",
            1,
            {
                "tenant_id": tenant_id,
                "screening_type": screening_type,
                "result": result,
            },
        )

    def record_auth_event(self, event_type: str, success: bool, tenant_id: str = ""):
        """Record authentication events (login, mfa, token_refresh)."""
        self._write_time_series(
            "auth/events",
            1,
            {
                "event_type": event_type,
                "success": str(success).lower(),
                "tenant_id": tenant_id,
            },
        )

    def record_api_error(self, endpoint: str, status_code: int, tenant_id: str = ""):
        """Record API errors."""
        self._write_time_series(
            "api/errors",
            1,
            {
                "endpoint": endpoint,
                "status_code": str(status_code),
                "tenant_id": tenant_id,
            },
        )

    @contextmanager
    def measure_latency(self, operation: str, tenant_id: str = ""):
        """
        Context manager to measure and record operation latency.

        Usage:
            with monitoring.measure_latency("document_analysis", tenant_id="t-123"):
                result = await analyze_document(...)
        """
        start = time.monotonic()
        try:
            yield
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            self._write_time_series(
                "operations/latency_ms",
                duration_ms,
                {"operation": operation, "tenant_id": tenant_id},
                value_type="double",
            )

    def record_tenant_activity(self, tenant_id: str, active_users: int):
        """Record tenant-level activity metrics."""
        self._write_time_series(
            "tenants/active_users",
            active_users,
            {"tenant_id": tenant_id},
        )

    def record_cross_tenant_access_attempt(
        self, requesting_tenant: str, target_tenant: str, resource_type: str
    ):
        """Record cross-tenant access attempts (security metric)."""
        self._write_time_series(
            "security/cross_tenant_attempts",
            1,
            {
                "requesting_tenant": requesting_tenant,
                "target_tenant": target_tenant,
                "resource_type": resource_type,
            },
        )
        logger.error(
            "SECURITY: Cross-tenant access attempt: %s tried to access %s resource of %s",
            requesting_tenant,
            resource_type,
            target_tenant,
        )


# --- Singleton ---

_monitoring: Optional[CloudMonitoringService] = None


def get_monitoring() -> CloudMonitoringService:
    """Get or create singleton CloudMonitoringService."""
    global _monitoring
    if _monitoring is None:
        _monitoring = CloudMonitoringService()
    return _monitoring
