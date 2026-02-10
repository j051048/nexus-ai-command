"""
P1 Fix #43: Settings migrated to Pydantic BaseSettings.

Benefits:
- Type safety with automatic validation
- Automatic .env file loading
- Clear field documentation  
- Validation errors on startup (fail fast)
"""
import sys
from typing import List, Optional

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
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:8080",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8080",
            "https://nexus-ai-command.vercel.app",
            "https://nexus-ai-command.zeabur.app",
            "https://aizhz.zeabur.app",
        ],
        description="Allowed CORS origins"
    )
    ADDITIONAL_ALLOWED_ORIGINS: Optional[str] = Field(
        default=None,
        description="Comma-separated additional CORS origins"
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
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key (or compatible provider)")
    AI_BASE_URL: str = Field(
        default="https://proxy.flydao.top/v1",
        description="Base URL for OpenAI-compatible API"
    )
    
    # Database (read by database.py via os.getenv, declared here for validation)
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_SERVICE_KEY: str = Field(default="", description="Supabase service role key")
    SUPABASE_JWT_SECRET: Optional[str] = Field(default=None, description="JWT secret for token verification")
    JWT_SECRET: Optional[str] = Field(default=None, description="Alternative JWT secret key")
    
    # Redis
    REDIS_URL: Optional[str] = Field(default=None, description="Redis connection URL")
    
    # Observability
    SENTRY_DSN: str = Field(default="", description="Sentry DSN for error tracking")
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="API rate limit per minute")
    RATE_LIMIT_BURST: int = Field(default=10, description="Rate limit burst size")
    
    # File upload
    MAX_FILE_SIZE_MB: int = Field(default=50, description="Maximum file upload size in MB")
    ALLOWED_FILE_TYPES: List[str] = Field(
        default=[".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".png", ".jpg", ".jpeg"],
        description="Allowed file upload extensions"
    )
    
    # Security
    ALLOW_UNSECURE_AUTH: Optional[str] = Field(default=None, description="Allow unsecure auth (dev only)")
    
    # Computed properties
    @property
    def IS_PRODUCTION(self) -> bool:
        return self.ENV in ("production", "prod")
    
    @property
    def all_cors_origins(self) -> List[str]:
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
    
    def validate_production_config(self) -> List[str]:
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
            
            if self.ALLOW_UNSECURE_AUTH == "true":
                errors.append("ALLOW_UNSECURE_AUTH must be disabled in production")
            
            if self.DEBUG:
                errors.append("DEBUG mode must be disabled in production")
        
        return errors
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",  # Ignore extra env vars not defined here
    }


settings = Settings()

# Validate configuration on startup
_config_errors = settings.validate_production_config()
if _config_errors:
    for error in _config_errors:
        print(f"❌ CONFIG ERROR: {error}")
    if settings.IS_PRODUCTION:
        sys.exit(1)  # Fail fast in production
    else:
        print("⚠️ Running in development mode with configuration warnings")
