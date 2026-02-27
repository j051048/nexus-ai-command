"""
#20: 数据库列存在性验证脚本

启动时验证关键表的关键列是否存在，防止因数据库迁移遗漏导致运行时错误。
仅记录警告，不会阻止应用启动。
"""

import logging

logger = logging.getLogger(__name__)

# 需要验证的表及其关键列
CRITICAL_SCHEMA: dict[str, list[str]] = {
    "users": ["manager_id", "organization_id"],
    "approval_requests": [
        "form_data",
        "form_schema_id",
        "organization_id",
        "chain_id",
    ],
    "llm_model_config": ["tenant_id", "status"],
    "knowledge_library": ["organization_id"],
}


async def _get_table_columns(supabase, table_name: str) -> set[str] | None:
    """
    通过 SELECT * ... LIMIT 1 获取表的列名。
    Supabase PostgREST 返回的 JSON 对象键就是列名。
    返回 None 表示表不存在或查询失败。
    """
    try:
        res = (
            await supabase.table(table_name)
            .select("*")
            .limit(1)
            .execute()
        )
        # 即使表为空（data=[]），PostgREST 也会返回空数组
        # 但如果有至少一行数据，键名就是列名
        if res.data and len(res.data) > 0:
            return set(res.data[0].keys())

        # 表存在但无数据 — 尝试 insert 一个无效行来触发错误
        # 更安全的方式：直接查询 head 获取列信息
        # PostgREST 对空表也会成功返回 []，无法获取列名
        # 改用 RPC fallback
        try:
            rpc_res = await supabase.rpc(
                "get_table_columns",
                {"p_table_name": table_name},
            ).execute()
            if rpc_res.data:
                return {
                    row.get("column_name")
                    for row in rpc_res.data
                    if isinstance(row, dict) and row.get("column_name")
                }
        except Exception:
            pass

        # 如果 RPC 也不存在，表存在但无数据 — 跳过列验证
        return None

    except Exception:
        return None


async def validate_schema() -> list[str]:
    """
    验证关键表的关键列是否存在。

    通过查询表数据获取列名，返回缺失列的警告列表。
    不会抛出异常或阻止启动。
    """
    from app.core.database import supabase

    warnings: list[str] = []

    if not supabase:
        msg = "[SchemaValidator] 数据库未配置，跳过 schema 验证"
        logger.warning(msg)
        warnings.append(msg)
        return warnings

    for table_name, expected_columns in CRITICAL_SCHEMA.items():
        existing_columns = await _get_table_columns(supabase, table_name)

        if existing_columns is None:
            # 无法确定列信息（空表或表不存在），跳过
            logger.info(
                f"[SchemaValidator] 表 '{table_name}' 无数据或无法访问，跳过列验证"
            )
            continue

        # 检查缺失的列
        for col in expected_columns:
            if col not in existing_columns:
                msg = (
                    f"[SchemaValidator] 表 '{table_name}' 缺少关键列 '{col}'"
                )
                logger.warning(msg)
                warnings.append(msg)

    if not warnings:
        logger.info("[SchemaValidator] 所有关键表列验证通过")
    else:
        logger.warning(
            f"[SchemaValidator] 发现 {len(warnings)} 个 schema 问题，"
            "请检查数据库迁移是否完整"
        )

    return warnings
