import pytest
from unittest.mock import MagicMock, patch
from app.services.finance_service import FinanceService
from app.core.exceptions import BusinessException

# P0: 财务核心逻辑 95%+ 覆盖率专项测试 (边界值与异常流)

@pytest.fixture
def finance_service():
    # Mock Database and Organization
    return FinanceService(db=MagicMock(), org_service=MagicMock())

@pytest.mark.parametrize("amount, budget_limit, expected_status", [
    (100.0, 500.0, "approved"),      # 正常范围
    (500.0, 500.0, "approved"),      # 边界：刚好等于预算上限
    (501.0, 500.0, "declined"),      # 边界：超出 1 元
    (10000.0, 500.0, "declined"),   # 严重超出
])
def test_budget_threshold_logic(finance_service, amount, budget_limit, expected_status):
    """验证预算审批的临界点逻辑 (100% 覆盖 if/else 分支)"""
    # 模拟预算查询结果
    finance_service.db.query_budget.return_value = {"limit": budget_limit, "current": 0}
    
    result = finance_service.check_and_process_expense(amount=amount)
    assert result["status"] == expected_status

def test_invoice_creation_failures(finance_service):
    """覆盖创建发票时的各种异常分支 (Error 500 预防)"""
    # 1. 负数金额
    with pytest.raises(BusinessException) as exc:
        finance_service.create_invoice(amount=-10.5, org_id="test_org")
    assert "Invalid amount" in str(exc.value)

    # 2. 组织 ID 缺失
    with pytest.raises(BusinessException) as exc:
        finance_service.create_invoice(amount=100, org_id="")
    assert "Organization ID required" in str(exc.value)

    # 3. 数据库连接超市 (注入真实的系统异常)
    finance_service.db.insert.side_effect = Exception("DB Connection Timeout")
    with pytest.raises(Exception) as exc:
        finance_service.create_invoice(amount=100, org_id="test_org")
    assert "DB Connection Timeout" in str(exc.value)

@pytest.mark.asyncio
async def test_complex_tax_calculation(finance_service):
    """验证由复杂数学逻辑组成的税务计算分支"""
    # 模拟多种税率配置
    tax_cases = [
        {"amount": 1000, "region": "CN", "expected": 130}, # 13% 增值税
        {"amount": 1000, "region": "US", "expected": 80},  # 8% 消费税
        {"amount": 0, "region": "CN", "expected": 0}       # 零金额
    ]
    for case in tax_cases:
        tax = await finance_service.calculate_tax(case["amount"], case["region"])
        assert tax == case["expected"]
