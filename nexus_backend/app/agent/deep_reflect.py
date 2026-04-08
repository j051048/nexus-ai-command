"""深度反思机制 - Tree of Thoughts

通过 LLM 生成多个候选方案，评估并选择最优策略，
用于 COMPLEX/CRITICAL 查询的重规划阶段。
"""

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

_GENERATE_PROMPT = """你是一个策略规划专家。针对以下问题，请提出3种不同的解决方案。

## 问题描述
{plan}

## 上下文
- 用户意图: {intent}
- 已尝试工具: {tools_used}

## 要求
为每个方案提供:
- approach: 方案名称和简要描述
- reasoning: 为什么这个方案可行
- score: 预估有效性 (0-1)
- tool_chain: 建议使用的工具列表

请严格按照以下 JSON 格式返回，不要输出其他内容:
[
  {{"approach": "...", "reasoning": "...", "score": 0.8, "tool_chain": ["tool1", "tool2"]}},
  {{"approach": "...", "reasoning": "...", "score": 0.7, "tool_chain": ["tool1"]}},
  {{"approach": "...", "reasoning": "...", "score": 0.6, "tool_chain": ["tool1", "tool2", "tool3"]}}
]"""

_EVALUATE_PROMPT = """请评估以下方案的可行性。

## 方案
{approach}

## 上下文
{context}

请严格按照以下 JSON 格式返回，不要输出其他内容:
{{"feasibility": 0.8, "completeness": 0.7, "risk": 0.2}}"""


class DeepReflector:
    async def generate_alternatives(
        self,
        plan: str,
        context: dict | None = None,
        config=None,
    ) -> list[dict]:
        """使用 LLM 生成多个候选方案 (Tree of Thoughts)。"""
        context = context or {}
        if not config:
            logger.warning("[DeepReflect] 无 config，返回透传方案")
            return [{"approach": plan, "reasoning": "直接执行", "score": 0.5, "tool_chain": []}]

        try:
            from app.services.llm_helpers import resolve_model_config

            org_id = getattr(config, "org_id", "default") or "default"
            resolved = None
            if hasattr(config, "resolved_configs") and config.resolved_configs:
                resolved = config.resolved_configs.get("economy") or config.resolved_configs.get("balanced")
            if not resolved:
                resolved = await resolve_model_config(org_id, complexity_tier="economy")

            llm = ChatOpenAI(
                model=resolved.get("model", getattr(config, "mini_model", "gpt-4o-mini")),
                api_key=resolved.get("api_key") or config.api_key,
                base_url=resolved.get("base_url") or config.base_url,
                temperature=0.7,
                max_tokens=800,
            )

            prompt = _GENERATE_PROMPT.format(
                plan=plan[:500],
                intent=context.get("intent", "")[:200],
                tools_used=", ".join(context.get("tools_used", [])[:5]) or "无",
            )

            resp = await llm.ainvoke([
                SystemMessage(content="你是策略规划专家，只返回JSON。"),
                HumanMessage(content=prompt),
            ])

            raw = resp.content.strip()
            # 提取 JSON 数组
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                raise ValueError(f"未找到JSON数组: {raw[:200]}")

            alternatives = json.loads(match.group())
            # 校验结构
            valid = []
            for alt in alternatives:
                if isinstance(alt, dict) and "approach" in alt:
                    valid.append({
                        "approach": alt.get("approach", ""),
                        "reasoning": alt.get("reasoning", ""),
                        "score": float(alt.get("score", 0.5)),
                        "tool_chain": alt.get("tool_chain", []) if isinstance(alt.get("tool_chain"), list) else [],
                    })
            if valid:
                logger.info(f"[DeepReflect] 生成 {len(valid)} 个候选方案")
                return valid

            raise ValueError("解析后无有效方案")

        except Exception as e:
            logger.warning(f"[DeepReflect] 生成候选方案失败，回退透传: {e}")
            return [{"approach": plan, "reasoning": "直接执行(回退)", "score": 0.5, "tool_chain": []}]

    async def select_best(self, alternatives: list[dict]) -> dict:
        """选择最优方案：按 score 降序，同分时优先工具链更短的方案。"""
        if not alternatives:
            return {}
        return max(
            alternatives,
            key=lambda x: (x.get("score", 0), -len(x.get("tool_chain", []))),
        )

    async def evaluate_approach(
        self,
        approach: dict,
        context: dict | None = None,
        config=None,
    ) -> dict:
        """使用 LLM 对单个方案进行多维度评分。"""
        if not config:
            return approach

        try:
            from app.services.llm_helpers import resolve_model_config

            org_id = getattr(config, "org_id", "default") or "default"
            resolved = None
            if hasattr(config, "resolved_configs") and config.resolved_configs:
                resolved = config.resolved_configs.get("economy") or config.resolved_configs.get("balanced")
            if not resolved:
                resolved = await resolve_model_config(org_id, complexity_tier="economy")

            llm = ChatOpenAI(
                model=resolved.get("model", getattr(config, "mini_model", "gpt-4o-mini")),
                api_key=resolved.get("api_key") or config.api_key,
                base_url=resolved.get("base_url") or config.base_url,
                temperature=0.3,
                max_tokens=200,
            )

            prompt = _EVALUATE_PROMPT.format(
                approach=json.dumps(approach, ensure_ascii=False)[:500],
                context=json.dumps(context or {}, ensure_ascii=False)[:300],
            )

            resp = await llm.ainvoke([HumanMessage(content=prompt)])
            raw = resp.content.strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                scores = json.loads(match.group())
                feasibility = float(scores.get("feasibility", 0.5))
                completeness = float(scores.get("completeness", 0.5))
                risk = float(scores.get("risk", 0.5))
                # 综合分: 可行性和完整性越高越好，风险越低越好
                composite = (feasibility + completeness + (1 - risk)) / 3
                approach["score"] = round(composite, 2)
                approach["eval_detail"] = {"feasibility": feasibility, "completeness": completeness, "risk": risk}
                logger.info(f"[DeepReflect] 方案评估: score={composite:.2f}")
        except Exception as e:
            logger.warning(f"[DeepReflect] 方案评估失败: {e}")

        return approach


deep_reflector = DeepReflector()
