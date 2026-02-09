"""
P3 Enhancement: Environment Configuration Helper

Provides validation and documentation for environment variables.
Ensures all required configuration is present before startup.
"""
import os
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EnvType(Enum):
    """Environment variable types"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    URL = "url"
    SECRET = "secret"


@dataclass
class EnvVar:
    """Configuration for an environment variable"""
    name: str
    env_type: EnvType
    required: bool = False
    default: Any = None
    description: str = ""
    production_only: bool = False
    validate: Optional[Callable[[Any], bool]] = None


class EnvironmentConfig:
    """
    Environment configuration manager.
    
    Usage:
        from app.core.env_config import env_config
        
        # Get validated value
        api_key = env_config.get("OPENAI_API_KEY")
        
        # Validate all required vars
        errors = env_config.validate_all()
    """
    
    # Define all environment variables
    VARIABLES: List[EnvVar] = [
        # Database
        EnvVar(
            name="SUPABASE_URL",
            env_type=EnvType.URL,
            required=True,
            description="Supabase project URL"
        ),
        EnvVar(
            name="SUPABASE_SERVICE_KEY",
            env_type=EnvType.SECRET,
            required=True,
            description="Supabase service role key (secret)"
        ),
        
        # Authentication
        EnvVar(
            name="SUPABASE_JWT_SECRET",
            env_type=EnvType.SECRET,
            required=True,
            production_only=True,
            description="JWT secret for token verification"
        ),
        EnvVar(
            name="JWT_SECRET",
            env_type=EnvType.SECRET,
            required=False,
            description="Alternative JWT secret key"
        ),
        
        # AI Service
        EnvVar(
            name="OPENAI_API_KEY",
            env_type=EnvType.SECRET,
            required=True,
            description="OpenAI API key (or compatible provider)"
        ),
        EnvVar(
            name="AI_BASE_URL",
            env_type=EnvType.URL,
            required=False,
            default="https://api.openai.com/v1",
            description="Base URL for OpenAI-compatible API"
        ),
        
        # Redis (optional)
        EnvVar(
            name="REDIS_URL",
            env_type=EnvType.URL,
            required=False,
            description="Redis connection URL for distributed caching"
        ),
        
        # Environment
        EnvVar(
            name="ENV",
            env_type=EnvType.STRING,
            required=False,
            default="development",
            description="Environment name (development, production)"
        ),
        EnvVar(
            name="DEBUG",
            env_type=EnvType.BOOLEAN,
            required=False,
            default=False,
            description="Enable debug mode"
        ),
        
        # Observability
        EnvVar(
            name="SENTRY_DSN",
            env_type=EnvType.URL,
            required=False,
            description="Sentry DSN for error tracking"
        ),
        
        # Rate Limiting
        EnvVar(
            name="RATE_LIMIT_PER_MINUTE",
            env_type=EnvType.INTEGER,
            required=False,
            default=60,
            description="API rate limit per minute"
        ),
        
        # File Upload
        EnvVar(
            name="MAX_FILE_SIZE_MB",
            env_type=EnvType.INTEGER,
            required=False,
            default=50,
            description="Maximum file upload size in MB"
        ),
    ]
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._is_production = os.getenv("ENV", "development") in ("production", "prod")
    
    def get(self, name: str, default: Any = None) -> Any:
        """
        Get an environment variable with validation.
        
        Args:
            name: Variable name
            default: Default value if not set
            
        Returns:
            Validated value
        """
        # Check cache
        if name in self._cache:
            return self._cache[name]
        
        # Find variable definition
        var_def = next((v for v in self.VARIABLES if v.name == name), None)
        
        raw_value = os.getenv(name)
        
        if raw_value is None:
            if var_def and var_def.default is not None:
                value = var_def.default
            else:
                value = default
        else:
            value = self._parse_value(raw_value, var_def.env_type if var_def else EnvType.STRING)
        
        self._cache[name] = value
        return value
    
    def _parse_value(self, raw: str, env_type: EnvType) -> Any:
        """Parse raw string to appropriate type"""
        if env_type == EnvType.INTEGER:
            try:
                return int(raw)
            except ValueError:
                return 0
        
        elif env_type == EnvType.FLOAT:
            try:
                return float(raw)
            except ValueError:
                return 0.0
        
        elif env_type == EnvType.BOOLEAN:
            return raw.lower() in ("true", "1", "yes", "on")
        
        else:  # STRING, URL, SECRET
            return raw
    
    def validate_all(self) -> List[str]:
        """
        Validate all required environment variables.
        
        Returns:
            List of error messages (empty if all valid)
        """
        errors = []
        
        for var in self.VARIABLES:
            # Skip production-only vars in development
            if var.production_only and not self._is_production:
                continue
            
            if var.required:
                value = os.getenv(var.name)
                if not value:
                    errors.append(f"{var.name}: Required but not set. {var.description}")
                elif var.validate and not var.validate(value):
                    errors.append(f"{var.name}: Validation failed. {var.description}")
        
        return errors
    
    def get_documentation(self) -> str:
        """Generate documentation for all environment variables"""
        lines = ["# Environment Variables Configuration\n"]
        
        required = [v for v in self.VARIABLES if v.required]
        optional = [v for v in self.VARIABLES if not v.required]
        
        lines.append("## Required Variables\n")
        for var in required:
            lines.append(f"### {var.name}")
            lines.append(f"- Type: {var.env_type.value}")
            lines.append(f"- Description: {var.description}")
            if var.production_only:
                lines.append("- *Required in production only*")
            lines.append("")
        
        lines.append("## Optional Variables\n")
        for var in optional:
            lines.append(f"### {var.name}")
            lines.append(f"- Type: {var.env_type.value}")
            lines.append(f"- Default: {var.default}")
            lines.append(f"- Description: {var.description}")
            lines.append("")
        
        return "\n".join(lines)
    
    def log_status(self) -> None:
        """Log configuration status (masking secrets)"""
        logger.info("=== Environment Configuration Status ===")
        
        for var in self.VARIABLES:
            value = os.getenv(var.name)
            
            if value:
                if var.env_type == EnvType.SECRET:
                    display = f"***{value[-4:]}" if len(value) > 4 else "****"
                else:
                    display = value[:30] + "..." if len(value) > 30 else value
                status = f"✓ {display}"
            elif var.default is not None:
                status = f"(default: {var.default})"
            else:
                status = "✗ NOT SET"
            
            req_marker = "[REQ]" if var.required else "[OPT]"
            logger.info(f"  {req_marker} {var.name}: {status}")


# Global instance
env_config = EnvironmentConfig()
