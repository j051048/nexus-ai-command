"""
#20: 数据库列存在性验证脚本

启动时验证关键表的关键列是否存在，防止因数据库迁移遗漏导致运行时错误。
仅记录警告，不会阻止应用启动。
"""

import logging
from typing import Any

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


async def validate_schema() -> list[str]:
    """
    验证关键表的关键列是否存在。

    通过查询 information_schema.columns 检查每个表的列，
    返回缺失列的警告列表。不会抛出异常或阻止启动。
    """
    from app.core.database import supabase

    warnings: list[str] = []

    if not supabase:
        msg = "[SchemaValidator] 数据库未配置，跳过 schema 验证"
        logger.warning(msg)
        warnings.append(msg)
        return warnings

    for table_name, expected_columns in CRITICAL_SCHEMA.items():
        try:
            # 查询 information_schema 获取表的所有列名
            res = await supabase.rpc(
                "get_table_columns",
                {"p_table_name": table_name},
            ).execute()

            # 如果 RPC 不存在，回退到直接查询
            if res.data is not None:
                existing_columns = {
                    row.get("column_name") for row in res.data if isinstance(row, dict)
                }
            else:
                existing_columns = set()

        except Exception:
            # RPC 可能不存在，回退到通过 information_schema 表直接查询
            try:
                res = (
                    await supabase.table("information_schema.columns")
                    .select("column_name")
                    .eq("table_schema", "public")
                    .eq("table_name", table_name)
                    .execute()
                )
                existing_columns = {
                    row.get("column_name")
                    for row in (res.data or [])
                    if isinstance(row, dict)
                }
            except Exception as e2:
                # 如果连 information_schema 也查不了，跳过此表
                msg = (
                    f"[SchemaValidator] 无法检查表 '{table_name}' 的列信息: {e2}"
                )
                logger.warning(msg)
                warnings.append(msg)
                continue

        if not existing_columns:
            # 表可能不存在
            msg = f"[SchemaValidator] 表 '{table_name}' 不存在或无列信息"
            logger.warning(msg)
            warnings.append(msg)
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
