# 响应速度优化方案

## 当前瓶颈分析

### 1. Agent 循环次数过多
- 当前: `LANGGRAPH_MAX_ITERATIONS = 5` (plan → execute → reflect 最多5轮)
- 问题: 简单问题也走完整循环,浪费时间

### 2. 记忆检索耗时
- 每次对话都进行语义搜索
- embedding 生成 + 向量检索耗时 1-2s

### 3. 模型选择不当
- 默认模型: `gemini-3-flash-preview`
- 如果实际使用的是 GPT-4 等慢速模型,会严重拖慢响应

### 4. 工具调用链路长
- 每个工具调用都是一次 LLM 往返
- 多工具场景延迟累加

## 优化方案

### 方案1: 降低循环次数 (立即生效)

**修改配置**:
```bash
# .env
LANGGRAPH_MAX_ITERATIONS=2  # 从5降到2
```

**效果**: 最坏情况从 5 轮降到 2 轮,节省 60% 时间

**风险**: 复杂任务可能完成度下降

---

### 方案2: 启用语义缓存 (P0已实现)

检查是否启用:
```bash
# .env
REDIS_URL=redis://localhost:6379  # 必须配置
```

**效果**: 相似问题直接返回缓存,延迟 <100ms

---

### 方案3: 切换到更快的模型

**推荐配置**:
```bash
# .env
AI_DEFAULT_MODEL=gpt-4o-mini  # 或 claude-3-5-haiku
```

**速度对比**:
- GPT-4: ~10-15s
- GPT-4o: ~3-5s  
- GPT-4o-mini: ~1-2s ✅
- Claude 3.5 Haiku: ~1-2s ✅

---

### 方案4: 优化记忆检索

**当前**: 每次都检索
**优化**: 只在需要时检索

修改 `app/agent/memory.py`:

```python
# 添加快速路径判断
def should_search_memory(user_input: str) -> bool:
    """判断是否需要检索记忆"""
    # 简单问候、确认等不需要记忆
    skip_keywords = ["你好", "谢谢", "好的", "明白", "继续"]
    return not any(kw in user_input for kw in skip_keywords)
```

**效果**: 30% 的简单对话跳过记忆检索,节省 1-2s

---

### 方案5: 并行化工具调用

**当前**: 串行调用工具
**优化**: 无依赖的工具并行执行

LangGraph 已支持,确保配置正确即可。

---

## 快速实施方案 (推荐)

**立即生效的3步优化**:

1. **降低循环次数**:
```bash
# .env
LANGGRAPH_MAX_ITERATIONS=2
```

2. **切换快速模型**:
```bash
# .env  
AI_DEFAULT_MODEL=gpt-4o-mini
```

3. **启用 Redis 缓存**:
```bash
# .env
REDIS_URL=redis://localhost:6379
```

**预期效果**: 
- 平均响应时间: 10-15s → 3-5s
- 缓存命中: <100ms

---

## 监控指标

添加到 Langfuse 追踪:
- 首 token 延迟 (TTFT)
- 总响应时间
- 循环次数
- 缓存命中率

通过 Langfuse 面板实时监控优化效果。
