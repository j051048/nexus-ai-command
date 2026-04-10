"""
用户画像持久化系统 (Hermes-inspired USER.md pattern)

核心设计：
1. 从对话中自动提取用户偏好、沟通风格、常用操作
2. 持久化到 Supabase user_preferences 表
3. 冻结快照模式：session 开始时加载，中途写入不改 prompt
4. 注入 system prompt 供 agent 使用
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)

# 用户画像分类
PROFILE_CATEGORIES = {
    "communication_style": "沟通风格（简洁/详细、正式/随意）",
    "work_role": "工作角色和职责",
    "frequent_tasks": "常用操作和高频任务",
    "preferences": "个人偏好（语言、格式、时区等）",
    "domain_knowledge": "领域知识水平",
    "interaction_patterns": "交互模式（喜欢确认/直接执行）",
}

# 每个分类的最大条目数
MAX_ENTRIES_PER_CATEGORY = 10
# 画像总字符上限（注入 system prompt 时）
MAX_PROFILE_CHARS = 1500


class UserProfileManager:
    """用户画像管理器 — Hermes-inspired frozen snapshot pattern."""

    # 支持的偏好类型
    PREFERENCE_TYPES = {
        "communication_style",  # 沟通风格：简洁/详细/正式/随意
        "language_preference",  # 语言偏好：中文/英文/混合
        "report_format",  # 报告格式偏好：表格/图表/文字
        "notification_preference",  # 通知偏好：频繁/仅重要/静默
        "common_operations",  # 常用操作列表
        "work_schedule",  # 工作时间习惯
        "tool_preferences",  # 工具使用偏好
    }

    def __init__(self):
        self._snapshot_cache: dict[str, str] = {}  # user_id -> frozen prompt block

    async def build_profile_snapshot(
        self, user_id: str, org_id: str = "default"
    ) -> str:
        """构建用户画像快照，用于注入 system prompt。

        在 session 开始时调用一次，结果缓存在内存中。
        后续写入不会改变已缓存的快照（冻结模式）。
        """
        cache_key = f"{user_id}:{org_id}"
        if cache_key in self._snapshot_cache:
            return self._snapshot_cache[cache_key]

        try:
            result = (
                await supabase.table("user_preferences")
                .select("preference_type, preference_data, updated_at")
                .eq("user_id", user_id)
                .eq("org_id", org_id)
                .order("updated_at", desc=True)
                .execute()
            )

            if not result.data:
                return ""

            # 构建结构化画像文本
            parts = ["[用户画像 — 跨会话持久化]"]
            total_chars = 0

            for row in result.data:
                ptype = row.get("preference_type", "")
                pdata = row.get("preference_data", {})

                label = PROFILE_CATEGORIES.get(ptype, ptype)

                if isinstance(pdata, dict):
                    value = pdata.get("value", str(pdata))
                elif isinstance(pdata, str):
                    value = pdata
                else:
                    value = str(pdata)

                line = f"- {label}: {value}"
                if total_chars + len(line) > MAX_PROFILE_CHARS:
                    break
                parts.append(line)
                total_chars += len(line)

            parts.append("[用户画像结束]")
            snapshot = "\n".join(parts)

            self._snapshot_cache[cache_key] = snapshot
            logger.info(
                f"[UserProfile] Built snapshot for {user_id} ({len(parts) - 2} entries, {total_chars} chars)"
            )
            return snapshot

        except Exception as e:
            logger.error(f"[UserProfile] Failed to build snapshot: {e}")
            return ""

    def invalidate_cache(self, user_id: str, org_id: str = "default"):
        """清除缓存（下次 session 开始时重新加载）"""
        cache_key = f"{user_id}:{org_id}"
        self._snapshot_cache.pop(cache_key, None)

    async def learn_from_feedback(
        self, user_id: str, feedback_type: str, content: Any, org_id: str = "default"
    ):
        """从用户反馈学习（支持 dict/str 等任意 JSON 可序列化值）"""
        try:
            await supabase.table("user_preferences").upsert(
                {
                    "user_id": user_id,
                    "org_id": org_id,
                    "preference_type": feedback_type,
                    "preference_data": content,
                    "updated_at": datetime.now(UTC).isoformat(),
                },
                on_conflict="user_id,preference_type",
            ).execute()
            # 不清除缓存 — 冻结快照模式，当前 session 不受影响
            logger.info(f"[UserProfile] Learned {feedback_type} for {user_id}")
        except Exception as e:
            logger.error(f"[UserProfile] Failed to learn preference: {e}")

    async def learn_from_conversation(
        self, user_id: str, messages: list[dict], org_id: str = "default"
    ):
        """从对话历史中自动提取用户偏好。

        在 session 结束时异步调用，分析对话模式。
        """
        if not messages or len(messages) < 4:
            return  # 对话太短，不值得分析

        try:
            # 分析沟通风格
            user_msgs = [m for m in messages if m.get("role") == "user"]
            if not user_msgs:
                return

            # 统计消息长度分布
            avg_len = sum(len(m.get("content", "")) for m in user_msgs) / len(user_msgs)
            style = "detailed" if avg_len > 100 else "concise"

            await self.learn_from_feedback(
                user_id=user_id,
                feedback_type="communication_style",
                content={
                    "value": style,
                    "avg_msg_length": int(avg_len),
                    "sample_size": len(user_msgs),
                },
                org_id=org_id,
            )

            # 统计高频操作关键词
            all_text = " ".join(m.get("content", "") for m in user_msgs)
            freq_tasks = []
            task_keywords = {
                "请假": "leave_request",
                "报销": "expense_claim",
                "审批": "approval",
                "客户": "crm",
                "销售": "sales",
                "报告": "report",
                "分析": "analysis",
            }
            for kw, task_type in task_keywords.items():
                if kw in all_text:
                    freq_tasks.append(task_type)

            if freq_tasks:
                await self.learn_from_feedback(
                    user_id=user_id,
                    feedback_type="frequent_tasks",
                    content={"value": ", ".join(freq_tasks), "tasks": freq_tasks},
                    org_id=org_id,
                )

        except Exception as e:
            logger.error(f"[UserProfile] Failed to learn from conversation: {e}")

    async def get_preferences(self, user_id: str, org_id: str = "default") -> dict:
        """获取用户偏好（保留原有接口）"""
        try:
            result = (
                await supabase.table("user_preferences")
                .select("*")
                .eq("user_id", user_id)
                .eq("org_id", org_id)
                .execute()
            )
            prefs = {}
            for row in result.data:
                prefs[row["preference_type"]] = row["preference_data"]
            return prefs
        except Exception as e:
            logger.error(f"[UserProfile] Failed to get preferences: {e}")
            return {}

    async def auto_extract_preferences(
        self,
        user_id: str,
        user_message: str,
        assistant_response: str,
        org_id: str = "default",
    ) -> None:
        """从对话中自动提取用户偏好（后台异步执行，不阻塞响应）。

        检测模式：
        - "我喜欢简洁的回答" → communication_style: concise
        - "用表格展示" → report_format: table
        - "以后都用中文" → language_preference: chinese
        """
        # 简单的关键词匹配提取，不调用 LLM（零成本）
        style_hints = {
            "简洁": "concise",
            "详细": "detailed",
            "简短": "concise",
            "正式": "formal",
            "随意": "casual",
            "专业": "professional",
        }
        format_hints = {
            "表格": "table",
            "图表": "chart",
            "文字": "text",
            "列表": "list",
            "markdown": "markdown",
        }
        lang_hints = {
            "中文": "chinese",
            "英文": "english",
            "英语": "english",
            "混合": "mixed",
            "双语": "mixed",
        }

        combined = user_message.lower()

        for keyword, value in style_hints.items():
            if keyword in combined and any(
                v in combined for v in ["喜欢", "偏好", "以后", "总是", "习惯"]
            ):
                await self.learn_from_feedback(
                    user_id, "communication_style", value, org_id
                )
                logger.info(
                    f"[UserProfile] Extracted communication_style={value} for {user_id}"
                )
                break

        for keyword, value in format_hints.items():
            if keyword in combined and any(
                v in combined for v in ["用", "展示", "显示", "格式"]
            ):
                await self.learn_from_feedback(user_id, "report_format", value, org_id)
                logger.info(
                    f"[UserProfile] Extracted report_format={value} for {user_id}"
                )
                break

        for keyword, value in lang_hints.items():
            if keyword in combined and any(
                v in combined for v in ["用", "以后", "总是", "偏好", "回答"]
            ):
                await self.learn_from_feedback(
                    user_id, "language_preference", value, org_id
                )
                logger.info(
                    f"[UserProfile] Extracted language_preference={value} for {user_id}"
                )
                break


# 向后兼容：PreferenceLearner 作为 UserProfileManager 的别名
PreferenceLearner = UserProfileManager

# 全局实例（保持向后兼容）
preference_learner = UserProfileManager()
# 别名
user_profile_manager = preference_learner
