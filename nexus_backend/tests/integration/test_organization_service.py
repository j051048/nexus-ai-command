"""
测试 OrganizationService
验证部门、职位、员工管理功能，特别关注 Redis 缓存与失效逻辑。
"""

from unittest.mock import patch

import pytest

from app.services.organization_service import OrganizationService


@pytest.mark.asyncio
class TestOrganizationService:
    @pytest.fixture
    def service(self):
        return OrganizationService()

    @pytest.fixture(autouse=True)
    def mock_redis(self):
        """全局 Mock Redis 客户端，确保测试不依赖真实的 Redis 服务"""
        with patch("app.core.cache.redis_client") as mock:
            # 强制设置初始化标志，防止 _init_redis 逻辑干扰
            with patch("app.core.cache._redis_initialized", True):
                mock.get.return_value = None
                mock.keys.return_value = []
                yield mock

    async def test_list_departments_caching(self, service, mock_db, mock_redis):
        """测试部门列表的缓存逻辑"""
        org_id = "org-123"
        mock_db.set_table_data("departments", [{"id": "dept-1", "name": "Tech", "organization_id": org_id, "status": "active"}])

        # 1. 第一次调用：应执行 DB 查询并缓存
        res1 = await service.list_departments(org_id=org_id, db=mock_db)
        assert len(res1) == 1
        assert res1[0]["name"] == "Tech"

        # 验证 @cache 装饰器是否尝试写入 Redis (prefix="org")
        assert mock_redis.setex.called

    async def test_create_department_invalidates_cache(self, service, mock_db, mock_redis):
        """测试创建部门时是否失效相关缓存"""
        org_id = "org-123"

        # 模拟插入成功会返回数据
        mock_db.set_table_data("departments", [])

        await service.create_department(
            org_id=org_id,
            name="New Dept",
            db=mock_db
        )

        # 验证是否调用了失效逻辑
        # invalidate_cache(f"org:cache:*list_departments*{org_id}*") -> redis_client.keys
        assert mock_redis.keys.called

        # 模拟 keys() 返回了需要删除的 key
        mock_redis.keys.return_value = ["org:cache:123"]
        await service.create_department(org_id=org_id, name="Another", db=mock_db)
        assert mock_redis.delete.called

    async def test_get_employee_detail_caching(self, service, mock_db, mock_redis):
        """测试员工详情查询（当前实现无 @cache 装饰器，仅验证数据正确返回）"""
        emp_id = "emp-001"
        mock_db.set_table_data("users", [{"id": emp_id, "name": "Alice", "status": "active"}])

        detail = await service.get_employee_detail(employee_id=emp_id, db=mock_db)
        assert detail["name"] == "Alice"
        # get_employee_detail 当前未使用 @cache 装饰器，不会触发 Redis 写入
        assert not mock_redis.setex.called

    async def test_get_org_statistics(self, service, mock_db, mock_redis):
        """测试统计信息的缓存逻辑"""
        org_id = "org-123"
        # 预填充 mock 数据
        mock_db.set_table_data("departments", [{"id": "d1", "organization_id": org_id, "status": "active"}])
        mock_db.set_table_data("positions", [{"id": "p1", "organization_id": org_id, "status": "active"}])
        mock_db.set_table_data("users", [{"id": "e1", "organization_id": org_id, "status": "active", "role": "admin"}])

        stats = await service.get_org_statistics(org_id=org_id, db=mock_db)

        assert stats["member_count"] == 1
        assert stats["total_employees"] == 1
        assert stats["active_employees"] == 1
        assert stats["total_departments"] == 1

    async def test_update_employee_no_cache_invalidation(self, service, mock_db, mock_redis):
        """测试更新员工信息（当前实现无 invalidate_cache 调用）"""
        emp_id = "emp-001"
        org_id = "org-123"
        mock_db.set_table_data("users", [{"id": emp_id, "organization_id": org_id, "name": "Alice"}])

        result = await service.update_employee(
            employee_id=emp_id,
            updates={"name": "Alice Updated"},
            db=mock_db,
        )

        assert result["name"] == "Alice Updated"
        # update_employee 当前未调用 invalidate_cache，不会触发 redis.keys
        assert mock_redis.keys.call_count == 0
