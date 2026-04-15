import pytest
from unittest.mock import AsyncMock, patch
from app.tools.finance_tools import ExpenseClaimTool, InvoiceOCRTool, SalaryQueryTool

@pytest.fixture
def mock_client():
    from unittest.mock import MagicMock
    client = MagicMock()
    return client

@pytest.mark.asyncio
class TestExpenseClaimTool:
    @patch("app.tools.finance_tools._get_client")
    @patch("app.services.approval_chain.approval_chain_service.match_and_bind_chain", new_callable=AsyncMock)
    async def test_expense_claim_success_auto_approve(self, mock_match, mock_get_client, mock_client):
        mock_get_client.return_value = mock_client
        mock_user_res = AsyncMock()
        mock_user_res.data = {"id": "user1", "organization_id": "org1", "name": "Test User"}
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=mock_user_res)
        
        mock_match.return_value = {
            "auto_approve": True,
            "chain_id": "chain1",
            "starting_step": 0,
            "approval_level": "system"
        }
        
        mock_insert_res = AsyncMock()
        mock_insert_res.data = [{"id": "req_1"}]
        mock_client.table.return_value.insert.return_value.execute = AsyncMock(return_value=mock_insert_res)

        tool = ExpenseClaimTool()
        args = {"expense_type": "travel", "amount": 800, "description": "Trip to Beijing"}
        res = await tool.run(args, "user1")
        assert "报销申请已提交" in res
        assert "已自动审批" in res

    @patch("app.tools.finance_tools._get_client")
    @patch("app.services.approval_chain.approval_chain_service.match_and_bind_chain", new_callable=AsyncMock)
    async def test_expense_claim_entertainment_over_limit(self, mock_match, mock_get_client, mock_client):
        mock_get_client.return_value = mock_client
        mock_user_res = AsyncMock()
        mock_user_res.data = {"id": "user1", "organization_id": "org1"}
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=mock_user_res)
        
        mock_match.return_value = {"auto_approve": False}
        
        mock_insert_res = AsyncMock()
        mock_insert_res.data = [{"id": "req_1"}]
        mock_client.table.return_value.insert.return_value.execute = AsyncMock(return_value=mock_insert_res)

        # Notify mock
        with patch("app.tools.approval_tools._notify_next_approver", new_callable=AsyncMock):
            tool = ExpenseClaimTool()
            args = {"expense_type": "entertainment", "amount": 900, "attendees": ["A", "B", "C"]} # 300 per person > 200
            res = await tool.run(args, "user1")
            
            assert "报销申请已提交" in res
            assert "超过标准" in res
            assert "等待审批中" in res

    async def test_expense_claim_invalid_amount(self):
        tool = ExpenseClaimTool()
        res = await tool.run({"expense_type": "travel", "amount": -10}, "user1")
        assert "必须大于0" in res

@pytest.mark.asyncio
class TestInvoiceOCRTool:
    @patch("httpx.AsyncClient.post")
    async def test_invoice_ocr_success(self, mock_post):
        from unittest.mock import MagicMock
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "- 发票号码: 123456\n- 金额: 100"}}]
        }
        mock_post.return_value = mock_resp

        tool = InvoiceOCRTool()
        args = {"image_url": "http://img.com/a.jpg"}
        res = await tool.run(args, "user1")
        res_str = str(res)
        assert "发票识别结果" in res_str
        assert "123456" in res_str
        
    async def test_invoice_ocr_no_url(self):
        tool = InvoiceOCRTool()
        res = await tool.run({}, "user1")
        res_str = str(res)
        assert "请提供发票图片URL" in res_str

@pytest.mark.asyncio
class TestSalaryQueryTool:
    @patch("app.tools.finance_tools._get_client")
    async def test_salary_query_success(self, mock_get_client, mock_client):
        from unittest.mock import MagicMock
        mock_get_client.return_value = mock_client
        mock_res = MagicMock()
        mock_res.data = {"base_salary": 10000, "net_salary": 9000, "status": "已发放"}
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=mock_res)
        
        tool = SalaryQueryTool()
        res = await tool.run({"month": "2026-03"}, "user1")
        res_str = str(res)
        assert "10,000" in res_str
        assert "9,000" in res_str
        assert "已发放" in res_str
