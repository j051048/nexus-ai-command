"""
P1 Optimization: Token Counting and Cost Control Service
Tracks token usage, estimates costs, and enforces usage limits.
"""
import os
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Try to import tiktoken for accurate counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    print("⚠️ tiktoken not installed. Using approximate token counting.")


class ModelPricing(Enum):
    """Pricing per 1M tokens (input, output) in USD"""
    GPT_4O = (2.50, 10.00)
    GPT_4O_MINI = (0.15, 0.60)
    GPT_4_TURBO = (10.00, 30.00)
    GPT_35_TURBO = (0.50, 1.50)
    GEMINI_PRO = (1.25, 5.00)
    GEMINI_FLASH = (0.075, 0.30)
    CLAUDE_3_OPUS = (15.00, 75.00)
    CLAUDE_3_SONNET = (3.00, 15.00)
    CLAUDE_3_HAIKU = (0.25, 1.25)
    TEXT_EMBEDDING_3_SMALL = (0.02, 0.0)
    TEXT_EMBEDDING_3_LARGE = (0.13, 0.0)
    DEFAULT = (5.00, 15.00)  # Conservative default


MODEL_MAPPING = {
    "gpt-4o": ModelPricing.GPT_4O,
    "gpt-4o-mini": ModelPricing.GPT_4O_MINI,
    "gpt-4-turbo": ModelPricing.GPT_4_TURBO,
    "gpt-4-turbo-preview": ModelPricing.GPT_4_TURBO,
    "gpt-3.5-turbo": ModelPricing.GPT_35_TURBO,
    "gemini-pro": ModelPricing.GEMINI_PRO,
    "gemini-2.5-pro": ModelPricing.GEMINI_PRO,
    "gemini-3-pro-preview": ModelPricing.GEMINI_PRO,
    "gemini-flash": ModelPricing.GEMINI_FLASH,
    "claude-3-opus": ModelPricing.CLAUDE_3_OPUS,
    "claude-3-sonnet": ModelPricing.CLAUDE_3_SONNET,
    "claude-3-haiku": ModelPricing.CLAUDE_3_HAIKU,
    "text-embedding-3-small": ModelPricing.TEXT_EMBEDDING_3_SMALL,
    "text-embedding-3-large": ModelPricing.TEXT_EMBEDDING_3_LARGE,
}


@dataclass
class TokenUsage:
    """Token usage statistics"""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    model: str


@dataclass
class UsageLimits:
    """Usage limits configuration"""
    max_tokens_per_request: int = 100000
    max_tokens_per_day: int = 1000000
    max_cost_per_day_usd: float = 50.0
    max_requests_per_day: int = 1000


class TokenCounter:
    """
    Token counter with tiktoken support and fallback.
    """
    
    def __init__(self):
        self._encoders: Dict[str, any] = {}
    
    def _get_encoder(self, model: str):
        """Get or create encoder for model"""
        if not TIKTOKEN_AVAILABLE:
            return None
        
        if model not in self._encoders:
            try:
                self._encoders[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback to cl100k_base for unknown models
                self._encoders[model] = tiktoken.get_encoding("cl100k_base")
        
        return self._encoders[model]
    
    def count_tokens(self, text: str, model: str = "gpt-4o") -> int:
        """Count tokens in text"""
        if not text:
            return 0
        
        encoder = self._get_encoder(model)
        if encoder:
            return len(encoder.encode(text))
        
        # Fallback: approximate count (1 token ≈ 4 characters for English, 2 for Chinese)
        # This is a rough estimate
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
    
    def count_messages_tokens(self, messages: List[Dict], model: str = "gpt-4o") -> int:
        """Count tokens in a list of messages"""
        total = 0
        for msg in messages:
            # Count role + content
            total += self.count_tokens(msg.get("role", ""), model)
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.count_tokens(content, model)
            elif isinstance(content, list):
                # Handle multimodal content
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        total += self.count_tokens(item.get("text", ""), model)
            # Add overhead per message (approximately 4 tokens per message)
            total += 4
        # Add overhead for the conversation structure
        total += 3
        return total
    
    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost in USD"""
        pricing = MODEL_MAPPING.get(model.lower(), ModelPricing.DEFAULT).value
        input_cost = (input_tokens / 1_000_000) * pricing[0]
        output_cost = (output_tokens / 1_000_000) * pricing[1]
        return round(input_cost + output_cost, 6)


class UsageTracker:
    """
    Track and enforce usage limits per user.
    Uses in-memory storage with daily reset (should use Redis in production).
    """
    
    def __init__(self):
        self._usage: Dict[str, Dict] = {}
        self._limits = UsageLimits(
            max_tokens_per_request=int(os.getenv("MAX_TOKENS_PER_REQUEST", 100000)),
            max_tokens_per_day=int(os.getenv("MAX_TOKENS_PER_DAY", 1000000)),
            max_cost_per_day_usd=float(os.getenv("MAX_COST_PER_DAY_USD", 50.0)),
            max_requests_per_day=int(os.getenv("MAX_REQUESTS_PER_DAY", 1000))
        )
    
    def _get_day_key(self) -> str:
        """Get current day key for tracking"""
        return time.strftime("%Y-%m-%d")
    
    def _get_user_usage(self, user_id: str) -> Dict:
        """Get or initialize user usage for today"""
        day_key = self._get_day_key()
        key = f"{user_id}:{day_key}"
        
        if key not in self._usage:
            self._usage[key] = {
                "tokens": 0,
                "cost_usd": 0.0,
                "requests": 0,
                "day": day_key
            }
        
        return self._usage[key]
    
    def check_limits(self, user_id: str, estimated_tokens: int) -> Tuple[bool, str]:
        """
        Check if request is within limits.
        Returns (is_allowed, reason_if_blocked)
        """
        # Check per-request limit
        if estimated_tokens > self._limits.max_tokens_per_request:
            return False, f"Request exceeds maximum tokens ({estimated_tokens} > {self._limits.max_tokens_per_request})"
        
        usage = self._get_user_usage(user_id)
        
        # Check daily request count
        if usage["requests"] >= self._limits.max_requests_per_day:
            return False, f"Daily request limit reached ({self._limits.max_requests_per_day})"
        
        # Check daily token limit
        if usage["tokens"] + estimated_tokens > self._limits.max_tokens_per_day:
            return False, f"Daily token limit would be exceeded"
        
        # Check daily cost limit
        if usage["cost_usd"] >= self._limits.max_cost_per_day_usd:
            return False, f"Daily cost limit reached (${self._limits.max_cost_per_day_usd})"
        
        return True, ""
    
    def record_usage(self, user_id: str, usage: TokenUsage):
        """Record token usage for a request"""
        user_usage = self._get_user_usage(user_id)
        user_usage["tokens"] += usage.total_tokens
        user_usage["cost_usd"] += usage.estimated_cost_usd
        user_usage["requests"] += 1
    
    def get_usage_summary(self, user_id: str) -> Dict:
        """Get usage summary for user"""
        usage = self._get_user_usage(user_id)
        return {
            "date": usage["day"],
            "tokens_used": usage["tokens"],
            "tokens_limit": self._limits.max_tokens_per_day,
            "tokens_remaining": max(0, self._limits.max_tokens_per_day - usage["tokens"]),
            "cost_usd": round(usage["cost_usd"], 4),
            "cost_limit_usd": self._limits.max_cost_per_day_usd,
            "requests": usage["requests"],
            "requests_limit": self._limits.max_requests_per_day
        }
    
    def cleanup_old_entries(self):
        """Remove entries from previous days"""
        current_day = self._get_day_key()
        keys_to_remove = [k for k in self._usage.keys() if not k.endswith(current_day)]
        for key in keys_to_remove:
            del self._usage[key]


# Global instances
token_counter = TokenCounter()
usage_tracker = UsageTracker()


def validate_request_tokens(messages: List[Dict], model: str, user_id: str) -> Tuple[bool, int, str]:
    """
    Validate that a request is within token/usage limits.
    Returns (is_valid, token_count, error_message)
    """
    token_count = token_counter.count_messages_tokens(messages, model)
    is_allowed, reason = usage_tracker.check_limits(user_id, token_count)
    return is_allowed, token_count, reason


def record_completion(user_id: str, input_tokens: int, output_tokens: int, model: str) -> TokenUsage:
    """Record a completed API call"""
    cost = token_counter.estimate_cost(input_tokens, output_tokens, model)
    usage = TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated_cost_usd=cost,
        model=model
    )
    usage_tracker.record_usage(user_id, usage)
    return usage