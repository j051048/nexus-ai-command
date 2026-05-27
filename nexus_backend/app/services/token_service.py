"""
P1 Optimization: Token Counting and Cost Control Service
Tracks token usage, estimates costs, and enforces usage limits.
"""

import collections
import logging
import os
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import tiktoken for accurate counting
try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not installed. Using approximate token counting.")

# ─── Re-export from canonical pricing module for backwards compatibility ────
from app.core.model_pricing import (
    DEFAULT_PRICE as DEFAULT_PRICE,
)
from app.core.model_pricing import (  # noqa: E402, F401
    MODEL_PRICES as MODEL_PRICES,
)
from app.core.model_pricing import (
    estimate_cost as _estimate_cost,
)

# Legacy aliases — some call sites import these names
ModelPricing = None  # Removed: use model_pricing.estimate_cost() directly
MODEL_MAPPING = None  # Removed: use model_pricing.MODEL_PRICES directly


@dataclass
class TokenUsage:
    """Token usage statistics"""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    model: str
    department_id: str | None = None
    project_id: str | None = None


@dataclass
class UsageLimits:
    """Usage limits configuration"""

    max_tokens_per_request: int = 100000
    max_tokens_per_day: int = 1000000
    max_cost_per_day_usd: float = 50.0
    max_requests_per_day: int = 1000
    # P1 Fix #13: Org-wide limits
    max_tokens_per_org_day: int = 10000000
    max_cost_per_org_day_usd: float = 500.0
    max_requests_per_org_day: int = 10000
    # TPM (Tokens Per Minute) 限制 — 防止短时间高成本突发
    max_tokens_per_minute: int = 200000


class TokenCounter:
    """
    Token counter with tiktoken support and fallback.
    """

    def __init__(self):
        self._encoders: dict[str, any] = {}

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

    def count_tokens(self, text: str, model: str = "deepseek-v4-flash") -> int:
        """Count tokens in text"""
        if not text:
            return 0

        encoder = self._get_encoder(model)
        if encoder:
            return len(encoder.encode(text))

        # Fallback: approximate count (1 token ≈ 4 characters for English, 2 for Chinese)
        # This is a rough estimate
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)

    def count_messages_tokens(
        self, messages: list[dict], model: str = "deepseek-v4-flash"
    ) -> int:
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
        """Estimate cost in USD — delegates to canonical model_pricing module."""
        return _estimate_cost(input_tokens, output_tokens, model)

    def estimate_prompt_tokens(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "deepseek-v4-flash",
    ) -> int:
        """Estimate total prompt tokens including system prompt, messages, and tool schemas."""
        total = self.count_tokens(system_prompt, model)
        total += self.count_messages_tokens(messages, model)
        if tools:
            import json

            tools_text = json.dumps(tools, ensure_ascii=False)
            total += self.count_tokens(tools_text, model)
        return total


class UsageTracker:
    """
    Track and enforce usage limits per user.

    P1 Fix #13: Hybrid approach - in-memory cache for fast limit checks,
    with async persistence to Supabase for durability across restarts.
    On startup, loads today's aggregates from DB to restore state.
    """

    def __init__(self):
        self._usage: dict[str, dict] = {}  # In-memory cache (fast path)
        self._db_loaded: dict[str, bool] = (
            {}
        )  # Track which users have been loaded from DB
        self._limits = UsageLimits(
            max_tokens_per_request=int(os.getenv("MAX_TOKENS_PER_REQUEST", 100000)),
            max_tokens_per_day=int(os.getenv("MAX_TOKENS_PER_DAY", 1000000)),
            max_cost_per_day_usd=float(os.getenv("MAX_COST_PER_DAY_USD", 50.0)),
            max_requests_per_day=int(os.getenv("MAX_REQUESTS_PER_DAY", 1000)),
            max_tokens_per_org_day=int(os.getenv("MAX_TOKENS_PER_ORG_DAY", 10000000)),
            max_cost_per_org_day_usd=float(
                os.getenv("MAX_COST_PER_ORG_DAY_USD", 500.0)
            ),
            max_tokens_per_minute=int(os.getenv("MAX_TOKENS_PER_MINUTE", 200000)),
        )
        self._org_usage: dict[str, dict] = {}  # In-memory cache for org totals
        self._user_to_org: dict[str, str] = {}  # User ID to Org ID cache
        # TPM 滑动窗口: user_id -> deque of (timestamp, token_count)
        self._tpm_window: dict[str, collections.deque] = {}

    def _get_day_key(self) -> str:
        """Get current day key for tracking"""
        return time.strftime("%Y-%m-%d")

    async def _load_from_db(self, user_id: str) -> dict:
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
                # P1 Fix #13: Load user usage and org ID
                res = (
                    await supabase.table("user_token_usage")
                    .select(
                        "user_id, org_id, total_tokens, estimated_cost_usd, request_count"
                    )
                    .eq("user_id", user_id)
                    .eq("date", day_key)
                    .maybe_single()
                    .execute()
                )

                # Also fetch user's org_id to ensure we can track org-wide usage
                if not res or not res.data or not res.data.get("org_id"):
                    user_res = (
                        await supabase.table("users")
                        .select("organization_id")
                        .eq("id", user_id)
                        .maybe_single()
                        .execute()
                    )
                    org_id = (
                        user_res.data.get("organization_id")
                        if user_res and user_res.data
                        else None
                    )
                else:
                    org_id = res.data.get("org_id")

                if org_id:
                    self._user_to_org[user_id] = org_id
                    # Load org totals if not already cached
                    org_key = f"org:{org_id}:{day_key}"
                    if org_key not in self._org_usage:
                        org_res = (
                            await supabase.table("user_token_usage")
                            .select("total_tokens, estimated_cost_usd, request_count")
                            .eq("org_id", org_id)
                            .eq("date", day_key)
                            .execute()
                        )

                        org_totals = {"tokens": 0, "cost": 0.0, "requests": 0}
                        for r in org_res.data or []:
                            org_totals["tokens"] += r.get("total_tokens", 0)
                            org_totals["cost"] += float(
                                r.get("estimated_cost_usd", 0.0)
                            )
                            org_totals["requests"] += r.get("request_count", 0)
                        self._org_usage[org_key] = org_totals

                if res and res.data:
                    self._usage[cache_key] = {
                        "tokens": res.data.get("total_tokens", 0),
                        "cost_usd": float(res.data.get("estimated_cost_usd", 0.0)),
                        "requests": res.data.get("request_count", 0),
                        "day": day_key,
                    }
                else:
                    self._usage[cache_key] = self._make_empty(day_key)
            else:
                self._usage[cache_key] = self._make_empty(day_key)
        except Exception as e:
            logger.warning(f"Failed to load usage from DB for {user_id}: {e}")
            self._usage[cache_key] = self._usage.get(
                cache_key, self._make_empty(day_key)
            )

        self._db_loaded[cache_key] = True
        return self._usage[cache_key]

    def _make_empty(self, day_key: str) -> dict:
        return {"tokens": 0, "cost_usd": 0.0, "requests": 0, "day": day_key}

    def _get_user_usage_sync(self, user_id: str) -> dict:
        """Sync getter for in-memory cache (used by check_limits)."""
        day_key = self._get_day_key()
        key = f"{user_id}:{day_key}"
        if key not in self._usage:
            self._usage[key] = self._make_empty(day_key)
        return self._usage[key]

    def check_limits(self, user_id: str, estimated_tokens: int) -> tuple[bool, str]:
        """
        Check if request is within limits.
        Uses in-memory cache for speed (DB state loaded on first access).
        Returns (is_allowed, reason_if_blocked)
        """
        # Check per-request limit
        if estimated_tokens > self._limits.max_tokens_per_request:
            return (
                False,
                f"Request exceeds maximum tokens ({estimated_tokens} > {self._limits.max_tokens_per_request})",
            )

        # TPM (Tokens Per Minute) 滑动窗口检查 — 防止短时间突发高成本
        now = time.time()
        window = self._tpm_window.get(user_id)
        if window is None:
            window = collections.deque()
            self._tpm_window[user_id] = window
        # 清除 60 秒前的记录
        cutoff = now - 60
        while window and window[0][0] < cutoff:
            window.popleft()
        tokens_in_window = sum(t for _, t in window)
        if tokens_in_window + estimated_tokens > self._limits.max_tokens_per_minute:
            return (
                False,
                f"Token rate limit exceeded ({tokens_in_window + estimated_tokens} > "
                f"{self._limits.max_tokens_per_minute} tokens/min)",
            )

        usage = self._get_user_usage_sync(user_id)

        # Check daily request count
        if usage["requests"] >= self._limits.max_requests_per_day:
            return (
                False,
                f"Daily request limit reached ({self._limits.max_requests_per_day})",
            )

        # Check daily token limit
        if usage["tokens"] + estimated_tokens > self._limits.max_tokens_per_day:
            return False, "Daily token limit would be exceeded"

        # Check daily cost limit
        if usage["cost_usd"] >= self._limits.max_cost_per_day_usd:
            return (
                False,
                f"Daily cost limit reached (${self._limits.max_cost_per_day_usd})",
            )

        # P1 Fix #13: Org-level checks
        org_id = self._user_to_org.get(user_id)
        if org_id:
            org_usage = self._org_usage.get(f"org:{org_id}:{self._get_day_key()}")
            if org_usage:
                if (
                    org_usage["tokens"] + estimated_tokens
                    > self._limits.max_tokens_per_org_day
                ):
                    return False, "Organization daily token limit exceeded"
                if org_usage["cost"] >= self._limits.max_cost_per_org_day_usd:
                    return False, "Organization daily cost limit reached"

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

        # TPM 滑动窗口记录
        window = self._tpm_window.get(user_id)
        if window is None:
            window = collections.deque()
            self._tpm_window[user_id] = window
        window.append((time.time(), usage.total_tokens))

        # P1 Fix #13: Update org aggregate
        org_id = self._user_to_org.get(user_id)
        if org_id:
            org_key = f"org:{org_id}:{self._get_day_key()}"
            if org_key in self._org_usage:
                self._org_usage[org_key]["tokens"] += usage.total_tokens
                self._org_usage[org_key]["cost"] += usage.estimated_cost_usd
                self._org_usage[org_key]["requests"] += 1

    async def persist_usage(self, user_id: str, usage: TokenUsage):
        """
        P1 Fix #13: Persist individual usage record AND update daily aggregate in Supabase.
        Uses upsert for the daily aggregate to handle concurrent writes.
        """
        day_key = self._get_day_key()
        org_id = self._user_to_org.get(user_id)

        try:
            from app.core.database import supabase

            if not supabase:
                return

            # 1. Update daily aggregate (idempotent via RPC with org_id)
            await supabase.rpc(
                "upsert_daily_token_usage",
                {
                    "p_user_id": user_id,
                    "p_org_id": org_id,
                    "p_date": day_key,
                    "p_tokens": usage.total_tokens,
                    "p_cost": usage.estimated_cost_usd,
                    "p_department_id": usage.department_id,
                    "p_project_id": usage.project_id,
                },
            ).execute()

        except Exception as e:
            logger.error(f"Failed to persist usage to DB for {user_id}: {e}")
            # Non-fatal: in-memory tracking still works for this process

    def get_usage_summary(self, user_id: str) -> dict:
        """Get usage summary for user"""
        usage = self._get_user_usage_sync(user_id)
        return {
            "date": usage["day"],
            "tokens_used": usage["tokens"],
            "tokens_limit": self._limits.max_tokens_per_day,
            "tokens_remaining": max(
                0, self._limits.max_tokens_per_day - usage["tokens"]
            ),
            "cost_usd": round(usage["cost_usd"], 4),
            "cost_limit_usd": self._limits.max_cost_per_day_usd,
            "requests": usage["requests"],
            "requests_limit": self._limits.max_requests_per_day,
        }

    def cleanup_old_entries(self):
        """Remove entries from previous days (memory only)"""
        current_day = self._get_day_key()
        keys_to_remove = [k for k in self._usage if not k.endswith(current_day)]
        for key in keys_to_remove:
            del self._usage[key]
        # Also reset db_loaded tracker for old days
        loaded_to_remove = [k for k in self._db_loaded if not k.endswith(current_day)]
        for key in loaded_to_remove:
            del self._db_loaded[key]

    async def get_cost_report(self, org_id: str, days: int = 30, db=None) -> dict:
        """
        #30 LLM Cost Attribution: Aggregate cost by department and project.
        Returns breakdown for the requested period.
        """
        if not db:
            try:
                from app.core.database import supabase

                db = supabase
            except Exception:
                pass

        report = {
            "org_id": org_id,
            "period_days": days,
            "by_department": [],
            "by_project": [],
            "by_model": [],
            "total_cost_usd": 0.0,
            "total_tokens": 0,
        }

        if not db:
            return report

        try:
            res = await db.rpc(
                "get_cost_report",
                {
                    "p_org_id": org_id,
                    "p_days": days,
                },
            ).execute()

            if res.data:
                data = (
                    res.data
                    if isinstance(res.data, dict)
                    else (res.data[0] if res.data else {})
                )
                report.update(
                    {
                        "by_department": data.get("by_department", []),
                        "by_project": data.get("by_project", []),
                        "by_model": data.get("by_model", []),
                        "total_cost_usd": data.get("total_cost_usd", 0.0),
                        "total_tokens": data.get("total_tokens", 0),
                    }
                )
        except Exception as e:
            logger.warning(f"Cost report RPC failed, using fallback: {e}")
            # Fallback: aggregate from daily usage table
            try:
                res = (
                    await db.table("user_token_usage")
                    .select(
                        "total_tokens, estimated_cost_usd, department_id, project_id"
                    )
                    .eq("org_id", org_id)
                    .execute()
                )
                dept_map: dict[str, dict] = {}
                proj_map: dict[str, dict] = {}
                total_cost = 0.0
                total_tokens = 0
                for row in res.data or []:
                    cost = float(row.get("estimated_cost_usd", 0))
                    tokens = row.get("total_tokens", 0)
                    total_cost += cost
                    total_tokens += tokens

                    dept = row.get("department_id") or "unassigned"
                    if dept not in dept_map:
                        dept_map[dept] = {
                            "department_id": dept,
                            "cost_usd": 0.0,
                            "tokens": 0,
                        }
                    dept_map[dept]["cost_usd"] += cost
                    dept_map[dept]["tokens"] += tokens

                    proj = row.get("project_id") or "unassigned"
                    if proj not in proj_map:
                        proj_map[proj] = {
                            "project_id": proj,
                            "cost_usd": 0.0,
                            "tokens": 0,
                        }
                    proj_map[proj]["cost_usd"] += cost
                    proj_map[proj]["tokens"] += tokens

                report["by_department"] = sorted(
                    dept_map.values(), key=lambda x: x["cost_usd"], reverse=True
                )
                report["by_project"] = sorted(
                    proj_map.values(), key=lambda x: x["cost_usd"], reverse=True
                )
                report["total_cost_usd"] = round(total_cost, 4)
                report["total_tokens"] = total_tokens
            except Exception as e2:
                logger.error(f"Cost report fallback failed: {e2}")

        return report


# Global instances
token_counter = TokenCounter()
usage_tracker = UsageTracker()


def validate_request_tokens(
    messages: list[dict], model: str, user_id: str
) -> tuple[bool, int, str]:
    """
    Validate that a request is within token/usage limits.
    Returns (is_valid, token_count, error_message)
    """
    token_count = token_counter.count_messages_tokens(messages, model)
    is_allowed, reason = usage_tracker.check_limits(user_id, token_count)
    return is_allowed, token_count, reason


async def record_completion(
    user_id: str, input_tokens: int, output_tokens: int, model: str
) -> TokenUsage:
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
        model=model,
    )
    usage_tracker.record_usage(user_id, usage)
    # Persist to database (non-blocking, errors are logged but don't fail the request)
    await usage_tracker.persist_usage(user_id, usage)
    return usage
