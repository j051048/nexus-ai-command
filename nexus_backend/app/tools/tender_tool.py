from .base_tool import BaseTool
from typing import Dict, Any
import httpx

class TenderAnalysisTool(BaseTool):
    name = "analyze_tender_document"
    description = "【智能投标专家】利用 LLM 深度分析招标文件，提取否决性条款并进行合规性比对"
    
    parameters = {
        "type": "object",
        "properties": {
            "tender_text": {"type": "string", "description": "招标文件的关键技术参数段落"}
        },
        "required": ["tender_text"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        text = args.get("tender_text", "")
        if not text:
            return "❌ 错误: 未提供招标文件内容。"

        # P0 Implementation: Real LLM Logic instead of Regex
        # We construct a secondary prompt to ask the LLM to act as a rigorous auditor.
        
        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model") or "gpt-4o-mini"
        
        if not api_key or not base_url:
            return "❌ 系统错误: 缺少 AI 配置，无法执行深度分析。"

        # URL Normalization (Reusing the robust logic from other services)
        target_url = base_url.split("/chat/completions")[0].rstrip("/")
        if not target_url.endswith("/v1") and "/v1" not in target_url:
            target_url = f"{target_url}/v1"
        chat_endpoint = f"{target_url}/chat/completions"

        prompt = f"""
        你是拥有10年经验的【科学仪器招投标专家】。
        请仔细审查以下招标文件片段，提取所有【硬性否决条款】（通常带有*号、或使用“必须”、“务必”、“不得”等绝对化词语）。
        
        招标文件内容：
        {text[:4000]} 
        
        请输出一个Markdown表格，列包含：
        1. 原文条款
        2. 关键指标数值
        3. 风险等级 (高/中/低)
        4. 建议 (满足/偏离/需澄清)
        
        假设我不具备该产品的知识，请仅根据常识逻辑判断（例如：要求<10分钟，若无数据则标记需确认）。
        """

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1 # Low temp for rigorous analysis
        }

        try:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(chat_endpoint, headers=headers, json=payload)
                if resp.status_code == 200:
                    analysis = resp.json()["choices"][0]["message"]["content"]
                    return f"📋 **智能合规矩阵分析报告**\n\n{analysis}"
                else:
                    return f"❌ AI 分析服务响应失败: {resp.status_code}"
        except Exception as e:
            return f"❌ 执行分析时发生错误: {str(e)}"
