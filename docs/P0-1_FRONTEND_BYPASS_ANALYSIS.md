# P0-1 前端直连数据库分析报告

## 搜索结果统计
- **总调用数**: 51次
- **涉及文件数**: 约15个文件
- **涉及表数**: 约20个表

## 涉及的表清单

### 1. 用户相关
- `users` - 用户信息

### 2. OA办公
- `attendance_records` - 考勤记录
- `oa_leave_requests` - 请假申请
- `oa_meeting_bookings` - 会议预订
- `oa_tasks` - 任务

### 3. 销售相关
- `sales_leads` - 销售线索
- `sales_targets` - 销售目标
- `sales_metrics` - 销售指标

### 4. 合同相关
- `contracts` - 合同
- `contract_events` - 合同事件
- `customers` - 客户

### 5. 项目相关
- `projects` - 项目
- `project_timeline` - 项目时间线

### 6. 财务相关
- `finance_budgets` - 预算
- `finance_invoices` - 发票

### 7. HR相关
- `hr_attendance` - HR考勤
- `hr_salary_records` - 薪资记录
- `hr_performance_reviews` - 绩效评审
- `hr_job_positions` - 职位
- `hr_candidates` - 候选人

### 8. 其他
- `documents` - 文档
- `assets` - 资产
- `certificates` - 证书
- `inventory` - 库存
- `audit_logs` - 审计日志
- `dashboard_configs` - 仪表板配置
- `notifications` - 通知

## 需要创建的后端API路由

按优先级分批实施:

### 批次1: 高频核心表 (优先)
- `/api/users` - 用户
- `/api/sales-leads` - 销售线索
- `/api/contracts` - 合同
- `/api/oa-tasks` - OA任务

### 批次2: OA办公模块
- `/api/attendance` - 考勤
- `/api/leave-requests` - 请假
- `/api/meeting-bookings` - 会议预订

### 批次3: 财务HR模块
- `/api/finance/budgets` - 预算
- `/api/finance/invoices` - 发票
- `/api/hr/attendance` - HR考勤
- `/api/hr/salary` - 薪资
- `/api/hr/performance` - 绩效

### 批次4: 其他模块
- `/api/projects` - 项目
- `/api/documents` - 文档
- `/api/assets` - 资产
- `/api/inventory` - 库存
- `/api/audit-logs` - 审计日志

## 下一步行动
开始批次1的API创建
