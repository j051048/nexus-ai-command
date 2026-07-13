"""Full Agent graph replay with an injectable deterministic executor."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, is_dataclass
from typing import Any

from app.services.agent_replay_harness import agent_replay_harness

GraphExecutor = Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]]


class FullGraphReplayService:
    async def run_case(
        self,
        case: dict[str, Any],
        *,
        executor: GraphExecutor | None = None,
    ) -> dict[str, Any]:
        state = self._initial_state(case)
        thread_id = str(case.get("thread_id") or f"replay:{case.get('id', 'case')}")
        runner = executor or self._execute_production_graph
        started = time.perf_counter()
        final_state = await runner(state, thread_id)
        duration_ms = int((time.perf_counter() - started) * 1000)
        trace = self._normalize_trace(final_state, duration_ms)
        result = agent_replay_harness.evaluate_trace(
            trace, case.get("expectations") or {}
        )
        return {
            "case_id": case.get("id"),
            "passed": result.passed,
            "score": result.score,
            "checks": result.checks,
            "trace": trace,
        }

    @staticmethod
    def _initial_state(case: dict[str, Any]) -> dict[str, Any]:
        from langchain_core.messages import HumanMessage

        from app.agent.state import AgentConfig

        config_data = {
            "user_id": str(case.get("user_id") or "replay-user"),
            "org_id": case.get("organization_id"),
            "user_role": str(case.get("user_role") or "employee"),
            "session_id": str(case.get("session_id") or "replay-session"),
            "agent_name": str(case.get("agent_code") or "default"),
            "dry_run": bool(case.get("dry_run", True)),
        }
        return {
            "messages": [HumanMessage(content=str(case.get("message") or ""))],
            "config": AgentConfig(**config_data),
            "iteration": 0,
            "thinking_steps": [],
            "tool_calls": [],
            "tool_results": [],
            "trace_id": str(case.get("id") or "replay"),
        }

    @staticmethod
    async def _execute_production_graph(
        state: dict[str, Any], thread_id: str
    ) -> dict[str, Any]:
        from app.agent.graph import get_agent_graph

        return await get_agent_graph().run(state, thread_id=thread_id)

    def _normalize_trace(
        self, final_state: dict[str, Any], duration_ms: int
    ) -> dict[str, Any]:
        steps = []
        for raw in final_state.get("thinking_steps") or []:
            item = self._to_dict(raw)
            steps.append(
                {
                    "node_type": item.get("phase") or item.get("node_type"),
                    "status": item.get("status"),
                    "error": item.get("error"),
                    "tool_calls": (
                        [
                            {
                                "name": item.get("tool_name"),
                                "args": item.get("tool_args") or {},
                            }
                        ]
                        if item.get("tool_name")
                        else []
                    ),
                }
            )
        for raw in final_state.get("tool_calls") or []:
            call = self._to_dict(raw)
            steps.append(
                {
                    "node_type": "execute",
                    "status": call.get("status"),
                    "error": call.get("error_type"),
                    "tool_calls": [call],
                }
            )
        if final_state.get("final_response") and not any(
            step.get("node_type") == "respond" for step in steps
        ):
            steps.append({"node_type": "respond", "tool_calls": []})
        return {
            "steps": steps,
            "final_state": self._json_safe_state(final_state),
            "final_response": final_state.get("final_response") or "",
            "total_tokens": int(final_state.get("total_input_tokens") or 0)
            + int(final_state.get("total_output_tokens") or 0),
            "total_duration_ms": duration_ms,
            "side_effects": final_state.get("side_effects") or [],
            "hitl_required": bool(final_state.get("requires_confirmation")),
            "evidence_contract": final_state.get("evidence_contract") or {},
        }

    @staticmethod
    def _to_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return {}

    @classmethod
    def _json_safe_state(cls, state: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in state.items():
            if key == "messages":
                continue
            safe_value = cls._json_safe_value(value)
            if safe_value is not None or value is None:
                safe[key] = safe_value
        return safe

    @classmethod
    def _json_safe_value(cls, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, dict):
            return {str(key): cls._json_safe_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._json_safe_value(item) for item in value]
        if is_dataclass(value):
            return cls._json_safe_value(asdict(value))
        if hasattr(value, "model_dump"):
            return cls._json_safe_value(value.model_dump())
        return str(value)


full_graph_replay_service = FullGraphReplayService()
