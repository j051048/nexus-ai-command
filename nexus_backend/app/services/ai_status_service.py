"""
P2 Enhancement: AI Status Service

Implements clear AI state indicators for better UX.
Fixes Issue #18: No clear AI state indicator during thinking.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AIState(Enum):
    """AI processing states."""
    IDLE = "idle"
    THINKING = "thinking"
    ANALYZING = "analyzing"
    SEARCHING = "searching"
    GENERATING = "generating"
    TOOL_CALLING = "tool_calling"
    WAITING_INPUT = "waiting_input"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class StatusIndicator:
    """Status indicator for AI state."""
    state: AIState
    message: str
    sub_message: str = ""
    progress: float = 0.0  # 0.0 to 1.0
    icon: str = "🤖"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class AIStatusService:
    """
    P2 Enhancement: Clear AI state indicators.

    Features:
    - Real-time status updates
    - Progress tracking
    - Estimated time remaining
    - State history
    - WebSocket/SSE integration ready
    """

    # State configurations
    STATE_CONFIGS = {
        AIState.IDLE: {
            "icon": "⚪",
            "message": "AI助手就绪",
            "color": "gray"
        },
        AIState.THINKING: {
            "icon": "🤔",
            "message": "正在思考...",
            "color": "blue"
        },
        AIState.ANALYZING: {
            "icon": "🔍",
            "message": "正在分析...",
            "color": "purple"
        },
        AIState.SEARCHING: {
            "icon": "🔎",
            "message": "正在搜索...",
            "color": "yellow"
        },
        AIState.GENERATING: {
            "icon": "✨",
            "message": "正在生成回复...",
            "color": "green"
        },
        AIState.TOOL_CALLING: {
            "icon": "🔧",
            "message": "正在调用工具...",
            "color": "orange"
        },
        AIState.WAITING_INPUT: {
            "icon": "⏳",
            "message": "等待输入...",
            "color": "yellow"
        },
        AIState.ERROR: {
            "icon": "❌",
            "message": "处理出错",
            "color": "red"
        },
        AIState.COMPLETED: {
            "icon": "✅",
            "message": "处理完成",
            "color": "green"
        }
    }

    # Thinking messages for variety
    THINKING_MESSAGES = [
        "正在思考...",
        "分析您的问题中...",
        "组织回答思路...",
        "查阅相关知识...",
        "构思最佳回复...",
    ]

    def __init__(self):
        self._current_states: dict[str, StatusIndicator] = {}  # session_id -> status
        self._state_history: dict[str, list[StatusIndicator]] = {}  # session_id -> history
        self._state_timers: dict[str, float] = {}  # session_id -> start_time
        self._progress_callbacks: list[callable] = []
        self._max_history = 50

    def register_progress_callback(self, callback: callable):
        """Register a callback for status updates."""
        self._progress_callbacks.append(callback)

    async def set_state(
        self,
        session_id: str,
        state: AIState,
        message: str = None,
        sub_message: str = "",
        progress: float = None,
        metadata: dict = None
    ) -> StatusIndicator:
        """
        Set AI state for a session.

        Args:
            session_id: Session identifier
            state: New AI state
            message: Custom message (uses default if None)
            sub_message: Additional detail message
            progress: Progress percentage (0.0 to 1.0)
            metadata: Additional metadata

        Returns:
            StatusIndicator object
        """
        config = self.STATE_CONFIGS.get(state, {})

        # Calculate duration
        duration_ms = 0
        if session_id in self._state_timers:
            duration_ms = int((time.time() - self._state_timers[session_id]) * 1000)

        # Create indicator
        indicator = StatusIndicator(
            state=state,
            message=message or config.get("message", ""),
            sub_message=sub_message,
            progress=progress if progress is not None else self._get_default_progress(state),
            icon=config.get("icon", "🤖"),
            duration_ms=duration_ms,
            metadata=metadata or {}
        )

        # Store state
        self._current_states[session_id] = indicator

        # Add to history
        if session_id not in self._state_history:
            self._state_history[session_id] = []
        self._state_history[session_id].append(indicator)

        # Trim history
        if len(self._state_history[session_id]) > self._max_history:
            self._state_history[session_id] = self._state_history[session_id][-self._max_history:]

        # Start timer for new processing states
        if state in [AIState.THINKING, AIState.ANALYZING, AIState.GENERATING, AIState.SEARCHING]:
            self._state_timers[session_id] = time.time()

        # Notify callbacks
        await self._notify_callbacks(session_id, indicator)

        logger.debug(f"AI State [{session_id}]: {state.value} - {indicator.message}")
        return indicator

    def _get_default_progress(self, state: AIState) -> float:
        """Get default progress for a state."""
        progress_map = {
            AIState.IDLE: 0.0,
            AIState.THINKING: 0.2,
            AIState.ANALYZING: 0.3,
            AIState.SEARCHING: 0.4,
            AIState.GENERATING: 0.6,
            AIState.TOOL_CALLING: 0.5,
            AIState.WAITING_INPUT: 0.0,
            AIState.ERROR: 0.0,
            AIState.COMPLETED: 1.0
        }
        return progress_map.get(state, 0.0)

    async def update_progress(
        self,
        session_id: str,
        progress: float,
        message: str = None
    ) -> StatusIndicator | None:
        """Update progress for current state."""
        if session_id not in self._current_states:
            return None

        current = self._current_states[session_id]

        # Update progress
        current.progress = min(1.0, max(0.0, progress))
        if message:
            current.sub_message = message

        await self._notify_callbacks(session_id, current)
        return current

    async def _notify_callbacks(self, session_id: str, indicator: StatusIndicator):
        """Notify all registered callbacks."""
        for callback in self._progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(session_id, indicator)
                else:
                    callback(session_id, indicator)
            except Exception as e:
                logger.error(f"Status callback error: {e}")

    def get_state(self, session_id: str) -> StatusIndicator | None:
        """Get current state for a session."""
        return self._current_states.get(session_id)

    def get_history(self, session_id: str, limit: int = 10) -> list[StatusIndicator]:
        """Get state history for a session."""
        history = self._state_history.get(session_id, [])
        return history[-limit:]

    def get_all_active(self) -> dict[str, StatusIndicator]:
        """Get all active states."""
        return {
            sid: indicator
            for sid, indicator in self._current_states.items()
            if indicator.state not in [AIState.IDLE, AIState.COMPLETED, AIState.ERROR]
        }

    def get_estimated_remaining(self, session_id: str) -> int | None:
        """
        Estimate remaining time in ms based on progress.
        Returns None if cannot estimate.
        """
        if session_id not in self._current_states:
            return None

        indicator = self._current_states[session_id]

        if indicator.progress <= 0.1 or indicator.state not in [AIState.GENERATING, AIState.THINKING]:
            return None

        # Calculate elapsed time
        if session_id not in self._state_timers:
            return None

        elapsed_ms = (time.time() - self._state_timers[session_id]) * 1000

        # Estimate remaining based on progress
        if indicator.progress > 0:
            total_estimated = elapsed_ms / indicator.progress
            remaining = total_estimated - elapsed_ms
            return int(max(0, remaining))

        return None

    def to_dict(self, indicator: StatusIndicator) -> dict:
        """Convert indicator to dict for API response."""
        config = self.STATE_CONFIGS.get(indicator.state, {})

        return {
            "state": indicator.state.value,
            "message": indicator.message,
            "subMessage": indicator.sub_message,
            "progress": round(indicator.progress * 100, 1),
            "icon": indicator.icon,
            "color": config.get("color", "gray"),
            "timestamp": indicator.timestamp,
            "durationMs": indicator.duration_ms,
            "estimatedRemainingMs": None,  # Will be filled if available
            "metadata": indicator.metadata
        }

    async def create_thinking_animation(self, session_id: str) -> 'ThinkingAnimation':
        """Create an animated thinking indicator."""
        return ThinkingAnimation(self, session_id)

    def clear_state(self, session_id: str):
        """Clear state for a session."""
        if session_id in self._current_states:
            del self._current_states[session_id]
        if session_id in self._state_timers:
            del self._state_timers[session_id]


class ThinkingAnimation:
    """
    Context manager for animated thinking indicator.
    """

    def __init__(self, status_service: AIStatusService, session_id: str):
        self.status_service = status_service
        self.session_id = session_id
        self._task = None
        self._running = False

    async def start(self, steps: list[str] = None):
        """Start thinking animation with steps."""
        self._running = True
        steps = steps or AIStatusService.THINKING_MESSAGES

        async def animate():
            idx = 0
            while self._running:
                await self.status_service.set_state(
                    self.session_id,
                    AIState.THINKING,
                    message=steps[idx % len(steps)]
                )
                idx += 1
                await asyncio.sleep(2)

        self._task = asyncio.create_task(animate())

    async def stop(self, final_state: AIState = AIState.COMPLETED):
        """Stop animation and set final state."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

        await self.status_service.set_state(self.session_id, final_state)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        final_state = AIState.ERROR if exc_type else AIState.COMPLETED
        await self.stop(final_state)


# Global instance
ai_status_service = AIStatusService()
