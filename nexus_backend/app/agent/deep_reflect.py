"""深度反思机制 - Tree of Thoughts

当复杂/关键任务多次反思仍未通过时，使用 LLM 生成多个候选方案，
评估可行性后选择最优路径，注入到下一轮规划中。
"""

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# 占位回退方案 — 任何异常时优雅降级
_FALLBACK_ALTERNATIVES = [
    {
        "approach": "方案A: 直接使用已有工具重新查询",
        "tools": [],
        "risk": "数据可能不完整",
        "score": 0.6,
    },
    {
        "approach": "方案B: 分步拆解问题逐一解决",
        "tools": [],
        "risk": "耗时较长",
        "score": 0.7,
    },
    {
        "approach": "方案C: 简化需求给出部分回答",
        "tools": [],
        "risk": "回答不够全面",
        "score": 0.5,
    },
]

_GENERATE_PROMPT = """你是一个策略规划专家。当前 AI Agent 在执行任务时遇到困难，需要你提出 3 个不同的解决方案。

## 当前计划
{plan}

## 上下文
- 用户意图: {intent_summary}
- 已有工具结果: {tool_results}
- 遇到的问题: {error_info}

## 要求
为每个方案提供:
- approach: 方案描述（一段话说明策略）
- tools: 建议使用的工具链（列表）
- risk: 潜在风险或局限性
- score: 自评可行性置信度（0-1，基于当前上下文）

请严格按照以下 JSON 格式返回，不要输出其他内容:
[
  {{"approach": "...", "tools": ["tool1", "tool2"], "risk": "...", "score": 0.8}},
  {{"approach": "...", "tools": ["tool1"], "risk": "...", "score": 0.7}},
  {{"approach": "...", "tools": [], "risk": "...", "score": 0.6}}
]"""

_EVALUATE_PROMPT = """请评估以下方案在当前上下文中的可行性。

## 方案
{approach}

## 上下文
- 用户意图: {intent_summary}
- 已有工具结果: {tool_results}

请返回一个 0-1 的可行性评分和简短理由。
严格按照以下 JSON 格式返回，不要输出其他内容:
{{"score": 0.8, "reason": "..."}}"""


class DeepReflector:
    """Tree of Thoughts 深度反思器。

    在常规反思无法解决问题时（高复杂度 + 多轮迭代），
    调用 LLM 生成多条候选路径并评估，选出最优方案。
    """

    async def generate_alternatives(
        self,
        plan: str,
        context: dict | None = None,
        config=None,
    ) -> list[dict]:
        """使用 LLM 生成 3 个不同的候选方案。

        Args:
            plan: 当前计划文本
            context: 包含 intent_summary, tool_results, error_info 的上下文字典
            config: AgentConfig，用于获取 LLM 访问凭据

        Returns:
            候选方案列表，每个包含 approach, tools, risk, score
        """
        ctx = context or {}
        if not config:
            logger.warning("[DeepReflect] 无 config，使用占位回退")
            return _FALLBACK_ALTERNATIVES

        try:
            llm = ChatOpenAI(
                model=getattr(config, "mini_model", None)
                or getattr(config, "model", "deepseek-v4-flash"),
                api_key=config.api_key,
                base_url=config.base_url,
                temperature=0.7,
                max_tokens=1000,
            )

            prompt = _GENERATE_PROMPT.format(
                plan=plan[:1500],
                intent_summary=ctx.get("intent_summary", "未知意图")[:300],
                tool_results=str(ctx.get("tool_results", "无工具结果"))[:1000],
                error_info=ctx.get("error_info", "无错误信息")[:500],
            )

            resp = await llm.ainvoke(
                [
                    SystemMessage(
                        content="你是 Tree of Thoughts 决策引擎，负责生成多条候选解决路径。只返回 JSON。"
                    ),
                    HumanMessage(content=prompt),
                ]
            )

            raw = resp.content.strip()
            # 提取 JSON 数组
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                # 解析失败 — 回退到单方案
                logger.warning(
                    "[DeepReflect] LLM 返回无法解析为 JSON 数组，使用原始文本作为单方案"
                )
                return [
                    {
                        "approach": raw[:500],
                        "tools": [],
                        "risk": "LLM输出格式异常",
                        "score": 0.5,
                    }
                ]

            alternatives = json.loads(match.group())
            # 校验结构完整性
            valid = []
            for alt in alternatives:
                if isinstance(alt, dict) and "approach" in alt:
                    valid.append(
                        {
                            "approach": alt.get("approach", ""),
                            "tools": (
                                alt.get("tools", [])
                                if isinstance(alt.get("tools"), list)
                                else []
                            ),
                            "risk": alt.get("risk", ""),
                            "score": float(alt.get("score", 0.5)),
                        }
                    )
            if valid:
                logger.info(f"[DeepReflect] LLM 生成 {len(valid)} 个候选方案")
                return valid

            raise ValueError("解析后无有效方案")

        except Exception as e:
            logger.error(f"[DeepReflect] generate_alternatives 失败，优雅降级: {e}")
            return _FALLBACK_ALTERNATIVES

    def select_best(self, alternatives: list[dict]) -> dict:
        """选择最优方案：按 score 降序，同分时优先选 risk 描述更短的（风险更低）。"""
        if not alternatives:
            return {}
        return max(
            alternatives,
            key=lambda x: (x.get("score", 0), -len(x.get("risk", ""))),
        )

    async def evaluate_approach(
        self,
        approach: dict,
        context: dict | None = None,
        config=None,
    ) -> dict:
        """使用 LLM 对单个方案进行可行性评估，返回更新后的 score。

        Args:
            approach: 待评估的方案 dict
            context: 上下文信息
            config: AgentConfig

        Returns:
            更新了 score 的方案 dict
        """
        if not config:
            return approach

        ctx = context or {}

        try:
            llm = ChatOpenAI(
                model=getattr(config, "mini_model", None)
                or getattr(config, "model", "deepseek-v4-flash"),
                api_key=config.api_key,
                base_url=config.base_url,
                temperature=0.3,
                max_tokens=200,
            )

            prompt = _EVALUATE_PROMPT.format(
                approach=json.dumps(approach, ensure_ascii=False)[:500],
                intent_summary=ctx.get("intent_summary", "未知意图")[:300],
                tool_results=str(ctx.get("tool_results", "无工具结果"))[:500],
            )

            resp = await llm.ainvoke(
                [
                    SystemMessage(content="你是方案可行性评估专家。只返回 JSON。"),
                    HumanMessage(content=prompt),
                ]
            )

            raw = resp.content.strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                new_score = float(parsed.get("score", approach.get("score", 0.5)))
                approach["score"] = max(0.0, min(1.0, new_score))
                if parsed.get("reason"):
                    approach["eval_reason"] = parsed["reason"]
                logger.info(
                    f"[DeepReflect] 方案评估完成，score={approach['score']:.2f}"
                )
        except Exception as e:
            logger.error(f"[DeepReflect] evaluate_approach 失败，保留原始 score: {e}")

        return approach


deep_reflector = DeepReflector()
