"""
Canonical model pricing table — single source of truth.

All costs are in USD per 1M tokens (input, output).
Every module that needs cost estimation MUST import from here.
"""

from __future__ import annotations

# ─── Pricing per 1M tokens (input_usd, output_usd) ──────────────────────────
# Keep sorted alphabetically.  Update here when providers change prices.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    # Google
    "gemini-pro": (1.25, 5.00),
    "gemini-2.5-pro": (1.25, 5.00),
    "gemini-3-pro-preview": (1.25, 5.00),
    "gemini-flash": (0.075, 0.30),
    # Anthropic
    "claude-3-opus": (15.00, 75.00),
    "claude-3-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3": (3.00, 15.00),  # generic → sonnet pricing
    # DeepSeek
    "deepseek": (1.00, 2.00),
    # Embeddings
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}

# Conservative fallback when model is unrecognised
DEFAULT_PRICE: tuple[float, float] = (5.00, 15.00)


def estimate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Estimate USD cost for a given token usage.

    Matches the model name by prefix (e.g. "gpt-4o-2024-08-06" → "gpt-4o").
    """
    model_lower = model.lower()
    price = DEFAULT_PRICE

    # Exact match first (fast path)
    if model_lower in MODEL_PRICES:
        price = MODEL_PRICES[model_lower]
    else:
        # Prefix match — longest prefix wins
        best_len = 0
        for prefix, p in MODEL_PRICES.items():
            if prefix in model_lower and len(prefix) > best_len:
                price = p
                best_len = len(prefix)

    return round(
        (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000, 6
    )
