# 企业流程改进实施方案

## 改进1: 增加执行确认节点

### 问题
审批通过后只发通知,没有"财务已打款"、"HR已录入"等执行确认

### 解决方案

#### 1.1 数据库 Schema 扩展
```sql
-- 在 workflow_templates 表的 nodes 中增加 executor 类型
-- nodes 字段示例:
{
  "type": "executor",
  "id": "finance_transfer",
  "role": "finance",
  "action": "transfer_money",
  "action_label": "确认打款",
  "require_evidence": true,  -- 是否需要上传凭证
  "timeout_hours": 24
}
```

#### 1.2 修改 approval_chain.py

**文件**: `app/services/approval_chain.py`

```python
# 在 advance_step 方法中增加 executor 节点处理

async def advance_step(self, request_id: str, decision: str, approver_id: str, ...):
    # ... 现有代码 ...
    
    # 新增: 处理 executor 节点
    if current_node.get("type") == "executor":
        # 记录执行确认
        await self._record_execution(
            request_id=request_id,
            executor_id=approver_id,
            action=current_node.get("action"),
            evidence=comment,  # 凭证URL
            db=db
        )
        
        # 发送完成通知给申请人
        await emit(EventType.WORKFLOW_EXECUTED, {
            "request_id": request_id,
            "action": current_node.get("action_label"),
            "executor": approver_id
        })
```

#### 1.3 前端显示
```typescript
// 在审批历史中显示执行确认
{
  step: "财务打款",
  type: "executor",
  status: "completed",
  executor: "张会计",
  evidence: "转账凭证.pdf",
  time: "2026-04-01 15:30"
}
```

---

## 改进2: 支持会签和或签

### 问题
只支持串行审批,无法实现"采购+财务同时审批"或"3个副总任意1人同意"

### 解决方案

#### 2.1 数据库 Schema
```sql
-- 新增并行网关节点
{
  "type": "parallel_gateway",
  "id": "multi_approval",
  "mode": "all",  -- all(会签) 或 any(或签)
  "approvers": [
    {"role": "cfo", "user_id": "xxx"},
    {"role": "coo", "user_id": "yyy"}
  ],
  "min_approvals": 2  -- 或签时至少需要几人同意
}
```

#### 2.2 修改 approval_chain.py

**文件**: `app/services/approval_chain.py`

```python
async def advance_step(self, request_id: str, decision: str, approver_id: str, ...):
    # 新增: 处理并行网关
    if current_node.get("type") == "parallel_gateway":
        mode = current_node.get("mode")
        approvers = current_node.get("approvers", [])
        
        # 记录当前审批人的决策
        await self._record_parallel_decision(request_id, approver_id, decision, db)
        
        # 检查是否满足条件
        decisions = await self._get_parallel_decisions(request_id, current_step, db)
        
        if mode == "all":
            # 会签: 所有人都同意才通过
            if all(d["decision"] == "approved" for d in decisions):
                return await self._move_to_next_step(request_id, db)
        elif mode == "any":
            # 或签: 任意人同意即通过
            min_approvals = current_node.get("min_approvals", 1)
            approved_count = sum(1 for d in decisions if d["decision"] == "approved")
            if approved_count >= min_approvals:
                return await self._move_to_next_step(request_id, db)
```

---

## 改进3: 驳回后重新提交

### 解决方案

#### 3.1 数据库字段
```sql
-- approval_requests 表增加字段
ALTER TABLE approval_requests ADD COLUMN reject_to_step INT;
ALTER TABLE approval_requests ADD COLUMN resubmit_count INT DEFAULT 0;
```

#### 3.2 修改代码
```python
async def advance_step(self, request_id: str, decision: str, ...):
    if decision == "rejected":
        reject_to = current_node.get("reject_to", "start")
        
        # 更新状态为 pending_resubmit
        await db.table("approval_requests").update({
            "status": "pending_resubmit",
            "reject_to_step": 0 if reject_to == "start" else current_step - 1,
            "current_step": None
        }).eq("id", request_id).execute()
        
        # 通知申请人修改
        await emit(EventType.APPROVAL_REJECTED, {
            "request_id": request_id,
            "reason": comment
        })
```

---

## 改进4: AI 主动服务能力

### 4.1 异常预警

**新建文件**: `app/services/ai_workflow_monitor.py`

```python
"""AI 工作流监控服务 - 异常预警"""
import logging
from datetime import datetime, timedelta
from app.core.database import supabase
from app.services.llm_gateway import get_llm

logger = logging.getLogger(__name__)

async def check_expense_anomaly(user_id: str, amount: float, expense_type: str):
    """检测报销异常"""
    # 获取用户近30天报销记录
    thirty_days_ago = datetime.now() - timedelta(days=30)
    history = await supabase.table("approval_requests").select("*").eq(
        "user_id", user_id
    ).eq("type", "expense").gte("created_at", thirty_days_ago.isoformat()).execute()
    
    records = history.data or []
    
    # 异常规则
    warnings = []
    
    # 1. 频率异常: 30天内超过10次
    if len(records) > 10:
        warnings.append(f"该用户本月已报销{len(records)}次,频率异常")
    
    # 2. 金额异常: 超过历史平均3倍
    if records:
        avg_amount = sum(r["amount"] for r in records) / len(records)
        if amount > avg_amount * 3:
            warnings.append(f"本次金额{amount}元,超过历史平均{avg_amount:.0f}元的3倍")
    
    # 3. AI 深度分析
    if warnings:
        llm = get_llm()
        prompt = f"""分析以下报销异常:
用户: {user_id}
本次报销: {amount}元 ({expense_type})
异常点: {', '.join(warnings)}

请判断风险等级(低/中/高)并给出建议。"""
        
        analysis = await llm.ainvoke(prompt)
        return {"risk": "medium", "warnings": warnings, "suggestion": analysis}
    
    return None
```

### 4.2 智能催办

**新建文件**: `app/services/ai_reminder.py`

```python
"""AI 智能催办服务"""
async def generate_reminder_strategy(request_id: str):
    """分析延迟原因并生成催办策略"""
    # 获取审批详情
    request = await supabase.table("approval_requests").select("*").eq("id", request_id).single().execute()
    approver_id = request.data["current_approver"]
    
    # 分析审批人状态
    # 1. 查看审批人今日日程
    # 2. 查看审批人历史审批速度
    # 3. 查看是否有委托记录
    
    llm = get_llm()
    prompt = f"""该审批已超时12小时,审批人: {approver_id}
    
分析:
- 审批人今日有3个会议
- 历史平均审批时间: 2小时
- 当前积压审批: 5个

请给出催办建议。"""
    
    suggestion = await llm.ainvoke(prompt)
    return suggestion
```

### 4.3 数据分析看板

**新建文件**: `app/routers/workflow_analytics.py`

```python
"""工作流数据分析 API"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/workflow-analytics", tags=["analytics"])

@router.get("/department-expense-trend")
async def get_department_expense_trend(dept_id: str, months: int = 6):
    """部门费用趋势"""
    # 查询近6个月费用数据
    # 按月份聚合
    # 返回图表数据
    pass

@router.get("/approval-efficiency")
async def get_approval_efficiency(org_id: str):
    """审批效率分析"""
    # 平均审批时长
    # 超时率
    # 各环节耗时占比
    pass
```

---

## 改进5: 事务流可视化提升

### 5.1 实时进度追踪

**前端组件**: `WorkflowProgress.tsx`

```typescript
// 实时进度条组件
interface Step {
  name: string;
  status: 'completed' | 'current' | 'pending';
  approver: string;
  time?: string;
  estimatedTime?: string;
}

export function WorkflowProgress({ requestId }: { requestId: string }) {
  const steps = [
    { name: '提交申请', status: 'completed', time: '10:00' },
    { name: '主管审批', status: 'completed', approver: '李主管', time: '10:30' },
    { name: '财务审核', status: 'current', approver: '张会计', estimatedTime: '还剩2小时' },
    { name: 'CFO审批', status: 'pending', approver: '王总' },
    { name: '财务打款', status: 'pending' }
  ];
  
  return (
    <div className="workflow-timeline">
      {steps.map((step, i) => (
        <div key={i} className={`step step-${step.status}`}>
          <div className="step-icon">
            {step.status === 'completed' && <CheckIcon />}
            {step.status === 'current' && <ClockIcon />}
          </div>
          <div className="step-content">
            <h4>{step.name}</h4>
            {step.approver && <p>审批人: {step.approver}</p>}
            {step.time && <span className="time">{step.time}</span>}
            {step.estimatedTime && <span className="estimate">{step.estimatedTime}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
```

### 5.2 流程图增强

**使用 React Flow 增强**:



