# HITL Blast Radius 分析

> 基于代码审计的 Human-in-the-Loop (HITL) 确认机制完整性分析

## 1. 现有 HITL 机制概述

### 1.1 实现架构

Nexus AI Command 的 HITL 机制通过以下组件实现：

- **`BaseTool.is_irreversible`** (`nexus_backend/app/tools/base_tool.py`): 工具级标记
- **`BaseTool.check_confirmation()`**: 统一确认门控（检查 irreversible + 高额 + 批量）
- **`ConfirmationType`** 枚举: IRREVERSIBLE / HIGH_VALUE / BULK_OPERATION / EXTERNAL / PERMISSION_ESCALATION
- **`CONFIRMATION_THRESHOLDS`**: 自动触发阈值（金额 ≥ 50,000 CNY，批量 ≥ 5 条）
- **`node_execute.py`**: 执行节点中拦截并阻断需确认的工具
- **`stream.py`**: 通过 SSE 发送 `confirmation_required` 事件到前端
- **`useAIStream.ts`**: 前端处理确认对话框和 `system_confirmed` 回传

### 1.2 确认流程

```
用户消息 → AI 决定调用工具 → check_confirmation()
  ├─ 无需确认 → 直接执行 → 返回结果
  └─ 需要确认 → 阻断执行 → SSE 发送 confirmation_required
                          → 前端弹出确认对话框
                          → 用户点击确认
                          → 重发请求 (system_confirmed=true)
                          → 跳过确认 → 执行 → 返回结果
```

## 2. 当前已标记为"需要确认"的操作

以下工具已设置 `is_irreversible = True`：

| # | 工具名 | 文件 | 操作说明 | 确认理由 |
|---|--------|------|---------|---------|
| 1 | `approve_request` | `approval_tools.py` | 批准审批申请 | 不可逆审批决策 |
| 2 | `reject_request` | `approval_tools.py` | 驳回审批申请 | 不可逆审批决策 |
| 3 | `smart_approve` | `boss_tools.py` | 智能批量审批 | 批量不可逆决策 |
| 4 | `create_contract` | `contract_crud_tools.py` | 创建合同 | 合同创建后影响大 |
| 5 | `create_asset` | `asset_tools.py` | 资产入库 | 资产管理变更 |
| 6 | `transfer_asset` | `asset_tools.py` | 资产转移/领用/归还 | 资产归属变更 |
| 7 | `delete_scheduled_task` | `scheduled_task_tools.py` | 删除定时任务 | 删除不可恢复 |
| 8 | `create_customer` | `crm_tools.py` | 创建客户 | 数据创建 |
| 9 | `update_customer` | `crm_tools.py` | 更新客户信息 | 客户信息变更 |
| 10 | `add_follow_up` | `crm_tools.py` | 添加跟进记录 | 记录不可删除 |
| 11 | `update_customer_stage` | `crm_tools.py` | 变更销售阶段 | 漏斗状态变更 |
| 12 | `submit_expense` | `expense_tools.py` | 提交报销 | 财务流程 |
| 13 | `process_onboarding` | `workflow_tools.py` | 入职全流程 | 多系统级联操作 |
| 14 | `process_resignation` | `workflow_tools.py` | 离职全流程 | 多系统级联操作 |
| 15 | `process_asset_lifecycle` | `workflow_tools.py` | 批量资产操作 | 批量变更 |

### 本次新增标记（本次审计补充）

| # | 工具名 | 文件 | 操作说明 | 确认理由 |
|---|--------|------|---------|---------|
| 16 | `approve_expense` | `expense_tools.py` | 审批报销单 | 财务审批决策，不可逆 |
| 17 | `update_system_config` | `system_config_tools.py` | 修改系统配置 | 影响全局行为 |
| 18 | `send_notification` | `oa_tools.py` | 发送站内通知 | 外部副作用，无法撤回 |

## 3. 未标记但应需确认的操作（Blast Radius 分析）

以下工具执行变更操作但未设置 `is_irreversible = True`，根据 blast radius 评估其风险：

### 3.1 高风险（建议立即添加 `is_irreversible = True`）

| 工具名 | 文件 | 风险分析 | Blast Radius |
|--------|------|---------|-------------|
| `create_leave_request` | `oa_tools.py:27` | 创建请假申请会进入审批流程，影响排班和工作安排 | 中 — 进入审批流后可被驳回，但已通知相关人 |
| `assign_task` | `oa_tools.py:458` | 分配任务给他人，产生通知，改变他人工作安排 | 中 — 通知已发出，任务已创建 |
| `create_approval_flow` | `approval_flow_tools.py:92` | 创建审批流模板，影响后续所有审批的路由 | 高 — 全局流程变更 |
| `award_badge` | `operational_tools.py:124` | 颁发荣誉徽章，产生全员可见的通知 | 低 — 但一旦发出无法撤回 |

### 3.2 中等风险（建议按场景评估）

| 工具名 | 文件 | 风险分析 | 当前缓解措施 |
|--------|------|---------|-------------|
| `clock_in_out` | `attendance_tools.py:42` | 打卡记录，影响考勤统计 | 低风险 — 仅影响自己 |
| `create_shift_schedule` | `attendance_tools.py:183` | 创建排班，影响团队安排 | 需 admin 角色 |
| `create_work_order` | `work_order_tools.py:42` | 创建工单 | 可关闭，影响有限 |
| `update_work_order` | `work_order_tools.py:317` | 更新工单状态 | 可再次更新 |
| `inventory_in` | `inventory_tools.py:117` | 库存入库 | 可用出库冲抵 |
| `inventory_out` | `inventory_tools.py:180` | 库存出库 | 减少库存不可逆 |
| `create_employee` | `organization_tools.py:372` | 创建员工 | 需 admin 角色 |
| `update_employee` | `organization_tools.py:460` | 更新员工信息 | 需 admin 角色 |
| `create_department` | `organization_tools.py:93` | 创建部门 | 需 admin 角色 |
| `meeting_booking` | `oa_tools.py:368` | 预订会议室 | 可取消，但会通知参会人 |
| `request_leave` | `attendance_tools.py:364` | 请假（考勤模块） | 进入审批流 |
| `create_project` | `project_tools.py:35` | 创建项目 | 可删除 |

### 3.3 低风险（无需添加确认）

| 工具名 | 风险分析 |
|--------|---------|
| 所有查询类工具 (get_*, list_*, query_*) | 只读操作，无副作用 |
| `create_scheduled_task` | 可随时删除 |
| `web_search` | 只读外部搜索 |
| 所有 AI 分析/生成工具 (smart_report, anomaly_detection 等) | 只生成报告，不修改数据 |

## 4. 自动确认触发器覆盖度分析

除了 `is_irreversible` 标记外，`check_confirmation()` 还检查：

### 4.1 高额金额触发器 (≥ ¥50,000)
- **覆盖**: `submit_expense`, `create_contract` 的 `amount` 参数
- **缺口**: 无明显缺口，金额阈值触发与工具无关

### 4.2 批量操作触发器 (≥ 5 条)
- **覆盖**: `smart_approve`, `process_asset_lifecycle` 的批量参数
- **缺口**: 无明显缺口

### 4.3 未覆盖的确认类型
- **EXTERNAL** (外部系统影响): `send_notification` 已在本次补充
- **PERMISSION_ESCALATION**: 当前无工具使用此类型

## 5. 确认 UI/UX 设计建议

### 5.1 当前实现

当前确认对话框 (`ChatMessageList.tsx`) 展示：
- 确认消息文本
- 操作参数 JSON（可编辑）
- 确认/取消按钮

### 5.2 改进建议

#### A. 分级确认 UI

```
┌─────────────────────────────────────────────────┐
│  ⚠️ 操作需要确认                                │
│                                                  │
│  ┌─ 风险标签 ──────────────────────────────────┐│
│  │ 🔒 不可逆操作    💰 大额(¥80,000)          ││
│  └─────────────────────────────────────────────┘│
│                                                  │
│  📋 操作预览                                    │
│  ┌─────────────────────────────────────────────┐│
│  │ 操作: 批准审批申请                           ││
│  │ 申请人: 张三                                 ││
│  │ 类型: 报销                                   ││
│  │ 金额: ¥80,000                               ││
│  │ 说明: 第四季度市场推广费用                    ││
│  └─────────────────────────────────────────────┘│
│                                                  │
│  ⚡ 影响范围                                    │
│  - 审批流程将终结                                │
│  - 财务系统将收到付款通知                        │
│  - 申请人将收到审批通过通知                      │
│                                                  │
│          [ 取消 ]        [ ✅ 确认执行 ]         │
└─────────────────────────────────────────────────┘
```

#### B. 建议增加的信息

1. **影响范围说明**: 每个 irreversible 工具应提供 `blast_radius_description`，解释操作会影响什么
2. **操作预览结构化展示**: 将 JSON 参数渲染为可读的表单而非原始 JSON
3. **风险标签彩色化**:
   - 🔴 不可逆 (IRREVERSIBLE)
   - 🟠 大额 (HIGH_VALUE)
   - 🟡 批量 (BULK_OPERATION)
   - 🔵 外部 (EXTERNAL)
4. **二次确认输入**: 对于最高风险操作（如离职流程、批量审批），要求用户输入操作名称确认

#### C. 工具端增强建议

```python
class BaseTool:
    @property
    def blast_radius_description(self) -> str:
        """描述此操作的影响范围，用于确认对话框展示。"""
        return ""

    def format_confirmation_preview(self, args: dict) -> dict:
        """
        将原始参数格式化为用户友好的预览信息。
        返回 {"title": "...", "details": [...], "impact": [...]}
        """
        return {"title": self.name, "details": args, "impact": []}
```

## 6. 总结

### 6.1 本次审计行动

| 行动 | 状态 |
|------|------|
| 补充 `approve_expense` 的 `is_irreversible` 标记 | ✅ 已完成 |
| 补充 `update_system_config` 的 `is_irreversible` 标记 | ✅ 已完成 |
| 补充 `send_notification` 的 `is_irreversible` 标记 | ✅ 已完成 |
| Blast radius 分析文档 | ✅ 本文档 |
| UI/UX 改进建议 | ✅ 见第 5 节 |

### 6.2 后续建议

1. **优先级 P1**: 为 `create_approval_flow` 添加 `is_irreversible = True`（影响全局审批流程）
2. **优先级 P2**: 为 `assign_task` 和 `meeting_booking` 添加外部通知类确认
3. **优先级 P2**: 实现 `blast_radius_description` 属性，增强确认对话框信息量
4. **优先级 P3**: 添加二次确认输入机制（针对级联操作如入职/离职流程）
5. **优先级 P3**: 建立 HITL 覆盖率指标，新增工具时自动检查是否需要确认标记
