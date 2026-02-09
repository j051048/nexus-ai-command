/**
 * OpenClaw / MoltBot Agent Registry
 * 智能体注册中心 - 管理所有智能体的注册、发现和生命周期
 */

import {
  Agent,
  AgentConfig,
  AgentStatus,
  AgentEvent,
  AgentEventType,
  AgentEventListener,
  Tool,
  ToolDefinition,
} from './types';

// ==================== 智能体注册表 ====================

class AgentRegistry {
  private static instance: AgentRegistry;
  private agents: Map<string, Agent> = new Map();
  private agentConfigs: Map<string, AgentConfig> = new Map();
  private tools: Map<string, Tool> = new Map();
  private eventListeners: Map<AgentEventType, Set<AgentEventListener>> = new Map();
  private globalListeners: Set<AgentEventListener> = new Set();

  private constructor() {
    // 私有构造函数，确保单例
  }

  /**
   * 获取单例实例
   */
  public static getInstance(): AgentRegistry {
    if (!AgentRegistry.instance) {
      AgentRegistry.instance = new AgentRegistry();
    }
    return AgentRegistry.instance;
  }

  // ==================== 智能体管理 ====================

  /**
   * 注册智能体配置
   */
  public registerAgentConfig(config: AgentConfig): void {
    if (this.agentConfigs.has(config.id)) {
      console.warn(`Agent config '${config.id}' already exists, overwriting...`);
    }
    this.agentConfigs.set(config.id, config);
    this.emit({
      type: 'agent:initialized',
      agentId: config.id,
      timestamp: new Date(),
      data: { config },
    });
  }

  /**
   * 注册智能体实例
   */
  public registerAgent(agent: Agent): void {
    const id = agent.config.id;
    if (this.agents.has(id)) {
      console.warn(`Agent '${id}' already registered, replacing...`);
    }
    this.agents.set(id, agent);
    this.agentConfigs.set(id, agent.config);
  }

  /**
   * 注销智能体
   */
  public async unregisterAgent(agentId: string): Promise<void> {
    const agent = this.agents.get(agentId);
    if (agent) {
      await agent.shutdown();
      this.agents.delete(agentId);
      this.emit({
        type: 'agent:shutdown',
        agentId,
        timestamp: new Date(),
        data: {},
      });
    }
    this.agentConfigs.delete(agentId);
  }

  /**
   * 获取智能体
   */
  public getAgent(agentId: string): Agent | undefined {
    return this.agents.get(agentId);
  }

  /**
   * 获取智能体配置
   */
  public getAgentConfig(agentId: string): AgentConfig | undefined {
    return this.agentConfigs.get(agentId);
  }

  /**
   * 获取所有智能体ID
   */
  public getAgentIds(): string[] {
    return Array.from(this.agentConfigs.keys());
  }

  /**
   * 获取所有智能体配置
   */
  public getAllAgentConfigs(): AgentConfig[] {
    return Array.from(this.agentConfigs.values());
  }

  /**
   * 检查智能体是否存在
   */
  public hasAgent(agentId: string): boolean {
    return this.agentConfigs.has(agentId);
  }

  /**
   * 获取智能体状态
   */
  public getAgentStatus(agentId: string): AgentStatus {
    const agent = this.agents.get(agentId);
    return agent?.getStatus() ?? 'offline';
  }

  // ==================== 工具管理 ====================

  /**
   * 注册工具
   */
  public registerTool(tool: Tool): void {
    if (this.tools.has(tool.name)) {
      console.warn(`Tool '${tool.name}' already exists, overwriting...`);
    }
    this.tools.set(tool.name, tool);
  }

  /**
   * 批量注册工具
   */
  public registerTools(tools: Tool[]): void {
    tools.forEach((tool) => this.registerTool(tool));
  }

  /**
   * 注销工具
   */
  public unregisterTool(toolName: string): void {
    this.tools.delete(toolName);
  }

  /**
   * 获取工具
   */
  public getTool(toolName: string): Tool | undefined {
    return this.tools.get(toolName);
  }

  /**
   * 获取工具定义（不包含执行函数）
   */
  public getToolDefinition(toolName: string): ToolDefinition | undefined {
    const tool = this.tools.get(toolName);
    if (!tool) return undefined;
    
    const { execute, validate, permissions, ...definition } = tool;
    return definition;
  }

  /**
   * 获取所有工具名称
   */
  public getToolNames(): string[] {
    return Array.from(this.tools.keys());
  }

  /**
   * 获取所有工具定义
   */
  public getAllToolDefinitions(): ToolDefinition[] {
    return Array.from(this.tools.values()).map(({ execute, validate, permissions, ...def }) => def);
  }

  /**
   * 获取智能体可用的工具
   */
  public getToolsForAgent(agentId: string): Tool[] {
    const config = this.agentConfigs.get(agentId);
    if (!config?.tools) return [];
    
    return config.tools
      .map((name) => this.tools.get(name))
      .filter((tool): tool is Tool => tool !== undefined);
  }

  // ==================== 事件系统 ====================

  /**
   * 订阅事件
   */
  public on<T = unknown>(eventType: AgentEventType, listener: AgentEventListener<T>): () => void {
    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, new Set());
    }
    this.eventListeners.get(eventType)!.add(listener as AgentEventListener);
    
    // 返回取消订阅函数
    return () => this.off(eventType, listener);
  }

  /**
   * 订阅所有事件
   */
  public onAll(listener: AgentEventListener): () => void {
    this.globalListeners.add(listener);
    return () => this.globalListeners.delete(listener);
  }

  /**
   * 取消订阅事件
   */
  public off<T = unknown>(eventType: AgentEventType, listener: AgentEventListener<T>): void {
    this.eventListeners.get(eventType)?.delete(listener as AgentEventListener);
  }

  /**
   * 发送事件
   */
  public emit<T = unknown>(event: AgentEvent<T>): void {
    // 触发特定事件监听器
    const listeners = this.eventListeners.get(event.type);
    if (listeners) {
      listeners.forEach((listener) => {
        try {
          listener(event);
        } catch (error) {
          console.error(`Error in event listener for ${event.type}:`, error);
        }
      });
    }

    // 触发全局监听器
    this.globalListeners.forEach((listener) => {
      try {
        listener(event);
      } catch (error) {
        console.error('Error in global event listener:', error);
      }
    });
  }

  // ==================== 查询方法 ====================

  /**
   * 根据能力查找智能体
   */
  public findAgentsByCapability(capability: string): AgentConfig[] {
    return this.getAllAgentConfigs().filter(
      (config) => config.capabilities.includes(capability as any)
    );
  }

  /**
   * 根据工具查找智能体
   */
  public findAgentsByTool(toolName: string): AgentConfig[] {
    return this.getAllAgentConfigs().filter(
      (config) => config.tools?.includes(toolName)
    );
  }

  // ==================== 生命周期 ====================

  /**
   * 初始化所有已注册的智能体
   */
  public async initializeAll(): Promise<void> {
    const promises = Array.from(this.agents.values()).map((agent) =>
      agent.initialize().catch((error) => {
        console.error(`Failed to initialize agent ${agent.config.id}:`, error);
        this.emit({
          type: 'agent:error',
          agentId: agent.config.id,
          timestamp: new Date(),
          data: { error: error.message },
        });
      })
    );
    await Promise.all(promises);
  }

  /**
   * 关闭所有智能体
   */
  public async shutdownAll(): Promise<void> {
    const promises = Array.from(this.agents.values()).map((agent) =>
      agent.shutdown().catch((error) => {
        console.error(`Failed to shutdown agent ${agent.config.id}:`, error);
      })
    );
    await Promise.all(promises);
    this.agents.clear();
  }

  /**
   * 重置注册表（主要用于测试）
   */
  public reset(): void {
    this.agents.clear();
    this.agentConfigs.clear();
    this.tools.clear();
    this.eventListeners.clear();
    this.globalListeners.clear();
  }
}

// 导出单例
export const agentRegistry = AgentRegistry.getInstance();
export default agentRegistry;