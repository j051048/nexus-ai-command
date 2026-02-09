/**
 * OpenClaw / MoltBot Agent Interface Types
 * 智能体接口类型定义
 * 
 * 这是一个通用的智能体框架，支持：
 * - 多种 LLM 后端（OpenAI, Anthropic, 本地模型等）
 * - 工具调用（Function Calling）
 * - 多智能体协作
 * - 事件驱动架构
 * - 状态管理
 */

// ==================== 基础类型 ====================

/**
 * 智能体状态
 */
export type AgentStatus = 
  | 'idle'          // 空闲
  | 'thinking'      // 思考中
  | 'executing'     // 执行工具
  | 'waiting'       // 等待输入
  | 'error'         // 错误状态
  | 'offline';      // 离线

/**
 * 消息角色
 */
export type MessageRole = 'system' | 'user' | 'assistant' | 'tool' | 'function';

/**
 * 智能体能力
 */
export type AgentCapability = 
  | 'chat'              // 对话
  | 'tool_use'          // 工具调用
  | 'code_execution'    // 代码执行
  | 'file_access'       // 文件访问
  | 'web_search'        // 网络搜索
  | 'data_analysis'     // 数据分析
  | 'image_generation'  // 图像生成
  | 'image_analysis'    // 图像分析
  | 'audio_processing'  // 音频处理
  | 'workflow'          // 工作流编排
  | 'memory'            // 长期记忆
  | 'planning';         // 任务规划

/**
 * 优先级
 */
export type Priority = 'low' | 'normal' | 'high' | 'urgent';

// ==================== 消息类型 ====================

/**
 * 消息内容块
 */
export interface ContentBlock {
  type: 'text' | 'image' | 'file' | 'code' | 'tool_call' | 'tool_result';
  text?: string;
  imageUrl?: string;
  fileUrl?: string;
  fileName?: string;
  mimeType?: string;
  language?: string;
  code?: string;
  toolCallId?: string;
  toolName?: string;
  toolInput?: Record<string, unknown>;
  toolOutput?: unknown;
}

/**
 * 智能体消息
 */
export interface AgentMessage {
  id: string;
  role: MessageRole;
  content: string | ContentBlock[];
  name?: string;              // 发送者名称
  agentId?: string;           // 智能体ID
  toolCalls?: ToolCall[];     // 工具调用
  metadata?: Record<string, unknown>;
  timestamp: Date;
}

/**
 * 工具调用
 */
export interface ToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string;  // JSON string
  };
}

/**
 * 工具调用结果
 */
export interface ToolResult {
  toolCallId: string;
  content: string | unknown;
  isError?: boolean;
}

// ==================== 工具定义 ====================

/**
 * 工具参数定义（JSON Schema）
 */
export interface ToolParameter {
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  description?: string;
  enum?: string[];
  items?: ToolParameter;         // for array
  properties?: Record<string, ToolParameter>;  // for object
  required?: string[];           // for object
  default?: unknown;
}

/**
 * 工具定义
 */
export interface ToolDefinition {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, ToolParameter>;
    required?: string[];
  };
  returns?: ToolParameter;
  examples?: Array<{
    input: Record<string, unknown>;
    output: unknown;
  }>;
}

/**
 * 工具实现
 */
export interface Tool extends ToolDefinition {
  execute: (params: Record<string, unknown>, context: ToolContext) => Promise<unknown>;
  validate?: (params: Record<string, unknown>) => boolean | string;
  permissions?: string[];  // 所需权限
}

/**
 * 工具执行上下文
 */
export interface ToolContext {
  agentId: string;
  userId: string;
  sessionId: string;
  conversationId?: string;
  metadata?: Record<string, unknown>;
  abortSignal?: AbortSignal;
}

// ==================== 智能体定义 ====================

/**
 * 智能体配置
 */
export interface AgentConfig {
  id: string;
  name: string;
  description: string;
  avatar?: string;
  color?: string;
  
  // 模型配置
  model: {
    provider: 'openai' | 'anthropic' | 'local' | 'custom';
    name: string;           // e.g., 'gpt-4', 'claude-3-opus'
    endpoint?: string;      // 自定义端点
    apiKey?: string;        // API密钥（通常从环境变量获取）
    temperature?: number;
    maxTokens?: number;
    topP?: number;
  };
  
  // 系统提示词
  systemPrompt: string;
  
  // 能力
  capabilities: AgentCapability[];
  
  // 工具
  tools?: string[];  // 工具名称列表
  
  // 权限
  permissions?: string[];
  
  // 限制
  limits?: {
    maxTurns?: number;          // 最大对话轮数
    maxTokensPerTurn?: number;  // 每轮最大token
    maxToolCalls?: number;      // 最大工具调用次数
    timeout?: number;           // 超时时间(ms)
  };
  
  // 元数据
  metadata?: Record<string, unknown>;
}

/**
 * 智能体实例
 */
export interface Agent {
  config: AgentConfig;
  status: AgentStatus;
  
  // 生命周期
  initialize: () => Promise<void>;
  shutdown: () => Promise<void>;
  
  // 核心方法
  chat: (messages: AgentMessage[], options?: ChatOptions) => Promise<AgentResponse>;
  streamChat: (messages: AgentMessage[], options?: ChatOptions) => AsyncGenerator<AgentStreamChunk>;
  
  // 工具管理
  registerTool: (tool: Tool) => void;
  unregisterTool: (toolName: string) => void;
  getTools: () => Tool[];
  
  // 状态
  getStatus: () => AgentStatus;
  getMetrics: () => AgentMetrics;
}

/**
 * 对话选项
 */
export interface ChatOptions {
  sessionId?: string;
  conversationId?: string;
  userId?: string;
  temperature?: number;
  maxTokens?: number;
  tools?: string[];           // 本次对话可用的工具
  toolChoice?: 'auto' | 'none' | 'required' | { name: string };
  responseFormat?: 'text' | 'json';
  metadata?: Record<string, unknown>;
  abortSignal?: AbortSignal;
}

/**
 * 智能体响应
 */
export interface AgentResponse {
  id: string;
  agentId: string;
  message: AgentMessage;
  toolCalls?: ToolCall[];
  toolResults?: ToolResult[];
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
  finishReason: 'stop' | 'tool_calls' | 'length' | 'content_filter' | 'error';
  metadata?: Record<string, unknown>;
}

/**
 * 流式响应块
 */
export interface AgentStreamChunk {
  type: 'text' | 'tool_call' | 'tool_result' | 'error' | 'done';
  content?: string;
  toolCall?: Partial<ToolCall>;
  toolResult?: ToolResult;
  error?: string;
  usage?: AgentResponse['usage'];
  finishReason?: AgentResponse['finishReason'];
}

/**
 * 智能体指标
 */
export interface AgentMetrics {
  totalRequests: number;
  successfulRequests: number;
  failedRequests: number;
  averageResponseTime: number;
  totalTokensUsed: number;
  toolCallsCount: number;
  lastActiveAt?: Date;
}

// ==================== 事件系统 ====================

/**
 * 事件类型
 */
export type AgentEventType =
  | 'agent:initialized'
  | 'agent:shutdown'
  | 'agent:status_changed'
  | 'agent:error'
  | 'chat:started'
  | 'chat:message'
  | 'chat:completed'
  | 'chat:error'
  | 'tool:calling'
  | 'tool:completed'
  | 'tool:error'
  | 'workflow:started'
  | 'workflow:step'
  | 'workflow:completed'
  | 'workflow:error';

/**
 * 事件数据
 */
export interface AgentEvent<T = unknown> {
  type: AgentEventType;
  agentId: string;
  timestamp: Date;
  data: T;
  metadata?: Record<string, unknown>;
}

/**
 * 事件监听器
 */
export type AgentEventListener<T = unknown> = (event: AgentEvent<T>) => void | Promise<void>;

// ==================== 工作流 ====================

/**
 * 工作流步骤
 */
export interface WorkflowStep {
  id: string;
  name: string;
  type: 'agent' | 'tool' | 'condition' | 'parallel' | 'loop';
  config: {
    agentId?: string;           // for agent step
    toolName?: string;          // for tool step
    prompt?: string;            // 提示词模板
    condition?: string;         // for condition step
    steps?: WorkflowStep[];     // for parallel/loop
    maxIterations?: number;     // for loop
  };
  inputs?: Record<string, string>;   // 输入映射
  outputs?: Record<string, string>;  // 输出映射
  onError?: 'fail' | 'skip' | 'retry';
  retryConfig?: {
    maxRetries: number;
    delay: number;
  };
}

/**
 * 工作流定义
 */
export interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  trigger?: {
    type: 'manual' | 'schedule' | 'event' | 'webhook';
    config?: Record<string, unknown>;
  };
  inputs?: Record<string, ToolParameter>;
  steps: WorkflowStep[];
  outputs?: Record<string, string>;
}

/**
 * 工作流执行上下文
 */
export interface WorkflowContext {
  workflowId: string;
  executionId: string;
  userId: string;
  inputs: Record<string, unknown>;
  state: Record<string, unknown>;
  history: Array<{
    stepId: string;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
    result?: unknown;
    error?: string;
    startedAt?: Date;
    completedAt?: Date;
  }>;
}

// ==================== 会话和记忆 ====================

/**
 * 会话
 */
export interface AgentSession {
  id: string;
  agentId: string;
  userId: string;
  messages: AgentMessage[];
  context: Record<string, unknown>;
  createdAt: Date;
  updatedAt: Date;
  expiresAt?: Date;
}

/**
 * 记忆条目
 */
export interface MemoryEntry {
  id: string;
  agentId: string;
  userId?: string;
  type: 'fact' | 'preference' | 'instruction' | 'summary';
  content: string;
  embedding?: number[];
  metadata?: Record<string, unknown>;
  importance: number;  // 0-1
  createdAt: Date;
  accessedAt: Date;
  accessCount: number;
}

export default {
  // 导出所有类型以便外部使用
};