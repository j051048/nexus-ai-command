import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.tools.finance_tools import ExpenseClaimTool, InvoiceOCRTool, SalaryQueryTool

@pytest.fixture
def mock_config():
    return {"org_id": "org1"}

@pytest.fixture
def mock_client():
    client = MagicMock()
    
    def get_table_mock(table_name):
        mock = MagicMock()
        # Common chain methods
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.ilike.return_value = mock
        mock.insert.return_value = mock
        mock.order.return_value = mock
        mock.limit.return_value = mock
        mock.maybe_single.return_value = mock
        # execute will be set per-table
        mock.execute = AsyncMock()
        return mock

    users_mock = get_table_mock("users")
    approval_mock = get_table_mock("approval_requests")
    
    def side_effect(table_name):
        if table_name == "users":
            return users_mock
        return approval_mock
        
    client.table.side_effect = side_effect
    client.users_mock = users_mock
    client.approval_mock = approval_mock
    return client

@pytest.mark.asyncio
class TestExpenseClaimTool:
    async def test_expense_claim_missing_org_id(self):
        tool = ExpenseClaimTool()
        # Use a simpler regex that matches both English and Chinese substrings
        with pytest.raises(PermissionError, match="Missing tenant context"):
            await tool.run({"expense_type": "travel", "amount": 100}, "user1", config={})

    @patch("app.tools.finance_tools._get_client")
    @patch("app.services.approval_chain.approval_chain_service.match_and_bind_chain", new_callable=AsyncMock)
    async def test_expense_claim_success_auto_approve(self, mock_match, mock_get_client, mock_client, mock_config):
        mock_get_client.return_value = mock_client
        
        mock_user_res = MagicMock()
        mock_user_res.data = {"id": "user1", "organization_id": "org1", "name": "Test User"}
        mock_client.users_mock.execute.return_value = mock_user_res
        
        mock_match.return_value = {
            "auto_approve": True,
            "chain_id": "chain1",
            "starting_step": 0,
            "approval_level": "system"
        }
        
        mock_insert_res = MagicMock()
        mock_insert_res.data = [{"id": "req_1"}]
        mock_client.approval_mock.execute.return_value = mock_insert_res

        tool = ExpenseClaimTool()
        args = {"expense_type": "travel", "amount": 800, "description": "Trip to Beijing"}
        res = await tool.run(args, "user1", config=mock_config)
        res_str = str(res)
        assert "报销申请已提交" in res_str
        assert "已自动审批" in res_str

    @patch("app.tools.finance_tools._get_client")
    @patch("app.services.approval_chain.approval_chain_service.match_and_bind_chain", new_callable=AsyncMock)
    async def test_expense_claim_entertainment_over_limit(self, mock_match, mock_get_client, mock_client, mock_config):
        mock_get_client.return_value = mock_client
        mock_user_res = MagicMock()
        mock_user_res.data = {"id": "user1", "organization_id": "org1"}
        mock_client.users_mock.execute.return_value = mock_user_res
        
        mock_match.return_value = {"auto_approve": False}
        
        mock_insert_res = MagicMock()
        mock_insert_res.data = [{"id": "req_1"}]
        mock_client.approval_mock.execute.return_value = mock_insert_res

        # Notify mock
        with patch("app.tools.approval_tools._notify_next_approver", new_callable=AsyncMock):
            tool = ExpenseClaimTool()
            args = {"expense_type": "entertainment", "amount": 900, "attendees": ["A", "B", "C"]} # 300 per person > 200
            res = await tool.run(args, "user1", config=mock_config)
            res_str = str(res)
            
            assert "报销申请已提交" in res_str
            assert "超过标准" in res_str
            assert "等待审批中" in res_str

    async def test_expense_claim_invalid_amount(self, mock_config):
        with patch("app.tools.finance_tools._get_client"):
            tool = ExpenseClaimTool()
            res = await tool.run({"expense_type": "travel", "amount": -10}, "user1", config=mock_config)
            assert "必须大于0" in str(res)

@pytest.mark.asyncio
class TestInvoiceOCRTool:
    @patch("app.services.llm_gateway.llm_gateway.chat", new_callable=AsyncMock)
    async def test_invoice_ocr_success(self, mock_chat, mock_config):
        mock_resp = MagicMock()
        mock_resp.finish_reason = "stop"
        mock_resp.content = "- 发票号码: 123456\n- 金额: 100"
        mock_chat.return_value = mock_resp

        tool = InvoiceOCRTool()
        args = {"image_url": "http://img.com/a.jpg"}
        res = await tool.run(args, "user1", config=mock_config)
        assert "发票识别结果" in res['summary']
        assert "123456" in res['summary']
        
    async def test_invoice_ocr_no_url(self, mock_config):
        tool = InvoiceOCRTool()
        res = await tool.run({}, "user1", config=mock_config)
        res_str = str(res)
        assert "请提供发票图片URL" in res_str

@pytest.mark.asyncio
class TestSalaryQueryTool:
    @patch("app.tools.finance_tools._get_client")
    async def test_salary_query_success(self, mock_get_client, mock_client, mock_config):
        mock_get_client.return_value = mock_client
        mock_res = MagicMock()
        mock_res.data = {"base_salary": 10000, "net_salary": 9000, "status": "已发放"}
        # Salary tool uses hr_salary_records table
        mock_client.approval_mock.execute.return_value = mock_res
        
        tool = SalaryQueryTool()
        res = await tool.run({"month": "2026-03"}, "user1", config=mock_config)
        res_str = str(res)
        assert "10,000" in res_str
        assert "9,000" in res_str
        assert "已发放" in res_str
