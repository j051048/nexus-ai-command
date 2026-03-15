# AG-UI 协议规范

> Agent-UI 通信协议标准化规范，定义 AI Agent 与前端 UI 之间的结构化事件流。

## 1. 概述

### 动机

当前 Nexus AI Command 使用自定义 SSE 格式进行 Agent-UI 通信。随着功能增加（GenUI、确认流、思考链、配额通知等），事件类型不断膨胀，缺乏统一规范。AG-UI 协议旨在标准化这一通信层。

### 设计目标

1. **类型安全**：每种事件都有严格的 JSON Schema
2. **可扩展**：新事件类型不破坏旧客户端
3. **可恢复**：支持断线重连和事件回放
4. **可观测**：每个事件都可追踪和审计

---

## 2. 传输层

### SSE（Server-Sent Events）

```
POST /api/agent/chat
Content-Type: application/json
Accept: text/event-stream

→ Request Body:
{
  "messages": [...],
  "agent": "sales_consultant",
  "session_id": "uuid",
  "resume_from": "event_id_123"  // 可选，断线重连
}

← Response:
Content-Type: text/event-stream
X-Session-Id: uuid
X-Protocol-Version: 1.0

id: evt_001
event: text_delta
data: {"content": "好的", "role": "assistant"}

id: evt_002
event: tool_start
data: {"tool_name": "query_sales", "args": {...}}

...
```

### 事件格式基础结构

```typescript
interface AGUIEvent {
  id: string;            // 唯一事件 ID，格式: evt_{ulid}
  event: AGUIEventType;  // 事件类型
  data: object;          // 事件负载（按类型不同）
  timestamp: number;     // Unix 毫秒时间戳
  seq: number;           // 序列号（用于排序和重连）
}
```

---

## 3. 事件类型定义

### 3.1 `text_delta` — 文本流式输出

Agent 生成文本的增量片段。

```json
{
  "id": "evt_01HQ...",
  "event": "text_delta",
  "data": {
    "content": "根据数据分析，",
    "role": "assistant",
    "finish_reason": null
  },
  "timestamp": 1710489600000,
  "seq": 1
}
```

**Schema:**

```typescript
interface TextDeltaEvent {
  content: string;                           // 增量文本
  role: 'assistant';                         // 固定为 assistant
  finish_reason: 'stop' | 'length' | null;   // null=未结束
}
```

**结束信号：**

```json
{
  "event": "text_delta",
  "data": {
    "content": "",
    "role": "assistant",
    "finish_reason": "stop"
  }
}
```

### 3.2 `tool_start` — 工具调用开始

Agent 决定调用某个工具。

```json
{
  "event": "tool_start",
  "data": {
    "tool_call_id": "tc_01HQ...",
    "tool_name": "query_sales_leads",
    "args": {
      "status": "active",
      "limit": 10
    },
    "display_name": "查询活跃线索"
  }
}
```

**Schema:**

```typescript
interface ToolStartEvent {
  tool_call_id: string;           // 工具调用唯一 ID
  tool_name: string;              // 工具函数名
  args: Record<string, unknown>;  // 调用参数
  display_name?: string;          // 用户可读的工具名称
}
```

### 3.3 `tool_result` — 工具调用结果

工具执行完成，返回结果。

```json
{
  "event": "tool_result",
  "data": {
    "tool_call_id": "tc_01HQ...",
    "tool_name": "query_sales_leads",
    "status": "success",
    "result": {
      "leads": [...],
      "total": 42
    },
    "duration_ms": 230,
    "display_summary": "找到 42 条活跃线索"
  }
}
```

**Schema:**

```typescript
interface ToolResultEvent {
  tool_call_id: string;                  // 对应 tool_start 的 ID
  tool_name: string;                     // 工具函数名
  status: 'success' | 'error';          // 执行状态
  result?: unknown;                      // 成功结果
  error?: {                              // 错误信息
    code: string;
    message: string;
  };
  duration_ms: number;                   // 执行耗时
  display_summary?: string;             // 用户可读的结果摘要
}
```

### 3.4 `genui_render` — GenUI 组件渲染

Agent 决定渲染一个前端 UI 组件。

```json
{
  "event": "genui_render",
  "data": {
    "component": "StatCards",
    "props": {
      "items": [
        { "label": "本月新增线索", "value": 42, "trend": "+12%" },
        { "label": "成交金额", "value": "¥128万", "trend": "+8%" }
      ]
    },
    "deep_link": "/sales",
    "title": "销售概览"
  }
}
```

**Schema:**

```typescript
interface GenUIRenderEvent {
  component: string;                      // GenUI 组件名
  props: Record<string, unknown>;         // 组件 props
  deep_link?: string;                     // "查看详情"跳转路径
  title?: string;                         // 组件标题
  interactive?: boolean;                  // 是否支持交互（默认 false）
}
```

### 3.5 `confirmation_request` — 确认请求

Agent 需要用户确认才能执行某个操作。

```json
{
  "event": "confirmation_request",
  "data": {
    "request_id": "cfm_01HQ...",
    "tool_name": "delete_lead",
    "message": "确认要删除线索「张三 - 华为」吗？此操作不可撤销。",
    "args": {
      "lead_id": "uuid-123"
    },
    "modifiable": false,
    "severity": "destructive",
    "timeout_seconds": 120
  }
}
```

**Schema:**

```typescript
interface ConfirmationRequestEvent {
  request_id: string;                    // 确认请求 ID
  tool_name: string;                     // 待执行的工具名
  message: string;                       // 用户可读的确认消息
  args: Record<string, unknown>;         // 待执行的参数
  modifiable?: boolean;                  // 用户是否可修改参数
  severity: 'info' | 'warning' | 'destructive';  // 操作严重程度
  timeout_seconds?: number;             // 超时自动取消（秒）
}
```

**用户响应（通过 POST 发送）：**

```json
{
  "type": "confirmation_response",
  "request_id": "cfm_01HQ...",
  "approved": true,
  "modified_args": null
}
```

### 3.6 `status_update` — 状态更新

Agent 处理状态变更通知。

```json
{
  "event": "status_update",
  "data": {
    "status": "thinking",
    "message": "正在分析销售数据...",
    "progress": 0.4
  }
}
```

**Schema:**

```typescript
interface StatusUpdateEvent {
  status: 'thinking' | 'searching' | 'analyzing' | 'generating' | 'waiting' | 'complete';
  message?: string;                     // 用户可读的状态描述
  progress?: number;                    // 0-1 进度（可选）
}
```

### 3.7 `error` — 错误事件

```json
{
  "event": "error",
  "data": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "请求过于频繁，请稍后再试",
    "retryable": true,
    "retry_after_ms": 5000
  }
}
```

**Schema:**

```typescript
interface ErrorEvent {
  code: string;                         // 错误码
  message: string;                      // 用户可读的错误消息
  retryable: boolean;                   // 是否可重试
  retry_after_ms?: number;              // 重试等待时间
  details?: Record<string, unknown>;    // 开发者调试信息
}
```

### 3.8 `thinking_step` — 思考链步骤

Agent 的推理过程可视化。

```json
{
  "event": "thinking_step",
  "data": {
    "step": 1,
    "total_steps": null,
    "title": "分析用户意图",
    "content": "用户想查看本月的销售数据，需要调用销售统计工具",
    "type": "reasoning"
  }
}
```

**Schema:**

```typescript
interface ThinkingStepEvent {
  step: number;                          // 步骤序号
  total_steps: number | null;           // 总步骤数（可能未知）
  title: string;                        // 步骤标题
  content: string;                      // 步骤内容
  type: 'reasoning' | 'planning' | 'reflection';  // 步骤类型
}
```

### 3.9 `ask_user` — 向用户提问

Agent 需要用户提供额外信息。

```json
{
  "event": "ask_user",
  "data": {
    "question_id": "ask_01HQ...",
    "question": "请选择要查看的时间范围：",
    "options": ["本周", "本月", "本季度", "自定义"],
    "context": "sales_report",
    "allow_free_text": true
  }
}
```

**Schema:**

```typescript
interface AskUserEvent {
  question_id: string;                  // 问题 ID
  question: string;                     // 问题文本
  options: string[];                    // 选项列表
  context: string;                      // 上下文标识
  allow_free_text?: boolean;            // 是否允许自由输入
}
```

### 3.10 `quota_update` — 配额更新

```json
{
  "event": "quota_update",
  "data": {
    "tokens_used": 15000,
    "tokens_limit": 100000,
    "tokens_remaining": 85000,
    "requests": 5,
    "requests_limit": 1000,
    "cost_usd": 0.03
  }
}
```

---

## 4. 完整消息生命周期

```
Client                          Server (Agent)
  │                                │
  │  POST /api/agent/chat          │
  │  {messages, agent, session_id} │
  │───────────────────────────────>│
  │                                │
  │  SSE: status_update            │
  │  {status: "thinking"}          │
  │<───────────────────────────────│
  │                                │
  │  SSE: thinking_step            │
  │  {step: 1, title: "分析意图"}  │
  │<───────────────────────────────│
  │                                │
  │  SSE: tool_start               │
  │  {tool_name: "query_sales"}    │
  │<───────────────────────────────│
  │                                │
  │  SSE: tool_result              │
  │  {status: "success", ...}      │
  │<───────────────────────────────│
  │                                │
  │  SSE: text_delta (多次)        │
  │  {content: "根据..."}          │
  │<───────────────────────────────│
  │                                │
  │  SSE: genui_render             │
  │  {component: "StatCards",...}   │
  │<───────────────────────────────│
  │                                │
  │  SSE: text_delta               │
  │  {finish_reason: "stop"}       │
  │<───────────────────────────────│
  │                                │
  │  SSE: quota_update             │
  │  {tokens_used: 15000, ...}     │
  │<───────────────────────────────│
  │                                │
  │  Connection closed             │
  │                                │
```

---

## 5. 错误处理与重连

### 5.1 重连机制

```typescript
class AGUIClient {
  private lastEventId: string = '';
  private retryCount: number = 0;
  private maxRetries: number = 5;

  async connect(request: ChatRequest) {
    const response = await fetch('/api/agent/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'Last-Event-Id': this.lastEventId,  // 断线重连
      },
      body: JSON.stringify({
        ...request,
        resume_from: this.lastEventId || undefined,
      }),
    });

    // 处理 SSE 流
    const reader = response.body.getReader();
    // ...
  }

  private handleEvent(event: AGUIEvent) {
    this.lastEventId = event.id;
    this.retryCount = 0;  // 重置重试计数

    switch (event.event) {
      case 'text_delta':
        this.emit('text', event.data);
        break;
      case 'error':
        if (event.data.retryable) {
          this.scheduleRetry(event.data.retry_after_ms);
        }
        break;
      // ...
    }
  }

  private scheduleRetry(afterMs: number = 1000) {
    if (this.retryCount >= this.maxRetries) {
      this.emit('fatal_error', 'Max retries exceeded');
      return;
    }
    const delay = Math.min(afterMs * Math.pow(2, this.retryCount), 30000);
    this.retryCount++;
    setTimeout(() => this.connect(this.lastRequest), delay);
  }
}
```

### 5.2 错误码体系

| 错误码 | HTTP | 含义 | 可重试 |
|--------|------|------|--------|
| `AUTH_EXPIRED` | 401 | Token 过期 | 是（刷新后） |
| `RATE_LIMIT_EXCEEDED` | 429 | 请求频率超限 | 是 |
| `QUOTA_EXHAUSTED` | 429 | 日配额耗尽 | 否（次日重置） |
| `AGENT_TIMEOUT` | 504 | Agent 执行超时 | 是 |
| `TOOL_FAILED` | 200 | 工具执行失败 | 视工具而定 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 | 是 |
| `SESSION_EXPIRED` | 410 | 会话已过期 | 否 |
| `MODEL_OVERLOADED` | 503 | AI 模型过载 | 是 |

---

## 6. 与当前格式的对比

### 当前 SSE 格式（非结构化）

```
data: {"choices":[{"delta":{"content":"你好"}}]}

data: {"type":"thinking_step","title":"分析","content":"..."}

data: {"type":"genui","component":"StatCards","props":{...}}

data: {"type":"confirmation","tool_name":"delete","message":"确认？"}

data: [DONE]
```

**问题：**
- 没有统一的事件信封（envelope）
- `type` 字段混在 `data` 中，需要解析后才知道类型
- 没有事件 ID，无法重连
- 没有序列号，无法保证顺序
- `[DONE]` 是特殊标记，不是标准 SSE

### AG-UI 格式（结构化）

```
id: evt_001
event: text_delta
data: {"content":"你好","role":"assistant","finish_reason":null}

id: evt_002
event: thinking_step
data: {"step":1,"title":"分析","content":"...","type":"reasoning"}

id: evt_003
event: genui_render
data: {"component":"StatCards","props":{...}}

id: evt_004
event: confirmation_request
data: {"request_id":"cfm_01","tool_name":"delete","message":"确认？",...}

id: evt_005
event: text_delta
data: {"content":"","role":"assistant","finish_reason":"stop"}
```

**改进：**
- 使用标准 SSE `event:` 字段区分事件类型
- 每个事件有唯一 `id:`，支持 `Last-Event-Id` 重连
- 事件负载有严格 Schema，前端可做类型检查
- 结束由 `finish_reason: "stop"` 表示，不需要特殊标记

---

## 7. 迁移路径

### Phase 1：双协议并行（第 1-2 周）

后端同时支持旧格式和 AG-UI 格式：

```python
# 通过 Accept header 区分
# Accept: text/event-stream; protocol=agui → 新格式
# Accept: text/event-stream → 旧格式
```

前端新增 `useAGUIStream` hook，与 `useAIStream` 并存。

### Phase 2：前端迁移（第 3-4 周）

将所有 SSE 消费端迁移到 `useAGUIStream`：
- `useAIStream.ts` → 使用 AG-UI 事件解析
- `useAgentTrace.ts` → 消费 `thinking_step` 事件
- `GenUIContainer.tsx` → 消费 `genui_render` 事件

### Phase 3：清理旧格式（第 5-6 周）

- 移除旧格式支持
- 更新 API 文档
- 客户端 SDK 升级指引

---

## 8. TypeScript 类型定义

```typescript
// src/types/agui.ts

export type AGUIEventType =
  | 'text_delta'
  | 'tool_start'
  | 'tool_result'
  | 'genui_render'
  | 'confirmation_request'
  | 'status_update'
  | 'error'
  | 'thinking_step'
  | 'ask_user'
  | 'quota_update';

export interface AGUIEventBase {
  id: string;
  event: AGUIEventType;
  timestamp: number;
  seq: number;
}

export interface AGUITextDelta extends AGUIEventBase {
  event: 'text_delta';
  data: TextDeltaEvent;
}

export interface AGUIToolStart extends AGUIEventBase {
  event: 'tool_start';
  data: ToolStartEvent;
}

export interface AGUIToolResult extends AGUIEventBase {
  event: 'tool_result';
  data: ToolResultEvent;
}

export interface AGUIGenUIRender extends AGUIEventBase {
  event: 'genui_render';
  data: GenUIRenderEvent;
}

export interface AGUIConfirmation extends AGUIEventBase {
  event: 'confirmation_request';
  data: ConfirmationRequestEvent;
}

export interface AGUIStatusUpdate extends AGUIEventBase {
  event: 'status_update';
  data: StatusUpdateEvent;
}

export interface AGUIError extends AGUIEventBase {
  event: 'error';
  data: ErrorEvent;
}

export interface AGUIThinkingStep extends AGUIEventBase {
  event: 'thinking_step';
  data: ThinkingStepEvent;
}

export type AGUIEvent =
  | AGUITextDelta
  | AGUIToolStart
  | AGUIToolResult
  | AGUIGenUIRender
  | AGUIConfirmation
  | AGUIStatusUpdate
  | AGUIError
  | AGUIThinkingStep;
```
