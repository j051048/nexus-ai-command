"""
P1-4: Pre-Flight Validation Rules — business-level checks before tool execution.

Prevents invalid API calls by validating business logic constraints (balance, inventory, permissions).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Pre-flight validation rules: tool_name -> list of checks
PRE_FLIGHT_RULES: dict[str, list[dict[str, Any]]] = {
    "update_sales_lead": [
        {
            "name": "lead_exists",
            "query": "SELECT id FROM sales_leads WHERE id = :lead_id",
            "params": ["lead_id"],
            "error": "销售线索不存在"
        }
    ],
    "create_order": [
        {
            "name": "inventory_check",
            "query": "SELECT stock FROM products WHERE id = :product_id",
            "params": ["product_id"],
            "validator": lambda row: row and row.get("stock", 0) > 0,
            "error": "库存不足"
        }
    ],
    "delete_sales_lead": [
        {
            "name": "lead_exists",
            "query": "SELECT id FROM sales_leads WHERE id = :lead_id",
            "params": ["lead_id"],
            "error": "销售线索不存在"
        }
    ],
}


async def run_preflight_checks(tool_name: str, tool_args: dict, supabase_client=None) -> tuple[bool, str]:
    """
    Execute pre-flight checks for a tool.

    Returns:
        (passed, error_message)
    """
    rules = PRE_FLIGHT_RULES.get(tool_name, [])
    if not rules:
        return True, ""  # No rules defined, pass

    if not supabase_client:
        logger.warning(f"[PreFlight] No Supabase client available for {tool_name}, skipping checks")
        return True, ""

    for rule in rules:
        try:
            # Extract params from tool_args
            params = {p: tool_args.get(p) for p in rule.get("params", [])}
            if None in params.values():
                continue  # Skip if required params missing

            # Execute check query
            query = rule["query"]
            for key, val in params.items():
                query = query.replace(f":{key}", f"'{val}'")

            result = await supabase_client.rpc("execute_sql", {"query": query}).execute()

            # Validate result
            validator = rule.get("validator")
            if validator:
                if not validator(result.data[0] if result.data else None):
                    return False, rule["error"]
            elif not result.data:
                return False, rule["error"]

        except Exception as e:
            logger.warning(f"[PreFlight] Check {rule['name']} failed: {e}")
            continue  # Don't block on check failures

    return True, ""
