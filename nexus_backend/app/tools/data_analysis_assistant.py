"""
智能数据分析助手
自然语言转SQL，自动执行查询并生成洞察
"""
import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def analyze_data_with_nl(
    query: str,
    org_id: str,
    context: str = "",
) -> dict[str, Any]:
    """使用自然语言分析数据

    Args:
        query: 自然语言查询（如"上个月销售额前10的客户"）
        org_id: 组织ID
        context: 额外上下文信息

    Returns:
        包含查询结果和洞察的字典

    Example:
        analyze_data_with_nl(
            query="本季度各销售人员的业绩排名",
            org_id="org_123"
        )
    """
    try:
        from app.core.database import supabase
        from app.services.llm_helpers import get_langchain_llm_sync, resolve_model_config

        # 1. 获取数据库 schema
        schema_info = await _get_schema_info(org_id)

        # 2. 使用 LLM 生成 SQL
        config = await resolve_model_config(scene_code="analysis", complexity_tier="balanced")
        llm = get_langchain_llm_sync(**config)

        prompt = f"""你是一个SQL专家。根据用户的自然语言查询生成安全的SQL语句。

数据库Schema:
{schema_info}

用户查询: {query}
{f"上下文: {context}" if context else ""}

要求:
1. 只返回SELECT语句，不要UPDATE/DELETE/DROP
2. 使用org_id过滤: WHERE org_id = '{org_id}'
3. 返回纯SQL，不要解释

SQL:"""

        sql = llm.invoke(prompt).content.strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()

        # 3. 执行查询（安全检查）
        if not _is_safe_sql(sql):
            return {"success": False, "error": "SQL不安全，拒绝执行"}

        result = await supabase.rpc("execute_safe_query", {"query_sql": sql}).execute()

        # 4. 生成洞察
        insight = await _generate_insight(llm, query, result.data)

        return {
            "success": True,
            "sql": sql,
            "data": result.data[:100],  # 最多返回100行
            "total_rows": len(result.data),
            "insight": insight,
        }

    except Exception as e:
        logger.error(f"数据分析失败: {e}")
        return {"success": False, "error": str(e)}


async def _get_schema_info(org_id: str) -> str:
    """获取数据库schema信息"""
    # 简化版：只返回核心表结构
    return """
核心表:
- crm_customers: 客户表 (id, org_id, name, industry, status, created_at)
- crm_leads: 线索表 (id, org_id, customer_id, source, stage, amount, owner_id)
- sales_orders: 订单表 (id, org_id, customer_id, amount, status, created_at)
- users: 用户表 (id, org_id, name, role)
"""


def _is_safe_sql(sql: str) -> bool:
    """检查SQL是否安全"""
    sql_lower = sql.lower()
    dangerous_keywords = ["drop", "delete", "update", "insert", "alter", "create", "truncate"]
    return not any(kw in sql_lower for kw in dangerous_keywords) and "select" in sql_lower


async def _generate_insight(llm, query: str, data: list) -> str:
    """生成数据洞察"""
    if not data:
        return "未找到相关数据"

    prompt = f"""根据查询结果生成简洁的洞察分析（2-3句话）。

用户查询: {query}
结果数据: {data[:5]}  # 只看前5行
总行数: {len(data)}

洞察:"""

    return llm.invoke(prompt).content.strip()

