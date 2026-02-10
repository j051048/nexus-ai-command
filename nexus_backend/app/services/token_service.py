"""
P1 Optimization: Token Counting and Cost Control Service
Tracks token usage, estimates costs, and enforces usage limits.
"""
import os
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import tiktoken for accurate counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not installed. Using approximate token counting.")


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
    
    P1 Fix #13: Hybrid approach - in-memory cache for fast limit checks,
    with async persistence to Supabase for durability across restarts.
    On startup, loads today's aggregates from DB to restore state.
    """
    
    def __init__(self):
        self._usage: Dict[str, Dict] = {}  # In-memory cache (fast path)
        self._db_loaded: Dict[str, bool] = {}  # Track which users have been loaded from DB
        self._limits = UsageLimits(
            max_tokens_per_request=int(os.getenv("MAX_TOKENS_PER_REQUEST", 100000)),
            max_tokens_per_day=int(os.getenv("MAX_TOKENS_PER_DAY", 1000000)),
            max_cost_per_day_usd=float(os.getenv("MAX_COST_PER_DAY_USD", 50.0)),
            max_requests_per_day=int(os.getenv("MAX_REQUESTS_PER_DAY", 1000))
        )
    
    def _get_day_key(self) -> str:
        """Get current day key for tracking"""
        return time.strftime("%Y-%m-%d")
    
    async def _load_from_db(self, user_id: str) -> Dict:
        """
        Load today's aggregate usage from Supabase.
        Called once per user per process lifetime (lazy init).
        """
        day_key = self._get_day_key()
        cache_key = f"{user_id}:{day_key}"
        
        if cache_key in self._db_loaded:
            return self._usage.get(cache_key, self._make_empty(day_key))
        
        try:
            from app.core.database import supabase
            if supabase:
                res = await supabase.table("token_usage_daily").select("*") \
                    .eq("user_id", user_id).eq("usage_date", day_key) \
                    .maybe_single().execute()
                
                if res.data:
                    self._usage[cache_key] = {
                        "tokens": res.data.get("total_tokens", 0),
                        "cost_usd": float(res.data.get("total_cost_usd", 0.0)),
                        "requests": res.data.get("request_count", 0),
                        "day": day_key
                    }
                else:
                    self._usage[cache_key] = self._make_empty(day_key)
            else:
                self._usage[cache_key] = self._make_empty(day_key)
        except Exception as e:
            logger.warning(f"Failed to load usage from DB for {user_id}: {e}")
            self._usage[cache_key] = self._usage.get(cache_key, self._make_empty(day_key))
        
        self._db_loaded[cache_key] = True
        return self._usage[cache_key]
    
    def _make_empty(self, day_key: str) -> Dict:
        return {"tokens": 0, "cost_usd": 0.0, "requests": 0, "day": day_key}
    
    def _get_user_usage_sync(self, user_id: str) -> Dict:
        """Sync getter for in-memory cache (used by check_limits)."""
        day_key = self._get_day_key()
        key = f"{user_id}:{day_key}"
        if key not in self._usage:
            self._usage[key] = self._make_empty(day_key)
        return self._usage[key]
    
    def check_limits(self, user_id: str, estimated_tokens: int) -> Tuple[bool, str]:
        """
        Check if request is within limits.
        Uses in-memory cache for speed (DB state loaded on first access).
        Returns (is_allowed, reason_if_blocked)
        """
        # Check per-request limit
        if estimated_tokens > self._limits.max_tokens_per_request:
            return False, f"Request exceeds maximum tokens ({estimated_tokens} > {self._limits.max_tokens_per_request})"
        
        usage = self._get_user_usage_sync(user_id)
        
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
    
    async def ensure_loaded(self, user_id: str):
        """Ensure user's daily usage is loaded from DB into memory cache."""
        await self._load_from_db(user_id)
    
    def record_usage(self, user_id: str, usage: TokenUsage):
        """Record token usage in memory. Caller should also call persist_usage()."""
        user_usage = self._get_user_usage_sync(user_id)
        user_usage["tokens"] += usage.total_tokens
        user_usage["cost_usd"] += usage.estimated_cost_usd
        user_usage["requests"] += 1
    
    async def persist_usage(self, user_id: str, usage: TokenUsage):
        """
        P1 Fix #13: Persist individual usage record AND update daily aggregate in Supabase.
        Uses upsert for the daily aggregate to handle concurrent writes.
        """
        day_key = self._get_day_key()
        
        try:
            from app.core.database import supabase
            if not supabase:
                return
            
            # 1. Insert individual usage record (append-only log)
            await supabase.table("token_usage_log").insert({
                "user_id": user_id,
                "usage_date": day_key,
                "model": usage.model,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
                "cost_usd": usage.estimated_cost_usd,
            }).execute()
            
            # 2. Upsert daily aggregate (idempotent via ON CONFLICT)
            current = self._get_user_usage_sync(user_id)
            await supabase.rpc("upsert_daily_token_usage", {
                "p_user_id": user_id,
                "p_date": day_key,
                "p_tokens": usage.total_tokens,
                "p_cost": usage.estimated_cost_usd,
            }).execute()
            
        except Exception as e:
            logger.error(f"Failed to persist usage to DB for {user_id}: {e}")
            # Non-fatal: in-memory tracking still works for this process
    
    def get_usage_summary(self, user_id: str) -> Dict:
        """Get usage summary for user"""
        usage = self._get_user_usage_sync(user_id)
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
        """Remove entries from previous days (memory only)"""
        current_day = self._get_day_key()
        keys_to_remove = [k for k in self._usage.keys() if not k.endswith(current_day)]
        for key in keys_to_remove:
            del self._usage[key]
        # Also reset db_loaded tracker for old days
        loaded_to_remove = [k for k in self._db_loaded.keys() if not k.endswith(current_day)]
        for key in loaded_to_remove:
            del self._db_loaded[key]


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


async def record_completion(user_id: str, input_tokens: int, output_tokens: int, model: str) -> TokenUsage:
    """
    Record a completed API call.
    P1 Fix #13: Now async — persists to Supabase in addition to in-memory cache.
    """
    cost = token_counter.estimate_cost(input_tokens, output_tokens, model)
    usage = TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated_cost_usd=cost,
        model=model
    )
    usage_tracker.record_usage(user_id, usage)
    # Persist to database (non-blocking, errors are logged but don't fail the request)
    await usage_tracker.persist_usage(user_id, usage)
    return usage