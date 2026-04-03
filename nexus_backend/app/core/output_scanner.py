"""
LLM Output Security Scanner: Indirect Prompt Injection & Sensitive Data Detection

Complements app.services.content_moderation by adding:
- Indirect prompt injection patterns (LLM output hijacking)
- SSN / credit card / Chinese ID / phone PII patterns
- API key / password / connection string leak detection
- SQL injection patterns in tool outputs
- XSS patterns in outputs

Usage:
    from app.core.output_scanner import output_scanner
    result = await output_scanner.scan(llm_output)
    if not result.is_safe:
        sanitized = result.sanitized_text
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.core.logging_config import SecurityLogger, get_logger

logger = get_logger(__name__)
security_logger = SecurityLogger()


# ---------------------------------------------------------------------------
#  Data structures
# ---------------------------------------------------------------------------

@dataclass
class ScanResult:
    """Result of an output security scan."""

    is_safe: bool
    violations: list[str] = field(default_factory=list)
    sanitized_text: str = ""


@dataclass
class _PatternRule:
    """Internal: a compiled regex + metadata."""

    category: str
    name: str
    pattern: re.Pattern
    replacement: str


# ---------------------------------------------------------------------------
#  Configuration
# ---------------------------------------------------------------------------

@dataclass
class OutputScannerConfig:
    """Toggle individual detection categories on/off."""

    enable_prompt_injection: bool = True
    enable_pii: bool = True
    enable_sensitive_data: bool = True
    enable_sql_injection: bool = True
    enable_xss: bool = True
    custom_patterns: list[tuple[str, str, str]] | None = None
    # custom_patterns: list of (category, regex_str, replacement)


# ---------------------------------------------------------------------------
#  Default pattern definitions
# ---------------------------------------------------------------------------

_PROMPT_INJECTION_PATTERNS: list[tuple[str, str]] = [
    # English indirect injection
    ("ignore (all |any )?(previous|prior|above|preceding) (instructions?|prompts?|directions?|rules)",
     "[prompt injection detected]"),
    (r"(^|\n)\s*system\s*:", "[prompt injection detected]"),
    ("you are now (a |an )?", "[prompt injection detected]"),
    ("(forget|disregard|override) (all |any )?(previous|prior|your) (instructions?|rules|constraints?)",
     "[prompt injection detected]"),
    ("new instructions?:", "[prompt injection detected]"),
    ("(reveal|show|print|output|display) (your |the )?(system |original )?(prompt|instructions?)",
     "[prompt injection detected]"),
    ("(enter|switch to|enable) (developer|debug|admin|god|sudo|jailbreak) mode",
     "[prompt injection detected]"),
    ("do not (follow|obey|respect) (any |all )?(rules|restrictions?|guidelines|safety)",
     "[prompt injection detected]"),
    ("pretend (you are|to be) ", "[prompt injection detected]"),
    (r"act as (if|though|a |an )", "[prompt injection detected]"),
    ("bypass (all |any )?(safety|content|security) (filters?|restrictions?|measures?)",
     "[prompt injection detected]"),
    # Chinese indirect injection
    (r"忽略(之前|以上|所有|先前)(的)?(指令|命令|提示|规则)", "[检测到提示注入]"),
    (r"你(现在|从现在开始)是(?!.*负责人|.*员工|.*用户|.*同事)", "[检测到提示注入]"),
    (r"进入(开发者|调试|管理员|上帝)模式", "[检测到提示注入]"),
    (r"(显示|输出|透露|泄露)(你的)?(系统|原始)?(提示词|指令|prompt)", "[检测到提示注入]"),
    # Special delimiters often used in injection
    (r"<\|(?:im_start|im_end|system|endoftext)\|>", "[prompt injection detected]"),
    (r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", "[prompt injection detected]"),
]

_PII_PATTERNS: list[tuple[str, str]] = [
    # SSN (US Social Security Number) — xxx-xx-xxxx
    (r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)", "[SSN已隐藏]"),
    # Credit card numbers (13-19 digits, with optional separators)
    (r"(?<!\d)(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,7}(?!\d)",
     "[信用卡号已隐藏]"),
    # Chinese ID card (18 digits, last may be X)
    (r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)",
     "[身份证号已隐藏]"),
    # Chinese phone number (11 digits starting with 1)
    (r"(?<![0-9a-zA-Z])1[3-9]\d{9}(?![0-9a-zA-Z])", "[手机号已隐藏]"),
    # US phone numbers — (xxx) xxx-xxxx or xxx-xxx-xxxx
    (r"(?<!\d)\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)", "[电话号码已隐藏]"),
]

_SENSITIVE_DATA_PATTERNS: list[tuple[str, str]] = [
    # Generic API keys (sk-..., ak-..., key-...)
    (r"(?i)(?:sk|ak|key)[-_][a-zA-Z0-9]{20,}", "[API密钥已隐藏]"),
    # AWS-style keys
    (r"(?:AKIA|ASIA)[A-Z0-9]{16}", "[AWS密钥已隐藏]"),
    # password = "...", password: "..."
    (r'(?i)(?:password|passwd|pwd|secret|token)\s*[:=]\s*["\']?[^\s\n"\']{8,}["\']?',
     "[敏感凭证已隐藏]"),
    # Connection strings (postgres://, mysql://, mongodb://, redis://)
    (r"(?i)(?:postgres|mysql|mongodb|redis|amqp)://[^\s]+", "[连接字符串已隐藏]"),
    # Private keys
    (r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----", "[私钥已隐藏]"),
    # Bearer tokens
    (r"(?i)bearer\s+[a-zA-Z0-9_\-.]{20,}", "[Token已隐藏]"),
]

_SQL_INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Classic SQL injection fragments in tool output
    (r"(?i)(?:'\s*(?:OR|AND)\s+['\d]+=\s*['\d]+)", "[SQL注入已过滤]"),
    (r"(?i)(?:UNION\s+(?:ALL\s+)?SELECT)", "[SQL注入已过滤]"),
    (r"(?i)(?:;\s*DROP\s+TABLE)", "[SQL注入已过滤]"),
    (r"(?i)(?:;\s*DELETE\s+FROM\s+\w+\s*(?:;|$|WHERE\s+1\s*=\s*1))", "[SQL注入已过滤]"),
    (r"(?i)(?:['\)]\s*--\s*$|/\*.*?\*/)", "[SQL注入已过滤]"),
    (r"(?i)(?:'\s*;\s*(?:INSERT|UPDATE|ALTER|CREATE|EXEC))", "[SQL注入已过滤]"),
]

_XSS_PATTERNS: list[tuple[str, str]] = [
    # Script tags
    (r"(?i)<\s*script[^>]*>", "[XSS已过滤]"),
    (r"(?i)</\s*script\s*>", "[XSS已过滤]"),
    # Event handlers in HTML attributes
    (r'(?i)\bon\w+\s*=\s*["\']?[^"\'>\s]+', "[XSS已过滤]"),
    # javascript: protocol
    (r"(?i)javascript\s*:", "[XSS已过滤]"),
    # data: URI with script content
    (r"(?i)data\s*:\s*text/html", "[XSS已过滤]"),
    # iframe / object / embed injection
    (r"(?i)<\s*(?:iframe|object|embed|applet|form|meta)\b[^>]*>", "[XSS已过滤]"),
    # SVG onload
    (r"(?i)<\s*svg[^>]*\bon\w+\s*=", "[XSS已过滤]"),
]


# ---------------------------------------------------------------------------
#  OutputScanner
# ---------------------------------------------------------------------------

class OutputScanner:
    """
    Scans LLM outputs for security threats and sensitive data leakage.

    Designed for *indirect* prompt injection detection in model outputs,
    complementing the *input* injection checks in content_moderation.py.
    """

    def __init__(self, config: OutputScannerConfig | None = None):
        self._config = config or OutputScannerConfig()
        self._rules: list[_PatternRule] = []
        self._compile_rules()

    # -- initialisation ----------------------------------------------------

    def _compile_rules(self) -> None:
        """Pre-compile all enabled pattern rules."""
        self._rules.clear()

        def _add(category: str, raw: Sequence[tuple[str, str]]) -> None:
            for idx, (pat, repl) in enumerate(raw):
                try:
                    compiled = re.compile(pat, re.IGNORECASE | re.MULTILINE)
                    self._rules.append(
                        _PatternRule(
                            category=category,
                            name=f"{category}_{idx}",
                            pattern=compiled,
                            replacement=repl,
                        )
                    )
                except re.error as exc:
                    logger.warning(f"[OutputScanner] Bad regex in {category}_{idx}: {exc}")

        if self._config.enable_prompt_injection:
            _add("prompt_injection", _PROMPT_INJECTION_PATTERNS)
        if self._config.enable_pii:
            _add("pii", _PII_PATTERNS)
        if self._config.enable_sensitive_data:
            _add("sensitive_data", _SENSITIVE_DATA_PATTERNS)
        if self._config.enable_sql_injection:
            _add("sql_injection", _SQL_INJECTION_PATTERNS)
        if self._config.enable_xss:
            _add("xss", _XSS_PATTERNS)

        # Append user-supplied custom patterns
        if self._config.custom_patterns:
            for category, pat_str, repl in self._config.custom_patterns:
                try:
                    compiled = re.compile(pat_str, re.IGNORECASE | re.MULTILINE)
                    self._rules.append(
                        _PatternRule(
                            category=category,
                            name=f"custom_{category}",
                            pattern=compiled,
                            replacement=repl,
                        )
                    )
                except re.error as exc:
                    logger.warning(f"[OutputScanner] Bad custom regex ({category}): {exc}")

    # -- public API --------------------------------------------------------

    async def scan(self, text: str) -> ScanResult:
        """
        Scan *text* for all enabled threat categories.

        Returns a ``ScanResult`` with ``is_safe``, ``violations``, and
        ``sanitized_text`` (with detected patterns redacted).
        """
        if not text:
            return ScanResult(is_safe=True, violations=[], sanitized_text=text or "")

        violations: list[str] = []
        sanitized = text

        for rule in self._rules:
            matches = list(rule.pattern.finditer(sanitized))
            if not matches:
                continue

            for m in matches:
                snippet = m.group()
                if len(snippet) > 80:
                    snippet = snippet[:77] + "..."
                violations.append(f"[{rule.category}] {rule.name}: {snippet}")

            # Replace all occurrences in one pass
            sanitized = rule.pattern.sub(rule.replacement, sanitized)

        is_safe = len(violations) == 0

        if not is_safe:
            # Log via security logger
            security_logger.suspicious_activity(
                user_id=None,
                activity="llm_output_violation",
                details=f"{len(violations)} violation(s): {', '.join(v.split(':')[0] for v in violations[:5])}",
            )

        return ScanResult(
            is_safe=is_safe,
            violations=violations,
            sanitized_text=sanitized,
        )

    def sanitize(self, text: str) -> str:
        """
        Synchronous convenience: redact all detected sensitive data.

        For the full async scan (with logging), use ``await scan(text)``.
        """
        if not text:
            return text or ""

        sanitized = text
        for rule in self._rules:
            sanitized = rule.pattern.sub(rule.replacement, sanitized)
        return sanitized


# ---------------------------------------------------------------------------
#  Module-level singleton
# ---------------------------------------------------------------------------

output_scanner = OutputScanner()
