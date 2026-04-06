"""
参数化测试：竞品路由权限覆盖
测试不同角色对竞品管理的访问权限
"""

import pytest
from tests.conftest_auth import AuthenticatedTestClient


@pytest.mark.parametrize(
    "role,user_id,expected_status",
    [
        ("employee", "emp-001", 200),
        ("manager", "mgr-001", 200),
        ("boss", "boss-001", 200),
    ],
)
@pytest.mark.asyncio
async def test_list_competitors_by_role(app, role, user_id, expected_status):
    """测试不同角色获取竞品列表"""
    client = AuthenticatedTestClient(app, user_id=user_id, role=role)
    response = await client.get("/api/competitors")
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "role,user_id,can_create",
    [
        ("employee", "emp-001", False),
        ("manager", "mgr-001", True),
        ("boss", "boss-001", True),
    ],
)
@pytest.mark.asyncio
async def test_create_competitor_by_role(app, role, user_id, can_create):
    """测试不同角色创建竞品的权限"""
    client = AuthenticatedTestClient(app, user_id=user_id, role=role)
    response = await client.post("/api/competitors", json={"name": "Test Competitor"})

    if can_create:
        assert response.status_code in [200, 201, 400]
    else:
        assert response.status_code == 403
