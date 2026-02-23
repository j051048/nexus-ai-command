from typing import Any

import httpx

from app.core.prompts_registry import TOOL_PROMPTS

from .base_tool import BaseTool


class TenderAnalysisTool(BaseTool):
    name = "analyze_tender_document"
    description = "【智能投标专家】利用 LLM 深度分析招标文件，提取否决性条款并进行合规性比对"

    parameters = {
        "type": "object",
        "properties": {
            "tender_text": {
                "type": "string",
                "description": "招标文件的关键技术参数段落",
            }
        },
        "required": ["tender_text"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        text = args.get("tender_text", "")
        if not text:
            return "❌ 错误: 未提供招标文件内容。"

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model") or "gpt-4o-mini"

        if not api_key or not base_url:
            return "❌ 系统错误: 缺少 AI 配置，无法执行深度分析。"

        target_url = base_url.split("/chat/completions")[0].rstrip("/")
        if not target_url.endswith("/v1") and "/v1" not in target_url:
            target_url = f"{target_url}/v1"
        chat_endpoint = f"{target_url}/chat/completions"

        # P2 Fix: Use centralized prompt
        prompt = TOOL_PROMPTS["tender_analysis"].format(text_preview=text[:4000])

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }

        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(chat_endpoint, headers=headers, json=payload)
                if resp.status_code == 200:
                    analysis = resp.json()["choices"][0]["message"]["content"]
                    return f"📋 **智能合规矩阵分析报告**\n\n{analysis}"
                else:
                    return f"❌ AI 分析服务响应失败: {resp.status_code}"
        except Exception as e:
            return f"❌ 执行分析时发生错误: {str(e)}"
