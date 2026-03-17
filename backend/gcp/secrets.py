"""
GCP Secret Manager Integration.

Loads secrets from Google Cloud Secret Manager with caching and fallback to
environment variables for local development.
"""

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Cache TTL: 5 minutes
SECRET_CACHE_TTL_SECONDS = 300


class SecretManagerService:
    """
    Service for loading secrets from GCP Secret Manager.
    Falls back to environment variables when running locally.
    """

    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID", "")
        self._cache: dict[str, tuple[str, float]] = {}  # secret_id -> (value, expiry_ts)
        self._client = None
        self._gcp_available = False

        if self.project_id:
            try:
                from google.cloud import secretmanager
                self._client = secretmanager.SecretManagerServiceClient()
                self._gcp_available = True
                logger.info("Secret Manager client initialized for project '%s'", self.project_id)
            except ImportError:
                logger.warning(
                    "google-cloud-secret-manager not installed. "
                    "Falling back to environment variables."
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize Secret Manager client: %s. "
                    "Falling back to environment variables.",
                    str(e),
                )
        else:
            logger.info("No GCP_PROJECT_ID set. Using environment variables for secrets.")

    def get_secret(
        self,
        secret_id: str,
        version: str = "latest",
        env_var_fallback: Optional[str] = None,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get a secret value from Secret Manager with caching.

        Args:
            secret_id: The secret ID in Secret Manager.
            version: Secret version (default "latest").
            env_var_fallback: Environment variable name to use as fallback.
            default: Default value if secret is not found anywhere.

        Returns:
            The secret value, or default if not found.
        """
        # Check cache first
        cache_key = f"{secret_id}:{version}"
        if cache_key in self._cache:
            value, expiry = self._cache[cache_key]
            if time.time() < expiry:
                return value
            else:
                del self._cache[cache_key]

        # Try Secret Manager
        if self._gcp_available and self._client:
            try:
                resource_name = (
                    f"projects/{self.project_id}/secrets/{secret_id}/versions/{version}"
                )
                response = self._client.access_secret_version(
                    request={"name": resource_name}
                )
                value = response.payload.data.decode("UTF-8")

                # Cache the result
                self._cache[cache_key] = (value, time.time() + SECRET_CACHE_TTL_SECONDS)
                logger.debug("Secret '%s' loaded from Secret Manager", secret_id)
                return value

            except Exception as e:
                logger.warning(
                    "Failed to load secret '%s' from Secret Manager: %s",
                    secret_id,
                    str(e),
                )

        # Fallback to environment variable
        if env_var_fallback:
            value = os.environ.get(env_var_fallback)
            if value:
                logger.debug(
                    "Secret '%s' loaded from env var '%s'", secret_id, env_var_fallback
                )
                return value

        # Fallback to default
        if default is not None:
            logger.debug("Secret '%s' using default value", secret_id)
            return default

        logger.warning("Secret '%s' not found in any source", secret_id)
        return None

    def get_secret_or_raise(
        self,
        secret_id: str,
        version: str = "latest",
        env_var_fallback: Optional[str] = None,
    ) -> str:
        """Get a secret value, raising ValueError if not found."""
        value = self.get_secret(secret_id, version, env_var_fallback)
        if value is None:
            raise ValueError(
                f"Required secret '{secret_id}' not found in Secret Manager "
                f"or environment variable '{env_var_fallback}'"
            )
        return value

    def invalidate_cache(self, secret_id: Optional[str] = None):
        """Invalidate cached secrets. If secret_id is None, clears all."""
        if secret_id:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{secret_id}:")]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()

    def load_all_app_secrets(self, environment: str) -> dict[str, str]:
        """
        Load all application secrets for the given environment.

        Returns a dict mapping logical name -> secret value.
        """
        prefix = f"ddys-{environment}"
        secret_map = {
            "JWT_SECRET": (f"{prefix}-jwt-secret", "JWT_SECRET"),
            "MONGO_URL": (f"{prefix}-mongo-url", "MONGO_URL"),
            "EMERGENT_LLM_KEY": (f"{prefix}-emergent-llm-key", "EMERGENT_LLM_KEY"),
        }

        results = {}
        for logical_name, (secret_id, env_var) in secret_map.items():
            value = self.get_secret(
                secret_id=secret_id,
                env_var_fallback=env_var,
            )
            if value:
                results[logical_name] = value
            else:
                logger.warning("Secret '%s' (%s) not available", logical_name, secret_id)

        return results


# --- Singleton ---

_secret_manager: Optional[SecretManagerService] = None


def get_secret_manager() -> SecretManagerService:
    """Get or create singleton SecretManagerService."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManagerService()
    return _secret_manager
