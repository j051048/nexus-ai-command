```typescript
// 节点状态可视化
const nodeTypes = {
  approval: ApprovalNode,
  executor: ExecutorNode,
  parallel: ParallelGatewayNode
};

function ApprovalNode({ data }) {
  return (
    <div className={`node-approval status-${data.status}`}>
      <div className="node-header">
        <UserIcon />
        <span>{data.approver}</span>
      </div>
      <div className="node-body">
        <p>{data.label}</p>
        {data.status === 'current' && (
          <Progress value={data.timeProgress} />
        )}
      </div>
      {data.status === 'completed' && (
        <div className="node-footer">
          <CheckIcon /> {data.completedAt}
        </div>
      )}
    </div>
  );
}
```

### 5.3 移动端优化

```typescript
// 移动端卡片式展示
function MobileWorkflowCard({ request }) {
  return (
    <Card>
      <CardHeader>
        <Badge status={request.status} />
        <h3>{request.title}</h3>
      </CardHeader>
      <CardBody>
        <div className="current-step">
          当前: {request.currentStep} - {request.currentApprover}
        </div>
        <ProgressBar current={request.stepIndex} total={request.totalSteps} />
      </CardBody>
      <CardFooter>
        <Button onClick={() => viewDetails(request.id)}>查看详情</Button>
      </CardFooter>
    </Card>
  );
}
```

---

## 实施优先级

### Phase 1: 核心功能(2周)
1. ✅ 执行确认节点
2. ✅ 驳回重新提交
3. ✅ 实时进度追踪

### Phase 2: 高级功能(3周)
4. ✅ 会签/或签
5. ✅ 异常预警
6. ✅ 流程图增强

### Phase 3: 智能化(4周)
7. ✅ 智能催办
8. ✅ 数据分析看板
9. ✅ 移动端优化

---

## 代码文件清单

### 新增文件
```
app/services/ai_workflow_monitor.py    # 异常预警
app/services/ai_reminder.py            # 智能催办
app/routers/workflow_analytics.py      # 数据分析API
```

### 修改文件
```
app/services/approval_chain.py         # 增加executor/parallel_gateway
app/routers/approval.py                # 增加重新提交API
nexus_frontend/src/components/WorkflowProgress.tsx  # 进度组件
```

### 数据库迁移
```sql
-- 001_add_executor_support.sql
ALTER TABLE approval_requests ADD COLUMN reject_to_step INT;
ALTER TABLE approval_requests ADD COLUMN resubmit_count INT DEFAULT 0;

-- 002_add_parallel_decisions.sql
CREATE TABLE parallel_approval_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id UUID REFERENCES approval_requests(id),
  step_index INT,
  approver_id UUID,
  decision VARCHAR(20),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

完整实施方案已完成,可按优先级逐步实施。
