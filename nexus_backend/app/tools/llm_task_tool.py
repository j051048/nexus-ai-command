"""
LLM Task Delegation Tool — 将简单子任务路由到轻量模型

让 Agent 可以将翻译、摘要、格式化等简单子任务委派给 mini 模型，
避免消耗主模型的 token 配额，降低成本。
"""

import logging
from typing import Any

from app.services.ai_service import AIService

from .base_tool import BaseTool
from app.tools._shared import safe_tool_error

logger = logging.getLogger(__name__)


class LLMTaskTool(BaseTool):
    """将简单子任务委派给轻量 LLM 处理"""

    name = "llm_task"
    domain = "system"
    description = (
        "将简单文本处理子任务委派给轻量模型执行，仅限短文本场景"
    )
    examples = [
        {"input": {"task_type": "translate", "instruction": "将以下内容翻译成英文", "content": "人工智能正在改变销售行业"}, "output_summary": "返回英文翻译结果"},
        {"input": {"task_type": "summarize", "instruction": "提炼关键信息", "content": "一段较长的会议纪要...", "output_format": "要点列表"}, "output_summary": "返回要点形式的摘要"},
        {"input": {"task_type": "extract", "instruction": "提取客户联系方式", "content": "邮件正文内容..."}, "output_summary": "返回提取到的联系方式信息"},
    ]
    gotchas = "严禁用于长文创作（超过500字的文章、软文、报告）。长文创作应由主模型直接完成。不支持需要工具调用或复杂推理的任务。"
    related_tools = ["analyze_data", "generate_report"]
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "task_type": {
                "type": "string",
                "enum": ["translate", "summarize", "format", "classify", "extract", "rewrite", "other"],
                "description": (
                    "任务类型: translate=翻译, summarize=摘要, format=格式化, "
                    "classify=分类, extract=信息提取, rewrite=改写, other=其他"
                ),
            },
            "instruction": {
                "type": "string",
                "description": "具体的任务指令（如：'将以下内容翻译成英文'、'提取关键信息'）",
            },
            "content": {
                "type": "string",
                "description": "需要处理的文本内容",
            },
            "output_format": {
                "type": "string",
                "description": "期望的输出格式（可选，如：'JSON'、'Markdown表格'、'要点列表'）",
            },
        },
        "required": ["instruction", "content"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        instruction = args.get("instruction", "").strip()
        content = args.get("content", "").strip()
        if not instruction or not content:
            return "❌ 请提供任务指令和待处理内容。"

        # Guard: reject long-form content creation tasks
        combined_text = instruction + content
        import re as _re
        long_form_pattern = _re.search(
            r"(\d{3,})\s*字|千字|万字|长文|软文|推广文|文章|方案书|策划案",
            combined_text,
        )
        if long_form_pattern:
            return (
                "⚠️ 此任务涉及长文创作，不适合委派给轻量模型。"
                "请你（主模型）直接完成此写作任务，不要使用 llm_task 工具。"
            )

        task_type = args.get("task_type", "other")
        output_format = args.get("output_format", "")

        # Build prompt for mini model
        format_hint = f"\n输出格式要求：{output_format}" if output_format else ""

        prompt = f"{instruction}\n\n---\n{content}\n---{format_hint}"

        system_prompts = {
            "translate": "你是专业翻译。请准确翻译，保持原文语义和专业术语。",
            "summarize": "你是文本摘要专家。请提炼关键信息，输出简洁精准。",
            "format": "你是格式化专家。请按指定格式整理内容，保持信息完整。",
            "classify": "你是文本分类专家。请按指令对内容进行分类。",
            "extract": "你是信息提取专家。请从文本中精准提取所需信息。",
            "rewrite": "你是文案改写专家。请按指令改写内容，保持核心含义。",
            "other": "你是高效的文本处理助手。请按指令处理内容。",
        }
        system = system_prompts.get(task_type, system_prompts["other"]) + " 中文输出（除非指令要求其他语言）。"

        try:
            # AIService.call_llm uses the mini model by default
            result = await AIService.call_llm(prompt, system)
            task_labels = {
                "translate": "翻译",
                "summarize": "摘要",
                "format": "格式化",
                "classify": "分类",
                "extract": "提取",
                "rewrite": "改写",
                "other": "处理",
            }
            label = task_labels.get(task_type, "处理")
            return f"📝 **{label}结果**\n\n{result}"
        except Exception as e:
            logger.error(f"LLM task delegation failed: {e}")
            return safe_tool_error(e, "任务处理")
