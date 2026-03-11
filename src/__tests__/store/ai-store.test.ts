import { describe, it, expect, vi, beforeEach } from 'vitest';

// mock crypto.randomUUID (jsdom 可能不支持)
const mockUUID = vi.fn(() => 'mock-uuid-001');
vi.stubGlobal('crypto', { randomUUID: mockUUID });

// mock localStorage for zustand persist
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
    get length() { return Object.keys(store).length; },
    key: vi.fn((i: number) => Object.keys(store)[i] ?? null),
  };
})();
vi.stubGlobal('localStorage', localStorageMock);

describe('ai-store (Zustand)', () => {
  let useAIStore: typeof import('@/store/ai-store').useAIStore;

  beforeEach(async () => {
    vi.resetModules();
    localStorageMock.clear();
    mockUUID.mockReturnValue('mock-uuid-001');
    const mod = await import('@/store/ai-store');
    useAIStore = mod.useAIStore;
    // 清空 store 状态
    useAIStore.setState({
      messages: [],
      isStreaming: false,
      currentAgent: '@总裁助理',
      sessionId: 'test-session',
    });
  });

  it('初始状态应正确设置', () => {
    const state = useAIStore.getState();
    expect(state.messages).toEqual([]);
    expect(state.isStreaming).toBe(false);
    expect(state.currentAgent).toBe('@总裁助理');
  });

  it('addMessage 应追加消息并自动生成 id 和 timestamp', () => {
    const { addMessage } = useAIStore.getState();
    const now = Date.now();
    vi.spyOn(Date, 'now').mockReturnValue(now);

    addMessage({ role: 'user', content: '你好' });

    const state = useAIStore.getState();
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]).toMatchObject({
      id: 'mock-uuid-001',
      role: 'user',
      content: '你好',
      timestamp: now,
    });

    vi.restoreAllMocks();
  });

  it('addMessage 应连续追加多条消息', () => {
    const { addMessage } = useAIStore.getState();
    addMessage({ role: 'user', content: '第一条' });
    addMessage({ role: 'assistant', content: '第二条' });

    const { messages } = useAIStore.getState();
    expect(messages).toHaveLength(2);
    expect(messages[0].content).toBe('第一条');
    expect(messages[1].content).toBe('第二条');
  });

  it('setStreaming 应正确切换流状态', () => {
    const { setStreaming } = useAIStore.getState();

    setStreaming(true);
    expect(useAIStore.getState().isStreaming).toBe(true);

    setStreaming(false);
    expect(useAIStore.getState().isStreaming).toBe(false);
  });

  it('setAgent 应正确设置 agent', () => {
    const { setAgent } = useAIStore.getState();
    setAgent('@销售助手');
    expect(useAIStore.getState().currentAgent).toBe('@销售助手');
  });

  it('clearHistory 应清空消息并生成新 sessionId', () => {
    const { addMessage } = useAIStore.getState();
    addMessage({ role: 'user', content: '测试' });

    const oldSessionId = useAIStore.getState().sessionId;
    const { clearHistory } = useAIStore.getState();

    const now = 1700000000000;
    vi.spyOn(Date, 'now').mockReturnValue(now);
    clearHistory();

    const state = useAIStore.getState();
    expect(state.messages).toEqual([]);
    expect(state.sessionId).toBe(`session_${now}`);
    expect(state.sessionId).not.toBe(oldSessionId);

    vi.restoreAllMocks();
  });

  it('updateLastMessage 应只更新最后一条 assistant 消息', () => {
    useAIStore.setState({
      messages: [
        { id: '1', role: 'user', content: '问题', timestamp: 1 },
        { id: '2', role: 'assistant', content: '原始回答', timestamp: 2 },
      ],
    });

    const { updateLastMessage } = useAIStore.getState();
    updateLastMessage('新回答');

    const { messages } = useAIStore.getState();
    expect(messages[0].content).toBe('问题');
    expect(messages[1].content).toBe('新回答');
  });

  it('updateLastMessage 最后一条非 assistant 时不应修改', () => {
    useAIStore.setState({
      messages: [
        { id: '1', role: 'assistant', content: '回答', timestamp: 1 },
        { id: '2', role: 'user', content: '追问', timestamp: 2 },
      ],
    });

    const { updateLastMessage } = useAIStore.getState();
    updateLastMessage('尝试更新');

    const { messages } = useAIStore.getState();
    expect(messages[1].content).toBe('追问'); // 未变化
  });

  it('updateLastMessage 空列表时不应崩溃', () => {
    const { updateLastMessage } = useAIStore.getState();
    expect(() => updateLastMessage('内容')).not.toThrow();
    expect(useAIStore.getState().messages).toEqual([]);
  });
});
