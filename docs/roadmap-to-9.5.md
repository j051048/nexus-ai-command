# 从 8.73 分到 9.5 分的改进路线图

> 基于 Gemini 综合评估报告的针对性提升方案

## 当前得分分析

| 维度 | 当前分数 | 目标分数 | 差距 | 优先级 |
|------|---------|---------|------|--------|
| Agent 架构 | 9.5 | 9.5 | 0 | ✅ 保持 |
| 安全合规 | 9.0 | 9.5 | +0.5 | P0 |
| 市场竞争力 | 9.0 | 9.5 | +0.5 | P1 |
| 技术架构 | 8.5 | 9.5 | +1.0 | P0 |
| 代码质量 | 8.5 | 9.5 | +1.0 | P0 |
| 性能成本 | 8.5 | 9.5 | +1.0 | P1 |
| 用户体验 | 8.5 | 9.5 | +1.0 | P1 |
| 功能模块 | 8.0 | 9.0 | +1.0 | P2 |

**总分:** 8.73 → 9.5 (需提升 0.77 分)

---

## 阶段一: 核心技术债清理 (2周 - 提升 0.4 分)

### 1. RAG for Tools 动态路由 ⭐⭐⭐⭐⭐
**问题:** 100+ 工具全量传给 LLM，导致 Context 窗口爆炸，路由准确率下降

**解决方案:**
```python
# nexus_backend/app/services/tool_retriever.py

from typing import List
import numpy as np
from app.core.embeddings import get_embedding

class ToolRetriever:
    """基于语义相似度的工具检索"""
    
    def __init__(self):
        self.tool_embeddings = self._precompute_embeddings()
    
    def _precompute_embeddings(self) -> dict:
        """预计算所有工具的 embedding"""
        tools = load_all_tools()
        embeddings = {}
        for tool in tools:
            # 工具描述 + 参数说明
            text = f"{tool.name}: {tool.description}"
            embeddings[tool.name] = get_embedding(text)
        return embeddings
    
    async def retrieve_relevant_tools(
        self, 
        user_query: str, 
        top_k: int = 5
    ) -> List[Tool]:
        """检索最相关的 K 个工具"""
        query_embedding = get_embedding(user_query)
        
        # 计算余弦相似度
        similarities = {}
        for tool_name, tool_emb in self.tool_embeddings.items():
            sim = np.dot(query_embedding, tool_emb)
            similarities[tool_name] = sim
        
        # 返回 Top-K
        top_tools = sorted(similarities.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [load_tool(name) for name, _ in top_tools]
```

**集成到 Router:**
```python
# app/agent/nodes/router.py

async def router_node(state: GraphState) -> dict:
    user_query = state["messages"][-1].content
    
    # 动态检索相关工具
    relevant_tools = await tool_retriever.retrieve_relevant_tools(user_query, top_k=5)
    
    # 只传递相关工具给 LLM
    response = await llm.invoke(
        messages=state["messages"],
        tools=relevant_tools  # 从 100+ 减少到 5 个
    )
```

**预期收益:**
- Context 窗口占用 -80%
- 路由准确率 +15%
- 响应延迟 -30%

**实施时间:** 4 天

---

### 2. LangSmith 可观测性集成 ⭐⭐⭐⭐⭐
**问题:** Agent 翻车时无法重现执行轨迹，调试困难

**解决方案:**
```python
# nexus_backend/app/core/config.py

LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "true")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "nexus-ai-command")
```

```python
# app/agent/graph.py

from langsmith import traceable

@traceable(name="nexus_agent_execution")
async def execute_graph(user_input: str, user_id: str):
    """所有 Agent 执行自动上报到 LangSmith"""
    result = await graph.ainvoke({
        "messages": [HumanMessage(content=user_input)],
        "user_id": user_id
    })
    return result
```

**预期收益:**
- 问题定位时间 -70%
- 可重现 100% 的执行轨迹
- 自动生成性能报告

**实施时间:** 3 天

---

### 3. 后端测试覆盖率提升 ⭐⭐⭐⭐
**问题:** 前端测试完善，后端测试覆盖率低

**解决方案:**
```python
# nexus_backend/tests/test_agent_graph.py

import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_router_simple_intent():
    """测试简单意图路由"""
    with patch('app.agent.llm.ainvoke') as mock_llm:
        mock_llm.return_value = AIMessage(
            content="",
            tool_calls=[{"name": "get_customer", "args": {"id": "123"}}]
        )
        
        result = await router_node({
            "messages": [HumanMessage(content="查询客户123")],
            "complexity": "SIMPLE"
        })
        
        assert result["next"] == "execute"
        assert len(result["tool_calls"]) == 1

@pytest.mark.asyncio
async def test_plan_execute_flow():
    """测试 Plan-Execute 流程"""
    # Mock LLM 返回计划
    # 验证计划分解正确
    # 验证执行顺序正确
    pass
```

**目标覆盖率:**
- 核心 Agent 节点: 90%
- 工具函数: 80%
- API 路由: 70%

**实施时间:** 1 周

---

## 阶段二: 架构解耦与成本优化 (2周 - 提升 0.2 分)

### 4. LiteLLM 网关集成 ⭐⭐⭐⭐⭐
**问题:** 硬编码 LLM Provider，计费不准确，无法动态切换模型

**解决方案:**
```python
# nexus_backend/app/services/llm_gateway.py

from litellm import acompletion, cost_per_token
import litellm

class LLMGateway:
    """统一 LLM 网关，支持多模型、精确计费、重试熔断"""
    
    def __init__(self):
        # 配置回退策略
        litellm.set_fallbacks([
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o-mini",
            "deepseek/deepseek-chat"
        ])
    
    async def invoke(
        self, 
        messages: list, 
        model: str = "anthropic/claude-sonnet-4",
        tools: list = None
    ):
        """统一调用接口"""
        response = await acompletion(
            model=model,
            messages=messages,
            tools=tools,
            timeout=30,
            num_retries=3
        )
        
        # 精确计费
        cost = cost_per_token(
            model=model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens
        )
        
        # 记录到数据库
        await self._log_usage(model, cost, response.usage)
        
        return response
```

**预期收益:**
- 支持 100+ 模型无缝切换
- 计费精确度 100%
- 自动重试 + 降级

**实施时间:** 1 周

---

### 5. Database Repository 抽象层 ⭐⭐⭐⭐
**问题:** 强绑定 Supabase，私有化部署困难

**解决方案:**
```python
# nexus_backend/app/repositories/base.py

from abc import ABC, abstractmethod
from typing import List, Optional

class BaseRepository(ABC):
    """数据库抽象层"""
    
    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[dict]:
        pass
    
    @abstractmethod
    async def find_many(self, filters: dict) -> List[dict]:
        pass
    
    @abstractmethod
    async def create(self, data: dict) -> dict:
        pass
    
    @abstractmethod
    async def update(self, id: str, data: dict) -> dict:
        pass

# Supabase 实现
class SupabaseRepository(BaseRepository):
    def __init__(self, table_name: str):
        self.table = supabase.table(table_name)
    
    async def find_by_id(self, id: str):
        return self.table.select("*").eq("id", id).single().execute()

# 未来可切换到 PostgreSQL 直连
class PostgresRepository(BaseRepository):
    def __init__(self, table_name: str):
        self.table_name = table_name
    
    async def find_by_id(self, id: str):
        async with asyncpg.connect() as conn:
            return await conn.fetchrow(f"SELECT * FROM {self.table_name} WHERE id = $1", id)
```

**预期收益:**
- 支持私有化部署
- 数据库迁移成本 -80%

**实施时间:** 3 周

---

### 6. 租户级配额与限流 ⭐⭐⭐⭐
**问题:** 无租户级别的 Token 消费限制，资源可能被刷爆

**解决方案:**
```python
# nexus_backend/app/middleware/quota_middleware.py

from fastapi import Request, HTTPException
from app.services.quota_service import QuotaService

async def check_quota(request: Request, call_next):
    """检查租户配额"""
    org_id = request.headers.get("X-Org-ID")
    
    # 检查月度配额
    quota = await QuotaService.get_quota(org_id)
    if quota.tokens_used >= quota.tokens_limit:
        raise HTTPException(
            status_code=429,
            detail=f"月度配额已用尽 ({quota.tokens_used}/{quota.tokens_limit})"
        )
    
    # 检查速率限制
    if not await QuotaService.check_rate_limit(org_id, limit=100, window=60):
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后再试"
        )
    
    response = await call_next(request)
    return response
```

**配额表设计:**
```sql
CREATE TABLE organization_quotas (
    org_id UUID PRIMARY KEY,
    tier TEXT CHECK (tier IN ('free', 'pro', 'enterprise')),
    tokens_limit INTEGER,
    tokens_used INTEGER DEFAULT 0,
    requests_per_minute INTEGER,
    reset_at TIMESTAMP
);
```

**预期收益:**
- 防止资源滥用
- 支持分层定价

**实施时间:** 3 天

---

## 阶段三: 安全加固与用户体验 (1周 - 提升 0.17 分)

### 7. PII 脱敏中间件 ⭐⭐⭐⭐⭐
**问题:** 敏感数据可能通过 LLM 响应泄露

**解决方案:**
```python
# nexus_backend/app/middleware/pii_filter.py

import re

class PIIFilter:
    """个人隐私信息过滤器"""
    
    PATTERNS = {
        "phone": r"1[3-9]\d{9}",
        "id_card": r"\d{17}[\dXx]",
        "email": r"[\w\.-]+@[\w\.-]+\.\w+",
        "bank_card": r"\d{16,19}",
        "salary": r"工资[:：]\s*\d+|薪资[:：]\s*\d+"
    }
    
    def mask(self, text: str) -> str:
        """脱敏处理"""
        for pii_type, pattern in self.PATTERNS.items():
            text = re.sub(pattern, self._get_mask(pii_type), text)
        return text
```

**实施时间:** 1.5 周

---

### 8. 行业模板引擎 ⭐⭐⭐⭐
**问题:** 新用户面对空白画布不知如何开始

**解决方案:**
```typescript
// src/lib/templates.ts

export const INDUSTRY_TEMPLATES = {
  retail: {
    name: "零售连锁",
    workflows: [{
      id: "store-inspection",
      name: "门店巡检",
      agents: ["vmd_agent", "task_agent"]
    }]
  }
};
```

**实施时间:** 1 周

---

## 总结: 5 周达到 9.5 分

| 阶段 | 改进项 | 时间 | 分数提升 | 累计分数 |
|------|--------|------|----------|----------|
| 当前 | - | - | - | 8.73 |
| 阶段一 | RAG Tools + LangSmith + 测试 | 2周 | +0.40 | 9.13 |
| 阶段二 | LiteLLM + Repository + 配额 | 2周 | +0.20 | 9.33 |
| 阶段三 | PII 过滤 + 模板引擎 | 1周 | +0.17 | 9.50 |

---

## 快速胜利 (10天提升到 9.0 分)

1. **RAG for Tools** (4天) - 路由准确率 +15%
2. **LangSmith 集成** (3天) - 调试效率 +70%
3. **租户配额限制** (3天) - 防止资源滥用

---

## 关键成功指标

- ✅ Agent 路由准确率 > 95%
- ✅ 问题定位时间 < 5 分钟
- ✅ 后端测试覆盖率 > 80%
- ✅ LLM 成本计费误差 < 2%
- ✅ 支持私有化部署
- ✅ PII 泄露风险 = 0

**下一步:** 是否开始实施阶段一的 RAG for Tools？
