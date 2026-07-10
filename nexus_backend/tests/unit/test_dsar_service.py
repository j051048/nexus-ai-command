"""
DSARService 单元测试
覆盖: 数据导出、数据删除（PII 匿名化）、审计日志
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.dsar_service import DSARService


def _make_mock_db(table_data=None):
    """创建 mock Supabase client，支持链式调用"""
    db = MagicMock()
    table_data = table_data or {}

    def _table(name):
        builder = MagicMock()
        data = table_data.get(name, [])

        # select chain
        resp = MagicMock()
        resp.data = data
        builder.select.return_value.eq.return_value.limit.return_value.execute = (
            AsyncMock(return_value=resp)
        )

        # update chain
        update_resp = MagicMock()
        update_resp.data = data
        builder.update.return_value.eq.return_value.execute = AsyncMock(
            return_value=update_resp
        )

        # insert chain
        builder.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{}])
        )

        return builder

    db.table = _table
    return db


class TestExportUserData:
    """数据导出测试"""

    @pytest.mark.asyncio
    async def test_export_all_tables(self):
        db = _make_mock_db(
            {
                "users": [{"id": "u-1", "name": "张三", "email": "z@test.com"}],
                "conversations": [{"id": "c-1", "user_id": "u-1", "title": "对话1"}],
            }
        )
        svc = DSARService(db)
        result = await svc.export_user_data("u-1")

        assert result["status"] == "completed"
        assert result["user_id"] == "u-1"
        assert "tables" in result
        assert "request_id" in result

    @pytest.mark.asyncio
    async def test_export_single_table_failure_continues(self):
        """单表查询失败不中断整体导出"""
        db = MagicMock()
        call_count = 0

        def _table(name):
            nonlocal call_count
            builder = MagicMock()
            if name == "conversations":
                builder.select.return_value.eq.return_value.limit.return_value.execute = AsyncMock(
                    side_effect=Exception("DB timeout")
                )
            else:
                resp = MagicMock()
                resp.data = []
                builder.select.return_value.eq.return_value.limit.return_value.execute = AsyncMock(
                    return_value=resp
                )
            builder.insert.return_value.execute = AsyncMock(
                return_value=MagicMock(data=[{}])
            )
            return builder

        db.table = _table
        svc = DSARService(db)
        result = await svc.export_user_data("u-1")

        assert result["status"] == "completed_with_errors"
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_export_empty_tables(self):
        db = _make_mock_db()
        svc = DSARService(db)
        result = await svc.export_user_data("u-1")
        assert result["status"] == "completed"


class TestDeleteUserData:
    """数据删除（匿名化）测试"""

    @pytest.mark.asyncio
    async def test_delete_anonymizes_users_table(self):
        db = _make_mock_db({"users": [{"id": "u-1", "name": "张三"}]})
        svc = DSARService(db)
        result = await svc.delete_user_data("u-1")

        assert result["status"] == "completed"
        users_action = result["actions"]["users"]
        assert users_action["action"] == "anonymized"
        assert "name" in users_action["fields_cleared"]

    @pytest.mark.asyncio
    async def test_delete_audit_logs_retained(self):
        """审计日志保留且不修改历史证据"""
        db = _make_mock_db({"audit_logs": [{"id": "al-1", "actor_user_id": "u-1"}]})
        svc = DSARService(db)
        result = await svc.delete_user_data("u-1")

        audit_action = result["actions"]["audit_logs"]
        assert audit_action["action"] == "retained_immutable"
        assert audit_action["records_affected"] == 0
        assert audit_action["records_retained"] == 1

    @pytest.mark.asyncio
    async def test_delete_single_table_failure_continues(self):
        """单表删除失败不中断整体处理"""
        db = MagicMock()

        def _table(name):
            builder = MagicMock()
            if name == "sales_leads":
                builder.update.return_value.eq.return_value.execute = AsyncMock(
                    side_effect=Exception("Permission denied")
                )
            else:
                resp = MagicMock()
                resp.data = [{"id": "x"}]
                builder.update.return_value.eq.return_value.execute = AsyncMock(
                    return_value=resp
                )
            builder.insert.return_value.execute = AsyncMock(
                return_value=MagicMock(data=[{}])
            )
            return builder

        db.table = _table
        svc = DSARService(db)
        result = await svc.delete_user_data("u-1")

        assert result["status"] == "completed_with_errors"
        assert result["actions"]["sales_leads"]["action"] == "failed"


class TestAuditLog:
    """审计日志写入测试"""

    @pytest.mark.asyncio
    async def test_audit_log_written(self):
        db = _make_mock_db()
        svc = DSARService(db)
        await svc._log_audit("u-1", "test_action", {"key": "value"})
        # Should not raise

    @pytest.mark.asyncio
    async def test_audit_log_failure_silent(self):
        """审计日志写入失败不抛异常"""
        db = MagicMock()
        db.table.return_value.insert.return_value.execute = AsyncMock(
            side_effect=Exception("DB error")
        )
        svc = DSARService(db)
        # Should not raise
        await svc._log_audit("u-1", "test", {})
