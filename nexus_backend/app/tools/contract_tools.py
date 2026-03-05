"""
合同分析工具集
AI 分析合同文档，提取关键条款、识别风险点、生成摘要
"""

import uuid as _uuid
from typing import Any

from app.core.database import supabase
from app.services.ai_service import AIService

from .base_tool import BaseTool


def _get_client(config: dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


class ContractAnalysisTool(BaseTool):
    """AI 合同条款分析工具"""

    name = "analyze_contract"
    description = (
        "AI分析合同文档，提取关键条款、识别风险点、生成摘要。当用户说'分析合同'、'合同风险'、'合同摘要'时调用。"
    )
    required_role = "manager"

    parameters = {
        "type": "object",
        "properties": {
            "contract_id": {
                "type": "string",
                "description": "合同ID（从系统中获取）",
            },
            "contract_text": {
                "type": "string",
                "description": "合同文本内容（如果无ID则直接传文本）",
            },
            "focus": {
                "type": "string",
                "enum": ["summary", "risks", "key_terms", "full"],
                "description": "分析重点: summary(摘要), risks(风险), key_terms(关键条款), full(全面分析)",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        contract_id = args.get("contract_id")
        contract_text = args.get("contract_text", "")
        focus = args.get("focus", "full")
        client = _get_client(config)

        # 如果提供了 contract_id，从数据库获取合同信息
        if contract_id and not contract_text:
            # Validate UUID format
            try:
                _uuid.UUID(contract_id)
            except (ValueError, TypeError, AttributeError):
                return f"contract_id '{contract_id}' 不是有效的UUID格式。"

            try:
                res = await client.table("contracts").select("*").eq("id", contract_id).maybe_single().execute()
                if res.data:
                    contract = res.data
                    contract_text = (
                        f"合同标题: {contract.get('title', '未知')}\n"
                        f"合同编号: {contract.get('contract_number', '未知')}\n"
                        f"合同类型: {contract.get('contract_type', '未知')}\n"
                        f"金额: ¥{contract.get('amount', 0):,.2f}\n"
                        f"状态: {contract.get('status', '未知')}\n"
                        f"开始日期: {contract.get('start_date', '未知')}\n"
                        f"结束日期: {contract.get('end_date', '未知')}\n"
                        f"标签: {contract.get('tags', [])}\n"
                        f"元数据: {contract.get('metadata', {})}"
                    )
                else:
                    return f"❌ 未找到ID为 {contract_id} 的合同。"
            except Exception as e:
                return f"❌ 查询合同失败: {str(e)}"

        if not contract_text:
            return "❌ 请提供合同ID或合同文本内容。"

        focus_prompts = {
            "summary": "请生成合同摘要，包括：合同主体、核心条款、关键日期、金额条款。",
            "risks": "请重点分析合同风险，包括：违约风险、法律风险、财务风险、执行风险。对每个风险标注严重程度（高/中/低）。",
            "key_terms": "请提取合同关键条款，包括：付款条款、违约责任、保密条款、知识产权、争议解决方式、终止条件。",
            "full": "请进行全面合同分析，包括：\n1. 合同摘要\n2. 关键条款提取\n3. 风险点识别\n4. 建议与注意事项",
        }

        prompt = f"合同内容:\n{contract_text}\n\n{focus_prompts.get(focus, focus_prompts['full'])}"
        system = "你是专业的法务合同分析师。基于合同内容进行专业分析，用中文回复，格式清晰，重点突出。"

        try:
            analysis = await AIService.call_llm(prompt, system)
            focus_names = {
                "summary": "摘要",
                "risks": "风险分析",
                "key_terms": "关键条款",
                "full": "全面分析",
            }
            return f"📄 合同{focus_names.get(focus, '分析')}:\n\n{analysis}"
        except Exception as e:
            return f"📄 合同分析失败: {str(e)}"
