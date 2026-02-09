/**
 * OpenClaw / MoltBot Agent Context
 * 智能体上下文 - 提供全局智能体访问
 */

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useMemo,
  ReactNode,
} from 'react';
import {
  agentRegistry,
  initializeAgentSystem,
  getOrCreateAgent,
  OpenClawAgent,
  AgentConfig,
  AgentEvent,
  AgentEventType,
  Tool,
} from '@/services/agents';

// ==================== 类型定义 ====================

interface AgentContextValue {
  // 状态
  isInitialized: boolean;
  isInitializing: boolean;
  error: string | null;
  
  // 智能体管理
  availableAgents: AgentConfig[];
  getAgent: (agentId: string) => OpenClawAgent | null;
  getAgentConfig: (agentId: string) => AgentConfig | undefined;
  
  // 工具管理
  availableTools: string[];
  registerTool: (tool: Tool) => void;
  
  // 事件
  onEvent: (eventType: AgentEventType, listener: (event: AgentEvent) => void) => () => void;
  
  // 重新初始化
  reinitialize: () => Promise<void>;
}

interface AgentProviderProps {
  children: ReactNode;
  autoInit?: boolean;
  customTools?: Tool[];
  customAgentConfigs?: AgentConfig[];
  onInitialized?: () => void;
  onError?: (error: Error) => void;
}

// ==================== Context ====================

const AgentContext = createContext<AgentContextValue | undefined>(undefined);

// ==================== Provider ====================

export function AgentProvider({
  children,
  autoInit = true,
  customTools = [],
  customAgentConfigs = [],
  onInitialized,
  onError,
}: AgentProviderProps) {
  const [isInitialized, setIsInitialized] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableAgents, setAvailableAgents] = useState<AgentConfig[]>([]);
  const [availableTools, setAvailableTools] = useState<string[]>([]);

  // 初始化智能体系统
  const initialize = useCallback(async () => {
    if (isInitializing) return;

    setIsInitializing(true);
    setError(null);

    try {
      await initializeAgentSystem({
        registerBuiltInTools: true,
        registerPresetAgents: true,
        customTools,
        customAgentConfigs,
      });

      // 更新状态
      setAvailableAgents(agentRegistry.getAllAgentConfigs());
      setAvailableTools(agentRegistry.getToolNames());
      setIsInitialized(true);
      
      onInitialized?.();
      console.log('[AgentContext] Initialized successfully');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      onError?.(err instanceof Error ? err : new Error(errorMessage));
      console.error('[AgentContext] Initialization failed:', err);
    } finally {
      setIsInitializing(false);
    }
  }, [customTools, customAgentConfigs, onInitialized, onError, isInitializing]);

  // 自动初始化
  useEffect(() => {
    if (autoInit && !isInitialized && !isInitializing) {
      initialize();
    }
  }, [autoInit, isInitialized, isInitializing, initialize]);

  // 获取智能体
  const getAgent = useCallback((agentId: string): OpenClawAgent | null => {
    if (!isInitialized) {
      console.warn('[AgentContext] System not initialized');
      return null;
    }
    return getOrCreateAgent(agentId);
  }, [isInitialized]);

  // 获取智能体配置
  const getAgentConfig = useCallback((agentId: string): AgentConfig | undefined => {
    return agentRegistry.getAgentConfig(agentId);
  }, []);

  // 注册工具
  const registerTool = useCallback((tool: Tool) => {
    agentRegistry.registerTool(tool);
    setAvailableTools(agentRegistry.getToolNames());
  }, []);

  // 事件订阅
  const onEvent = useCallback(
    (eventType: AgentEventType, listener: (event: AgentEvent) => void): (() => void) => {
      return agentRegistry.on(eventType, listener);
    },
    []
  );

  // 重新初始化
  const reinitialize = useCallback(async () => {
    agentRegistry.reset();
    setIsInitialized(false);
    await initialize();
  }, [initialize]);

  // Context value
  const value = useMemo<AgentContextValue>(
    () => ({
      isInitialized,
      isInitializing,
      error,
      availableAgents,
      getAgent,
      getAgentConfig,
      availableTools,
      registerTool,
      onEvent,
      reinitialize,
    }),
    [
      isInitialized,
      isInitializing,
      error,
      availableAgents,
      getAgent,
      getAgentConfig,
      availableTools,
      registerTool,
      onEvent,
      reinitialize,
    ]
  );

  return (
    <AgentContext.Provider value={value}>
      {children}
    </AgentContext.Provider>
  );
}

// ==================== Hook ====================

export function useAgentContext(): AgentContextValue {
  const context = useContext(AgentContext);
  if (!context) {
    throw new Error('useAgentContext must be used within AgentProvider');
  }
  return context;
}

/**
 * 便捷 Hook: 使用特定智能体
 */
export function useAgentInstance(agentId: string) {
  const { isInitialized, getAgent, getAgentConfig } = useAgentContext();
  const [agent, setAgent] = useState<OpenClawAgent | null>(null);

  useEffect(() => {
    if (isInitialized) {
      const instance = getAgent(agentId);
      setAgent(instance);
    }
  }, [isInitialized, agentId, getAgent]);

  return {
    agent,
    config: getAgentConfig(agentId),
    isReady: !!agent,
  };
}

/**
 * 便捷 Hook: 监听智能体事件
 */
export function useAgentEvents(
  eventTypes: AgentEventType[],
  callback: (event: AgentEvent) => void
) {
  const { onEvent } = useAgentContext();

  useEffect(() => {
    const unsubscribers = eventTypes.map((type) => onEvent(type, callback));
    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  }, [eventTypes, callback, onEvent]);
}

export default AgentProvider;