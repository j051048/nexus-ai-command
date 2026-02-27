/**
 * useAgentTrace - 从 SSE 流事件构建 Agent 执行追踪数据
 * 解析 thinking_step、tool_call、tool_result 等事件，
 * 供 AgentTracePanel 展示 Agent 的思考过程和工具调用链。
 */

import { useState, useCallback } from 'react';
import type { ThinkingStep } from '@/types/nexus';

export interface TraceStep {
  type: 'thinking' | 'tool_call' | 'tool_result';
  content: string;
  name?: string;
  args?: string;
  tokens?: number;
  timestamp: number;
  duration_ms?: number;
}

export interface AgentTrace {
  steps: TraceStep[];
  totalTokens: number;
  startTime: number | null;
  endTime: number | null;
  isActive: boolean;
}

const INITIAL_TRACE: AgentTrace = {
  steps: [],
  totalTokens: 0,
  startTime: null,
  endTime: null,
  isActive: false,
};

export function useAgentTrace() {
  const [trace, setTrace] = useState<AgentTrace>(INITIAL_TRACE);

  /** 开始新的追踪（清空之前的数据） */
  const startTrace = useCallback(() => {
    setTrace({
      steps: [],
      totalTokens: 0,
      startTime: Date.now(),
      endTime: null,
      isActive: true,
    });
  }, []);

  /** 结束追踪 */
  const endTrace = useCallback(() => {
    setTrace((prev) => ({
      ...prev,
      endTime: Date.now(),
      isActive: false,
    }));
  }, []);

  /** 清空追踪数据 */
  const clearTrace = useCallback(() => {
    setTrace(INITIAL_TRACE);
  }, []);

  /**
   * 处理来自 SSE 的 thinking_step 事件
   * 兼容 useAIStream 中的 ThinkingStep 类型
   */
  const addThinkingStep = useCallback((step: ThinkingStep) => {
    const traceStep: TraceStep = {
      type: step.tool_name ? 'tool_call' : 'thinking',
      content: step.content,
      name: step.tool_name,
      args: step.tool_args ? JSON.stringify(step.tool_args, null, 2) : undefined,
      timestamp: step.timestamp || Date.now(),
      duration_ms: step.duration_ms,
    };

    setTrace((prev) => ({
      ...prev,
      steps: [...prev.steps, traceStep],
    }));
  }, []);

  /** 添加工具执行结果 */
  const addToolResult = useCallback((toolName: string, result: string, tokens?: number) => {
    const resultStep: TraceStep = {
      type: 'tool_result',
      content: result.length > 500 ? result.slice(0, 500) + '...' : result,
      name: toolName,
      tokens,
      timestamp: Date.now(),
    };

    setTrace((prev) => ({
      ...prev,
      steps: [...prev.steps, resultStep],
      totalTokens: prev.totalTokens + (tokens || 0),
    }));
  }, []);

  /** 添加 token 用量 */
  const addTokenUsage = useCallback((tokens: number) => {
    setTrace((prev) => ({
      ...prev,
      totalTokens: prev.totalTokens + tokens,
    }));
  }, []);

  return {
    trace,
    startTrace,
    endTrace,
    clearTrace,
    addThinkingStep,
    addToolResult,
    addTokenUsage,
  };
}
