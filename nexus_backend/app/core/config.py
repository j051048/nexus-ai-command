import os
from typing import List

class Settings:
    PROJECT_NAME: str = "Project Nexus Backend"
    VERSION: str = "1.0.0"
    
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

settings = Settings()
