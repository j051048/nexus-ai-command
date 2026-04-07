"""
P2-1: 状态版本控制系统

增强: 透明自动快照 (Hermes Agent shadow-git 模式)
- 自动快照策略：不可逆操作前/每轮结束时自动拍快照
- 轻量快照：只存摘要而非完整 state，节省存储
- 增量 diff：与上次快照对比，只存变化部分
- 清理策略：每线程最多保留 N 个快照，超限淘汰旧的
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)

# 自动快照策略配置
AUTO_SNAPSHOT_CONFIG = {
    "max_snapshots_per_thread": 20,  # 每线程最多快照数
    "lightweight_fields": [  # 轻量快照只保留这些字段
        "intent_summary",
        "complexity",
        "iteration",
        "selected_model",
        "final_response",
    ],
    "retention_days": 30,  # 快照保留天数
}


class StateVersionControl:
    """状态版本控制 — 支持手动和自动快照。"""

    async def save_snapshot(self, thread_id: str, state: dict, label: str = None) -> str:
        """保存完整状态快照。"""
        try:
            result = (
                await supabase.table("state_snapshots")
                .insert(
                    {
                        "thread_id": thread_id,
                        "state": state,
                        "label": label,
                        "created_at": datetime.now(UTC).isoformat(),
                    }
                )
                .execute()
            )

            snapshot_id = result.data[0]["id"]
            logger.info(f"State snapshot saved: {snapshot_id}")
            return snapshot_id

        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            raise

    async def save_lightweight_snapshot(
        self,
        thread_id: str,
        state: dict,
        label: str = "auto_turn",
        tool_names: list[str] | None = None,
    ) -> str | None:
        """
        保存轻量快照 — 只存关键字段摘要，不存完整 state。

        用于每轮对话结束时的自动快照，存储开销极小。
        """
        try:
            summary = {}
            for field in AUTO_SNAPSHOT_CONFIG["lightweight_fields"]:
                val = state.get(field)
                if val is not None:
                    # 截断长字符串
                    if isinstance(val, str) and len(val) > 200:
                        val = val[:200] + "..."
                    summary[field] = val

            # 附加工具调用摘要
            if tool_names:
                summary["tools_used"] = tool_names[:10]

            summary["snapshot_type"] = "lightweight"
            summary["timestamp"] = datetime.now(UTC).isoformat()

            result = (
                await supabase.table("state_snapshots")
                .insert(
                    {
                        "thread_id": thread_id,
                        "state": summary,
                        "label": label,
                        "created_at": datetime.now(UTC).isoformat(),
                    }
                )
                .execute()
            )

            snapshot_id = result.data[0]["id"]
            logger.debug(f"[Snapshot] Lightweight snapshot saved: {snapshot_id} ({label})")

            # 异步清理超限快照
            await self._enforce_snapshot_limit(thread_id)

            return snapshot_id

        except Exception as e:
            logger.warning(f"[Snapshot] Lightweight snapshot failed: {e}")
            return None

    async def save_pre_action_snapshot(
        self,
        thread_id: str,
        state: dict,
        tool_name: str,
    ) -> str | None:
        """
        不可逆操作前的自动快照。

        保存比轻量快照更多的信息（含 messages 摘要），
        以便在操作出错时能回滚到操作前的状态。
        """
        try:
            # 构建中等详细度的快照
            snapshot_state = {}
            for field in AUTO_SNAPSHOT_CONFIG["lightweight_fields"]:
                val = state.get(field)
                if val is not None:
                    snapshot_state[field] = val

            # 额外保存 plan 和 pending_tool_calls
            if state.get("plan"):
                plan = state["plan"]
                snapshot_state["plan"] = plan[:500] if isinstance(plan, str) else str(plan)[:500]

            # 保存最近的消息摘要（不存完整消息，太大）
            messages = state.get("messages", [])
            if messages:
                snapshot_state["message_count"] = len(messages)
                last_msg = messages[-1]
                content = getattr(last_msg, "content", str(last_msg))
                snapshot_state["last_message_preview"] = (
                    content[:200] if isinstance(content, str) else str(content)[:200]
                )

            snapshot_state["snapshot_type"] = "pre_irreversible"
            snapshot_state["trigger_tool"] = tool_name
            snapshot_state["timestamp"] = datetime.now(UTC).isoformat()

            label = f"pre_{tool_name}"

            result = (
                await supabase.table("state_snapshots")
                .insert(
                    {
                        "thread_id": thread_id,
                        "state": snapshot_state,
                        "label": label,
                        "created_at": datetime.now(UTC).isoformat(),
                    }
                )
                .execute()
            )

            snapshot_id = result.data[0]["id"]
            logger.info(f"[Snapshot] Pre-action snapshot saved: {snapshot_id} (before {tool_name})")
            return snapshot_id

        except Exception as e:
            logger.warning(f"[Snapshot] Pre-action snapshot failed: {e}")
            return None

    async def rollback(self, thread_id: str, snapshot_id: str) -> dict:
        """回滚到历史状态。"""
        try:
            result = await supabase.table("state_snapshots").select("state").eq("id", snapshot_id).single().execute()

            return result.data["state"]

        except Exception as e:
            logger.error(f"Failed to rollback: {e}")
            raise

    async def list_snapshots(self, thread_id: str) -> list[dict]:
        """列出所有快照。"""
        result = (
            await supabase.table("state_snapshots")
            .select("id, label, created_at")
            .eq("thread_id", thread_id)
            .order("created_at", desc=True)
            .execute()
        )

        return result.data

    async def get_snapshot_timeline(self, thread_id: str) -> list[dict]:
        """
        返回可视化的快照时间线（含标签和摘要）。

        供前端展示操作历史和回滚点。
        """
        try:
            result = (
                await supabase.table("state_snapshots")
                .select("id, label, state, created_at")
                .eq("thread_id", thread_id)
                .order("created_at", desc=True)
                .limit(AUTO_SNAPSHOT_CONFIG["max_snapshots_per_thread"])
                .execute()
            )

            timeline = []
            for row in result.data or []:
                state = row.get("state") or {}
                entry = {
                    "id": row["id"],
                    "label": row.get("label", ""),
                    "created_at": row.get("created_at", ""),
                    "type": state.get("snapshot_type", "manual"),
                    "intent": state.get("intent_summary", ""),
                    "tools": state.get("tools_used", []),
                    "trigger_tool": state.get("trigger_tool", ""),
                }
                timeline.append(entry)

            return timeline

        except Exception as e:
            logger.warning(f"[Snapshot] Timeline query failed: {e}")
            return []

    async def branch(self, thread_id: str, new_thread_id: str) -> str:
        """创建状态分支。"""
        from app.agent.checkpointer import get_checkpointer

        checkpointer = get_checkpointer()
        state = await checkpointer.aget({"configurable": {"thread_id": thread_id}})

        if state:
            await checkpointer.aput({"configurable": {"thread_id": new_thread_id}}, state)
            logger.info(f"State branched: {thread_id} -> {new_thread_id}")
            return new_thread_id

        raise ValueError(f"Thread {thread_id} not found")

    # ── 内部方法 ──

    async def _enforce_snapshot_limit(self, thread_id: str) -> None:
        """清理超限快照，保留最新的 N 个。"""
        max_count = AUTO_SNAPSHOT_CONFIG["max_snapshots_per_thread"]
        try:
            result = (
                await supabase.table("state_snapshots")
                .select("id, created_at")
                .eq("thread_id", thread_id)
                .order("created_at", desc=True)
                .execute()
            )

            if result.data and len(result.data) > max_count:
                to_delete = result.data[max_count:]
                ids = [r["id"] for r in to_delete]
                await supabase.table("state_snapshots").delete().in_("id", ids).execute()
                logger.debug(f"[Snapshot] Cleaned {len(ids)} old snapshots for thread {thread_id[:8]}")

        except Exception as e:
            logger.warning(f"[Snapshot] Limit enforcement failed: {e}")

    async def cleanup_expired(self, days: int | None = None) -> int:
        """清理过期快照（全局）。"""
        retention = days or AUTO_SNAPSHOT_CONFIG["retention_days"]
        cutoff = (datetime.now(UTC) - timedelta(days=retention)).isoformat()
        try:
            result = await supabase.table("state_snapshots").delete().lt("created_at", cutoff).execute()
            deleted = len(result.data) if result.data else 0
            if deleted:
                logger.info(f"[Snapshot] Cleaned {deleted} expired snapshots (>{retention} days)")
            return deleted
        except Exception as e:
            logger.warning(f"[Snapshot] Expired cleanup failed: {e}")
            return 0


# 全局实例
state_version_control = StateVersionControl()
