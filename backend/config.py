"""Centralized configuration with validation using Pydantic Settings."""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # MongoDB
    mongo_url: str = Field(default="mongodb://localhost:27017", alias="MONGO_URL")
    db_name: str = Field(default="ddys_compliance", alias="DB_NAME")

    # JWT
    jwt_secret: str = Field(..., alias="JWT_SECRET", min_length=32)
    jwt_expiry_hours: int = Field(default=12, alias="JWT_EXPIRY_HOURS")

    # MFA
    mfa_issuer: str = Field(default="DDYs Compliance", alias="MFA_ISSUER")

    # CORS
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # LLM
    emergent_llm_key: Optional[str] = Field(default=None, alias="EMERGENT_LLM_KEY")
    llm_provider: str = Field(default="emergent", alias="LLM_PROVIDER")
    llm_model: str = Field(default="claude-sonnet-4-20250514", alias="LLM_MODEL")

    # Storage
    storage_type: str = Field(default="local", alias="STORAGE_TYPE")
    aws_access_key_id: Optional[str] = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_s3_bucket: Optional[str] = Field(default=None, alias="AWS_S3_BUCKET")
    aws_region: str = Field(default="eu-central-1", alias="AWS_REGION")

    # Rate Limiting
    rate_limit_default: str = Field(default="100/minute", alias="RATE_LIMIT_DEFAULT")
    rate_limit_auth: str = Field(default="10/minute", alias="RATE_LIMIT_AUTH")
    rate_limit_upload: str = Field(default="20/minute", alias="RATE_LIMIT_UPLOAD")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="text", alias="LOG_FORMAT")

    # Environment
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Feature Flags
    feature_video_ident: bool = Field(default=False, alias="FEATURE_VIDEO_IDENT")
    feature_real_screening: bool = Field(default=False, alias="FEATURE_REAL_SCREENING")
    feature_real_email: bool = Field(default=False, alias="FEATURE_REAL_EMAIL")
    feature_s3_storage: bool = Field(default=False, alias="FEATURE_S3_STORAGE")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
