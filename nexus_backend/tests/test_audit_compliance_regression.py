"""
Audit & Compliance - 法务、审计与合规工具专项回归
"""

import pytest
from unittest.mock import AsyncMock, patch
from tests.test_tool_e2e_regression import _load_tool

USER_ID = "auditor-01"
ORG_ID = "audit-org"

@pytest.fixture
def audit_config():
    return {"org_id": ORG_ID, "user_role": "boss"}

@pytest.mark.asyncio
async def test_contract_retrieval_flow(audit_config):
    """验证合约查询及状态展示"""
    tool = _load_tool("get_contracts")
    
    with patch("app.tools._shared.supabase.table", return_value=MagicMock()) as mock_table:
        # Mock 数据库返回 2 条合约
        mock_table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "c1", "title": "科学仪器采购协议-A", "status": "active", "amount": 50000},
            {"id": "c2", "title": "维保服务合同-B", "status": "pending", "amount": 12000}
        ]
        
        args = {"status": "all"}
        result = await tool.run(args, USER_ID, audit_config)
        
        assert "科学仪器采购" in result
        assert "维保服务" in result
        assert "status='all'" in str(mock_table.call_args_list)


@pytest.mark.asyncio
async def test_tender_analysis_flow(audit_config):
    """验证招标文件解析及风险评估工具"""
    tool = _load_tool("analyze_tender_document")
    
    with patch("app.services.ai_service.AIService.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "🚩 **投标风险提示**\n1. 垫资比例过高\n2. 违约金条款过严"
        
        args = {"tender_id": "T2026-X01", "focus_areas": ["legal", "financial"]}
        result = await tool.run(args, USER_ID, audit_config)
        
        assert "投标风险提示" in result
        assert "违约金" in result


def test_audit_tools_registration():
    """验证审计类工具是否注册在正确 Domain"""
    tools = ["get_audit_logs", "query_compliance_status"]
    for t_name in tools:
        tool = _load_tool(t_name)
        assert tool.domain in ["audit", "compliance"]
