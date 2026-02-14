import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  name?: string;
  tool_call_id?: string;
  timestamp: number;
  agent?: string;
}

interface AIState {
  messages: Message[];
  isStreaming: boolean;
  currentAgent: string;
  sessionId: string;
  
  // Actions
  addMessage: (message: Omit<Message, 'timestamp' | 'id'>) => void;
  setStreaming: (isStreaming: boolean) => void;
  setAgent: (agent: string) => void;
  clearHistory: () => void;
  updateLastMessage: (content: string) => void;
}

export const useAIStore = create<AIState>()(
  persist(
    (set) => ({
      messages: [],
      isStreaming: false,
      currentAgent: "@总裁助理",
      sessionId: `session_${Date.now()}`,

      addMessage: (msg) => set((state) => ({
        messages: [...state.messages, { 
          ...msg, 
          id: crypto.randomUUID(),
          timestamp: Date.now() 
        }]
      })),

      setStreaming: (isStreaming) => set({ isStreaming }),
      
      setAgent: (currentAgent) => set({ currentAgent }),

      clearHistory: () => set({ 
        messages: [], 
        sessionId: `session_${Date.now()}` 
      }),

      updateLastMessage: (content) => set((state) => {
        const newMessages = [...state.messages];
        if (newMessages.length > 0) {
          const last = newMessages[newMessages.length - 1];
          if (last.role === 'assistant') {
            last.content = content;
          }
        }
        return { messages: newMessages };
      }),
    }),
    {
      name: 'nexus-ai-storage',
      partialize: (state) => ({ 
        messages: state.messages.slice(-20), // Only persist last 20 messages
        currentAgent: state.currentAgent 
      }),
    }
  )
);
