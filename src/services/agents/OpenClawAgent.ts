/**
 * OpenClaw / MoltBot Agent Implementation
 * OpenClaw 智能体实现 - 支持多种 LLM 后端
 */

import {
  AgentConfig,
  AgentMessage,
  AgentResponse,
  AgentStreamChunk,
  ChatOptions,
  ToolCall,
} from './types';
import { BaseAgent } from './BaseAgent';
import { agentRegistry } from './AgentRegistry';

/**
 * OpenClaw 智能体
 * 支持 OpenAI、Anthropic 等多种后端
 */
export class OpenClawAgent extends BaseAgent {
  private apiEndpoint: string;
  private apiKey: string;

  constructor(config: AgentConfig) {
    super(config);
    this.apiEndpoint = this.resolveEndpoint();
    this.apiKey = config.model.apiKey || this.getEnvApiKey();
  }

  /**
   * 解析 API 端点
   */
  private resolveEndpoint(): string {
    if (this.config.model.endpoint) {
      return this.config.model.endpoint;
    }

    switch (this.config.model.provider) {
      case 'openai':
        return 'https://api.openai.com/v1/chat/completions';
      case 'anthropic':
        return 'https://api.anthropic.com/v1/messages';
      case 'local':
        return 'http://localhost:11434/api/chat'; // Ollama default
      default:
        return import.meta.env.VITE_API_BASE_URL || 'https://aizhz.zeabur.app/api/chat';
    }
  }

  /**
   * 从环境变量获取 API Key
   */
  private getEnvApiKey(): string {
    switch (this.config.model.provider) {
      case 'openai':
        return import.meta.env.VITE_OPENAI_API_KEY || '';
      case 'anthropic':
        return import.meta.env.VITE_ANTHROPIC_API_KEY || '';
      default:
        return '';
    }
  }

  /**
   * 转换消息格式为 OpenAI 格式
   */
  private formatMessagesForOpenAI(messages: AgentMessage[]): Array<{
    role: string;
    content: string;
    name?: string;
    /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
    tool_calls?: any[];
    tool_call_id?: string;
  }> {
    return messages.map((msg) => {
      /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
      const formatted: any = {
        role: msg.role,
        content: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content),
      };

      if (msg.name) {
        formatted.name = msg.name;
      }

      if (msg.toolCalls) {
        formatted.tool_calls = msg.toolCalls;
      }

      return formatted;
    });
  }

  /**
   * 非流式对话
   */
  public async chat(
    messages: AgentMessage[],
    options: ChatOptions = {}
  ): Promise<AgentResponse> {
    const startTime = Date.now();
    this.setStatus('thinking');
    this.createAbortController();

    agentRegistry.emit({
      type: 'chat:started',
      agentId: this.config.id,
      timestamp: new Date(),
      data: { messageCount: messages.length },
    });

    try {
      const fullMessages = this.buildMessages(messages);
      const formattedMessages = this.formatMessagesForOpenAI(fullMessages);

      // 获取可用工具
      const tools = options.tools
        ? options.tools.map((name) => this.tools.get(name)).filter(Boolean)
        : this.getTools();

      /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
      const requestBody: any = {
        model: this.config.model.name,
        messages: formattedMessages,
        temperature: options.temperature ?? this.config.model.temperature ?? 0.7,
        max_tokens: options.maxTokens ?? this.config.model.maxTokens ?? 4096,
      };

      // 添加工具定义
      if (tools.length > 0 && options.toolChoice !== 'none') {
        requestBody.tools = tools.map((tool) => ({
          type: 'function',
          function: {
            name: tool!.name,
            description: tool!.description,
            parameters: tool!.parameters,
          },
        }));

        if (options.toolChoice && options.toolChoice !== 'auto') {
          requestBody.tool_choice = options.toolChoice;
        }
      }

      if (options.responseFormat === 'json') {
        requestBody.response_format = { type: 'json_object' };
      }

      const response = await fetch(this.apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.apiKey && { Authorization: `Bearer ${this.apiKey}` }),
        },
        body: JSON.stringify(requestBody),
        signal: this.abortController?.signal,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error?.message || `API Error: ${response.status}`);
      }

      const data = await response.json();
      const choice = data.choices?.[0];

      if (!choice) {
        throw new Error('No response from API');
      }

      // 处理工具调用
      let toolCalls: ToolCall[] | undefined;
      /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
      let toolResults: any[] | undefined;

      if (choice.message?.tool_calls) {
        this.setStatus('executing');
        toolCalls = choice.message.tool_calls;
        toolResults = await this.executeToolCalls(toolCalls, options);
      }

      const responseTime = Date.now() - startTime;
      const tokensUsed = data.usage?.total_tokens || 0;
      this.updateMetrics(responseTime, tokensUsed, true);

      const agentResponse: AgentResponse = {
        id: data.id || this.generateId(),
        agentId: this.config.id,
        message: {
          id: this.generateId(),
          role: 'assistant',
          content: choice.message?.content || '',
          agentId: this.config.id,
          toolCalls,
          timestamp: new Date(),
        },
        toolCalls,
        toolResults,
        usage: data.usage && {
          promptTokens: data.usage.prompt_tokens,
          completionTokens: data.usage.completion_tokens,
          totalTokens: data.usage.total_tokens,
        },
        finishReason: this.mapFinishReason(choice.finish_reason),
      };

      this.setStatus('idle');

      agentRegistry.emit({
        type: 'chat:completed',
        agentId: this.config.id,
        timestamp: new Date(),
        data: { response: agentResponse },
      });

      return agentResponse;
    } catch (error) {
      const responseTime = Date.now() - startTime;
      this.updateMetrics(responseTime, 0, false);
      this.setStatus('error');

      agentRegistry.emit({
        type: 'chat:error',
        agentId: this.config.id,
        timestamp: new Date(),
        data: { error: (error as Error).message },
      });

      throw error;
    }
  }

  /**
   * 流式对话
   */
  public async *streamChat(
    messages: AgentMessage[],
    options: ChatOptions = {}
  ): AsyncGenerator<AgentStreamChunk> {
    const startTime = Date.now();
    this.setStatus('thinking');
    this.createAbortController();

    agentRegistry.emit({
      type: 'chat:started',
      agentId: this.config.id,
      timestamp: new Date(),
      data: { messageCount: messages.length, streaming: true },
    });

    try {
      const fullMessages = this.buildMessages(messages);
      const formattedMessages = this.formatMessagesForOpenAI(fullMessages);

      const tools = options.tools
        ? options.tools.map((name) => this.tools.get(name)).filter(Boolean)
        : this.getTools();

      /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
      const requestBody: any = {
        model: this.config.model.name,
        messages: formattedMessages,
        temperature: options.temperature ?? this.config.model.temperature ?? 0.7,
        max_tokens: options.maxTokens ?? this.config.model.maxTokens ?? 4096,
        stream: true,
      };

      if (tools.length > 0 && options.toolChoice !== 'none') {
        requestBody.tools = tools.map((tool) => ({
          type: 'function',
          function: {
            name: tool!.name,
            description: tool!.description,
            parameters: tool!.parameters,
          },
        }));
      }

      const response = await fetch(this.apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.apiKey && { Authorization: `Bearer ${this.apiKey}` }),
        },
        body: JSON.stringify(requestBody),
        signal: this.abortController?.signal,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error?.message || `API Error: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      const toolCallsInProgress: Map<number, Partial<ToolCall>> = new Map();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed === 'data: [DONE]') continue;
          if (!trimmed.startsWith('data: ')) continue;

          try {
            const json = JSON.parse(trimmed.slice(6));
            const delta = json.choices?.[0]?.delta;
            const finishReason = json.choices?.[0]?.finish_reason;

            if (delta?.content) {
              yield { type: 'text', content: delta.content };
            }

            // 处理工具调用
            if (delta?.tool_calls) {
              for (const tc of delta.tool_calls) {
                const index = tc.index ?? 0;
                if (!toolCallsInProgress.has(index)) {
                  toolCallsInProgress.set(index, {
                    id: tc.id,
                    type: 'function',
                    function: { name: '', arguments: '' },
                  });
                }

                const current = toolCallsInProgress.get(index)!;
                if (tc.id) current.id = tc.id;
                if (tc.function?.name) current.function!.name = tc.function.name;
                if (tc.function?.arguments) {
                  current.function!.arguments += tc.function.arguments;
                }

                yield { type: 'tool_call', toolCall: current };
              }
            }

            if (finishReason === 'tool_calls') {
              this.setStatus('executing');
              // 执行所有工具调用
              const completedCalls = Array.from(toolCallsInProgress.values()) as ToolCall[];
              const results = await this.executeToolCalls(completedCalls, options);
              
              for (const result of results) {
                yield { type: 'tool_result', toolResult: result };
              }
            }

            if (finishReason) {
              yield {
                type: 'done',
                finishReason: this.mapFinishReason(finishReason),
                usage: json.usage && {
                  promptTokens: json.usage.prompt_tokens,
                  completionTokens: json.usage.completion_tokens,
                  totalTokens: json.usage.total_tokens,
                },
              };
            }
          } catch (e) {
            // 忽略解析错误，继续处理
          }
        }
      }

      const responseTime = Date.now() - startTime;
      this.updateMetrics(responseTime, 0, true);
      this.setStatus('idle');

      agentRegistry.emit({
        type: 'chat:completed',
        agentId: this.config.id,
        timestamp: new Date(),
        data: { streaming: true },
      });
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        yield { type: 'done', finishReason: 'stop' };
        return;
      }

      this.setStatus('error');
      yield { type: 'error', error: (error as Error).message };

      agentRegistry.emit({
        type: 'chat:error',
        agentId: this.config.id,
        timestamp: new Date(),
        data: { error: (error as Error).message },
      });

      throw error;
    }
  }

  /**
   * 映射完成原因
   */
  private mapFinishReason(
    reason: string
  ): AgentResponse['finishReason'] {
    switch (reason) {
      case 'stop':
        return 'stop';
      case 'tool_calls':
      case 'function_call':
        return 'tool_calls';
      case 'length':
        return 'length';
      case 'content_filter':
        return 'content_filter';
      default:
        return 'stop';
    }
  }
}

export default OpenClawAgent;