"""
批量操作工具
支持批量导入、更新、分配等操作
"""

import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def batch_import_customers(
    data: list[dict[str, Any]],
    org_id: str,
    user_id: str,
) -> dict[str, Any]:
    """批量导入客户数据

    Args:
        data: 客户数据列表，每个元素包含 name, industry, contact 等字段
        org_id: 组织ID
        user_id: 操作用户ID

    Returns:
        导入结果统计

    Example:
        batch_import_customers(
            data=[
                {"name": "A公司", "industry": "IT", "contact": "张三"},
                {"name": "B公司", "industry": "制造", "contact": "李四"}
            ],
            org_id="org_123",
            user_id="user_456"
        )
    """
    try:
        from app.core.database import supabase

        success_count = 0
        failed_count = 0
        errors = []

        for idx, customer in enumerate(data):
            try:
                await supabase.table("crm_customers").insert(
                    {
                        "org_id": org_id,
                        "name": customer.get("name"),
                        "industry": customer.get("industry"),
                        "contact_person": customer.get("contact"),
                        "phone": customer.get("phone"),
                        "email": customer.get("email"),
                        "created_by": user_id,
                    }
                ).execute()
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"第{idx+1}行: {str(e)}")

        return {
            "success": True,
            "total": len(data),
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": errors[:10],  # 最多返回10个错误
        }

    except Exception as e:
        logger.error(f"批量导入失败: {e}")
        return {"success": False, "error": str(e)}


@tool
async def batch_update_leads(
    lead_ids: list[str],
    updates: dict[str, Any],
    org_id: str,
) -> dict[str, Any]:
    """批量更新线索状态

    Args:
        lead_ids: 线索ID列表
        updates: 要更新的字段（如 {"stage": "商机", "priority": "高"}）
        org_id: 组织ID

    Returns:
        更新结果统计
    """
    try:
        from app.core.database import supabase

        result = (
            await supabase.table("crm_leads")
            .update(updates)
            .in_("id", lead_ids)
            .eq("org_id", org_id)
            .execute()
        )

        return {
            "success": True,
            "updated_count": len(result.data),
            "lead_ids": lead_ids,
        }

    except Exception as e:
        logger.error(f"批量更新失败: {e}")
        return {"success": False, "error": str(e)}


@tool
async def batch_assign_leads(
    lead_ids: list[str],
    owner_id: str,
    org_id: str,
) -> dict[str, Any]:
    """批量分配线索给销售人员

    Args:
        lead_ids: 线索ID列表
        owner_id: 负责人ID
        org_id: 组织ID

    Returns:
        分配结果统计
    """
    try:
        from app.core.database import supabase

        result = (
            await supabase.table("crm_leads")
            .update({"owner_id": owner_id})
            .in_("id", lead_ids)
            .eq("org_id", org_id)
            .execute()
        )

        return {
            "success": True,
            "assigned_count": len(result.data),
            "owner_id": owner_id,
        }

    except Exception as e:
        logger.error(f"批量分配失败: {e}")
        return {"success": False, "error": str(e)}
