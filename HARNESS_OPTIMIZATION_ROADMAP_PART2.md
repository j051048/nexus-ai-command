# Harness 优化路线图 Part 2: 具体实施方案

## P0: 主动性改造

### 1. 后台任务调度器

**实现方案**:
```python
# nexus_backend/app/agent/proactive_scheduler.py
class ProactiveScheduler:
    """让 Agent 主动工作的调度器"""

    async def schedule_routine_task(self, task_config: dict):
        """
        定时任务配置:
        {
            "name": "每日销售汇总",
            "cron": "0 9 * * *",  # 每天 9 点
            "agent_prompt": "汇总昨日销售数据并发送给管理层",
            "target_users": ["boss@company.com"]
        }
        """
        pass
```

**预期效果**:
- Agent 每天早上 9 点自动生成销售报表
- 每周五下午自动发送周报
- 合同到期前 7 天自动提醒

**实施成本**: 2-3 天

---

### 2. 目标追踪系统

**数据库设计**:
```sql
CREATE TABLE agent_goals (
    id UUID PRIMARY KEY,
    user_id UUID,
    goal_text TEXT,  -- "本月完成 5 个销售订单"
    deadline TIMESTAMP,
    status TEXT,  -- pending/in_progress/completed
    progress JSONB,  -- {"completed": 2, "total": 5}
    created_at TIMESTAMP
);
```

**Agent 行为**:
- 每次对话开始时检查未完成目标
- 主动询问："您的销售目标进展如何？"
- 自动追踪进度并提醒

**实施成本**: 3-4 天

---

### 3. 事件驱动触发

**实现方案**:
```python
# nexus_backend/app/agent/event_triggers.py
class EventTrigger:
    """数据变化时自动触发 Agent"""

    async def on_contract_expiring(self, contract_id: str):
        """合同即将到期时触发"""
        await self.trigger_agent(
            prompt=f"合同 {contract_id} 将在 7 天后到期，请提醒相关人员续签"
        )

    async def on_sales_milestone(self, milestone: dict):
        """销售里程碑达成时触发"""
        await self.trigger_agent(
            prompt=f"恭喜！本月销售额已达到 {milestone['amount']}，请生成庆祝通知"
        )
```

**预期效果**:
- 数据异常时自动报警
- 重要事件自动通知
- 无需用户主动询问

**实施成本**: 2-3 天

---

## P1: 学习与适应

### 4. 错误学习机制

**实现方案**:
```python
# nexus_backend/app/agent/learning_system.py
class LearningSystem:
    """从错误中学习"""

    async def record_failure(self, context: dict):
        """
        记录失败案例:
        - 工具调用失败的参数
        - 用户纠正的内容
        - 重复出现的问题
        """
        await supabase.table("agent_failures").insert({
            "tool_name": context["tool"],
            "error_pattern": context["error"],
            "correct_solution": context["fix"],
            "frequency": 1
        })

    async def get_learned_patterns(self, tool_name: str):
        """获取历史经验"""
        return await supabase.table("agent_failures")\
            .select("*")\
            .eq("tool_name", tool_name)\
            .order("frequency", desc=True)\
            .limit(5)\
            .execute()
```

**集成到 Plan Node**:
- 规划前查询历史失败案例
- 避免重复错误
- 优先使用成功方案

**实施成本**: 3-4 天

---

### 5. 用户偏好学习

**实现方案**:
```python
# 自动学习用户偏好
class PreferenceLearner:
    async def learn_from_feedback(self, interaction: dict):
        """
        从用户反馈学习:
        - 用户修改了 Agent 生成的报表格式 → 记住格式偏好
        - 用户总是要求"简洁回答" → 记住沟通风格
        - 用户常用某个工具 → 优先推荐
        """
        pass
```

**预期效果**:
- 越用越懂用户
- 自动适应沟通风格
- 减少重复纠正

**实施成本**: 2-3 天

---

## P2: 工具调用优化

### 6. 批量操作优化

**当前问题**:
```python
# 低效：串行查询 10 个客户
for customer_id in customer_ids:
    result = await get_customer_info(customer_id)
```

**优化方案**:
```python
# 高效：批量查询
results = await get_customers_batch(customer_ids)
```

**实施**:
- 为常用工具添加 `_batch` 版本
- Plan Node 自动识别可批量操作
- 并行执行优化

**预期提升**: 响应速度 5-10x

**实施成本**: 3-5 天

---

### 7. 工具调用缓存

**实现方案**:
```python
# nexus_backend/app/agent/tool_cache.py
class ToolCache:
    """智能工具缓存"""

    async def get_or_execute(self, tool_name: str, args: dict):
        cache_key = f"{tool_name}:{hash(frozenset(args.items()))}"

        # 只读工具缓存 5 分钟
        if tool_name in READ_ONLY_TOOLS:
            cached = await redis.get(cache_key)
            if cached:
                return cached

        result = await execute_tool(tool_name, args)
        await redis.setex(cache_key, 300, result)
        return result
```

**预期效果**:
- 相同查询秒级响应
- 减少数据库压力

**实施成本**: 1-2 天

---

## 总结

| 优化项 | 优先级 | 实施成本 | 预期收益 |
|--------|--------|----------|----------|
| 后台调度器 | P0 | 2-3 天 | 主动性 ↑↑↑ |
| 目标追踪 | P0 | 3-4 天 | 长期规划 ↑↑↑ |
| 事件触发 | P0 | 2-3 天 | 实时响应 ↑↑ |
| 错误学习 | P1 | 3-4 天 | 准确率 ↑↑ |
| 偏好学习 | P1 | 2-3 天 | 用户体验 ↑↑ |
| 批量优化 | P2 | 3-5 天 | 速度 5-10x |
| 工具缓存 | P2 | 1-2 天 | 速度 3-5x |

**总计**: 16-24 天可完成核心改造

下一部分将提供最小可行实现代码...
