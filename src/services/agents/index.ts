/**
 * OpenClaw / MoltBot Agent System
 * 智能体系统入口 - 统一导出和初始化
 */

// ==================== 类型导出 ====================
export * from './types';

// ==================== 核心模块导出 ====================
export { agentRegistry, default as AgentRegistry } from './AgentRegistry';
export { BaseAgent } from './BaseAgent';
export { OpenClawAgent } from './OpenClawAgent';

// ==================== 工具导出 ====================
export { builtInTools } from './tools';
export * from './tools';

// ==================== 预设导出 ====================
export {
  agentPresets,
  agentPresetsMap,
  salesCommanderConfig,
  performanceCoachConfig,
  enterpriseAssistantConfig,
  knowledgeAssistantConfig,
  executiveAssistantConfig,
  workflowOrchestratorConfig,
} from './presets';

// ==================== 初始化函数 ====================

import { agentRegistry } from './AgentRegistry';
import { builtInTools } from './tools';
import { agentPresets } from './presets';
import { OpenClawAgent } from './OpenClawAgent';
import { AgentConfig } from './types';

/**
 * 初始化智能体系统
 * 注册内置工具和预设智能体
 */
export async function initializeAgentSystem(options?: {
  registerBuiltInTools?: boolean;
  registerPresetAgents?: boolean;
  customTools?: typeof builtInTools;
  customAgentConfigs?: AgentConfig[];
}): Promise<void> {
  const {
    registerBuiltInTools = true,
    registerPresetAgents = true,
    customTools = [],
    customAgentConfigs = [],
  } = options || {};

  console.log('[AgentSystem] Initializing...');

  // 注册内置工具
  if (registerBuiltInTools) {
    console.log(`[AgentSystem] Registering ${builtInTools.length} built-in tools`);
    agentRegistry.registerTools(builtInTools);
  }

  // 注册自定义工具
  if (customTools.length > 0) {
    console.log(`[AgentSystem] Registering ${customTools.length} custom tools`);
    agentRegistry.registerTools(customTools);
  }

  // 注册预设智能体配置
  if (registerPresetAgents) {
    console.log(`[AgentSystem] Registering ${agentPresets.length} preset agents`);
    agentPresets.forEach((config) => {
      agentRegistry.registerAgentConfig(config);
    });
  }

  // 注册自定义智能体配置
  if (customAgentConfigs.length > 0) {
    console.log(`[AgentSystem] Registering ${customAgentConfigs.length} custom agents`);
    customAgentConfigs.forEach((config) => {
      agentRegistry.registerAgentConfig(config);
    });
  }

  console.log('[AgentSystem] Initialization complete');
}

/**
 * 创建智能体实例
 */
export function createAgent(agentId: string): OpenClawAgent | null {
  const config = agentRegistry.getAgentConfig(agentId);
  if (!config) {
    console.error(`[AgentSystem] Agent config not found: ${agentId}`);
    return null;
  }

  const agent = new OpenClawAgent(config);
  agentRegistry.registerAgent(agent);
  return agent;
}

/**
 * 获取或创建智能体实例
 */
export function getOrCreateAgent(agentId: string): OpenClawAgent | null {
  const existing = agentRegistry.getAgent(agentId);
  if (existing) {
    return existing as OpenClawAgent;
  }
  return createAgent(agentId);
}

/**
 * 快速对话接口
 */
export async function chat(
  agentId: string,
  message: string,
  options?: {
    sessionId?: string;
    userId?: string;
    stream?: boolean;
  }
): Promise<string> {
  const agent = getOrCreateAgent(agentId);
  if (!agent) {
    throw new Error(`Agent not found: ${agentId}`);
  }

  const response = await agent.chat(
    [
      {
        id: Date.now().toString(),
        role: 'user',
        content: message,
        timestamp: new Date(),
      },
    ],
    {
      sessionId: options?.sessionId,
      userId: options?.userId,
    }
  );

  return typeof response.message.content === 'string'
    ? response.message.content
    : JSON.stringify(response.message.content);
}

/**
 * 流式对话接口
 */
export async function* streamChat(
  agentId: string,
  message: string,
  options?: {
    sessionId?: string;
    userId?: string;
  }
): AsyncGenerator<string> {
  const agent = getOrCreateAgent(agentId);
  if (!agent) {
    throw new Error(`Agent not found: ${agentId}`);
  }

  const stream = agent.streamChat(
    [
      {
        id: Date.now().toString(),
        role: 'user',
        content: message,
        timestamp: new Date(),
      },
    ],
    {
      sessionId: options?.sessionId,
      userId: options?.userId,
    }
  );

  for await (const chunk of stream) {
    if (chunk.type === 'text' && chunk.content) {
      yield chunk.content;
    }
  }
}

// ==================== React Hook ====================

import { useState, useCallback, useRef, useEffect } from 'react';
import { AgentMessage, AgentStreamChunk, ChatOptions } from './types';

export interface UseAgentOptions {
  agentId: string;
  autoInit?: boolean;
}

export interface UseAgentReturn {
  isReady: boolean;
  isLoading: boolean;
  error: string | null;
  messages: AgentMessage[];
  sendMessage: (content: string, options?: ChatOptions) => Promise<void>;
  sendMessageStream: (content: string, options?: ChatOptions) => Promise<void>;
  clearMessages: () => void;
  abort: () => void;
}

/**
 * React Hook for using agents
 */
export function useAgent({ agentId, autoInit = true }: UseAgentOptions): UseAgentReturn {
  const [isReady, setIsReady] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const agentRef = useRef<OpenClawAgent | null>(null);

  // 初始化智能体
  useEffect(() => {
    if (autoInit) {
      const agent = getOrCreateAgent(agentId);
      if (agent) {
        agentRef.current = agent;
        agent.initialize().then(() => {
          setIsReady(true);
        }).catch((err) => {
          setError(err.message);
        });
      } else {
        setError(`Agent not found: ${agentId}`);
      }
    }

    return () => {
      agentRef.current?.abort();
    };
  }, [agentId, autoInit]);

  // 发送消息（非流式）
  const sendMessage = useCallback(async (content: string, options?: ChatOptions) => {
    if (!agentRef.current) {
      setError('Agent not initialized');
      return;
    }

    const userMessage: AgentMessage = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    try {
      const response = await agentRef.current.chat([...messages, userMessage], options);
      setMessages((prev) => [...prev, response.message]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [messages]);

  // 发送消息（流式）
  const sendMessageStream = useCallback(async (content: string, options?: ChatOptions) => {
    if (!agentRef.current) {
      setError('Agent not initialized');
      return;
    }

    const userMessage: AgentMessage = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    };

    const assistantMessageId = (Date.now() + 1).toString();
    const assistantMessage: AgentMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      agentId,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsLoading(true);
    setError(null);

    try {
      const stream = agentRef.current.streamChat([...messages, userMessage], options);
      
      for await (const chunk of stream) {
        if (chunk.type === 'text' && chunk.content) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: (msg.content as string) + chunk.content }
                : msg
            )
          );
        }

        if (chunk.type === 'error') {
          setError(chunk.error || 'Unknown error');
        }
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [messages, agentId]);

  // 清除消息
  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  // 中止
  const abort = useCallback(() => {
    agentRef.current?.abort();
    setIsLoading(false);
  }, []);

  return {
    isReady,
    isLoading,
    error,
    messages,
    sendMessage,
    sendMessageStream,
    clearMessages,
    abort,
  };
}

export default {
  initializeAgentSystem,
  createAgent,
  getOrCreateAgent,
  chat,
  streamChat,
  useAgent,
  agentRegistry,
};