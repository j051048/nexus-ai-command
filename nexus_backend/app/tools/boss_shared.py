"""
Shared utilities for boss tool modules.
Extracted from boss_tools.py (P2-3 split).
"""

import logging
import re
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)

# P0 Security: Maximum batch size to prevent mass operations
MAX_BATCH_SIZE = 10


def _get_client(config: dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


def _parse_amount_from_condition(condition: str) -> float:
    """
    解析条件中的金额，支持中文单位（万/千/k/w/K/W）

    示例:
    - "5万" -> 50000.0
    - "3千" -> 3000.0
    - "10k" -> 10000.0
    - "2.5W" -> 25000.0
    - "500" -> 500.0

    Returns:
        float: 解析后的金额，解析失败返回 None
    """
    # 提取数字和可能的单位
    pattern = r"(\d+(?:\.\d+)?)\s*([万千kKwW]?)"
    match = re.search(pattern, condition)

    if not match:
        return None

    number_str, unit = match.groups()

    try:
        amount = float(number_str)

        # 单位换算
        if unit in ["万", "w", "W"]:
            amount *= 10000
        elif unit in ["千", "k", "K"]:
            amount *= 1000

        return amount
    except (ValueError, TypeError):
        return None
