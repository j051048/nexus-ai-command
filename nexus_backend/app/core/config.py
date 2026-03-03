"""
P1 Fix #43: Settings migrated to Pydantic BaseSettings.

Benefits:
- Type safety with automatic validation
- Automatic .env file loading
- Clear field documentation
- Validation errors on startup (fail fast)
"""

import logging
import sys

try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback: if pydantic-settings not installed, use pydantic v2 directly
    from pydantic import BaseModel as BaseSettings

from pydantic import Field, field_validator


class Settings(BaseSettings):
    """
    Application settings with automatic environment variable loading.

    Pydantic BaseSettings automatically reads from:
    1. Environment variables
    2. .env file (via model_config)
    3. Default values defined here
    """

    # Project metadata
    PROJECT_NAME: str = "Project Nexus Backend"
    VERSION: str = "1.0.0"

    # Environment detection
    ENV: str = Field(default="development", description="Environment name (development, production)")
    DEBUG: bool = Field(default=False, description="Enable debug mode")

    # CORS Configuration
    CORS_ORIGINS: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:8080",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8080",
            "https://nexus-ai-command.vercel.app",
            "https://nexus-ai-command.zeabur.app",
            "https://aizhz.zeabur.app",
            "https://aizk.flydao.top",
        ],
        description="Allowed CORS origins",
    )
    ADDITIONAL_ALLOWED_ORIGINS: str | None = Field(default=None, description="Comma-separated additional CORS origins")

    # --- Rule Engine Thresholds ---
    APPROVAL_PURCHASE_AUTO_LIMIT: float = 15000.0
    APPROVAL_PURCHASE_OVERRUN_TOLERANCE: float = 0.10  # 10%
    APPROVAL_TRAVEL_DAILY_LIMIT: float = 2000.0
    APPROVAL_EXPENSE_SMALL_LIMIT: float = 500.0

    SCORE_DAILY_UPDATE_THRESHOLD: int = 3
    SCORE_DAILY_UPDATE_BONUS: float = 20.0
    SCORE_AI_QUALITY_THRESHOLD: float = 80.0
    SCORE_AI_QUALITY_BONUS: float = 30.0
    SCORE_DEAL_POINTS_PER_1000: float = 5.0

    # AI Configuration
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key (or compatible provider)")
    AI_BASE_URL: str = Field(
        default="https://api.apiyi.com/v1",
        description="Base URL for OpenAI-compatible API",
    )
    AI_DEFAULT_MODEL: str = Field(default="gpt-4o", description="Default AI model for general tasks")
    AI_MINI_MODEL: str = Field(default="gpt-4o-mini", description="Lightweight model for simple queries")

    # Brave Search (联网搜索)
    BRAVE_SEARCH_API_KEY: str = Field(default="", description="Brave Search API key for web search tool")

    # APISpace 招投标数据
    APISPACE_BIDDING_TOKEN: str = Field(default="", description="APISpace bidding data API token")

    # Database (read by database.py via os.getenv, declared here for validation)
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_SERVICE_KEY: str = Field(default="", description="Supabase service role key")
    SUPABASE_JWT_SECRET: str | None = Field(default=None, description="JWT secret for token verification")
    JWT_SECRET: str | None = Field(default=None, description="Alternative JWT secret key")

    # Redis
    REDIS_URL: str | None = Field(default=None, description="Redis connection URL")

    # Observability
    SENTRY_DSN: str = Field(default="", description="Sentry DSN for error tracking")

    # Langfuse (LLM Observability)
    LANGFUSE_ENABLED: bool = Field(default=False, description="Enable Langfuse LLM tracing")
    LANGFUSE_PUBLIC_KEY: str = Field(default="", description="Langfuse public key")
    LANGFUSE_SECRET_KEY: str = Field(default="", description="Langfuse secret key")
    LANGFUSE_HOST: str = Field(default="https://cloud.langfuse.com", description="Langfuse host URL")

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="API rate limit per minute")
    RATE_LIMIT_BURST: int = Field(default=10, description="Rate limit burst size")

    # File upload
    MAX_FILE_SIZE_MB: int = Field(default=50, description="Maximum file upload size in MB")
    MAX_CHAT_HISTORY: int = Field(default=10, description="Maximum chat message history window size")
    ALLOWED_FILE_TYPES: list[str] = Field(
        default=[
            ".pdf",
            ".docx",
            ".txt",
            ".md",
            ".csv",
            ".json",
            ".png",
            ".jpg",
            ".jpeg",
        ],
        description="Allowed file upload extensions",
    )

    # RAG Configuration
    RAG_CHUNK_SIZE: int = Field(default=600, description="Document chunk size for RAG embedding")
    RAG_CHUNK_OVERLAP: int = Field(default=100, description="Document chunk overlap for RAG embedding")
    RAG_PARENT_CHUNK_SIZE: int = Field(default=1800, description="Parent chunk size for parent-document retriever")

    # Reranker Configuration
    RERANK_MAX_DOCS: int = Field(default=8, description="Maximum documents to send to LLM reranker")
    RERANK_TIMEOUT: int = Field(default=8, description="Timeout in seconds for reranker LLM call")

    # LangGraph Agent Configuration
    LANGGRAPH_MAX_ITERATIONS: int = Field(default=5, description="Maximum plan-execute-reflect loop iterations")
    LANGGRAPH_TOOL_TIMEOUT: int = Field(default=30, description="Timeout in seconds for individual tool execution")
    LANGGRAPH_GATHER_TIMEOUT: int = Field(default=60, description="Timeout in seconds for parallel tool gather")
    LANGGRAPH_ENABLE_RAG_INJECT: bool = Field(default=True, description="Auto-inject RAG context into agent messages")
    LANGGRAPH_RAG_INJECT_THRESHOLD: float = Field(
        default=0.5, description="Minimum similarity threshold for RAG auto-injection"
    )
    LANGGRAPH_RAG_INJECT_LIMIT: int = Field(default=3, description="Max number of RAG chunks to auto-inject")
    LANGGRAPH_REFLECT_USE_LLM: bool = Field(
        default=True, description="Use LLM for grounded hallucination detection in reflect node"
    )
    LANGGRAPH_CHECKPOINTER: str = Field(default="memory", description="Checkpointer backend: 'memory' or 'postgres'")
    SEMANTIC_CACHE_THRESHOLD: float = Field(default=0.95, description="Similarity threshold for semantic cache hits")

    # Security
    # P1 Fix #42: Key for encryption
    ENCRYPTION_KEY: str = Field(default="", description="Master key for encrypting API keys")

    # Observability (OpenTelemetry)
    OTEL_ENABLED: bool = Field(default=False, description="Enable OpenTelemetry distributed tracing")
    OTEL_EXPORTER_ENDPOINT: str = Field(
        default="", description="OTLP exporter gRPC endpoint (e.g. http://localhost:4317)"
    )

    # B2: Notification Channel Configuration
    # Email (SMTP)
    SMTP_HOST: str | None = Field(default=None, description="SMTP server hostname")
    SMTP_PORT: int = Field(default=587, description="SMTP server port (587 for STARTTLS, 465 for SSL)")
    SMTP_USER: str | None = Field(default=None, description="SMTP username")
    SMTP_PASSWORD: str | None = Field(default=None, description="SMTP password")
    SMTP_FROM: str | None = Field(default=None, description="Sender email address")

    # Wecom (企业微信) - Webhook
    WECOM_WEBHOOK_URL: str | None = Field(default=None, description="Wecom group bot webhook URL")
    # Wecom (企业微信) - 深度集成
    WECOM_CORP_ID: str = Field(default="", description="企业微信 Corp ID")
    WECOM_CORP_SECRET: str = Field(default="", description="企业微信 Corp Secret (应用 Secret)")
    WECOM_AGENT_ID: str = Field(default="", description="企业微信 Agent ID (应用 AgentId)")

    # Dingtalk (钉钉) - Webhook
    DINGTALK_WEBHOOK_URL: str | None = Field(default=None, description="Dingtalk group bot webhook URL")
    DINGTALK_SECRET: str | None = Field(default=None, description="Dingtalk webhook secret for signature")
    # Dingtalk (钉钉) - 深度集成
    DINGTALK_APP_KEY: str = Field(default="", description="钉钉 App Key")
    DINGTALK_APP_SECRET: str = Field(default="", description="钉钉 App Secret")
    DINGTALK_AGENT_ID: str = Field(default="", description="钉钉 Agent ID (应用 agentId)")

    # Feishu (飞书) - Webhook
    FEISHU_WEBHOOK_URL: str | None = Field(default=None, description="Feishu group bot webhook URL")
    # Feishu (飞书) - 深度集成
    FEISHU_APP_ID: str = Field(default="", description="飞书 App ID")
    FEISHU_APP_SECRET: str = Field(default="", description="飞书 App Secret")
    FEISHU_ENCRYPT_KEY: str = Field(default="", description="飞书事件订阅 Encrypt Key（签名验证）")

    # Web Push VAPID
    VAPID_PUBLIC_KEY: str = Field(default="", description="VAPID public key for Web Push")
    VAPID_PRIVATE_KEY: str = Field(default="", description="VAPID private key for Web Push")

    # Computed properties
    @property
    def IS_PRODUCTION(self) -> bool:  # noqa: N802
        return self.ENV in ("production", "prod")

    @property
    def all_cors_origins(self) -> list[str]:
        """Get all CORS origins including additional ones from env"""
        origins = list(self.CORS_ORIGINS)
        if self.ADDITIONAL_ALLOWED_ORIGINS:
            extras = [o.strip() for o in self.ADDITIONAL_ALLOWED_ORIGINS.split(",") if o.strip()]
            origins.extend(extras)
        return origins

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        """Parse DEBUG from string env var"""
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Handle CORS_ORIGINS as comma-separated string from env"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    def validate_production_config(self) -> list[str]:
        """Validate critical configuration for production"""
        errors = []

        if self.IS_PRODUCTION:
            if not self.OPENAI_API_KEY:
                errors.append("OPENAI_API_KEY is required in production")

            if not self.SUPABASE_URL:
                errors.append("SUPABASE_URL is required in production")

            if not self.SUPABASE_SERVICE_KEY:
                errors.append("SUPABASE_SERVICE_KEY is required in production")

            if not self.SUPABASE_JWT_SECRET and not self.JWT_SECRET:
                errors.append("JWT secret (SUPABASE_JWT_SECRET or JWT_SECRET) is required in production")

            if self.DEBUG:
                errors.append("DEBUG mode must be disabled in production")

            if not self.ENCRYPTION_KEY or self.ENCRYPTION_KEY == "":
                errors.append("ENCRYPTION_KEY is required in production")

        return errors

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",  # Ignore extra env vars not defined here
    }


settings = Settings()

# Validate configuration on startup
_logger = logging.getLogger(__name__)
_config_errors = settings.validate_production_config()
if _config_errors:
    for error in _config_errors:
        _logger.critical(f"CONFIG ERROR: {error}")
    if settings.IS_PRODUCTION:
        sys.exit(1)  # Fail fast in production
    else:
        _logger.warning("Running in development mode with configuration warnings")

# S-3 Fix: Warn when Redis is not configured in production
if settings.IS_PRODUCTION and not settings.REDIS_URL:
    _logger.warning(
        "REDIS_URL is not configured. Rate limiting and caching will use "
        "in-memory fallback which does not share state across workers."
    )
