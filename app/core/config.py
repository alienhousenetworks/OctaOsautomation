from typing import List, Optional, Union, Any
from pydantic import validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "OctaOS"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEV: bool = True

    # SECURITY — never ship production with default SECRET_KEY
    SECRET_KEY: str = "dev-only-insecure-secret-key-change-me"
    ENCRYPTION_KEY: Optional[str] = None  # optional dedicated Fernet key
    # Access JWT lifetime. Frontend also supports refresh tokens for longer sessions.
    # 7 days avoids mass 403s when users reopen the app after a few days without refresh handling.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    MFA_REQUIRED: bool = False

    # CORS — comma-separated origins; empty/"*" only allowed in DEV
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # POSTGRES
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "octaos"
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: dict) -> Any:
        if isinstance(v, str):
            return v
        return (
            f"postgresql://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}"
            f"@{values.get('POSTGRES_SERVER')}/{values.get('POSTGRES_DB')}"
        )

    # REDIS
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # LLM KEYS
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # PILOT CONFIG
    SHARED_CLAUDE_KEY: Optional[str] = None
    PILOT_BUDGET_LIMIT: float = 7000.0  # in INR

    # Product feature flags (user-facing)
    ENABLE_IN_APP_VIDEO: bool = False  # hide Video Studio + campaign video gen until ready
    # High global API rate limits (per tenant+IP+path / minute) for exploration
    TENANT_API_RATE_LIMIT_PER_MINUTE: int = 300

    # PUBLIC MEDIA
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    MEDIA_UPLOAD_DIR: str = "uploads"

    # OAUTH — Meta
    META_APP_ID: Optional[str] = None
    META_APP_SECRET: Optional[str] = None

    # OAUTH — LinkedIn
    LINKEDIN_CLIENT_ID: Optional[str] = None
    LINKEDIN_CLIENT_SECRET: Optional[str] = None

    # OPTIONAL
    PINTEREST_ACCESS_TOKEN: Optional[str] = None

    # Stripe (optional / legacy)
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRICE_STARTER: Optional[str] = None
    STRIPE_PRICE_GROWTH: Optional[str] = None
    STRIPE_PRICE_BUSINESS: Optional[str] = None

    # Razorpay (primary payments — India)
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    # Currency for checkout: INR recommended for Razorpay
    RAZORPAY_CURRENCY: str = "INR"
    # If true, /billing/plan requires a paid Razorpay receipt (admins can still force)
    RAZORPAY_REQUIRE_PAYMENT: bool = False

    # SSO (OIDC) optional
    OIDC_CLIENT_ID: Optional[str] = None
    OIDC_CLIENT_SECRET: Optional[str] = None
    OIDC_DISCOVERY_URL: Optional[str] = None
    OIDC_REDIRECT_URI: Optional[str] = None

    # Metrics auth
    METRICS_TOKEN: Optional[str] = None

    # Webhook email HMAC default (per-tenant preferred)
    EMAIL_WEBHOOK_HMAC_SECRET: Optional[str] = None

    # SMTP & DEV SETTINGS
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None

    EMAIL_HOST: Optional[str] = None
    EMAIL_PORT: Optional[int] = None
    EMAIL_USE_TLS: bool = True
    EMAIL_HOST_USER: Optional[str] = None
    EMAIL_HOST_PASSWORD: Optional[str] = None
    DEFAULT_FROM_EMAIL: Optional[str] = None

    def cors_origin_list(self) -> List[str]:
        raw = (self.CORS_ORIGINS or "").strip()
        if not raw or raw == "*":
            if self.DEV or self.ENVIRONMENT in ("development", "dev", "local", "test"):
                return ["*"]
            return ["http://localhost:3000"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    def __init__(self, **values: Any):
        super().__init__(**values)
        if self.EMAIL_HOST is not None:
            self.SMTP_HOST = self.EMAIL_HOST
        if self.EMAIL_PORT is not None:
            self.SMTP_PORT = self.EMAIL_PORT
        if self.EMAIL_HOST_USER is not None:
            self.SMTP_USER = self.EMAIL_HOST_USER
        if self.EMAIL_HOST_PASSWORD is not None:
            self.SMTP_PASSWORD = self.EMAIL_HOST_PASSWORD
        if self.DEFAULT_FROM_EMAIL is not None:
            self.SMTP_FROM = self.DEFAULT_FROM_EMAIL
        elif self.EMAIL_HOST_USER is not None:
            self.SMTP_FROM = self.EMAIL_HOST_USER

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
