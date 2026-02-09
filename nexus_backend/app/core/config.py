import os
import sys
from typing import List, Optional

class Settings:
    PROJECT_NAME: str = "Project Nexus Backend"
    VERSION: str = "1.0.0"
    
    # P0 Security: Environment detection
    ENV: str = os.getenv("ENV", "development")
    IS_PRODUCTION: bool = ENV in ("production", "prod")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true" and not IS_PRODUCTION
    
    # CORS Configuration
    # Default includes local development ports and production domains
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
        "https://nexus-ai-command.vercel.app",
        "https://nexus-ai-command.zeabur.app",
        "https://aizhz.zeabur.app",
    ]
    
    # Add extra origins from environment variable (comma separated)
    _extra_origins = os.getenv("ADDITIONAL_ALLOWED_ORIGINS")
    if _extra_origins:
        CORS_ORIGINS.extend([origin.strip() for origin in _extra_origins.split(",") if origin.strip()])

    # --- Rule Engine Thresholds ---
    
    # Approval Rules
    APPROVAL_PURCHASE_AUTO_LIMIT: float = 15000.0
    APPROVAL_PURCHASE_OVERRUN_TOLERANCE: float = 0.10  # 10%
    APPROVAL_TRAVEL_DAILY_LIMIT: float = 2000.0
    APPROVAL_EXPENSE_SMALL_LIMIT: float = 500.0
    
    # Performance Rules
    SCORE_DAILY_UPDATE_THRESHOLD: int = 3
    SCORE_DAILY_UPDATE_BONUS: float = 20.0
    
    SCORE_AI_QUALITY_THRESHOLD: float = 80.0
    SCORE_AI_QUALITY_BONUS: float = 30.0
    
    SCORE_DEAL_POINTS_PER_1000: float = 5.0

        # AI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    AI_BASE_URL: str = os.getenv("AI_BASE_URL", "https://proxy.flydao.top/v1")

    # Observability
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    
    # P0 Security: Rate limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    RATE_LIMIT_BURST: int = int(os.getenv("RATE_LIMIT_BURST", "10"))
    
    # P0 Security: File upload limits
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    ALLOWED_FILE_TYPES: List[str] = [".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".png", ".jpg", ".jpeg"]

    def validate_production_config(self) -> List[str]:
        """P0 Security: Validate critical configuration for production"""
        errors = []
        
        if self.IS_PRODUCTION:
            if not self.OPENAI_API_KEY:
                errors.append("OPENAI_API_KEY is required in production")
            
            if not os.getenv("SUPABASE_URL"):
                errors.append("SUPABASE_URL is required in production")
            
            if not os.getenv("SUPABASE_SERVICE_KEY"):
                errors.append("SUPABASE_SERVICE_KEY is required in production")
            
            if not os.getenv("SUPABASE_JWT_SECRET") and not os.getenv("JWT_SECRET"):
                errors.append("JWT secret (SUPABASE_JWT_SECRET or JWT_SECRET) is required in production")
            
            if os.getenv("ALLOW_UNSECURE_AUTH") == "true":
                errors.append("ALLOW_UNSECURE_AUTH must be disabled in production")
            
            if self.DEBUG:
                errors.append("DEBUG mode must be disabled in production")
        
        return errors

settings = Settings()

# P0 Security: Validate configuration on startup
_config_errors = settings.validate_production_config()
if _config_errors:
    for error in _config_errors:
        print(f"❌ CONFIG ERROR: {error}")
    if settings.IS_PRODUCTION:
        sys.exit(1)  # Fail fast in production
    else:
        print("⚠️ Running in development mode with configuration warnings")
