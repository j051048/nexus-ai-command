# 测试结构说明

## 目录组织

```
tests/
├── unit/           # 单元测试 - 纯函数/单一模块逻辑
├── integration/    # 集成测试 - 跨模块/跨服务交互
└── e2e/           # 端到端测试 - 完整用户场景流
```

## 运行测试

```bash
# 运行所有测试
pytest

# 只运行单元测试
pytest tests/unit/

# 只运行集成测试
pytest tests/integration/

# 只运行 E2E 测试
pytest tests/e2e/

# 运行特定测试文件
pytest tests/unit/test_auth.py
```

## 测试分类标准

### Unit Tests (13个)
纯函数逻辑，无外部依赖或使用 Mock
- 认证、过滤、限流、向量服务等

### Integration Tests (19个)
跨路由/跨服务逻辑，需要多个组件协作
- API集成、工作流、计费、CRM工具等

### E2E Tests (27个)
真实用户场景，完整业务流程
- Agent流程、安全审计、性能测试、工具回归等
