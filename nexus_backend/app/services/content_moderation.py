"""
P1 Optimization: Content Moderation Service
Scans AI outputs for sensitive information and policy violations.
"""
import re
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class ViolationType(Enum):
    """Types of content violations"""
    PII_PHONE = "pii_phone"
    PII_ID_CARD = "pii_id_card"
    PII_EMAIL = "pii_email"
    PII_BANK_CARD = "pii_bank_card"
    CREDENTIAL_LEAK = "credential_leak"
    PRIVATE_KEY = "private_key"
    PROMPT_INJECTION = "prompt_injection"
    HARMFUL_CONTENT = "harmful_content"
    COMPETITOR_MENTION = "competitor_mention"


@dataclass
class Violation:
    """Represents a content violation"""
    type: ViolationType
    severity: str  # "low", "medium", "high", "critical"
    matched_text: str
    position: Tuple[int, int]  # start, end
    suggestion: str


class ContentModerator:
    """
    Scans content for sensitive information and policy violations.
    Can be used for both input validation and output sanitization.
    """
    
    # Pattern definitions with severity levels
    PATTERNS: Dict[ViolationType, Tuple[str, str, str]] = {
        # (pattern, severity, replacement_suggestion)
        ViolationType.PII_PHONE: (
            r'(?<![0-9a-zA-Z])(1[3-9]\d{9})(?![0-9a-zA-Z])',
            "high",
            "[电话号码已隐藏]"
        ),
        ViolationType.PII_ID_CARD: (
            r'(?<!\d)(\d{6})(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(\d{3})([0-9Xx])(?!\d)',
            "critical",
            "[身份证号已隐藏]"
        ),
        ViolationType.PII_EMAIL: (
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            "medium",
            "[邮箱已隐藏]"
        ),
        ViolationType.PII_BANK_CARD: (
            r'(?<!\d)([4-6]\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4})(?!\d)',
            "critical",
            "[银行卡号已隐藏]"
        ),
        ViolationType.CREDENTIAL_LEAK: (
            r'(?i)(password|passwd|pwd|secret|api[_-]?key|access[_-]?key|token|credential)[\s]*[:=][\s]*[^\s\n,]{8,}',
            "critical",
            "[敏感凭证已隐藏]"
        ),
        ViolationType.PRIVATE_KEY: (
            r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(RSA\s+)?PRIVATE\s+KEY-----',
            "critical",
            "[私钥已隐藏]"
        ),
    }
    
    # Prompt injection patterns
    INJECTION_PATTERNS = [
        r'忽略(之前|上面|以上)(的|所有)?(指令|命令|提示)',
        r'ignore\s+(previous|above|all)\s+(instructions?|prompts?|commands?)',
        r'你(现在)?是(.{0,20})(而不是|不再是)',
        r'you\s+are\s+(now\s+)?a?\s*(?!helpful)',
        r'(reveal|show|display|print)\s+(your\s+)?(system\s+)?(prompt|instructions?)',
        r'(透露|显示|输出|告诉我)(你的)?(系统|原始)?(提示词|指令|prompt)',
        r'\[\[.*?\]\]',  # Potential jailbreak markers
        r'<\|.*?\|>',    # Potential jailbreak markers
    ]
    
    # Competitor names (configurable)
    COMPETITOR_NAMES = [
        # Add competitor names here if needed
        # "竞品A", "竞品B"
    ]
    
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self._compiled_patterns = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for performance"""
        for vtype, (pattern, _, _) in self.PATTERNS.items():
            self._compiled_patterns[vtype] = re.compile(pattern)
        
        self._injection_patterns = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]
    
    def scan(self, content: str) -> Tuple[bool, List[Violation]]:
        """
        Scan content for violations.
        Returns (is_safe, list_of_violations)
        """
        if not content:
            return True, []
        
        violations = []
        
        # Check PII and credential patterns
        for vtype, (_, severity, suggestion) in self.PATTERNS.items():
            pattern = self._compiled_patterns[vtype]
            for match in pattern.finditer(content):
                violations.append(Violation(
                    type=vtype,
                    severity=severity,
                    matched_text=self._mask_text(match.group(), vtype),
                    position=(match.start(), match.end()),
                    suggestion=suggestion
                ))
        
        # Check prompt injection
        for pattern in self._injection_patterns:
            for match in pattern.finditer(content):
                violations.append(Violation(
                    type=ViolationType.PROMPT_INJECTION,
                    severity="high",
                    matched_text=match.group()[:50] + "..." if len(match.group()) > 50 else match.group(),
                    position=(match.start(), match.end()),
                    suggestion="[疑似注入攻击]"
                ))
        
        # Check competitor mentions
        for competitor in self.COMPETITOR_NAMES:
            if competitor.lower() in content.lower():
                idx = content.lower().find(competitor.lower())
                violations.append(Violation(
                    type=ViolationType.COMPETITOR_MENTION,
                    severity="low",
                    matched_text=competitor,
                    position=(idx, idx + len(competitor)),
                    suggestion="[竞品名称]"
                ))
        
        # Determine if content is safe
        is_safe = len(violations) == 0
        if not is_safe and not self.strict_mode:
            # In non-strict mode, only block critical violations
            critical_violations = [v for v in violations if v.severity == "critical"]
            is_safe = len(critical_violations) == 0
        
        return is_safe, violations
    
    def _mask_text(self, text: str, vtype: ViolationType) -> str:
        """Mask sensitive text for logging"""
        if len(text) <= 4:
            return "*" * len(text)
        
        if vtype == ViolationType.PII_PHONE:
            return text[:3] + "****" + text[-4:]
        elif vtype == ViolationType.PII_ID_CARD:
            return text[:6] + "********" + text[-4:]
        elif vtype == ViolationType.PII_BANK_CARD:
            return text[:4] + " **** **** " + text[-4:]
        elif vtype == ViolationType.PII_EMAIL:
            parts = text.split("@")
            if len(parts) == 2:
                return parts[0][:2] + "***@" + parts[1]
        
        return text[:2] + "***" + text[-2:]
    
    def sanitize(self, content: str) -> Tuple[str, List[Violation]]:
        """
        Scan and sanitize content by replacing sensitive information.
        Returns (sanitized_content, list_of_violations)
        """
        is_safe, violations = self.scan(content)
        
        if is_safe:
            return content, violations
        
        # Sort violations by position (reverse order for replacement)
        sorted_violations = sorted(violations, key=lambda v: v.position[0], reverse=True)
        
        sanitized = content
        for violation in sorted_violations:
            start, end = violation.position
            sanitized = sanitized[:start] + violation.suggestion + sanitized[end:]
        
        return sanitized, violations
    
    def check_input(self, user_input: str) -> Tuple[bool, Optional[str]]:
        """
        Check user input for injection attempts.
        Returns (is_safe, warning_message)
        """
        for pattern in self._injection_patterns:
            if pattern.search(user_input):
                return False, "检测到可能的注入攻击，请修改您的输入。"
        
        return True, None
    
    def get_violation_summary(self, violations: List[Violation]) -> Dict:
        """Generate a summary of violations"""
        if not violations:
            return {"total": 0, "by_severity": {}, "by_type": {}}
        
        by_severity = {}
        by_type = {}
        
        for v in violations:
            by_severity[v.severity] = by_severity.get(v.severity, 0) + 1
            by_type[v.type.value] = by_type.get(v.type.value, 0) + 1
        
        return {
            "total": len(violations),
            "by_severity": by_severity,
            "by_type": by_type,
            "has_critical": by_severity.get("critical", 0) > 0
        }


# Global moderator instance
content_moderator = ContentModerator(strict_mode=False)


def scan_content(content: str) -> Tuple[bool, List[Violation]]:
    """Convenience function to scan content"""
    return content_moderator.scan(content)


def sanitize_output(content: str) -> str:
    """Convenience function to sanitize AI output"""
    sanitized, _ = content_moderator.sanitize(content)
    return sanitized


def check_user_input(user_input: str) -> Tuple[bool, Optional[str]]:
    """Convenience function to check user input"""
    return content_moderator.check_input(user_input)