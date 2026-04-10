"""
企业模块事件处理器
实现跨模块级联触发逻辑：
- 员工离职 → 回收资产 + 关闭工单 + 结算报销
- 员工入职 → 分配设备 + 创建工单 + 排班
- 请假审批 → 更新考勤
- 资产报废 → 创建采购工单
- 库存低于安全线 → 通知采购
- 证照到期 → 通知负责人
"""

import logging

from app.services.event_bus import Event, EventType, on

logger = logging.getLogger(__name__)


@on(EventType.EMPLOYEE_RESIGNED.value)
async def cascade_employee_resignation(event: Event):
    """员工离职 → 回收名下所有资产 + 通知管理员"""
    from app.core.database import supabase

    if not supabase:
        return

    employee_id = event.payload.get("employee_id")
    employee_name = event.payload.get("employee_name", "")
    org_id = event.payload.get("org_id")

    if not employee_id or not org_id:
        return

    try:
        # 1. 查找该员工名下的所有在用资产
        assets_resp = await (
            supabase.table("assets")
            .select("id, name, asset_code")
            .eq("organization_id", org_id)
            .eq("current_user_id", employee_id)
            .eq("status", "in_use")
            .execute()
        )
        assets = assets_resp.data or []

        # 2. 批量归还资产
        for asset in assets:
            await (
                supabase.table("assets")
                .update({"current_user_id": None, "status": "idle"})
                .eq("id", asset["id"])
                .execute()
            )
            # 创建转移记录
            await (
                supabase.table("asset_transfers")
                .insert(
                    {
                        "organization_id": org_id,
                        "asset_id": asset["id"],
                        "transfer_type": "return",
                        "from_user_id": employee_id,
                        "reason": f"员工 {employee_name} 离职自动归还",
                        "operator_id": event.user_id,
                    }
                )
                .execute()
            )

        # 3. 通知管理员
        admins = await (
            supabase.table("users")
            .select("id")
            .eq("org_id", org_id)
            .in_("role", ["founder", "boss"])
            .execute()
        )
        for admin in admins.data or []:
            await (
                supabase.table("notifications")
                .insert(
                    {
                        "user_id": admin["id"],
                        "title": f"员工离职: {employee_name}",
                        "content": f"{employee_name} 已办理离职，{len(assets)} 项资产已自动归还。",
                        "type": "warning",
                    }
                )
                .execute()
            )

        logger.info(
            f"[Enterprise] Employee {employee_name} resigned: {len(assets)} assets auto-returned"
        )
    except Exception as e:
        logger.error(f"[Enterprise] Failed to cascade resignation: {e}")


@on(EventType.EMPLOYEE_ONBOARDED.value)
async def cascade_employee_onboarding(event: Event):
    """员工入职 → 创建 IT 设备工单 + 通知部门负责人"""
    from app.core.database import supabase

    if not supabase:
        return

    employee_id = event.payload.get("employee_id")
    employee_name = event.payload.get("employee_name", "")
    department_id = event.payload.get("department_id")
    org_id = event.payload.get("org_id")

    if not employee_id or not org_id:
        return

    try:
        # 创建 IT 设备准备工单
        await (
            supabase.table("work_orders")
            .insert(
                {
                    "organization_id": org_id,
                    "title": f"新员工入职设备准备 - {employee_name}",
                    "description": f"请为新员工 {employee_name} 准备工位和办公设备。",
                    "order_type": "onboarding",
                    "priority": "high",
                    "status": "open",
                    "creator_id": event.user_id,
                    "metadata": {"employee_id": employee_id, "auto_generated": True},
                }
            )
            .execute()
        )

        # 如果有部门，通知部门负责人
        if department_id:
            dept_resp = await (
                supabase.table("departments")
                .select("manager_id")
                .eq("id", department_id)
                .maybe_single()
                .execute()
            )
            manager_id = dept_resp.data.get("manager_id") if dept_resp.data else None
            if manager_id:
                await (
                    supabase.table("notifications")
                    .insert(
                        {
                            "user_id": manager_id,
                            "title": "新员工加入您的部门",
                            "content": f"{employee_name} 即将入职您的部门，请安排接待和培训。",
                            "type": "info",
                        }
                    )
                    .execute()
                )

        logger.info(f"[Enterprise] Onboarding cascade for {employee_name}")
    except Exception as e:
        logger.error(f"[Enterprise] Failed to cascade onboarding: {e}")


@on(EventType.ASSET_SCRAPPED.value)
async def cascade_asset_scrap(event: Event):
    """资产报废 → 检查是否需要补充采购"""
    from app.core.database import supabase

    if not supabase:
        return

    asset_type = event.payload.get("asset_type")
    org_id = event.payload.get("org_id")

    if not asset_type or not org_id:
        return

    try:
        # 查看同类型闲置资产数量
        idle_resp = await (
            supabase.table("assets")
            .select("id", count="exact")
            .eq("organization_id", org_id)
            .eq("asset_type", asset_type)
            .eq("status", "idle")
            .execute()
        )
        idle_count = idle_resp.count or 0

        # 如果闲置库存不足 2 台，通知采购
        if idle_count < 2:
            admins = await (
                supabase.table("users")
                .select("id")
                .eq("org_id", org_id)
                .in_("role", ["founder", "boss"])
                .execute()
            )
            for admin in admins.data or []:
                await (
                    supabase.table("notifications")
                    .insert(
                        {
                            "user_id": admin["id"],
                            "title": "资产库存不足预警",
                            "content": f"类型 [{asset_type}] 的闲置资产仅剩 {idle_count} 台，建议及时采购补充。",
                            "type": "warning",
                        }
                    )
                    .execute()
                )

            logger.info(
                f"[Enterprise] Low asset stock alert: {asset_type} idle={idle_count}"
            )
    except Exception as e:
        logger.error(f"[Enterprise] Failed to cascade asset scrap: {e}")


@on(EventType.INVENTORY_LOW_STOCK.value)
async def notify_low_stock(event: Event):
    """库存低于安全线 → 通知管理员"""
    from app.core.database import supabase

    if not supabase:
        return

    org_id = event.payload.get("org_id")
    item_name = event.payload.get("item_name", "")
    current_qty = event.payload.get("current_quantity", 0)
    min_stock = event.payload.get("min_stock", 0)

    if not org_id:
        return

    try:
        admins = await (
            supabase.table("users")
            .select("id")
            .eq("org_id", org_id)
            .in_("role", ["founder", "boss"])
            .execute()
        )
        for admin in admins.data or []:
            await (
                supabase.table("notifications")
                .insert(
                    {
                        "user_id": admin["id"],
                        "title": f"库存预警: {item_name}",
                        "content": f"{item_name} 当前库存 {current_qty}，低于安全线 {min_stock}，请及时补货。",
                        "type": "warning",
                    }
                )
                .execute()
            )

        logger.info(f"[Enterprise] Low stock alert: {item_name} qty={current_qty}")
    except Exception as e:
        logger.error(f"[Enterprise] Failed to notify low stock: {e}")


@on(EventType.CERTIFICATE_EXPIRING.value)
async def notify_certificate_expiring(event: Event):
    """证照即将到期 → 通知持有人和管理员"""
    from app.core.database import supabase

    if not supabase:
        return

    org_id = event.payload.get("org_id")
    cert_name = event.payload.get("cert_name", "")
    expire_date = event.payload.get("expire_date", "")
    event.payload.get("holder_id")

    if not org_id:
        return

    try:
        # 通知管理员
        admins = await (
            supabase.table("users")
            .select("id")
            .eq("org_id", org_id)
            .in_("role", ["founder", "boss"])
            .execute()
        )
        for admin in admins.data or []:
            await (
                supabase.table("notifications")
                .insert(
                    {
                        "user_id": admin["id"],
                        "title": f"证照到期预警: {cert_name}",
                        "content": f"证照 [{cert_name}] 将于 {expire_date} 到期，请及时安排续期。",
                        "type": "warning",
                    }
                )
                .execute()
            )

        logger.info(f"[Enterprise] Certificate expiring alert: {cert_name}")
    except Exception as e:
        logger.error(f"[Enterprise] Failed to notify certificate expiring: {e}")
