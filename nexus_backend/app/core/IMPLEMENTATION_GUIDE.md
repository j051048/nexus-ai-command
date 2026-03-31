# 简化改进方案实施指南

## 已完成的改进

### 1. 统一错误处理 ✅
**文件**: `nexus_backend/app/core/tool_wrapper.py`

**用法示例**:

```python
from app.core.tool_wrapper import execute_tool_safely, safe_tool

# 方式1: 直接使用包装器
async def my_handler():
    result = await execute_tool_safely(
        tool_func=search_leads,
        params={'query': 'test'},
        timeout=30
    )
    
    if result['success']:
        data = result['data']
    else:
        error = result['error']

# 方式2: 使用装饰器
@safe_tool(timeout=60)
async def analyze_sales_data(date_range: str):
    # 工具逻辑
    return {'revenue': 100000}

# 调用时自动包装
result = await analyze_sales_data(date_range='last_30_days')
```

---

### 2. 简化版上下文压缩 ✅
**文件**: `nexus_backend/app/core/context_manager.py`

**用法示例**:

```python
from app.core.context_manager import context_manager

# 在保存新消息后调用
async def save_message(conversation_id: str, message: str):
    # 保存消息到数据库
    await save_to_db(conversation_id, message)
    
    # 检查并修剪旧消息
    trimmed = await context_manager.trim_if_needed(conversation_id)
    if trimmed:
        logger.info(f"Trimmed old messages for {conversation_id}")
```

**集成位置**:
- `nexus_backend/app/agent/graph.py` - 在 Agent 执行后
- `nexus_backend/app/api/routes/chat.py` - 在保存消息后

---

### 3. 简单进度反馈 ✅
**文件**: `nexus_backend/app/core/progress.py`

**用法示例**:

```python
from app.core.progress import send_progress

async def execute_task(websocket):
    # 步骤1
    await send_progress("开始执行任务...", websocket)
    
    # 步骤2
    await send_progress("正在搜索销售线索...", websocket)
    leads = await search_leads()
    
    # 步骤3
    await send_progress(f"找到 {len(leads)} 条线索，正在分析...", websocket)
    result = await analyze_leads(leads)
    
    # 完成
    await send_progress("分析完成", websocket)
    return result
```

---

## 集成步骤

### 步骤1: 在 Agent 工具中添加错误处理

找到现有工具函数，添加 `@safe_tool` 装饰器：

```python
# 修改前
async def search_leads(query: str):
    result = await db.query(...)
    return result

# 修改后
from app.core.tool_wrapper import safe_tool

@safe_tool(timeout=30)
async def search_leads(query: str):
    result = await db.query(...)
    return result
```

### 步骤2: 在消息保存后添加上下文压缩

```python
# 在 nexus_backend/app/agent/graph.py 或相关文件中
from app.core.context_manager import context_manager

async def save_conversation_message(conversation_id, message):
    # 保存消息
    await supabase.table('conversation_memories').insert({
        'conversation_id': conversation_id,
        'content': message
    }).execute()
    
    # 修剪旧消息
    await context_manager.trim_if_needed(conversation_id)
```

### 步骤3: 在 WebSocket 处理中添加进度反馈

```python
# 在 nexus_backend/app/api/routes/websocket.py 或相关文件中
from app.core.progress import send_progress

@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    
    # 接收消息
    data = await websocket.receive_json()
    
    # 发送进度
    await send_progress("正在处理您的请求...", websocket)
    
    # 执行 Agent
    result = await agent.execute(data['message'])
    
    # 发送结果
    await websocket.send_json({'type': 'result', 'data': result})
```

---

## 测试

### 测试错误处理
```python
# 测试超时
result = await execute_tool_safely(
    slow_function,
    {},
    timeout=1  # 1秒超时
)
assert result['success'] == False
assert '超时' in result['error']

# 测试异常
result = await execute_tool_safely(
    failing_function,
    ,
    timeout=30
)
assert result['success'] == False
assert '执行失败' in result['error']
```

### 测试上下文压缩
```python
# 创建 60 条消息
for i in range(60):
    await save_message(conversation_id, f"message {i}")

# 执行压缩
trimmed = await context_manager.trim_if_needed(conversation_id)
assert trimmed == True

# 验证只保留 50 条
count = await get_message_count(conversation_id)
assert count == 50
```

---

## 预期效果

1. **错误处理**: 所有工具执行失败都有清晰的错误信息
2. **上下文压缩**: 长对话不会导致 token 超限
3. **进度反馈**: 用户知道系统正在工作

---

## 下一步（可选）

如果需要进一步优化，可以考虑：

1. **添加重试机制**: 在 `tool_wrapper.py` 中添加自动重试
2. **优化压缩策略**: 保留重要消息（如用户明确指令）
3. **进度百分比**: 在 `progress.py` 中添加进度百分比

但建议先观察当前改进的效果，再决定是否需要进一步优化。
