"""
Item 12: Workflow Template Marketplace Service

Manages built-in and organization-shared workflow templates.
Allows organizations to quickly create approval workflows from pre-defined templates.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)


class WorkflowTemplateService:
    """工作流模板管理服务"""

    # ─── 预置模板（内置，不存数据库）────────────────────────────────

    BUILTIN_TEMPLATES: list[dict[str, Any]] = [
        {
            "id": "tpl_expense",
            "name": "费用报销标准流程",
            "description": "适用于日常费用报销，含自动审批（≤500元）+ 部门经理审批 + 财务复核",
            "category": "finance",
            "applies_to": ["expense"],
            "is_builtin": True,
            "usage_count": 0,
            "preview_image": None,
            "steps": [
                {
                    "id": "start",
                    "type": "auto_approve",
                    "label": "小额自动审批",
                    "config": {"condition": "amount <= 500"},
                    "is_start": True,
                    "next": ["mgr_approve"],
                },
                {
                    "id": "mgr_approve",
                    "type": "approver",
                    "label": "部门经理审批",
                    "config": {"role": "manager", "timeout_hours": 24},
                    "next": ["finance_review"],
                },
                {
                    "id": "finance_review",
                    "type": "approver",
                    "label": "财务复核",
                    "config": {"role": "finance", "timeout_hours": 48},
                    "is_end": True,
                    "next": [],
                },
            ],
        },
        {
            "id": "tpl_purchase",
            "name": "采购申请标准流程",
            "description": "适用于物资采购，含部门审批 + 金额分级审批（>10000元需总监）+ 采购部确认",
            "category": "procurement",
            "applies_to": ["purchase"],
            "is_builtin": True,
            "usage_count": 0,
            "preview_image": None,
            "steps": [
                {
                    "id": "mgr_approve",
                    "type": "approver",
                    "label": "部门经理审批",
                    "config": {"role": "manager", "timeout_hours": 24},
                    "is_start": True,
                    "next": ["amount_check"],
                },
                {
                    "id": "amount_check",
                    "type": "condition",
                    "label": "金额判断",
                    "config": {"field": "amount", "operator": ">", "value": 10000},
                    "next": ["director_approve", "procurement_confirm"],
                },
                {
                    "id": "director_approve",
                    "type": "approver",
                    "label": "总监审批",
                    "config": {"role": "director", "timeout_hours": 48},
                    "next": ["procurement_confirm"],
                },
                {
                    "id": "procurement_confirm",
                    "type": "approver",
                    "label": "采购部确认",
                    "config": {"role": "procurement", "timeout_hours": 24},
                    "is_end": True,
                    "next": [],
                },
            ],
        },
        {
            "id": "tpl_leave",
            "name": "请假审批流程",
            "description": "适用于各类请假申请，含直属上级审批 + 人事备案通知",
            "category": "hr",
            "applies_to": ["leave"],
            "is_builtin": True,
            "usage_count": 0,
            "preview_image": None,
            "steps": [
                {
                    "id": "supervisor_approve",
                    "type": "approver",
                    "label": "直属上级审批",
                    "config": {"role": "supervisor", "timeout_hours": 12},
                    "is_start": True,
                    "next": ["hr_notify"],
                },
                {
                    "id": "hr_notify",
                    "type": "notify",
                    "label": "人事部门备案",
                    "config": {"role": "hr", "message": "请假审批已通过，请备案"},
                    "is_end": True,
                    "next": [],
                },
            ],
        },
        {
            "id": "tpl_travel",
            "name": "出差审批流程",
            "description": "适用于出差申请，含部门审批 + 行政确认 + 财务预算审核",
            "category": "travel",
            "applies_to": ["travel"],
            "is_builtin": True,
            "usage_count": 0,
            "preview_image": None,
            "steps": [
                {
                    "id": "mgr_approve",
                    "type": "approver",
                    "label": "部门经理审批",
                    "config": {"role": "manager", "timeout_hours": 24},
                    "is_start": True,
                    "next": ["admin_confirm"],
                },
                {
                    "id": "admin_confirm",
                    "type": "approver",
                    "label": "行政确认行程",
                    "config": {"role": "admin", "timeout_hours": 24},
                    "next": ["finance_budget"],
                },
                {
                    "id": "finance_budget",
                    "type": "approver",
                    "label": "财务预算审核",
                    "config": {"role": "finance", "timeout_hours": 48},
                    "is_end": True,
                    "next": [],
                },
            ],
        },
        {
            "id": "tpl_contract",
            "name": "合同审批流程",
            "description": "适用于合同签署，含法务审核 + 并行会签（业务 + 财务）+ 总经理审批",
            "category": "legal",
            "applies_to": ["custom"],
            "is_builtin": True,
            "usage_count": 0,
            "preview_image": None,
            "steps": [
                {
                    "id": "legal_review",
                    "type": "approver",
                    "label": "法务审核",
                    "config": {"role": "legal", "timeout_hours": 72},
                    "is_start": True,
                    "next": ["parallel_sign"],
                },
                {
                    "id": "parallel_sign",
                    "type": "parallel",
                    "label": "业务 + 财务会签",
                    "config": {
                        "branches": [
                            {"role": "business", "label": "业务负责人"},
                            {"role": "finance", "label": "财务负责人"},
                        ],
                        "require_all": True,
                    },
                    "next": ["gm_approve"],
                },
                {
                    "id": "gm_approve",
                    "type": "approver",
                    "label": "总经理审批",
                    "config": {"role": "general_manager", "timeout_hours": 72},
                    "is_end": True,
                    "next": [],
                },
            ],
        },
    ]

    # 分类元数据
    CATEGORIES: dict[str, dict[str, str]] = {
        "finance": {"label": "财务", "color": "blue"},
        "procurement": {"label": "采购", "color": "green"},
        "hr": {"label": "人事", "color": "purple"},
        "travel": {"label": "差旅", "color": "orange"},
        "legal": {"label": "法务", "color": "red"},
        "custom": {"label": "自定义", "color": "gray"},
    }

    # ─── 模板查询 ─────────────────────────────────────────────────

    async def list_templates(
        self,
        category: str | None = None,
        org_id: str | None = None,
        db: Any = None,
    ) -> list[dict]:
        """列出所有模板（内置 + 组织共享）"""
        templates: list[dict] = []

        # 1) 内置模板
        for tpl in self.BUILTIN_TEMPLATES:
            if category and tpl["category"] != category:
                continue
            templates.append({**tpl, "source": "builtin"})

        # 2) 组织共享模板（从数据库查询）
        if org_id:
            client = db or supabase
            if client:
                try:
                    query = (
                        client.table("workflow_shared_templates")
                        .select("*")
                        .eq("organization_id", org_id)
                    )
                    if category:
                        query = query.eq("category", category)
                    result = await query.order("created_at", desc=True).execute()

                    for row in result.data or []:
                        row["source"] = "shared"
                        row["is_builtin"] = False
                        templates.append(row)
                except Exception as e:
                    logger.warning(f"Failed to load shared templates: {e}")

        return templates

    async def get_template(self, template_id: str, db: Any = None) -> dict | None:
        """获取模板详情"""
        # 先搜索内置模板
        for tpl in self.BUILTIN_TEMPLATES:
            if tpl["id"] == template_id:
                return {**tpl, "source": "builtin"}

        # 再搜索数据库共享模板
        client = db or supabase
        if client:
            try:
                result = (
                    await client.table("workflow_shared_templates")
                    .select("*")
                    .eq("id", template_id)
                    .maybe_single()
                    .execute()
                )
                if result.data:
                    data = result.data
                    data["source"] = "shared"
                    data["is_builtin"] = False
                    return data
            except Exception as e:
                logger.warning(f"Failed to get shared template {template_id}: {e}")

        return None

    async def create_workflow_from_template(
        self,
        template_id: str,
        org_id: str,
        name: str | None = None,
        created_by: str | None = None,
        db: Any = None,
    ) -> dict:
        """从模板创建工作流实例"""
        template = await self.get_template(template_id, db=db)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")

        client = db or supabase
        if not client:
            raise RuntimeError("数据库连接不可用")

        workflow_name = name or f"{template['name']} (副本)"
        workflow_data = {
            "organization_id": org_id,
            "name": workflow_name,
            "applies_to": template.get("applies_to", []),
            "steps": template.get("steps", []),
            "conditions": template.get("conditions"),
            "is_active": True,
            "is_default": False,
            "version": 1,
            "created_by": created_by,
        }

        result = await client.table("approval_chains").insert(workflow_data).execute()
        if not result.data:
            raise RuntimeError("从模板创建工作流失败")

        created = result.data[0] if isinstance(result.data, list) else result.data

        # 更新模板使用次数（仅共享模板）
        if template.get("source") == "shared":
            try:
                await (
                    client.table("workflow_shared_templates")
                    .update(
                        {
                            "usage_count": (template.get("usage_count", 0) or 0) + 1,
                        }
                    )
                    .eq("id", template_id)
                    .execute()
                )
            except Exception as e:
                logger.warning(f"Failed to increment template usage count: {e}")

        logger.info(
            f"Created workflow '{workflow_name}' from template '{template_id}' for org {org_id}"
        )
        return created

    async def share_workflow_as_template(
        self,
        workflow_id: str,
        org_id: str,
        shared_by: str | None = None,
        db: Any = None,
    ) -> dict:
        """将现有工作流分享为组织模板"""
        client = db or supabase
        if not client:
            raise RuntimeError("数据库连接不可用")

        # 获取原始工作流
        result = (
            await client.table("approval_chains")
            .select("*")
            .eq("id", workflow_id)
            .eq("organization_id", org_id)
            .maybe_single()
            .execute()
        )

        if not result.data:
            raise ValueError(f"工作流不存在或无权访问: {workflow_id}")

        workflow = result.data

        # 创建共享模板记录
        template_data = {
            "id": f"shared_{uuid.uuid4().hex[:12]}",
            "organization_id": org_id,
            "name": f"{workflow.get('name', '未命名')} (模板)",
            "description": workflow.get("description", ""),
            "category": "custom",
            "applies_to": workflow.get("applies_to", []),
            "steps": workflow.get("steps", []),
            "conditions": workflow.get("conditions"),
            "usage_count": 0,
            "shared_by": shared_by,
            "source_workflow_id": workflow_id,
            "created_at": datetime.now(UTC).isoformat(),
        }

        insert_result = (
            await client.table("workflow_shared_templates")
            .insert(template_data)
            .execute()
        )

        if not insert_result.data:
            raise RuntimeError("分享模板失败")

        shared = (
            insert_result.data[0]
            if isinstance(insert_result.data, list)
            else insert_result.data
        )

        logger.info(f"Shared workflow '{workflow_id}' as template for org {org_id}")
        return shared

    def get_categories(self) -> dict[str, dict[str, str]]:
        """获取模板分类元数据"""
        return self.CATEGORIES


# Global service instance
workflow_template_service = WorkflowTemplateService()
