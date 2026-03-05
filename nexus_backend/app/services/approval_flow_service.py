"""
审批流程服务
提供审批流程的查询、创建、匹配等功能
"""

import logging

logger = logging.getLogger(__name__)


class ApprovalFlowService:
    """审批流程管理服务"""

    async def list_approval_flows(
        self,
        org_id: str,
        trigger_type: str | None = None,
        db=None,
    ) -> list[dict]:
        """
        查询审批流程列表

        Args:
            org_id: 组织ID
            trigger_type: 触发类型（可选）
            db: 数据库客户端

        Returns:
            审批流程列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = (
                db.table("approval_flows")
                .select("*")
                .eq("organization_id", org_id)
                .order("created_at", desc=True)
            )

            if trigger_type:
                query = query.eq("trigger_type", trigger_type)

            result = await query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"查询审批流程列表失败: {e}")
            raise

    async def create_approval_flow(
        self,
        org_id: str,
        name: str,
        trigger_type: str,
        steps: list[dict],
        conditions: dict | None = None,
        db=None,
    ) -> dict:
        """
        创建审批流程

        Args:
            org_id: 组织ID
            name: 流程名称
            trigger_type: 触发类型
            steps: 审批步骤
            conditions: 触发条件
            db: 数据库客户端

        Returns:
            审批流程对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            data = {
                "organization_id": org_id,
                "name": name,
                "trigger_type": trigger_type,
                "steps": steps,
                "conditions": conditions or {},
                "is_active": True,
            }

            result = await db.table("approval_flows").insert(data).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"审批流程已创建: org={org_id}, name={name}, trigger={trigger_type}")
                return result.data[0]

            raise RuntimeError("审批流程创建失败")

        except Exception as e:
            logger.error(f"创建审批流程失败: {e}")
            raise

    async def get_approval_flow(
        self,
        org_id: str,
        trigger_type: str,
        db=None,
    ) -> dict | None:
        """
        根据触发类型获取激活的审批流程

        Args:
            org_id: 组织ID
            trigger_type: 触发类型
            db: 数据库客户端

        Returns:
            审批流程对象，不存在则返回 None
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await (
                db.table("approval_flows")
                .select("*")
                .eq("organization_id", org_id)
                .eq("trigger_type", trigger_type)
                .eq("is_active", True)
                .maybe_single()
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"获取审批流程失败: {e}")
            raise


approval_flow_service = ApprovalFlowService()
