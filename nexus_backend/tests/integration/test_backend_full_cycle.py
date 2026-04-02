import pytest
from httpx import AsyncClient
from app.main import app
from unittest.mock import MagicMock

# P1: 后端全路径集成测试 (Integration)
# 验证：API 入口 -> Auth 中间层 -> RLS 判定 -> 响应

@pytest.fixture
async def mock_db():
    """Mock 数据库以跳过真实的 Supabase 网络请求，侧重于后端逻辑。"""
    mock = MagicMock()
    # 模拟 Supabase 链式调用
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = \
        [{"id": "1", "customer_name": "测试客户", "organization_id": "test_org_id"}]
    return mock

@pytest.mark.asyncio
async def test_crm_leads_integration(mock_db, auth_token="mock_valid_token"):
    """
    测试 CRM 线索获取流，重点在于后端对 RLS (Row Level Security) 的应用逻辑
    和 Auth 权限的透传。
    """
    # 模拟通过 Request.state 传递正确的 org_id 和 db 实例
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 这个请求依赖于 auth.py 中 get_current_user_id 的依赖注入
        # 我们假设其在集成测试环境下会有 mock 掉 Token 验证的逻辑
        response = await ac.get(
            "/api/sales-leads", 
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # 验证 200 或由于权限问题导致的 403
        if response.status_code == 200:
            data = response.json()
            assert "leads" in data["data"]
            # 确认数据是否属于该组织
            for lead in data["data"]["leads"]:
                assert lead["organization_id"] == "test_org_id"
        else:
            pytest.fail(f"API 集成测试未通过: {response.status_code} {response.text}")

@pytest.mark.asyncio
async def test_organization_switching_security():
    """验证多租户切换时的安全性：试图访问非本组织的资源。"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 当 org_id 不匹配时的 403 案例
        headers = {"Authorization": "Bearer mock_token_other_org", "X-Org-Id": "victim_org_id"}
        response = await ac.get("/api/organization/detail", headers=headers)
        
        assert response.status_code in [401, 403], "多租户越权漏洞：应拒绝通过跨组织访问请求"

if __name__ == "__main__":
    print("Running backend integration tests...")
