"""
Canonical model pricing table.

All costs are in USD per 1M tokens (input, output). Unknown models use a
conservative fallback and emit a warning once so cost dashboards do not silently
drift when providers release new model codes.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

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
    "gemini-3-flash-preview": (0.075, 0.30),
    "gemini-flash": (0.075, 0.30),
    # Anthropic
    "claude-3-opus": (15.00, 75.00),
    "claude-3-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3": (3.00, 15.00),
    # DeepSeek
    "deepseek-v4-flash": (0.07, 0.28),
    "deepseek-v4": (0.50, 1.50),
    "deepseek-chat": (0.14, 0.28),
    "deepseek": (1.00, 2.00),
    # Embeddings
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}

DEFAULT_PRICE: tuple[float, float] = (5.00, 15.00)
_WARNED_UNKNOWN_MODELS: set[str] = set()


def resolve_model_price(model: str) -> tuple[float, float]:
    """Resolve pricing by exact match, then longest startswith prefix."""
    model_lower = (model or "").strip().lower()
    if model_lower in MODEL_PRICES:
        return MODEL_PRICES[model_lower]

    best_prefix = ""
    best_price: tuple[float, float] | None = None
    for prefix, price in MODEL_PRICES.items():
        if model_lower.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix = prefix
            best_price = price

    if best_price:
        return best_price

    if model_lower and model_lower not in _WARNED_UNKNOWN_MODELS:
        _WARNED_UNKNOWN_MODELS.add(model_lower)
        logger.warning(
            "Unknown model pricing for %s; using conservative fallback %.2f/%.2f USD per 1M tokens",
            model_lower,
            DEFAULT_PRICE[0],
            DEFAULT_PRICE[1],
        )
    return DEFAULT_PRICE


def estimate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Estimate USD cost for a given token usage."""
    input_price, output_price = resolve_model_price(model)
    safe_input = max(0, int(input_tokens or 0))
    safe_output = max(0, int(output_tokens or 0))
    return round((safe_input * input_price + safe_output * output_price) / 1_000_000, 6)
