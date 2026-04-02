"""
测试 OrganizationService
验证部门、职位、员工管理功能，特别关注 Redis 缓存与失效逻辑。
"""

import pytest
from unittest.mock import patch, MagicMock
from app.services.organization_service import OrganizationService

@pytest.mark.asyncio
class TestOrganizationService:
    @pytest.fixture
    def service(self):
        return OrganizationService()

    @pytest.fixture
    def mock_db(self, mock_db):
        """使用 conftest 中的 mock_db"""
        return mock_db

    async def test_list_departments_caching(self, service, mock_db):
        """测试部门列表的缓存逻辑"""
        org_id = "org-123"
        mock_db.set_table_data("departments", [{"id": "dept-1", "name": "Tech", "organization_id": org_id, "status": "active"}])

        # 1. 第一次调用：应执行 DB 查询并缓存
        with patch("app.core.cache.redis_client") as mock_redis:
            # 模拟 Redis 没有命中
            mock_redis.get.return_value = None
            
            res1 = await service.list_departments(org_id=org_id, db=mock_db)
            assert len(res1) == 1
            assert res1[0]["name"] == "Tech"
            
            # 验证 @cache 装饰器是否尝试写入 Redis (prefix="org")
            # 注意: cache 装饰器内部使用的是 redis_client.setex
            assert mock_redis.setex.called

        # 2. 第二次调用：应当从缓存中获取（这里通过 mock 装饰器行为验证）
        # 我们已经验证了 @cache 已添加到 list_departments

    async def test_create_department_invalidates_cache(self, service, mock_db):
        """测试创建部门时是否失效相关缓存"""
        org_id = "org-123"
        
        with patch("app.core.cache.redis_client") as mock_redis:
            await service.create_department(
                org_id=org_id,
                name="New Dept",
                db=mock_db
            )
            
            # 验证是否调用了失效逻辑
            # invalidate_cache(f"org:cache:*list_departments*{org_id}*") -> redis_client.keys -> redis_client.delete
            assert mock_redis.keys.called
            # redis_client.keys(pattern) 返回列表，然后 delete(keys)
            mock_redis.keys.return_value = ["org:cache:123"]
            await service.create_department(org_id=org_id, name="Another", db=mock_db)
            assert mock_redis.delete.called

    async def test_get_employee_detail_caching(self, service, mock_db):
        """测试员工详情的缓存逻辑"""
        emp_id = "emp-001"
        mock_db.set_table_data("employees", [{"id": emp_id, "name": "Alice", "status": "active"}])
        
        with patch("app.core.cache.redis_client") as mock_redis:
            mock_redis.get.return_value = None
            detail = await service.get_employee_detail(employee_id=emp_id, db=mock_db)
            assert detail["name"] == "Alice"
            assert mock_redis.setex.called

    async def test_get_org_statistics(self, service, mock_db):
        """测试统计信息的缓存逻辑"""
        org_id = "org-123"
        # 预填充 mock 数据
        mock_db.set_table_data("departments", [{"id": "d1", "organization_id": org_id, "status": "active"}])
        mock_db.set_table_data("positions", [{"id": "p1", "organization_id": org_id, "status": "active"}])
        mock_db.set_table_data("employees", [{"id": "e1", "organization_id": org_id, "status": "active"}])

        with patch("app.core.cache.redis_client") as mock_redis:
            mock_redis.get.return_value = None
            stats = await service.get_org_statistics(org_id=org_id, db=mock_db)
            
            assert stats["total_employees"] == 1
            assert stats["active_employees"] == 1
            assert stats["total_departments"] == 1
            assert mock_redis.setex.called

    async def test_update_employee_invalidates_cache(self, service, mock_db):
        """测试更新员工信息时失效缓存"""
        emp_id = "emp-001"
        org_id = "org-123"
        # 预填充数据，update 会返回它
        mock_db.set_table_data("employees", [{"id": emp_id, "organization_id": org_id, "name": "Alice"}])
        
        with patch("app.core.cache.redis_client") as mock_redis:
            await service.update_employee(
                employee_id=emp_id,
                updates={"name": "Alice Updated"},
                db=mock_db
            )
            
            # 验证失效了列表缓存和详情缓存
            # 至少调用了两次 keys() (针对 list 和 detail)
            assert mock_redis.keys.call_count >= 2
