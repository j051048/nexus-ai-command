"""
P2-2: 子 Agent 隔离系统
"""

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from app.agent.state import AgentState
from app.agent.nodes import execute_node, plan_node

logger = logging.getLogger(__name__)


class SubAgent:
    """独立子 Agent"""

    def __init__(self, name: str, tools: list[str], system_prompt: str = None):
        self.name = name
        self.tools = tools
        self.system_prompt = system_prompt or f"你是 {name} 专家"
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """构建独立图"""
        graph = StateGraph(AgentState)

        graph.add_node("plan", plan_node)
        graph.add_node("execute", execute_node)

        graph.set_entry_point("plan")
        graph.add_edge("plan", "execute")
        graph.add_edge("execute", END)

        return graph.compile()

    async def execute(self, task: dict) -> dict:
        """独立执行任务"""
        try:
            result = await self.graph.ainvoke({
                "messages": [{"role": "user", "content": task["description"]}],
                "config": task.get("config", {})
            })
            return result
        except Exception as e:
            logger.error(f"SubAgent {self.name} failed: {e}")
            return {"error": str(e)}


class SupervisorAgent:
    """主管 Agent - 任务委派"""

    def __init__(self):
        self.sub_agents = {
            "content_writer": SubAgent(
                "content_writer",
                ["write_article", "edit_content"],
                "你是内容创作专家"
            ),
            "data_analyst": SubAgent(
                "data_analyst",
                ["analyze_data", "generate_report"],
                "你是数据分析专家"
            ),
            "customer_service": SubAgent(
                "customer_service",
                ["reply_customer", "handle_complaint"],
                "你是客服专家"
            )
        }

    async def delegate(self, task: dict) -> dict:
        """任务委派"""
        task_type = task.get("type", "general")

        if task_type in self.sub_agents:
            sub_agent = self.sub_agents[task_type]
            return await sub_agent.execute(task)

        return {"error": f"Unknown task type: {task_type}"}


# 全局实例
supervisor = SupervisorAgent()
