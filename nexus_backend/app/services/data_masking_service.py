"""
P2 Enhancement: Data Masking API Service

Implements comprehensive data masking and anonymization.
Fixes Issue #11: Missing data masking API.
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MaskingLevel(Enum):
    """Data masking levels."""
    FULL = "full"           # 完全隐藏 (****)
    PARTIAL = "partial"     # 部分隐藏 (张**)
    HASH = "hash"           # 哈希替换
    TOKENIZE = "tokenize"   # Token化 (可逆)
    REDACT = "redact"       # 移除


class DataType(Enum):
    """Data types for masking."""
    PHONE = "phone"
    EMAIL = "email"
    ID_CARD = "id_card"
    BANK_CARD = "bank_card"
    NAME = "name"
    ADDRESS = "address"
    IP_ADDRESS = "ip_address"
    API_KEY = "api_key"
    PASSWORD = "password"
    CREDIT_CARD = "credit_card"
    SSN = "ssn"
    CUSTOM = "custom"


@dataclass
class MaskingRule:
    """Rule for masking a specific data type."""
    data_type: DataType
    pattern: str
    masking_level: MaskingLevel
    replacement: str
    preserve_format: bool = True


class DataMaskingService:
    """
    P2 Enhancement: Comprehensive data masking service.

    Features:
    - Multiple masking strategies
    - Configurable rules per data type
    - Tokenization with reversible mapping
    - Format preservation
    - Batch processing
    - API-ready endpoints
    """

    # Default masking patterns
    DEFAULT_PATTERNS = {
        DataType.PHONE: r'1[3-9]\d{9}',
        DataType.EMAIL: r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        DataType.ID_CARD: r'\d{17}[\dXx]',
        DataType.BANK_CARD: r'\d{16,19}',
        DataType.IP_ADDRESS: r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
        DataType.API_KEY: r'sk-[a-zA-Z0-9]{20,}|api[_-]?key[_-]?[a-zA-Z0-9]{16,}',
        DataType.CREDIT_CARD: r'\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}',
    }

    def __init__(self, secret_key: str = "default-secret-key"):
        self.secret_key = secret_key
        self._token_map: dict[str, str] = {}  # token -> original
        self._reverse_map: dict[str, str] = {}  # original -> token
        self._rules: dict[DataType, MaskingRule] = self._init_default_rules()

    def _init_default_rules(self) -> dict[DataType, MaskingRule]:
        """Initialize default masking rules."""
        return {
            DataType.PHONE: MaskingRule(
                data_type=DataType.PHONE,
                pattern=self.DEFAULT_PATTERNS[DataType.PHONE],
                masking_level=MaskingLevel.PARTIAL,
                replacement="***"
            ),
            DataType.EMAIL: MaskingRule(
                data_type=DataType.EMAIL,
                pattern=self.DEFAULT_PATTERNS[DataType.EMAIL],
                masking_level=MaskingLevel.PARTIAL,
                replacement="***"
            ),
            DataType.ID_CARD: MaskingRule(
                data_type=DataType.ID_CARD,
                pattern=self.DEFAULT_PATTERNS[DataType.ID_CARD],
                masking_level=MaskingLevel.PARTIAL,
                replacement="***********"
            ),
            DataType.BANK_CARD: MaskingRule(
                data_type=DataType.BANK_CARD,
                pattern=self.DEFAULT_PATTERNS[DataType.BANK_CARD],
                masking_level=MaskingLevel.PARTIAL,
                replacement="****"
            ),
            DataType.API_KEY: MaskingRule(
                data_type=DataType.API_KEY,
                pattern=self.DEFAULT_PATTERNS[DataType.API_KEY],
                masking_level=MaskingLevel.FULL,
                replacement="[REDACTED]"
            ),
            DataType.IP_ADDRESS: MaskingRule(
                data_type=DataType.IP_ADDRESS,
                pattern=self.DEFAULT_PATTERNS[DataType.IP_ADDRESS],
                masking_level=MaskingLevel.PARTIAL,
                replacement=".***"
            ),
            DataType.CREDIT_CARD: MaskingRule(
                data_type=DataType.CREDIT_CARD,
                pattern=self.DEFAULT_PATTERNS[DataType.CREDIT_CARD],
                masking_level=MaskingLevel.PARTIAL,
                replacement="****"
            ),
        }

    def set_rule(self, data_type: DataType, rule: MaskingRule):
        """Set a custom masking rule."""
        self._rules[data_type] = rule

    def mask(self, text: str, data_types: list[DataType] = None) -> str:
        """
        Mask sensitive data in text.

        Args:
            text: Input text to mask
            data_types: Specific data types to mask (None = all)

        Returns:
            Text with sensitive data masked
        """
        if not text:
            return text

        types_to_mask = data_types or list(self._rules.keys())
        result = text

        for data_type in types_to_mask:
            if data_type not in self._rules:
                continue

            rule = self._rules[data_type]
            result = self._apply_masking(result, rule)

        return result

    def _apply_masking(self, text: str, rule: MaskingRule) -> str:
        """Apply masking rule to text."""
        pattern = re.compile(rule.pattern)

        def replace(match):
            original = match.group()

            if rule.masking_level == MaskingLevel.FULL:
                return "*" * len(original)

            elif rule.masking_level == MaskingLevel.PARTIAL:
                return self._partial_mask(original, rule.data_type)

            elif rule.masking_level == MaskingLevel.HASH:
                return self._hash_mask(original)

            elif rule.masking_level == MaskingLevel.TOKENIZE:
                return self._tokenize(original)

            elif rule.masking_level == MaskingLevel.REDACT:
                return rule.replacement

            return original

        return pattern.sub(replace, text)

    def _partial_mask(self, value: str, data_type: DataType) -> str:
        """Apply partial masking to preserve some format."""
        if data_type == DataType.PHONE:
            # 138****1234
            if len(value) == 11:
                return value[:3] + "****" + value[7:]

        elif data_type == DataType.EMAIL:
            # a***@example.com
            parts = value.split('@')
            if len(parts) == 2:
                name = parts[0]
                if len(name) > 1:
                    return name[0] + "***@" + parts[1]

        elif data_type == DataType.ID_CARD:
            # 110***********1234
            if len(value) >= 15:
                return value[:3] + "***********" + value[-4:]

        elif data_type == DataType.BANK_CARD:
            # 6222****1234
            if len(value) >= 8:
                return value[:4] + "****" + value[-4:]

        elif data_type == DataType.IP_ADDRESS:
            # 192.168.*.*
            parts = value.split('.')
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.*.*"

        elif data_type == DataType.CREDIT_CARD:
            # ****-****-****-1234
            digits = re.sub(r'[\s-]', '', value)
            if len(digits) >= 4:
                return "****-****-****-" + digits[-4:]

        # Default: show first and last char
        if len(value) > 2:
            return value[0] + "*" * (len(value) - 2) + value[-1]

        return "*" * len(value)

    def _hash_mask(self, value: str) -> str:
        """Replace with hash."""
        hash_val = hashlib.sha256((value + self.secret_key).encode()).hexdigest()[:8]
        return f"[HASH:{hash_val}]"

    def _tokenize(self, value: str) -> str:
        """Replace with reversible token."""
        if value in self._reverse_map:
            return self._reverse_map[value]

        # Generate token
        token = f"[TOKEN:{hashlib.md5((value + self.secret_key).encode()).hexdigest()[:8]}]"

        self._token_map[token] = value
        self._reverse_map[value] = token

        return token

    def detokenize(self, token: str) -> str | None:
        """Recover original value from token."""
        return self._token_map.get(token)

    def mask_dict(
        self,
        data: dict[str, Any],
        field_rules: dict[str, DataType] = None
    ) -> dict[str, Any]:
        """
        Mask sensitive fields in a dictionary.

        Args:
            data: Dictionary to mask
            field_rules: Mapping of field names to data types

        Returns:
            Dictionary with masked values
        """
        result = {}

        for key, value in data.items():
            if isinstance(value, str):
                # Check if this field has a specific rule
                if field_rules and key in field_rules:
                    data_type = field_rules[key]
                    if data_type in self._rules:
                        result[key] = self._apply_masking(value, self._rules[data_type])
                    else:
                        result[key] = self.mask(value)
                else:
                    # Auto-detect and mask
                    result[key] = self.mask(value)
            elif isinstance(value, dict):
                result[key] = self.mask_dict(value, field_rules)
            elif isinstance(value, list):
                result[key] = [
                    self.mask_dict(item, field_rules) if isinstance(item, dict)
                    else self.mask(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                result[key] = value

        return result

    def detect_sensitive_data(self, text: str) -> list[dict[str, Any]]:
        """
        Detect all sensitive data in text.

        Returns:
            List of detected sensitive data with type and position
        """
        detections = []

        for data_type, pattern in self.DEFAULT_PATTERNS.items():
            for match in re.finditer(pattern, text):
                detections.append({
                    "type": data_type.value,
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end()
                })

        return detections

    def get_masking_stats(self, text: str) -> dict[str, int]:
        """Get statistics on sensitive data in text."""
        detections = self.detect_sensitive_data(text)

        stats = {}
        for detection in detections:
            data_type = detection["type"]
            stats[data_type] = stats.get(data_type, 0) + 1

        return stats


# Global instance
data_masking_service = DataMaskingService()


# Convenience functions for API
def mask_text(text: str, data_types: list[str] = None) -> str:
    """API function to mask text."""
    if data_types:
        types = [DataType(t) for t in data_types if t in [d.value for d in DataType]]
        return data_masking_service.mask(text, types)
    return data_masking_service.mask(text)


def mask_data(data: dict, field_rules: dict[str, str] = None) -> dict:
    """API function to mask dictionary."""
    rules = None
    if field_rules:
        rules = {k: DataType(v) for k, v in field_rules.items() if v in [d.value for d in DataType]}
    return data_masking_service.mask_dict(data, rules)


def detect_sensitive(text: str) -> list[dict]:
    """API function to detect sensitive data."""
    return data_masking_service.detect_sensitive_data(text)
