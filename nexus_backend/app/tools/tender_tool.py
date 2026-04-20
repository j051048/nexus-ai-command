from typing import Any

from app.core.prompts_registry import TOOL_PROMPTS

from .base_tool import BaseTool


class TenderAnalysisTool(BaseTool):
    name = "analyze_tender_document"
    domain = "tender"
    description = "深度分析招标文件内容，提取否决性条款并生成合规性比对报告"
    examples = [
        {
            "input": {"tender_text": "投标人须具备ISO9001认证...最低注册资本500万..."},
            "output_summary": "返回合规矩阵分析报告，标注否决性条款和合规风险",
        },
        {
            "input": {"tender_text": "技术参数要求：精度不低于0.01mm..."},
            "output_summary": "返回技术参数合规性分析及我方产品匹配度评估",
        },
    ]
    gotchas = "需要系统配置了有效的大模型接口。输入文本最长截取前4000字符。分析结果依赖大模型能力，建议人工复核。"
    related_tools = ["search_bidding_projects"]

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

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        text = args.get("tender_text", "")
        if not text:
            return self.format_result(data={}, summary="❌ 错误: 未提供招标文件内容。")

        # P2 Fix: Use centralized prompt
        prompt = TOOL_PROMPTS["tender_analysis"].format(text_preview=text[:4000])

        try:
            from app.services.llm_gateway import llm_gateway

            org_id = config.get("org_id", "system") if config else "system"

            response = await llm_gateway.chat(
                scene_code="tender_analysis",
                agent_code="analyzer",
                user_id=user_id,
                org_id=org_id,
                system_prompt="",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )

            if response.finish_reason == "error":
                return self.format_result(
                    data={}, summary=f"❌ AI 分析服务响应失败: {response.raw_response}"
                )

            analysis = response.content
            return self.format_result(
                data={"analysis": analysis, "text_length": len(text)},
                summary=f"📋 智能合规矩阵分析报告\n\n{analysis}",
            )
        except Exception as e:
            return self.format_result(
                data={}, summary=f"❌ 执行分析时发生错误: {str(e)}"
            )
