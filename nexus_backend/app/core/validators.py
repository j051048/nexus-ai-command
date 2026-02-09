"""
P2 Security: Input Validation Utilities

Provides validation functions for common input types to prevent:
- Injection attacks (SQL, NoSQL, command)
- Path traversal attacks
- Invalid data formats
- XSS attempts
"""
import re
import logging
from typing import Optional, Tuple, List
from datetime import datetime

logger = logging.getLogger(__name__)


class InputValidator:
    """
    Centralized input validation for the application.
    
    Usage:
        from app.core.validators import validator
        
        is_valid, error = validator.validate_uuid(user_input)
        if not is_valid:
            raise HTTPException(400, error)
    """
    
    # Compiled regex patterns for efficiency
    UUID_PATTERN = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    # Dangerous patterns that might indicate injection attempts
    INJECTION_PATTERNS = [
        r'(?i)(\b(select|insert|update|delete|drop|union|exec|execute)\b)',  # SQL keywords
        r'(?i)(--|;|/\*|\*/)',  # SQL comment/terminator
        r'(?i)(\$where|\$regex|\$gt|\$lt)',  # MongoDB injection
        r'(?i)(<script|javascript:|on\w+\s*=)',  # XSS
        r'(?i)(\.\.\/|\.\.\\)',  # Path traversal
    ]
    
    def __init__(self):
        self._injection_regex = [re.compile(p) for p in self.INJECTION_PATTERNS]
    
    def validate_uuid(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a UUID string.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value:
            return False, "UUID cannot be empty"
        
        if not isinstance(value, str):
            return False, "UUID must be a string"
        
        if not self.UUID_PATTERN.match(value):
            return False, "Invalid UUID format"
        
        return True, None
    
    def validate_email(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Validate an email address.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value:
            return False, "Email cannot be empty"
        
        if len(value) > 254:
            return False, "Email too long"
        
        if not self.EMAIL_PATTERN.match(value):
            return False, "Invalid email format"
        
        return True, None
    
    def validate_date(self, value: str, format: str = "%Y-%m-%d") -> Tuple[bool, Optional[str]]:
        """
        Validate a date string.
        
        Args:
            value: Date string to validate
            format: Expected date format (default: YYYY-MM-DD)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value:
            return False, "Date cannot be empty"
        
        try:
            datetime.strptime(value, format)
            return True, None
        except ValueError:
            return False, f"Invalid date format. Expected: {format}"
    
    def validate_amount(
        self, 
        value: float, 
        min_value: float = 0, 
        max_value: float = 1000000000
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a monetary amount.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            amount = float(value)
        except (ValueError, TypeError):
            return False, "Amount must be a number"
        
        if amount < min_value:
            return False, f"Amount must be at least {min_value}"
        
        if amount > max_value:
            return False, f"Amount cannot exceed {max_value}"
        
        return True, None
    
    def check_injection(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a string contains potential injection patterns.
        
        Returns:
            Tuple of (is_safe, warning_message)
        """
        if not value:
            return True, None
        
        for pattern in self._injection_regex:
            if pattern.search(value):
                logger.warning(f"Potential injection detected: {value[:50]}...")
                return False, "Input contains potentially dangerous content"
        
        return True, None
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename to prevent path traversal and other attacks.
        
        Returns:
            Sanitized filename
        """
        if not filename:
            return "unnamed"
        
        # Remove path separators
        sanitized = filename.replace("/", "_").replace("\\", "_")
        
        # Remove null bytes
        sanitized = sanitized.replace("\x00", "")
        
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip(". ")
        
        # Limit length
        if len(sanitized) > 255:
            # Keep extension if present
            parts = sanitized.rsplit(".", 1)
            if len(parts) == 2 and len(parts[1]) <= 10:
                sanitized = parts[0][:240] + "." + parts[1]
            else:
                sanitized = sanitized[:255]
        
        return sanitized or "unnamed"
    
    def validate_string_length(
        self, 
        value: str, 
        field_name: str = "Field",
        min_length: int = 0, 
        max_length: int = 10000
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate string length constraints.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None:
            if min_length > 0:
                return False, f"{field_name} is required"
            return True, None
        
        if not isinstance(value, str):
            return False, f"{field_name} must be a string"
        
        length = len(value)
        
        if length < min_length:
            return False, f"{field_name} must be at least {min_length} characters"
        
        if length > max_length:
            return False, f"{field_name} cannot exceed {max_length} characters"
        
        return True, None
    
    def validate_list(
        self,
        value: List,
        field_name: str = "List",
        min_items: int = 0,
        max_items: int = 100
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate list constraints.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None:
            if min_items > 0:
                return False, f"{field_name} is required"
            return True, None
        
        if not isinstance(value, list):
            return False, f"{field_name} must be a list"
        
        length = len(value)
        
        if length < min_items:
            return False, f"{field_name} must have at least {min_items} items"
        
        if length > max_items:
            return False, f"{field_name} cannot exceed {max_items} items"
        
        return True, None


# Singleton instance
validator = InputValidator()
