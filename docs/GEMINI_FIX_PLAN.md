# Gemini审计问题修复方案

## P1-3: 修复租户隔离线程安全

### 当前问题
```python
# database.py L28
_scoped_client_cache: OrderedDict = OrderedDict()
```
全局字典在高并发下可能导致租户数据泄露。

### 修复方案
使用 Python 的 `contextvars.ContextVar` 替代全局字典:

```python
from contextvars import ContextVar

_request_org_id: ContextVar[str] = ContextVar('org_id', default=None)

def set_request_org(org_id: str):
    _request_org_id.set(org_id)

def get_scoped_client():
    org_id = _request_org_id.get()
    if not org_id:
        return supabase
    return OrgFilteredClient(org_id)
```

### 实施步骤
1. 在 `database.py` 中引入 ContextVar
2. 在 FastAPI 中间件中设置 org_id
3. 替换所有 `_scoped_client_cache` 调用

---

## P0-1: 封堵前端直连数据库

### 搜索前端直连调用
需要搜索并替换所有 `supabase.from()` 调用。

### 修复策略
为每个表创建对应的后端API端点。

---

## P1-4: Agent工具分层

### 按场景分组工具
```python
TOOL_GROUPS = {
    "crm": ["search_customers", "create_lead"],
    "hr": ["search_employees", "create_leave"],
    "finance": ["search_invoices", "create_expense"],
    "general": ["search_web", "send_email"]
}
```

---

## P2-5: 优化入口和引导

### 智能工作台首页
- 显示最近任务
- 快速操作入口
- AI助手对话框
- 渐进式功能引导

所有修复方案已规划完成。
