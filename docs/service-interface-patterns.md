# Service 层接口抽象设计规范

## 1. 设计目标

在 Service 层引入 `typing.Protocol` 接口，实现：

- **解耦依赖**：Router 层依赖抽象接口而非具体实现
- **可测试性**：通过 Protocol 定义，轻松创建 mock 实现
- **结构化子类型**：使用 Protocol（鸭子类型）而非 ABC，无需显式继承
- **渐进式迁移**：现有 Service 类自动满足 Protocol（如果方法签名匹配）

## 2. 为什么选择 Protocol 而非 ABC

| 特性 | typing.Protocol | abc.ABC |
|------|-----------------|---------|
| 继承要求 | 无需继承（结构化子类型） | 必须显式继承 |
| 运行时开销 | 零（纯静态检查） | 有（元类机制） |
| 已有类兼容 | 自动满足（鸭子类型） | 需要修改类定义 |
| IDE 支持 | pyright/mypy 完整支持 | 完整支持 |
| 适合场景 | 渐进式接口化 | 严格的继承体系 |

## 3. Protocol 定义规范

### 3.1 文件位置

所有核心 Protocol 定义在 `nexus_backend/app/services/interfaces.py`。

### 3.2 命名规范

- Protocol 类名后缀为 `Protocol`
- 方法签名与现有 Service 方法保持一致
- 使用 `runtime_checkable` 装饰器支持 `isinstance` 检查

### 3.3 核心 Protocol 列表

| Protocol | 职责 | 对应实现 |
|----------|------|---------|
| `CRMServiceProtocol` | CRM 线索管理 | `crm_service.py` |
| `ApprovalServiceProtocol` | 审批流程 | `approval_chain.py` |
| `StorageServiceProtocol` | 文件存储 | 内部 Supabase Storage |
| `EventBusProtocol` | 事件发布 | `event_bus.py` |
| `LLMGatewayProtocol` | LLM 调用 | `llm_gateway/` |

## 4. 使用模式

### 4.1 在 Router 中使用

```python
from app.services.interfaces import CRMServiceProtocol

# 依赖注入
def get_crm_service() -> CRMServiceProtocol:
    from app.services.crm_service import crm_service
    return crm_service

@router.get("/leads")
async def list_leads(
    crm: CRMServiceProtocol = Depends(get_crm_service),
):
    return await crm.get_leads(tenant_id=..., filters=...)
```

### 4.2 在测试中使用

```python
from app.services.interfaces import CRMServiceProtocol

class MockCRMService:
    """自动满足 CRMServiceProtocol（鸭子类型，无需继承）"""

    async def get_leads(self, tenant_id: str, filters: dict | None = None) -> list[dict]:
        return [{"id": "test-1", "name": "Test Lead"}]

    async def create_lead(self, tenant_id: str, data: dict) -> dict:
        return {"id": "new-1", **data}

    async def update_lead(self, tenant_id: str, lead_id: str, data: dict) -> dict:
        return {"id": lead_id, **data}

# 静态类型检查会验证 MockCRMService 满足 CRMServiceProtocol
```

### 4.3 渐进式迁移策略

1. **Phase 1**：定义 Protocol，不修改现有代码
2. **Phase 2**：新 router 使用 Protocol + Depends 注入
3. **Phase 3**：逐步将现有 router 迁移到 Protocol 注入
4. **Phase 4**：添加 mypy 类型检查到 CI

## 5. 示例实现

完整的 Protocol 定义见 `nexus_backend/app/services/interfaces.py`。

## 6. 注意事项

1. **不要过度抽象**：只为有多种实现可能或需要 mock 的 Service 创建 Protocol
2. **方法签名稳定性**：Protocol 一旦发布，修改方法签名是 breaking change
3. **避免循环导入**：interfaces.py 只 import typing 模块中的类型
4. **返回类型使用 dict**：避免在 Protocol 中引入 Pydantic model 依赖
