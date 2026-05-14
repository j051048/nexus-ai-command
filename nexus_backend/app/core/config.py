"""
P1 Fix #43: Settings migrated to Pydantic BaseSettings.

Benefits:
- Type safety with automatic validation
- Automatic .env file loading
- Clear field documentation
- Validation errors on startup (fail fast)
"""

import logging
import os
import sys
from pathlib import Path

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
    ENV: str = Field(
        default="development", description="Environment name (development, production)"
    )
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
    ADDITIONAL_ALLOWED_ORIGINS: str | None = Field(
        default=None, description="Comma-separated additional CORS origins"
    )

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
    OPENAI_API_KEY: str = Field(
        default="", description="OpenAI API key (or compatible provider)"
    )
    AI_BASE_URL: str = Field(
        default="https://api.apiyi.com/v1",
        description="Base URL for OpenAI-compatible API",
    )
    AI_DEFAULT_MODEL: str = Field(
        default="gemini-3-flash-preview",
        description="Default AI model for general tasks",
    )
    AI_MINI_MODEL: str = Field(
        default="gemini-3-flash-preview",
        description="Lightweight model for simple queries",
    )
    AI_STRONG_MODEL: str = Field(
        default="gemini-3-flash-preview",
        description="Strong model for complex/flagship tasks. When user's saved model is weak (mini/flash/turbo), "
        "power/flagship tier auto-upgrades to this. Falls back to AI_DEFAULT_MODEL if empty.",
    )

    # AI Fallback (备用 AI 服务，主服务欠费/不可用时自动切换)
    AI_FALLBACK_API_KEY: str = Field(
        default="", description="Fallback AI provider API key"
    )
    AI_FALLBACK_BASE_URL: str = Field(
        default="", description="Fallback AI provider base URL"
    )

    # Brave Search (联网搜索)
    BRAVE_SEARCH_API_KEY: str = Field(
        default="", description="Brave Search API key for web search tool"
    )

    # APISpace 招投标数据
    APISPACE_BIDDING_TOKEN: str = Field(
        default="", description="APISpace bidding data API token"
    )

    # Database (read by database.py via os.getenv, declared here for validation)
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_SERVICE_KEY: str = Field(
        default="", description="Supabase service role key"
    )
    SUPABASE_JWT_SECRET: str | None = Field(
        default=None, description="JWT secret for token verification"
    )
    JWT_SECRET: str | None = Field(
        default=None, description="Alternative JWT secret key"
    )

    # Redis
    REDIS_URL: str | None = Field(default=None, description="Redis connection URL")
    # P1: Redis 高可用配置
    REDIS_SENTINEL_HOSTS: str = Field(
        default="",
        description="Redis Sentinel hosts, comma-separated (e.g. 'sentinel1:26379,sentinel2:26379,sentinel3:26379'). Empty = not using Sentinel.",
    )
    REDIS_SENTINEL_MASTER: str = Field(
        default="mymaster", description="Redis Sentinel master name (default: mymaster)"
    )
    REDIS_CLUSTER_HOSTS: str = Field(
        default="",
        description="Redis Cluster hosts, comma-separated (e.g. 'node1:6379,node2:6379,node3:6379'). Empty = not using Cluster.",
    )
    CELERY_MONITORED_QUEUES: str = Field(
        default="default,agent_tools,agent_tools_high_risk,webhooks,sensors",
        description="Comma-separated Celery queue names monitored for backlog alerts.",
    )
    CELERY_QUEUE_DEPTH_WARNING: int = Field(
        default=100,
        description="Queue depth that should raise a warning in deployment health.",
    )
    CELERY_QUEUE_DEPTH_CRITICAL: int = Field(
        default=1000,
        description="Queue depth that marks deployment health as not ready.",
    )
    IDEMPOTENCY_TTL_SECONDS: int = Field(
        default=86400,
        description="Distributed idempotency response cache TTL in seconds.",
    )
    IDEMPOTENCY_MEMORY_FALLBACK_MAX: int = Field(
        default=1000,
        description="Max process-local idempotency fallback entries if Redis is unavailable.",
    )
    IDEMPOTENCY_MEMORY_FALLBACK_TTL_SECONDS: int = Field(
        default=3600,
        description="TTL for process-local idempotency fallback entries.",
    )

    # Observability
    SENTRY_DSN: str = Field(default="", description="Sentry DSN for error tracking")

    # Langfuse (LLM Observability)
    LANGFUSE_ENABLED: bool = Field(
        default=False, description="Enable Langfuse LLM tracing"
    )
    LANGFUSE_PUBLIC_KEY: str = Field(default="", description="Langfuse public key")
    LANGFUSE_SECRET_KEY: str = Field(default="", description="Langfuse secret key")
    LANGFUSE_HOST: str = Field(
        default="https://cloud.langfuse.com", description="Langfuse host URL"
    )
    LANGFUSE_SAMPLE_RATE: float = Field(
        default=1.0,
        description="Langfuse trace sample rate 0.0-1.0. Set <1.0 in production to reduce overhead.",
    )

    # LangSmith (LangChain Observability)
    LANGCHAIN_TRACING_V2: bool = Field(
        default=False, description="Enable LangSmith tracing"
    )
    LANGCHAIN_API_KEY: str = Field(default="", description="LangSmith API key")
    LANGCHAIN_PROJECT: str = Field(
        default="nexus-ai-command", description="LangSmith project name"
    )

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=60, description="API rate limit per minute"
    )
    RATE_LIMIT_BURST: int = Field(default=10, description="Rate limit burst size")

    # Tenant-level rate limiting (#35)
    TENANT_RATE_LIMIT_PER_MINUTE: int = Field(
        default=1000, description="Max requests per tenant per minute"
    )
    TENANT_RATE_LIMIT_PER_HOUR: int = Field(
        default=10000, description="Max requests per tenant per hour"
    )

    # Noisy-neighbor throttle (#59)
    MAX_CONCURRENT_LLM_PER_TENANT: int = Field(
        default=10, description="Max concurrent LLM requests per tenant"
    )
    # P0: Global system-wide LLM concurrency cap — prevents all tenants
    # combined from exhausting uvicorn workers
    GLOBAL_MAX_CONCURRENT_LLM: int = Field(
        default=50,
        description="Max total concurrent LLM requests across all tenants (system-wide hard cap)",
    )

    # G5: Token budget / cost circuit-breaker
    TOKEN_BUDGET_MAX_PER_SESSION: int = Field(
        default=100000, description="Max tokens per single chat session"
    )
    TOKEN_BUDGET_MAX_PER_HOUR_PER_USER: int = Field(
        default=200000, description="Max tokens per user per hour"
    )
    TOKEN_BUDGET_MAX_COST_PER_SESSION: float = Field(
        default=5.0, description="Max cost (USD) per single chat session"
    )
    TOKEN_BUDGET_MAX_COST_PER_DAY_PER_TENANT: float = Field(
        default=100.0, description="Max cost (USD) per tenant per day"
    )
    # P0: Hard cost limits (防止 CRITICAL n=3 投票等场景成本失控)
    LLM_MAX_COST_PER_REQUEST: float = Field(
        default=2.0,
        description="Hard cost cap (USD) per single LLM request. Exceeding triggers auto-downgrade to mini model.",
    )
    TOKEN_BUDGET_MAX_COST_PER_MONTH_PER_TENANT: float = Field(
        default=2000.0,
        description="Max cost (USD) per tenant per calendar month. Exceeding blocks LLM calls until next month.",
    )
    TOKEN_BUDGET_MEMORY_FALLBACK_ENABLED: bool = Field(
        default=False,
        description="Allow in-memory token budget fallback in production when Redis is unavailable.",
    )

    # File upload
    MAX_FILE_SIZE_MB: int = Field(
        default=50, description="Maximum file upload size in MB"
    )
    MAX_CHAT_HISTORY: int = Field(
        default=10, description="Maximum chat message history window size"
    )
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
    RAG_CHUNK_SIZE: int = Field(
        default=600, description="Document chunk size for RAG embedding"
    )
    RAG_CHUNK_OVERLAP: int = Field(
        default=100, description="Document chunk overlap for RAG embedding"
    )
    RAG_PARENT_CHUNK_SIZE: int = Field(
        default=1800, description="Parent chunk size for parent-document retriever"
    )

    # Reranker Configuration
    RERANK_ENABLED: bool = Field(
        default=True, description="Enable reranking in hybrid search"
    )
    RERANK_PROVIDER: str = Field(
        default="api_reranker", description="Reranker provider: 'api_reranker' or 'llm'"
    )
    RERANK_MODEL: str = Field(
        default="bge-reranker-v2-m3", description="Model name for API-based reranker"
    )
    RERANK_TOP_N: int = Field(
        default=5, description="Number of top results to return from reranker"
    )
    RERANK_MAX_DOCS: int = Field(
        default=8, description="Maximum documents to send to reranker"
    )
    RERANK_TIMEOUT: int = Field(
        default=8, description="Timeout in seconds for reranker call"
    )
    COHERE_API_KEY: str = Field(
        default="", description="Cohere API key for Cohere Rerank backend"
    )
    RERANKER_BACKEND: str = Field(
        default="",
        description="Reranker backend override: 'cohere', 'bge', or 'llm'. Empty = auto-detect",
    )

    # LangGraph Agent Configuration
    LANGGRAPH_MAX_ITERATIONS: int = Field(
        default=5, description="Maximum plan-execute-reflect loop iterations"
    )
    LANGGRAPH_TOOL_TIMEOUT: int = Field(
        default=30, description="Timeout in seconds for individual tool execution"
    )
    LANGGRAPH_GATHER_TIMEOUT: int = Field(
        default=60, description="Timeout in seconds for parallel tool gather"
    )
    LANGGRAPH_ENABLE_RAG_INJECT: bool = Field(
        default=True, description="Auto-inject RAG context into agent messages"
    )
    LANGGRAPH_RAG_INJECT_THRESHOLD: float = Field(
        default=0.5, description="Minimum similarity threshold for RAG auto-injection"
    )
    LANGGRAPH_RAG_INJECT_LIMIT: int = Field(
        default=3, description="Max number of RAG chunks to auto-inject"
    )
    LANGGRAPH_REFLECT_USE_LLM: bool = Field(
        default=True,
        description="Use LLM for grounded hallucination detection in reflect node",
    )
    LANGGRAPH_CHECKPOINTER: str = Field(
        default="memory", description="Checkpointer backend: 'memory' or 'postgres'"
    )
    SEMANTIC_CACHE_THRESHOLD: float = Field(
        default=0.90,
        description="Similarity threshold for semantic cache hits (lowered from 0.95 to improve hit rate)",
    )

    # --- Externalized runtime-tunable constants ---
    # Orchestrator
    ORCHESTRATOR_MAX_SUB_TASKS: int = Field(default=8)
    ORCHESTRATOR_MAX_CONCURRENCY: int = Field(default=4)
    ORCHESTRATOR_MAX_TOOL_ROUNDS: int = Field(default=3)
    ORCHESTRATOR_REPLAN_FAILURE_THRESHOLD: float = Field(default=0.3)
    ORCHESTRATOR_TOKEN_BUDGET: int = Field(default=30000)
    # Tool selection
    TOOL_MAX_TOOLS: int = Field(default=20)
    TOOL_EMBEDDING_TOP_K: int = Field(default=12)
    TOOL_EMBEDDING_MIN_SCORE: float = Field(default=0.15)
    TOOL_EMBEDDING_GATE: int = Field(default=12)
    # Loop detection
    LOOP_WINDOW_SIZE: int = Field(default=30)
    LOOP_GENERIC_REPEAT_THRESHOLD: int = Field(default=3)
    LOOP_POLL_NO_PROGRESS_THRESHOLD: int = Field(default=5)
    LOOP_GLOBAL_CIRCUIT_BREAKER: int = Field(default=15)
    # Prompt compression
    PROMPT_MAX_TURNS_BEFORE_COMPRESS: int = Field(default=6)
    PROMPT_MAX_TOKENS_BEFORE_COMPRESS: int = Field(default=4500)
    PROMPT_KEEP_RECENT_TURNS: int = Field(default=3)
    PROMPT_TAIL_TOKEN_BUDGET: int = Field(default=8000)
    # Memory lifecycle
    MEMORY_LEVEL2_START_DAYS: int = Field(default=30)
    MEMORY_LEVEL3_START_DAYS: int = Field(default=90)
    MEMORY_BATCH_SIZE: int = Field(default=50)
    MEMORY_HIGH_IMPORTANCE_SKIP: float = Field(default=0.7)
    MEMORY_FORGET_THRESHOLD: float = Field(default=0.08)
    # Context engine
    CONTEXT_BUDGET_RATIO: float = Field(default=0.30)
    CONTEXT_MIN_BUDGET: int = Field(default=2000)
    CONTEXT_MAX_BUDGET: int = Field(default=16000)
    # Token window
    TOKEN_HARD_TURN_LIMIT: int = Field(default=40)
    TOKEN_DEFAULT_CONTEXT_WINDOW: int = Field(default=128000)
    # AI metrics
    METRICS_WINDOW_SIZE: int = Field(default=100)
    METRICS_CONSECUTIVE_FAIL_THRESHOLD: int = Field(default=3)
    METRICS_AGENT_ALERT_WINDOW_S: int = Field(default=3600)
    METRICS_AGENT_ALERT_THRESHOLD: float = Field(default=0.80)
    METRICS_AGENT_ALERT_MIN_SAMPLES: int = Field(default=10)

    # SLO Definitions (Item 16)
    SLO_AI_RESPONSE_P95_MS: int = Field(
        default=5000, description="SLO: AI response P95 latency in ms"
    )
    SLO_API_RESPONSE_P99_MS: int = Field(
        default=1000, description="SLO: API response P99 latency in ms"
    )
    SLO_AVAILABILITY_TARGET: float = Field(
        default=99.5, description="SLO: target availability percentage"
    )
    SLO_ERROR_BUDGET_WINDOW_DAYS: int = Field(
        default=30, description="SLO: error budget rolling window in days"
    )

    # Sentry per-endpoint sampling (Item 26)
    SENTRY_SECURITY_SAMPLE_RATE: float = Field(
        default=1.0,
        description="Sentry trace sample rate for security-critical endpoints (auth/approval/billing)",
    )

    # Migration control (Item 19)
    RUN_MIGRATIONS_ON_STARTUP: bool = Field(
        default=False,
        description="Run DB migrations on app startup. Use CI/CD pipeline in production.",
    )

    # Security
    # P1 Fix #42: Key for encryption
    ENCRYPTION_KEY: str = Field(
        default="", description="Master key for encrypting API keys"
    )

    # Stripe Payment Gateway
    STRIPE_SECRET_KEY: str = Field(default="", description="Stripe secret key")
    STRIPE_PUBLISHABLE_KEY: str = Field(
        default="", description="Stripe publishable key"
    )
    STRIPE_WEBHOOK_SECRET: str = Field(
        default="", description="Stripe webhook signing secret"
    )
    STRIPE_PRICE_BASIC: str = Field(
        default="", description="Stripe Price ID for Starter plan (legacy alias: basic)"
    )
    STRIPE_PRICE_PREMIUM: str = Field(
        default="",
        description="Stripe Price ID for Professional plan (legacy alias: premium)",
    )
    STRIPE_PRICE_ENTERPRISE: str = Field(
        default="", description="Stripe Price ID for Enterprise plan"
    )

    # Canonical aliases — prefer these in new code
    @property
    def STRIPE_PRICE_STARTER(self) -> str:
        return self.STRIPE_PRICE_BASIC

    @property
    def STRIPE_PRICE_PROFESSIONAL(self) -> str:
        return self.STRIPE_PRICE_PREMIUM

    # G4: Prompt Firewall
    PROMPT_FIREWALL_ENABLED: bool = Field(
        default=True, description="Enable Prompt Firewall pre-agent input protection"
    )

    # Observability (OpenTelemetry)
    OTEL_ENABLED: bool = Field(
        default=False, description="Enable OpenTelemetry distributed tracing"
    )
    OTEL_EXPORTER_ENDPOINT: str = Field(
        default="",
        description="OTLP exporter gRPC endpoint (e.g. http://localhost:4317)",
    )

    # B2: Notification Channel Configuration
    # Email (SMTP)
    SMTP_HOST: str | None = Field(default=None, description="SMTP server hostname")
    SMTP_PORT: int = Field(
        default=587, description="SMTP server port (587 for STARTTLS, 465 for SSL)"
    )
    SMTP_USER: str | None = Field(default=None, description="SMTP username")
    SMTP_PASSWORD: str | None = Field(default=None, description="SMTP password")
    SMTP_FROM: str | None = Field(default=None, description="Sender email address")

    # Wecom (企业微信) - Webhook
    WECOM_WEBHOOK_URL: str | None = Field(
        default=None, description="Wecom group bot webhook URL"
    )
    # Wecom (企业微信) - 深度集成
    WECOM_CORP_ID: str = Field(default="", description="企业微信 Corp ID")
    WECOM_CORP_SECRET: str = Field(
        default="", description="企业微信 Corp Secret (应用 Secret)"
    )
    WECOM_AGENT_ID: str = Field(
        default="", description="企业微信 Agent ID (应用 AgentId)"
    )

    # Dingtalk (钉钉) - Webhook
    DINGTALK_WEBHOOK_URL: str | None = Field(
        default=None, description="Dingtalk group bot webhook URL"
    )
    DINGTALK_SECRET: str | None = Field(
        default=None, description="Dingtalk webhook secret for signature"
    )
    # Dingtalk (钉钉) - 深度集成
    DINGTALK_APP_KEY: str = Field(default="", description="钉钉 App Key")
    DINGTALK_APP_SECRET: str = Field(default="", description="钉钉 App Secret")
    DINGTALK_AGENT_ID: str = Field(
        default="", description="钉钉 Agent ID (应用 agentId)"
    )

    # Feishu (飞书) - Webhook
    FEISHU_WEBHOOK_URL: str | None = Field(
        default=None, description="Feishu group bot webhook URL"
    )
    # Feishu (飞书) - 深度集成
    FEISHU_APP_ID: str = Field(default="", description="飞书 App ID")
    FEISHU_APP_SECRET: str = Field(default="", description="飞书 App Secret")
    FEISHU_ENCRYPT_KEY: str = Field(
        default="", description="飞书事件订阅 Encrypt Key（签名验证）"
    )

    # Web Push VAPID
    VAPID_PUBLIC_KEY: str = Field(
        default="", description="VAPID public key for Web Push"
    )
    VAPID_PRIVATE_KEY: str = Field(
        default="", description="VAPID private key for Web Push"
    )

    # Computed properties
    @property
    def IS_PRODUCTION(self) -> bool:  # noqa: N802
        return self.ENV in ("production", "prod")

    @property
    def all_cors_origins(self) -> list[str]:
        """Get all CORS origins including additional ones from env"""
        origins = list(self.CORS_ORIGINS)
        if self.ADDITIONAL_ALLOWED_ORIGINS:
            extras = [
                o.strip()
                for o in self.ADDITIONAL_ALLOWED_ORIGINS.split(",")
                if o.strip()
            ]
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

            if not self.AI_BASE_URL:
                errors.append("AI_BASE_URL is required in production")

            if not self.SUPABASE_URL:
                errors.append("SUPABASE_URL is required in production")

            if not self.SUPABASE_SERVICE_KEY:
                errors.append("SUPABASE_SERVICE_KEY is required in production")

            if not self.SUPABASE_JWT_SECRET and not self.JWT_SECRET:
                errors.append(
                    "JWT secret (SUPABASE_JWT_SECRET or JWT_SECRET) is required in production"
                )

            if self.LANGGRAPH_CHECKPOINTER.lower() != "postgres":
                errors.append(
                    "LANGGRAPH_CHECKPOINTER must be 'postgres' in production for durable Agent state"
                )

            if not self.REDIS_URL:
                errors.append(
                    "REDIS_URL is required in production for shared rate limits, token budgets, and Celery"
                )

            if self.DEBUG:
                errors.append("DEBUG mode must be disabled in production")

            if not self.ENCRYPTION_KEY or self.ENCRYPTION_KEY == "":
                errors.append("ENCRYPTION_KEY is required in production")

            health_token = os.getenv("HEALTH_CHECK_TOKEN", "")
            if not health_token or len(health_token) < 24:
                errors.append(
                    "HEALTH_CHECK_TOKEN must be configured in production with at least 24 characters"
                )

            if self.TOKEN_BUDGET_MEMORY_FALLBACK_ENABLED:
                errors.append(
                    "TOKEN_BUDGET_MEMORY_FALLBACK_ENABLED must stay false in production"
                )

        return errors

    model_config = {
        "env_file": str(Path(__file__).parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",  # Ignore extra env vars not defined here
    }


settings = Settings()

# Sync critical env vars from Pydantic back to os.environ
# so that modules using os.getenv() (celery_app, rate_limiter, etc.) can also read them
import os as _os

_sync_keys = [
    "REDIS_URL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "OPENAI_API_KEY",
    "AI_BASE_URL",
]
for _key in _sync_keys:
    _val = getattr(settings, _key, None)
    if _val and _key not in _os.environ:
        _os.environ[_key] = _val

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
