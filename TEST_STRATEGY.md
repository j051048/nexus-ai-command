# Nexus AI Command — 全覆盖测试策略

## 框架选择

| 层级 | 框架 | 理由 |
|------|------|------|
| 前端单元/集成 | Vitest + @testing-library/react | 项目已有，与 Vite 原生集成 |
| 前端 E2E | Playwright (Chromium) | 项目已有，支持 SSE/WebSocket 拦截 |
| 后端单元/集成 | pytest + pytest-asyncio | 项目已有，原生 async 支持 |
| 后端 E2E | httpx AsyncClient + pytest | 项目已有，零启动开销 |
| 性能/负载 | k6 (脚本) + pytest-benchmark | 轻量级，CI 友好 |
| 安全 | 自定义 pytest fixtures + OWASP 检查 | 针对 prompt injection/XSS/IDOR |

## 覆盖率目标

| 模块 | 行覆盖率 | 分支覆盖率 | 质量门禁 |
|------|----------|-----------|---------|
| Agent 核心 (router/plan/execute/reflect) | ≥85% | ≥75% | 必须 |
| 工具层 (131 tools) | ≥80% | ≥70% | 必须 |
| 前端 hooks (45 hooks) | ≥80% | ≥70% | 必须 |
| React Flow 设计器 | ≥75% | ≥65% | 必须 |
| RLS/权限 | 100% 场景覆盖 | N/A | 必须 |
| E2E 业务闭环 | 8 条核心流程 | N/A | 必须 |
| 整体 | ≥70% | ≥60% | CI 门禁 |

## 风险优先级矩阵

| P0 (阻断上线) | P1 (高风险) | P2 (中风险) |
|--------------|-----------|-----------|
| AI 意图路由误分类 | React Flow 保存丢数据 | GenUI 组件渲染异常 |
| 多租户数据泄露 | SSE 流中断无恢复 | 离线队列重放失败 |
| HITL 确认绕过 | 工具调用权限越权 | 主题切换闪烁 |
| 审批流程状态机错误 | 长时记忆漂移/幻觉 | 移动端布局溢出 |
| Prompt injection | WBS 分解死循环 | 图表数据精度 |
| RLS 策略失效 | 并发审批冲突 | 国际化缺失 |

## 测试文件清单 (按生成顺序)

### 1. 单元测试 - 前端
- `src/__tests__/hooks/useApprovals.test.ts`
- `src/__tests__/hooks/useCRM.test.ts`
- `src/__tests__/hooks/useSalesLeads.test.ts`
- `src/__tests__/hooks/useWebSocketPush.test.ts`
- `src/__tests__/hooks/useVMD.test.ts`
- `src/__tests__/lib/apiConfig.test.ts`
- `src/__tests__/lib/schemas.test.ts`
- `src/__tests__/components/GenUIContainer.test.tsx`
- `src/__tests__/components/ThinkingChain.test.tsx`
- `src/__tests__/components/CommandPalette.test.tsx`

### 2. 单元测试 - 后端
- `nexus_backend/tests/unit/test_router_classify.py`
- `nexus_backend/tests/unit/test_state.py`
- `nexus_backend/tests/unit/test_node_helpers.py`
- `nexus_backend/tests/unit/test_loop_detector.py`
- `nexus_backend/tests/unit/test_safety_guards.py`
- `nexus_backend/tests/unit/test_tool_base.py`
- `nexus_backend/tests/unit/test_prompt_firewall.py`
- `nexus_backend/tests/unit/test_sanitize.py`

### 3. 集成测试
- `nexus_backend/tests/integration/test_graph_flow.py`
- `nexus_backend/tests/integration/test_tool_execution.py`
- `nexus_backend/tests/integration/test_memory_pipeline.py`
- `src/__tests__/integration/aiStream-httpClient.test.ts`

### 4. React Flow 设计器专项
- `src/__tests__/features/WorkflowCanvas.test.tsx`
- `src/__tests__/features/WorkflowNodes.test.tsx`
- `src/__tests__/features/WorkflowProperties.test.tsx`

### 5. AI Agent 中控测试矩阵
- `nexus_backend/tests/agent/test_intent_matrix.py`
- `nexus_backend/tests/agent/test_plan_execute_reflect.py`
- `nexus_backend/tests/agent/test_wbs_orchestrator.py`
- `nexus_backend/tests/agent/test_tool_priority.py`
- `nexus_backend/tests/agent/test_memory_drift.py`

### 6. 多租户 & 权限
- `nexus_backend/tests/security/test_tenant_isolation.py`
- `nexus_backend/tests/security/test_role_permission_matrix.py`
- `src/__tests__/security/permission-boundary.test.ts`

### 7. E2E 业务闭环
- `e2e/flows/contract-approval-payment.spec.ts`
- `e2e/flows/task-assign-execute-review.spec.ts`
- `e2e/flows/sales-lead-to-deal.spec.ts`
- `e2e/flows/employee-onboarding.spec.ts`
- `nexus_backend/tests/e2e/test_approval_e2e.py`
- `nexus_backend/tests/e2e/test_crm_e2e.py`
- `nexus_backend/tests/e2e/test_workflow_e2e.py`
- `nexus_backend/tests/e2e/test_ai_chat_e2e.py`

### 8. 性能/安全/PWA/边缘
- `nexus_backend/tests/performance/test_load.py`
- `nexus_backend/tests/security/test_prompt_injection.py`
- `nexus_backend/tests/security/test_xss_csrf.py`
- `src/__tests__/pwa/offline-queue.test.ts`
- `src/__tests__/edge/error-boundary-cascade.test.tsx`

### 9. CI/CD 集成
- `.github/workflows/test-full.yml`

---

## 已生成文件清单 (实际产出 — 重构后)

### 前端测试 (Vitest)
| 文件 | 类别 | 测试数 |
|------|------|--------|
| `src/__tests__/hooks/useApprovals.test.ts` | 单元 | 6 |
| `src/__tests__/hooks/useWebSocketPush.test.ts` | 单元 | 3 |
| `src/__tests__/hooks/useAIStream.test.ts` | 单元 | - |
| `src/__tests__/lib/schemas.test.ts` | 单元 | 14 |
| `src/__tests__/lib/apiConfig.test.ts` | 单元 | 6 |
| `src/__tests__/lib/httpClient.test.ts` | 单元 | - |
| `src/__tests__/lib/httpClient-edge.test.ts` | 边缘 | 15 |
| `src/__tests__/components/ThinkingChain.test.tsx` | 单元 | 7 |
| `src/__tests__/components/CommandPalette.test.tsx` | 单元 | 1 |
| `src/__tests__/components/ErrorBoundary.test.tsx` | 边缘 | 13 |
| `src/__tests__/components/GenUIComponents.test.tsx` | 单元 | - |
| `src/__tests__/features/WorkflowCanvas.test.tsx` | 设计器 | 6 |
| `src/__tests__/features/WorkflowDesigner.test.tsx` | 设计器 | - |
| `src/__tests__/features/WorkflowNodes.test.tsx` | 设计器 | - |
| `src/__tests__/security/permission-boundary.test.ts` | 安全 | 4 |

### 后端测试 (pytest)
| 文件 | 类别 | 测试数 |
|------|------|--------|
| `tests/unit/test_router_classify.py` | 单元 | 50+ |
| `tests/unit/test_state.py` | 单元 | 10+ |
| `tests/unit/test_loop_detector.py` | 单元 | 10+ |
| `tests/unit/test_safety_guards.py` | 单元 | 8 |
| `tests/unit/test_tool_coverage.py` | 单元 | - |
| `tests/unit/test_tool_resilience.py` | 单元 | - |
| `tests/unit/test_tool_full_sweep.py` | 单元 | - |
| `tests/integration/test_graph_flow.py` | 集成 | 5 |
| `tests/integration/test_tool_execution.py` | 集成 | 4 |
| `tests/agent/test_intent_matrix.py` | Agent矩阵 | 50+ |
| `tests/agent/test_plan_execute_reflect.py` | Agent链路 | 6 |
| `tests/agent/test_agent_core.py` | Agent | - |
| `tests/agent/test_agent_modules.py` | Agent | - |
| `tests/agent/test_agent_nodes.py` | Agent | - |
| `tests/agent/test_agent_evals.py` | Agent | - |
| `tests/agent/test_agent_graph.py` | Agent | - |
| `tests/agent/test_agent_flow.py` | Agent | - |
| `tests/security/test_tenant_role_matrix.py` | 权限 | 10+ |
| `tests/security/test_prompt_injection.py` | 安全 | 35+ |
| `tests/security/test_xss_csrf.py` | 安全 | 25+ |
| `tests/security/test_hitl_security.py` | 安全 | - |
| `tests/security/test_security_middleware.py` | 安全 | - |
| `tests/security/test_security_multi_tenant.py` | 安全 | - |
| `tests/performance/test_load.py` | 性能 | 15+ |
| `tests/performance/test_performance_audit.py` | 性能 | - |
| `tests/e2e/test_business_e2e.py` | E2E | 8 |

### E2E (Playwright)
| 文件 | 类别 | 测试数 |
|------|------|--------|
| `e2e/flows/business-flows.spec.ts` | 业务闭环 | 9 |

### CI/CD
| 文件 | 说明 |
|------|------|
| `.github/workflows/test-full.yml` | 9 大类全量回归 + 质量门禁 |
| `.github/workflows/ci.yml` | 已有：push/PR 触发的主 CI |
| `.github/workflows/test.yml` | 已有：手动触发的集成测试 |

---

## 质量门禁标准

| 门禁 | 阈值 | 阻断级别 |
|------|------|---------|
| 前端覆盖率 | ≥ 60% lines | Warning |
| 后端覆盖率 | ≥ 50% lines | Blocking |
| 安全测试 | 0 failure | Blocking |
| Agent 矩阵 | 0 failure | Blocking |
| E2E 关键路径 | 100% pass | Blocking |
| 性能 SLO | 全部 pass | Warning |

## 运行命令速查

```bash
# 前端全量
npx vitest run --coverage

# 后端全量
cd nexus_backend && pytest tests/ -v --cov=app

# 仅安全测试
cd nexus_backend && pytest tests/security/ -v

# 仅 Agent 矩阵
cd nexus_backend && pytest tests/agent/ -v

# 仅性能测试
cd nexus_backend && pytest tests/performance/ -v

# Playwright E2E
npx playwright test

# CI 全量回归 (GitHub Actions)
gh workflow run "Full Test Suite"
```
