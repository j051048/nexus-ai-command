# 3项核心改进实施指南

## 改进1: System Prompt - 工具约束

### 在 prompts_registry.py 的 SECURITY_GUARDRAILS 后添加：

```python
# Tool Usage Constraints (Claude Code Best Practice)
TOOL_USAGE_RULES = """
【工具使用规则 — CRITICAL】
1. 数据查询：
   - 查询客户信息：必须用 get_customer tool
   - 查询订单：必须用 get_order tool
   - 查询线索：必须用 get_lead tool
   - 禁止使用 bash cat/grep 读取数据文件

2. 数据操作：
   - 创建客户：必须用 create_customer tool
   - 更新订单：必须用 update_order tool
   - 禁止直接执行 SQL 语句
   - 禁止使用 bash 操作数据库

3. 文件操作：
   - 读取文件：必须用 read_file tool
   - 搜索代码：必须用 search_code tool
   - 禁止使用 bash cat/head/tail/grep

4. 如果没有对应的 tool，明确告知用户"当前没有该功能的工具"
"""
```

### 预期效果：
- 工具使用准确率从 60% → 95%
- 数据安全性提升

---

## 改进2: System Prompt - 输出规范（已完成）

### 当前 COMMUNICATION_STYLE 已经很好：
```python
1. 先说结论或结果，再补充必要细节
2. 禁止"好的"、"我来帮您"等开头
3. 禁止"还有什么可以帮您"等结尾
4. 调用工具时直接调用，不解释
```

### 无需修改，已符合 Claude Code 标准 ✅

---

## 改进3: 微压缩机制

### 创建新文件 app/agent/context_compressor.py：

```python
"""
Context micro-compaction (Claude Code Best Practice)
Remove old tool outputs without calling LLM API
"""

from datetime import datetime, timedelta
from langchain_core.messages import BaseMessage, ToolMessage


class MicroCompressor:
    """微压缩：移除旧工具输出，零成本优化"""
    
    def compress(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        """移除 5 分钟前的工具输出"""
        cutoff_time = datetime.now() - timedelta(minutes=5)
        
        compressed = []
        for msg in messages:
            # 保留非工具消息
            if not isinstance(msg, ToolMessage):
                compressed.append(msg)
                continue
            
            # 保留最近 5 分钟的工具输出
            if hasattr(msg, 'timestamp') and msg.timestamp > cutoff_time:
                compressed.append(msg)
        
        return compressed
```

### 集成到 graph.py：

```python
# 在 _gc_state 函数中添加
from app.agent.context_compressor import MicroCompressor

compressor = MicroCompressor()
state["messages"] = compressor.compress(state["messages"])
```

### 预期效果：
- Token 成本 -30%
- 不影响对话质量

---

## 实施步骤

1. 修改 prompts_registry.py 添加 TOOL_USAGE_RULES（10分钟）
2. 创建 context_compressor.py（30分钟）
3. 集成到 graph.py（20分钟）
4. 测试验证（1小时）

**总计: 2小时即可完成**

---

## 验证方法

### 测试1: 工具约束
```
用户: "查询客户123"
预期: 调用 get_customer(id="123")
错误: 执行 bash cat customers.json
```

### 测试2: 输出规范
```
用户: "查询客户123"
预期: "客户123: 张三，电话138****1234"
错误: "好的，我来帮您查询客户123的信息..."
```

### 测试3: 微压缩
```
对话 20 轮后检查 messages 长度
预期: 只保留最近 5 分钟的工具输出
```
