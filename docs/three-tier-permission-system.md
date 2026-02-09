# 三级权限系统设计文档

## 概述

Project Nexus 采用三级权限架构，确保数据安全和操作可追溯性。

## 权限层级

### Level 1: Boss (老板/创始人)
**数据库角色**: `founder`  
**前端角色**: `boss`  
**权限范围**:
- ✅ 完整的管理后台访问权限
- ✅ 审批所有请求的权限
- ✅ 查看所有员工数据
- ✅ 员工管理（删除、转移数据）
- ✅ 系统设置和配置
- ✅ 查看完整的审计日志

### Level 2: AI Assistant (AI助手 - 豆豆)
**数据库角色**: `ai_assistant`  
**前端角色**: `ai_assistant`  
**固定UUID**: `00000000-0000-0000-0000-000000000001`  
**权限范围**:
- ✅ 代表员工提交审批请求（使用员工的身份）
- ✅ 查询员工基本信息（不包括敏感数据）
- ✅ 查询员工的审批历史
- ✅ 自动审批小额请求（根据规则）
- ❌ 不能删除任何数据
- ❌ 不能访问管理后台
- ❌ 不能查看老板的数据
- ❌ 不能修改权限设置

### Level 3: Employee (普通员工)
**数据库角色**: `sales` / `employee`  
**前端角色**: `employee`  
**权限范围**:
- ✅ 只能看到自己的数据
- ✅ 可以提交审批请求
- ✅ 查看自己的历史记录
- ✅ 使用 AI 助手（豆豆）帮助提交申请
- ❌ 不能查看其他员工数据
- ❌ 不能访问管理后台

## AI 代理提交流程

当员工（如宇飞）通过 AI 助手（豆豆）提交审批申请时：

```
员工请求 → AI助手(豆豆) → 验证员工身份 → 创建审批记录
                                              ↓
                                    submitted_by = 员工ID
                                    submitted_via = 'ai_assistant'
                                    on_behalf_of = 员工ID
```

### 关键设计原则

1. **归属清晰**: 审批记录的 `submitted_by` 始终是员工ID，不是 AI 的ID
2. **可追溯**: `submitted_via` 字段记录提交渠道，老板可以看到是「豆豆代提交」
3. **员工可见**: 员工登录后可以在「我的申请历史」中看到所有申请，包括 AI 代提交的
4. **审计日志**: 所有 AI 代理操作都会记录在审计日志中

## 数据库表结构变更

### users 表
```sql
CREATE TYPE user_role AS ENUM ('founder', 'sales', 'employee', 'ai_assistant');
```

### approval_requests 表新增字段
```sql
ALTER TABLE approval_requests 
ADD COLUMN on_behalf_of uuid REFERENCES users(id),
ADD COLUMN submitted_via text DEFAULT 'direct'; -- 'direct' | 'ai_assistant' | 'api'
```

## AI 助手工具

### submit_approval_on_behalf
代表员工提交审批申请。

**参数**:
- `employee_id` (必需): 员工ID
- `employee_name`: 员工姓名（用于确认）
- `type` (必需): 审批类型 (travel/leave/expense/purchase)
- `amount`: 金额
- `description` (必需): 详细说明
- `start_date`: 开始日期
- `end_date`: 结束日期

### get_employee_info
根据员工姓名查询其ID和基本信息。

**参数**:
- `employee_name` (必需): 员工姓名

### get_employee_approval_history
查询指定员工的审批申请历史记录。

**参数**:
- `employee_id` (必需): 员工ID
- `limit`: 返回记录数量（默认5条）

## UI 显示规则

### 员工管理页面
- 老板(founder): 显示「老板」标签（金色）
- AI助手(ai_assistant): 显示「AI助手」标签（紫色）+ 🤖 图标
- 员工(sales/employee): 显示「员工」标签（蓝色）

### 审批记录
- 如果 `submitted_via === 'ai_assistant'`，显示「豆豆代提交」标签
- 申请人始终显示实际员工姓名

## 安全考虑

1. **AI 助手不能代老板提交**: 系统会拒绝为 `founder` 角色创建代理审批
2. **操作审计**: 所有 AI 代理操作都会记录 `actor_user_id` 为 AI 助手的 UUID
3. **RLS 策略**: 数据库层面限制 AI 助手只能访问允许的数据
