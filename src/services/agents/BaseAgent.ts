/**
 * OpenClaw / MoltBot Base Agent Implementation
 * 基础智能体实现 - 提供通用的智能体功能
 */

import {
  Agent,
  AgentConfig,
  AgentStatus,
  AgentMessage,
  AgentResponse,
  AgentStreamChunk,
  AgentMetrics,
  ChatOptions,
  Tool,
  ToolCall,
  ToolResult,
  ToolContext,
} from './types';
import { agentRegistry } from './AgentRegistry';

export abstract class BaseAgent implements Agent {
  public config: AgentConfig;
  protected _status: AgentStatus = 'idle';
  protected _metrics: AgentMetrics;
  protected tools: Map<string, Tool> = new Map();
  protected abortController: AbortController | null = null;

  constructor(config: AgentConfig) {
    this.config = config;
    this._metrics = {
      totalRequests: 0,
      successfulRequests: 0,
      failedRequests: 0,
      averageResponseTime: 0,
      totalTokensUsed: 0,
      toolCallsCount: 0,
    };

    // 从注册表加载工具
    if (config.tools) {
      config.tools.forEach((toolName) => {
        const tool = agentRegistry.getTool(toolName);
        if (tool) {
          this.tools.set(toolName, tool);
        }
      });
    }
  }

  // ==================== 生命周期 ====================

  public async initialize(): Promise<void> {
    this._status = 'idle';
    agentRegistry.emit({
      type: 'agent:initialized',
      agentId: this.config.id,
      timestamp: new Date(),
      data: { config: this.config },
    });
  }

  public async shutdown(): Promise<void> {
    this.abort();
    this._status = 'offline';
    agentRegistry.emit({
      type: 'agent:shutdown',
      agentId: this.config.id,
      timestamp: new Date(),
      data: {},
    });
  }

  // ==================== 状态管理 ====================

  public getStatus(): AgentStatus {
    return this._status;
  }

  protected setStatus(status: AgentStatus): void {
    const oldStatus = this._status;
    this._status = status;
    if (oldStatus !== status) {
      agentRegistry.emit({
        type: 'agent:status_changed',
        agentId: this.config.id,
        timestamp: new Date(),
        data: { oldStatus, newStatus: status },
      });
    }
  }

  public getMetrics(): AgentMetrics {
    return { ...this._metrics };
  }

  // ==================== 工具管理 ====================

  public registerTool(tool: Tool): void {
    this.tools.set(tool.name, tool);
  }

  public unregisterTool(toolName: string): void {
    this.tools.delete(toolName);
  }

  public getTools(): Tool[] {
    return Array.from(this.tools.values());
  }

  public getToolDefinitions(): Array<{
    type: 'function';
    function: {
      name: string;
      description: string;
      parameters: Tool['parameters'];
    };
  }> {
    return this.getTools().map((tool) => ({
      type: 'function' as const,
      function: {
        name: tool.name,
        description: tool.description,
        parameters: tool.parameters,
      },
    }));
  }

  // ==================== 工具执行 ====================

  protected async executeTool(
    toolCall: ToolCall,
    context: ToolContext
  ): Promise<ToolResult> {
    const tool = this.tools.get(toolCall.function.name);
    
    if (!tool) {
      return {
        toolCallId: toolCall.id,
        content: `Error: Tool '${toolCall.function.name}' not found`,
        isError: true,
      };
    }

    agentRegistry.emit({
      type: 'tool:calling',
      agentId: this.config.id,
      timestamp: new Date(),
      data: { toolName: toolCall.function.name, toolCallId: toolCall.id },
    });

    try {
      const params = JSON.parse(toolCall.function.arguments);
      
      // 验证参数
      if (tool.validate) {
        const validationResult = tool.validate(params);
        if (validationResult !== true) {
          const errorMsg = typeof validationResult === 'string' 
            ? validationResult 
            : 'Parameter validation failed';
          return {
            toolCallId: toolCall.id,
            content: `Validation Error: ${errorMsg}`,
            isError: true,
          };
        }
      }

      // 执行工具
      const result = await tool.execute(params, context);
      this._metrics.toolCallsCount++;

      agentRegistry.emit({
        type: 'tool:completed',
        agentId: this.config.id,
        timestamp: new Date(),
        data: { toolName: toolCall.function.name, toolCallId: toolCall.id, result },
      });

      return {
        toolCallId: toolCall.id,
        content: typeof result === 'string' ? result : JSON.stringify(result),
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      agentRegistry.emit({
        type: 'tool:error',
        agentId: this.config.id,
        timestamp: new Date(),
        data: { toolName: toolCall.function.name, toolCallId: toolCall.id, error: errorMessage },
      });

      return {
        toolCallId: toolCall.id,
        content: `Error: ${errorMessage}`,
        isError: true,
      };
    }
  }

  protected async executeToolCalls(
    toolCalls: ToolCall[],
    options: ChatOptions
  ): Promise<ToolResult[]> {
    const context: ToolContext = {
      agentId: this.config.id,
      userId: options.userId || 'anonymous',
      sessionId: options.sessionId || 'default',
      conversationId: options.conversationId,
      metadata: options.metadata,
      abortSignal: this.abortController?.signal,
    };

    // 并行执行所有工具调用
    const results = await Promise.all(
      toolCalls.map((call) => this.executeTool(call, context))
    );

    return results;
  }

  // ==================== 中止控制 ====================

  protected createAbortController(): AbortController {
    this.abortController = new AbortController();
    return this.abortController;
  }

  public abort(): void {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  // ==================== 抽象方法 ====================

  /**
   * 执行对话（由子类实现）
   */
  public abstract chat(
    messages: AgentMessage[],
    options?: ChatOptions
  ): Promise<AgentResponse>;

  /**
   * 流式对话（由子类实现）
   */
  public abstract streamChat(
    messages: AgentMessage[],
    options?: ChatOptions
  ): AsyncGenerator<AgentStreamChunk>;

  // ==================== 辅助方法 ====================

  /**
   * 构建完整的消息列表（包含系统提示）
   */
  protected buildMessages(messages: AgentMessage[]): AgentMessage[] {
    const systemMessage: AgentMessage = {
      id: 'system',
      role: 'system',
      content: this.config.systemPrompt,
      timestamp: new Date(),
    };
    return [systemMessage, ...messages];
  }

  /**
   * 更新指标
   */
  protected updateMetrics(
    responseTime: number,
    tokensUsed: number,
    success: boolean
  ): void {
    this._metrics.totalRequests++;
    if (success) {
      this._metrics.successfulRequests++;
    } else {
      this._metrics.failedRequests++;
    }
    this._metrics.totalTokensUsed += tokensUsed;
    this._metrics.lastActiveAt = new Date();

    // 计算移动平均响应时间
    const n = this._metrics.successfulRequests;
    this._metrics.averageResponseTime =
      (this._metrics.averageResponseTime * (n - 1) + responseTime) / n;
  }

  /**
   * 生成唯一ID
   */
  protected generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}

export default BaseAgent;