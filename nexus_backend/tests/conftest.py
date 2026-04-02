"""测试基础设施"""
import pytest
import asyncio
from typing import Any, List, Dict, Optional
from httpx import AsyncClient
from app.main import app

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def test_user():
    return {
        "user_id": "test-123",
        "org_id": "org-456",
        "tenant_id": "tenant-789",
        "id": "test-123",
        "role": "admin"
    }

class MockResponse:
    def __init__(self, data: Any = None, error: Any | None = None, count: int | None = None):
        self.data = data if data is not None else []
        self.error = error
        self.count = count if count is not None else (len(data) if isinstance(data, list) else 0)

class MockQueryBuilder:
    def __init__(self, table: str, data: list | None = None):
        self.table_name = table
        self._data = data or []
        self._filters = []
        self._do_count = False
        self._is_single = False

    def select(self, *columns, **kwargs):
        if kwargs.get("count"):
            self._do_count = True
        return self

    def single(self):
        self._is_single = True
        return self

    def maybe_single(self):
        self._is_single = True
        return self
    def eq(self, column, value): 
        # 简单的内存过滤逻辑
        if isinstance(self._data, list):
            self._data = [d for d in self._data if isinstance(d, dict) and d.get(column) == value]
        return self
    def is_(self, column, value): 
        # 处理 status is null 的情况
        if value == "null" and isinstance(self._data, list):
            self._data = [d for d in self._data if d.get(column) is None]
        return self

    def neq(self, column, value):
        if isinstance(self._data, list):
            self._data = [d for d in self._data if isinstance(d, dict) and d.get(column) != value]
        return self
    def order(self, column, desc=False): return self
    def limit(self, count): 
        if isinstance(self._data, list):
            self._data = self._data[:count]
        return self
    def insert(self, data):
        self._data = [data]
        return self
    def update(self, data):
        for d in self._data:
            d.update(data)
        return self
    def delete(self):
        self._data = []
        return self

    async def execute(self):
        count = len(self._data) if self._do_count else None
        data = self._data
        if self._is_single:
            data = data[0] if data else None
        print(f"DEBUG: table={self.table_name} is_single={self._is_single} data_type={type(data)}")
        return MockResponse(data=data, count=count)

class MockSupabaseClient:
    def __init__(self):
        self.tables = {}

    def set_table_data(self, table_name: str, data: list):
        self.tables[table_name] = data

    def table(self, table_name: str):
        data = self.tables.get(table_name, [])
        return MockQueryBuilder(table_name, data)

@pytest.fixture
def mock_db():
    return MockSupabaseClient()
