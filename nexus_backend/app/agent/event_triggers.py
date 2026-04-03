"""
P0-3: 事件驱动触发器 - 数据变化时自动执行

核心功能:
1. 监听数据库变化
2. 条件匹配触发
3. 自动执行 Agent 任务
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from app.core.database import supabase
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)


class EventTrigger:
    """事件驱动触发器"""

    def __init__(self):
        self.triggers: dict[str, dict] = {}

    def register_trigger(
        self,
        trigger_id: str,
        table_name: str,
        condition: Callable[[dict], bool],
        prompt_template: str,
        user_id: str,
        org_id: str = "default"
    ):
        """
        注册触发器

        Args:
            trigger_id: 触发器唯一标识
            table_name: 监听的表名
            condition: 触发条件函数
            prompt_template: Agent 提示词模板
            user_id: 用户 ID
            org_id: 组织 ID
        """
        self.triggers[trigger_id] = {
            "table": table_name,
            "condition": condition,
            "prompt": prompt_template,
            "user_id": user_id,
            "org_id": org_id
        }

    async def check_and_trigger(self, table_name: str, record: dict):
        """检查并触发匹配的触发器"""
        for trigger_id, config in self.triggers.items():
            if config["table"] != table_name:
                continue

            try:
                if config["condition"](record):
                    await self._execute_trigger(trigger_id, config, record)
            except Exception as e:
                logger.error(f"Trigger {trigger_id} check failed: {e}")

    async def _execute_trigger(self, trigger_id: str, config: dict, record: dict):
        """执行触发器"""
        try:
            # 生成提示词
            prompt = config["prompt"].format(**record)

            # 触发 Agent
            chat_service = ChatService()
            await chat_service.send_message(
                user_id=config["user_id"],
                org_id=config["org_id"],
                message=prompt,
                session_id=f"trigger_{trigger_id}_{datetime.utcnow().timestamp()}"
            )

            logger.info(f"Trigger {trigger_id} executed for record {record.get('id')}")

        except Exception as e:
            logger.error(f"Trigger execution failed: {e}")

    async def check_contract_expiring(self):
        """检查即将到期的合同"""
        seven_days_later = (datetime.utcnow() + timedelta(days=7)).isoformat()

        result = await supabase.table("contracts")\
            .select("*")\
            .eq("status", "active")\
            .lt("end_date", seven_days_later)\
            .execute()

        for contract in result.data:
            await self.check_and_trigger("contracts", contract)

    async def check_sales_milestone(self):
        """检查销售里程碑"""
        result = await supabase.rpc("get_monthly_sales_summary").execute()

        if result.data:
            await self.check_and_trigger("sales_summary", result.data[0])


# 全局实例
event_trigger = EventTrigger()


# 预定义触发器
def register_default_triggers():
    """注册默认触发器"""

    # 合同到期提醒
    event_trigger.register_trigger(
        trigger_id="contract_expiring",
        table_name="contracts",
        condition=lambda r: r.get("status") == "active",
        prompt_template="合同 {name} 将在 7 天后到期，请提醒相关人员续签",
        user_id="system",
        org_id="default"
    )

    # 销售里程碑
    event_trigger.register_trigger(
        trigger_id="sales_milestone",
        table_name="sales_summary",
        condition=lambda r: r.get("total_amount", 0) >= 100000,
        prompt_template="恭喜！本月销售额已达到 {total_amount} 元，请生成庆祝通知",
        user_id="system",
        org_id="default"
    )
