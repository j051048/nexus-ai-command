# AI-First 企业管理平台 - 实施指南

## 🎯 项目目标

将传统 OA/ERP 功能与 AI 智能体深度融合，实现：
- **对话即操作**：用自然语言完成所有办公事务
- **AI即中枢**：智能体自动执行、自动决策、自动通知
- **傻瓜式交互**：无需培训，人人会用

---

## 📦 新增文件清单

### 后端工具 (nexus_backend/app/tools/)

| 文件 | 功能 | 工具数量 |
|------|------|----------|
| `oa_tools.py` | OA办公自动化 | 5个 |
| `finance_tools.py` | 财务报销管理 | 5个 |
| `hr_tools.py` | 人力资源管理 | 5个 |
| `boss_tools.py` | 领导专属工具 | 5个 |

### 新增工具详情

#### OA 工具 (oa_tools.py)
```
1. create_leave_request - 请假申请
2. query_leave_status - 请假查询
3. book_meeting - 会议预约
4. assign_task - 任务分配
5. create_work_handover - 工作交接
```

#### 财务工具 (finance_tools.py)
```
1. create_expense_claim - 报销申请
2. query_expense_status - 报销查询
3. query_budget - 预算查询
4. query_salary - 薪资查询
5. recognize_invoice - 发票识别
```

#### HR 工具 (hr_tools.py)
```
1. query_attendance - 考勤查询
2. query_team_attendance - 团队考勤（管理者）
3. get_employee_profile - 员工画像（管理者）
4. create_performance_review - 绩效评估
5. manage_recruitment - 招聘管理
```

#### 领导工具 (boss_tools.py)
```
1. smart_approve - 智能审批（批量/条件/委托）
2. get_daily_briefing - 每日简报
3. get_business_dashboard - 经营仪表盘
4. get_team_insight - 团队洞察
5. publish_announcement - 发布公告
```

### 数据库迁移
```
nexus_backend/supabase_migrations/20241220_ai_first_enterprise.sql
```

包含以下新表：
- `oa_leave_requests` - 请假申请
- `oa_meeting_rooms` - 会议室
- `oa_meeting_bookings` - 会议预约
- `oa_tasks` - 任务
- `oa_work_handovers` - 工作交接
- `finance_expense_details` - 报销明细
- `finance_budgets` - 预算
- `finance_invoices` - 发票
- `hr_attendance` - 考勤
- `hr_performance_reviews` - 绩效评估
- `hr_salary_records` - 薪资记录
- `hr_job_positions` - 招聘职位
- `hr_candidates` - 候选人
- `ai_interactions` - AI交互记录

### 前端组件
```
src/components/ai/QuickActions.tsx - 快捷操作面板
```

### 文档
```
docs/AI_FIRST_ENTERPRISE_DESIGN.md - 详细设计文档
docs/AI_FIRST_IMPLEMENTATION_GUIDE.md - 本实施指南
```

---

## 🚀 部署步骤

### Step 1: 执行数据库迁移

```bash
# 在 Supabase Dashboard 执行 SQL
# 或使用 supabase cli
supabase db push
```

直接在 Supabase SQL Editor 中执行：
`nexus_backend/supabase_migrations/20241220_ai_first_enterprise.sql`

### Step 2: 重启后端服务

```bash
cd nexus_backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

### Step 3: 验证工具注册

访问 `http://localhost:8000/docs` 查看 API 文档，确认新工具已加载。

调用测试：
```bash
curl http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"messages": [{"role": "user", "content": "我想请假3天"}]}'
```

---

## 💬 使用示例

### 员工场景

```
用户: 我想请假，下周一到周三，家里有事
AI: ✅ 请假申请已提交！
    - 类型: 事假
    - 时间: 12/23 - 12/25 (3天)
    - 审批状态: 需直属领导审批
    已通知您的领导张经理

用户: 报销昨天请客户吃饭800块
AI: ✅ 报销申请已提交！
    - 类型: 业务招待费
    - 金额: ¥800
    - 金额<1000，已自动审批，预计3天到账

用户: 我这个月工资怎么少了
AI: 📊 12月工资明细：
    应发: ¥18,700
    扣除: ¥5,382 (社保+公积金+个税+迟到)
    实发: ¥13,318
    比上月少 ¥200，因为迟到扣款
```

### 领导场景

```
用户: 今天有什么事
AI: ☀️ 早上好，老板！
    
    ✅ 已自动处理 12 件
    ⏳ 需您决策 3 件：
    
    1️⃣ 王小明 - 设备采购 ¥58,000
       AI建议: ✅ 批准（价格合理）
    
    2️⃣ 市场部 - 增加2个HC
       AI建议: ⚠️ 先批1个观察
    
    您可以说「全部批了」或「第1个批，第2个先不批」

用户: 第一个批了，第二个改成批1个
AI: ✅ 已处理：
    - 设备采购 ¥58,000 → 已批准
    - HC申请 → 已批准1个，通知HR启动招聘

用户: 5000以下的报销都批了
AI: ✅ 条件审批完成！
    批准 8 件，共 ¥12,350
    已通知相关申请人
```

---

## 🔧 配置说明

### 审批规则配置

编辑 `nexus_backend/app/services/approval_chain.py` 中的 `DEFAULT_CHAINS`：

```python
DEFAULT_CHAINS = {
    "expense": ApprovalChainConfig(
        steps=[
            ApprovalStep(ApprovalLevel.AUTO, 500, "system"),      # <500 自动批
            ApprovalStep(ApprovalLevel.MANAGER, 5000, "manager"),  # <5000 主管批
            ApprovalStep(ApprovalLevel.CFO, 50000, "cfo"),         # <50000 CFO批
        ]
    )
}
```

### 权限控制

工具的 `required_role` 属性控制访问权限：
- `"all"` - 所有人可用
- `"manager"` - 管理者及以上
- `"boss"` - 仅领导可用

---

## 📊 效果预期

| 场景 | 传统操作 | AI操作 | 效率提升 |
|------|----------|--------|----------|
| 请假申请 | 3分钟 | 10秒 | 95% |
| 报销提交 | 15分钟 | 30秒 | 97% |
| 领导审批(10件) | 20分钟 | 1分钟 | 95% |
| 薪资查询 | 找HR问 | 5秒 | 99% |
| 考勤确认 | 登录系统查 | 5秒 | 99% |

---

## 🛣️ 后续扩展

### Phase 2 (计划中)
- [ ] 语音交互支持
- [ ] 图片/发票OCR识别
- [ ] 钉钉/企微集成
- [ ] 金蝶/用友对接

### Phase 3 (规划中)
- [ ] 预测分析（离职风险、业绩预测）
- [ ] 知识图谱（员工关系、项目关联）
- [ ] 自动化工作流引擎

---

## ❓ FAQ

**Q: 工具调用失败怎么办？**
A: 检查 `nexus_backend/app/tools/__init__.py` 是否正确注册，查看后端日志。

**Q: 如何添加新工具？**
A: 
1. 在 `tools/` 下创建新文件
2. 继承 `BaseTool`，实现 `run` 方法
3. 在 `__init__.py` 中 `register_tool`

**Q: 如何修改审批规则？**
A: 编辑 `approval_chain.py` 中的阈值配置。

**Q: 敏感数据如何保护？**
A: 
- 薪资表启用了 RLS，只能查自己的
- 工具有 `required_role` 权限检查
- 所有操作记录在 `ai_interactions` 表

---

*文档版本: v1.0*
*创建时间: 2024-12-20*