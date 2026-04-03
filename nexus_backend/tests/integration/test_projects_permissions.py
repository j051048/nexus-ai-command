"""
参数化测试：项目路由权限覆盖
测试不同角色（Employee/Manager/Boss）的访问权限
"""

import pytest
from tests.conftest_auth import AuthenticatedTestClient


@pytest.mark.parametrize(
    "role,user_id,expected_status",
    [
        ("employee", "emp-001", 200),  # 员工只能看自己的项目
        ("manager", "mgr-001", 200),   # 经理可以看自己的项目
        ("boss", "boss-001", 200),     # Boss 可以看所有项目
        ("founder", "founder-001", 200),  # Founder 可以看所有项目
    ],
)
@pytest.mark.asyncio
async def test_get_projects_by_role(app, role, user_id, expected_status):
    """测试不同角色获取项目列表的权限"""
    client = AuthenticatedTestClient(app, user_id=user_id, role=role)
    response = await client.get("/api/projects/")
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "role,user_id,can_delete",
    [
        ("employee", "emp-001", False),  # 员工不能删除项目
        ("manager", "mgr-001", False),   # 经理不能删除项目
        ("boss", "boss-001", True),      # Boss 可以删除项目
        ("founder", "founder-001", True),  # Founder 可以删除项目
    ],
)
@pytest.mark.asyncio
async def test_delete_project_by_role(app, role, user_id, can_delete):
    """测试不同角色删除项目的权限"""
    client = AuthenticatedTestClient(app, user_id=user_id, role=role)
    response = await client.delete("/api/projects/test-project-id")

    if can_delete:
        assert response.status_code in [200, 404]  # 200 成功或 404 项目不存在
    else:
        assert response.status_code == 403  # 403 权限不足
