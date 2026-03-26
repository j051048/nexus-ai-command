"""
P2-1: 状态版本控制系统
"""

import logging
from datetime import datetime

from app.core.database import supabase

logger = logging.getLogger(__name__)


class StateVersionControl:
    """状态版本控制"""

    async def save_snapshot(
        self,
        thread_id: str,
        state: dict,
        label: str = None
    ) -> str:
        """保存状态快照"""
        try:
            result = await supabase.table("state_snapshots").insert({
                "thread_id": thread_id,
                "state": state,
                "label": label,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

            snapshot_id = result.data[0]["id"]
            logger.info(f"State snapshot saved: {snapshot_id}")
            return snapshot_id

        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            raise

    async def rollback(self, thread_id: str, snapshot_id: str) -> dict:
        """回滚到历史状态"""
        try:
            result = await supabase.table("state_snapshots")\
                .select("state")\
                .eq("id", snapshot_id)\
                .single()\
                .execute()

            return result.data["state"]

        except Exception as e:
            logger.error(f"Failed to rollback: {e}")
            raise

    async def list_snapshots(self, thread_id: str) -> list[dict]:
        """列出所有快照"""
        result = await supabase.table("state_snapshots")\
            .select("id, label, created_at")\
            .eq("thread_id", thread_id)\
            .order("created_at", desc=True)\
            .execute()

        return result.data

    async def branch(self, thread_id: str, new_thread_id: str) -> str:
        """创建状态分支"""
        from app.agent.checkpointer import get_checkpointer

        checkpointer = get_checkpointer()
        state = await checkpointer.aget({"configurable": {"thread_id": thread_id}})

        if state:
            await checkpointer.aput(
                {"configurable": {"thread_id": new_thread_id}},
                state
            )
            logger.info(f"State branched: {thread_id} -> {new_thread_id}")
            return new_thread_id

        raise ValueError(f"Thread {thread_id} not found")


# 全局实例
state_version_control = StateVersionControl()
