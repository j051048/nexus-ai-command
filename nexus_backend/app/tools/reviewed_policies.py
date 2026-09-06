"""Explicitly reviewed effects. Unlisted tools retain conservative UNKNOWN policy.

Source review: crm_tools, asset_tools, work_order_tools and load_knowledge_tool.
Do not infer safety from verbs, names or the absence of confirmation prompts.
"""

REVIEWED_ACTIONS = {
    "get_customers": "read",
    "get_customer_detail": "read",
    "get_follow_ups": "read",
    "get_sales_pipeline": "read",
    "get_pipeline_kanban": "read",
    "create_customer": "irreversible",
    "update_customer": "irreversible",
    "add_follow_up": "irreversible",
    "update_customer_stage": "irreversible",
    "list_assets": "read",
    "get_asset_detail": "read",
    "asset_statistics": "read",
    "create_asset": "irreversible",
    "update_asset": "mutate",
    "transfer_asset": "irreversible",
    "list_work_orders": "read",
    "get_work_order_detail": "read",
    "work_order_statistics": "read",
    "create_work_order": "mutate",
    "update_work_order": "mutate",
    "load_knowledge": "read",
}
