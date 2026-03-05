"""
复合工作流工具集
提供高阶意图工具，一次调用完成多步串联操作。
这些工具体现 AI-Native 的设计理念：不让 LLM 逐步调用离散 CRUD，
而是通过单一意图工具完成完整业务流程。
"""

import logging
import uuid as _uuid
from typing import Any

from app.core.database import supabase
from app.services.event_bus import EventType, emit

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_client(config: dict = None):
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


def _validate_uuid(value: str, field_name: str = "ID") -> str | None:
    try:
        _uuid.UUID(value)
        return None
    except (ValueError, TypeError, AttributeError):
        return f"{field_name} '{value}' 不是有效的UUID格式。"


class ProcessOnboardingTool(BaseTool):
    """员工入职一键办理"""

    name = "process_onboarding"
    description = (
        "员工入职全流程一键办理：创建员工记录 → 分配闲置设备 → 创建 IT 工单 → 通知部门负责人。"
        "当用户说'新员工入职'、'办理入职'、'入职全流程'时调用。"
    )
    required_role = "admin"
    is_irreversible = True
    confirmation_message = "⚠️ 即将执行员工入职全流程（创建员工+分配设备+创建工单），确认继续？"

    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "员工姓名",
                "maxLength": 50,
            },
            "department_id": {
                "type": "string",
                "description": "部门ID",
            },
            "position_id": {
                "type": "string",
                "description": "职位ID（可选）",
            },
            "phone": {
                "type": "string",
                "description": "手机号（可选）",
            },
            "email": {
                "type": "string",
                "description": "邮箱（可选）",
            },
            "asset_type": {
                "type": "string",
                "description": "需要分配的设备类型（如: computer，可选）",
            },
        },
        "required": ["name", "department_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        name = args.get("name", "").strip()
        department_id = args.get("department_id", "").strip()

        if not name or not department_id:
            return "❌ 员工姓名和部门ID不能为空"

        if err := _validate_uuid(department_id, "department_id"):
            return f"❌ {err}"

        results = []
        employee_id = None

        try:
            # Step 1: 创建员工
            emp_data = {
                "organization_id": org_id,
                "name": name,
                "department_id": department_id,
                "status": "active",
            }
            for field in ["position_id", "phone", "email"]:
                if args.get(field):
                    emp_data[field] = args[field]

            emp_result = await client.table("employees").insert(emp_data).execute()
            if emp_result.data:
                employee_id = emp_result.data[0]["id"]
                results.append(f"✅ 员工创建成功: {name} (ID: {employee_id[:8]}...)")
            else:
                return "❌ 员工创建失败"

            # Step 2: 自动分配闲置设备
            asset_type = args.get("asset_type", "computer")
            asset_resp = await (
                client.table("assets")
                .select("id, name, asset_code")
                .eq("organization_id", org_id)
                .eq("asset_type", asset_type)
                .eq("status", "idle")
                .limit(1)
                .execute()
            )

            if asset_resp.data:
                asset = asset_resp.data[0]
                await (
                    client.table("assets")
                    .update({"current_user_id": employee_id, "status": "in_use"})
                    .eq("id", asset["id"])
                    .execute()
                )
                await client.table("asset_transfers").insert({
                    "organization_id": org_id,
                    "asset_id": asset["id"],
                    "transfer_type": "allocate",
                    "to_user_id": employee_id,
                    "reason": f"入职自动分配",
                    "operator_id": user_id,
                }).execute()
                results.append(f"✅ 已分配设备: {asset.get('name')} [{asset.get('asset_code')}]")
            else:
                results.append(f"⚠️ 无闲置 {asset_type} 设备可分配，请手动处理")

            # Step 3: 创建 IT 工单
            await client.table("work_orders").insert({
                "organization_id": org_id,
                "title": f"新员工入职准备 - {name}",
                "description": f"请为 {name} 开通邮箱、系统账号、配置工位等。",
                "order_type": "onboarding",
                "priority": "high",
                "status": "open",
                "creator_id": user_id,
            }).execute()
            results.append("✅ IT 工单已创建")

            # Step 4: 发送事件（触发通知等级联动作）
            await emit(
                EventType.EMPLOYEE_ONBOARDED.value,
                payload={
                    "employee_id": employee_id,
                    "employee_name": name,
                    "department_id": department_id,
                    "org_id": org_id,
                },
                user_id=user_id,
            )
            results.append("✅ 部门负责人已通知")

            return f"🎉 入职流程已完成:\n\n" + "\n".join(results)

        except Exception as e:
            logger.error(f"入职流程失败: {e}")
            partial = "\n".join(results) if results else "无"
            return f"❌ 入职流程部分失败: {str(e)}\n\n已完成步骤:\n{partial}"


class ProcessResignationTool(BaseTool):
    """员工离职一键办理"""

    name = "process_resignation"
    description = (
        "员工离职全流程一键办理：更新员工状态 → 回收名下所有资产 → 通知相关人员。"
        "当用户说'员工离职'、'办理离职'、'离职交接'时调用。"
    )
    required_role = "admin"
    is_irreversible = True
    confirmation_message = "⚠️ 即将执行员工离职全流程（更新状态+回收资产+通知），确认继续？"

    parameters = {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "员工ID",
            },
            "reason": {
                "type": "string",
                "description": "离职原因（可选）",
                "maxLength": 500,
            },
        },
        "required": ["employee_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        employee_id = args.get("employee_id", "").strip()
        if err := _validate_uuid(employee_id, "employee_id"):
            return f"❌ {err}"

        results = []

        try:
            # Step 1: 获取员工信息
            emp_resp = await (
                client.table("employees")
                .select("id, name, department_id")
                .eq("id", employee_id)
                .maybe_single()
                .execute()
            )
            if not emp_resp.data:
                return f"❌ 未找到ID为 {employee_id} 的员工"

            emp = emp_resp.data
            emp_name = emp.get("name", "")

            # Step 2: 更新员工状态为离职
            await (
                client.table("employees")
                .update({"status": "resigned"})
                .eq("id", employee_id)
                .execute()
            )
            results.append(f"✅ 员工状态已更新为离职: {emp_name}")

            # Step 3: 发送离职事件（触发级联：回收资产 + 通知）
            await emit(
                EventType.EMPLOYEE_RESIGNED.value,
                payload={
                    "employee_id": employee_id,
                    "employee_name": emp_name,
                    "department_id": emp.get("department_id"),
                    "org_id": org_id,
                    "reason": args.get("reason"),
                },
                user_id=user_id,
            )
            results.append("✅ 资产回收和管理员通知已触发")

            # Step 4: 关闭该员工的待处理工单
            open_orders = await (
                client.table("work_orders")
                .select("id")
                .eq("organization_id", org_id)
                .eq("assignee_id", employee_id)
                .in_("status", ["open", "processing"])
                .execute()
            )
            closed_count = 0
            for order in open_orders.data or []:
                await (
                    client.table("work_orders")
                    .update({"status": "closed", "assignee_id": None})
                    .eq("id", order["id"])
                    .execute()
                )
                closed_count += 1
            if closed_count:
                results.append(f"✅ 已关闭 {closed_count} 个待处理工单")

            return f"📋 离职流程已完成:\n\n" + "\n".join(results)

        except Exception as e:
            logger.error(f"离职流程失败: {e}")
            partial = "\n".join(results) if results else "无"
            return f"❌ 离职流程部分失败: {str(e)}\n\n已完成步骤:\n{partial}"


class ProcessAssetLifecycleTool(BaseTool):
    """资产全生命周期操作"""

    name = "process_asset_lifecycle"
    description = (
        "资产全生命周期操作：支持批量入库、批量分配、批量报废等操作。"
        "当用户说'批量入库'、'批量分配设备'、'批量报废资产'时调用。"
    )
    required_role = "admin"
    is_irreversible = True
    confirmation_message = "⚠️ 即将执行批量资产操作，确认继续？"

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "操作类型",
                "enum": ["batch_create", "batch_allocate", "batch_scrap"],
            },
            "asset_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "资产ID列表（batch_allocate/batch_scrap 时需要）",
            },
            "to_user_id": {
                "type": "string",
                "description": "目标使用人ID（batch_allocate 时需要）",
            },
            "assets_data": {
                "type": "array",
                "items": {"type": "object"},
                "description": "资产数据列表（batch_create 时需要，每项含 asset_code, name, asset_type）",
            },
            "reason": {
                "type": "string",
                "description": "操作原因（可选）",
                "maxLength": 500,
            },
        },
        "required": ["action"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        action = args.get("action")
        reason = args.get("reason", "")

        try:
            if action == "batch_create":
                assets_data = args.get("assets_data", [])
                if not assets_data:
                    return "❌ 请提供要创建的资产数据列表"

                for item in assets_data:
                    item["organization_id"] = org_id
                    item.setdefault("status", "idle")

                result = await client.table("assets").insert(assets_data).execute()
                count = len(result.data) if result.data else 0
                return f"✅ 批量入库完成: 成功创建 {count} 项资产"

            elif action == "batch_allocate":
                asset_ids = args.get("asset_ids", [])
                to_user_id = args.get("to_user_id")
                if not asset_ids or not to_user_id:
                    return "❌ 批量分配需要 asset_ids 和 to_user_id"
                if err := _validate_uuid(to_user_id, "to_user_id"):
                    return f"❌ {err}"

                count = 0
                for aid in asset_ids:
                    await (
                        client.table("assets")
                        .update({"current_user_id": to_user_id, "status": "in_use"})
                        .eq("id", aid)
                        .execute()
                    )
                    await client.table("asset_transfers").insert({
                        "organization_id": org_id,
                        "asset_id": aid,
                        "transfer_type": "allocate",
                        "to_user_id": to_user_id,
                        "reason": reason or "批量分配",
                        "operator_id": user_id,
                    }).execute()
                    count += 1
                return f"✅ 批量分配完成: {count} 项资产已分配"

            elif action == "batch_scrap":
                asset_ids = args.get("asset_ids", [])
                if not asset_ids:
                    return "❌ 请提供要报废的资产ID列表"

                count = 0
                for aid in asset_ids:
                    asset_resp = await (
                        client.table("assets")
                        .select("asset_type")
                        .eq("id", aid)
                        .maybe_single()
                        .execute()
                    )
                    await (
                        client.table("assets")
                        .update({"status": "scrapped", "current_user_id": None})
                        .eq("id", aid)
                        .execute()
                    )
                    await client.table("asset_transfers").insert({
                        "organization_id": org_id,
                        "asset_id": aid,
                        "transfer_type": "scrap",
                        "reason": reason or "批量报废",
                        "operator_id": user_id,
                    }).execute()

                    # 触发报废事件（检查库存）
                    if asset_resp.data:
                        await emit(
                            EventType.ASSET_SCRAPPED.value,
                            payload={
                                "asset_id": aid,
                                "asset_type": asset_resp.data.get("asset_type"),
                                "org_id": org_id,
                            },
                            user_id=user_id,
                        )
                    count += 1
                return f"✅ 批量报废完成: {count} 项资产已报废"

            else:
                return f"❌ 不支持的操作类型: {action}"

        except Exception as e:
            logger.error(f"资产生命周期操作失败: {e}")
            return f"❌ 操作失败: {str(e)}"
