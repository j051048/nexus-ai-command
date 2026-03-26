"""
P1-4: 自动降级策略
"""

import logging

logger = logging.getLogger(__name__)

# 降级链配置
FALLBACK_CHAINS = {
    "send_email": [
        "send_email_smtp",
        "send_email_sendgrid",
        "send_sms",
        "create_notification"
    ],
    "get_customer_crm": [
        "get_customer_cache",
        "get_customer_basic"
    ],
    "search_documents": [
        "search_documents_vector",
        "search_documents_fulltext",
        "search_documents_basic"
    ]
}


async def execute_with_fallback(tool_name: str, args: dict, executor: callable):
    """自动降级执行"""
    chain = FALLBACK_CHAINS.get(tool_name, [tool_name])

    last_error = None
    for fallback_tool in chain:
        try:
            logger.info(f"Trying {fallback_tool}")
            return await executor(fallback_tool, args)
        except Exception as e:
            logger.warning(f"{fallback_tool} failed: {e}")
            last_error = e
            continue

    raise Exception(f"All fallbacks failed for {tool_name}: {last_error}")
