import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ChatMessageList } from "../ChatMessageList";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { AgentTrace } from "@/hooks/useAgentTrace";
import type { AIMessage } from "@/types/nexus";

// Mock essential hooks for ChatMessageList
vi.mock("@/contexts/UserContext", () => ({
  useUser: () => ({ user: null }),
}));

vi.mock("@/components/auth/AuthContext", () => ({
  useAuth: () => ({ user: { id: "123" } }),
}));

// Mock useVirtualizer
vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: () => ({
    getVirtualItems: () => [],
    getTotalSize: () => 0,
    scrollToIndex: vi.fn(),
  } as unknown), // Use unknown then type assertion if needed elsewhere, reducing 'any' noise
}));

describe("ChatMessageList A11y", () => {
  const mockAgentTrace: AgentTrace = {
    steps: [],
    totalTokens: 0,
    startTime: null,
    endTime: null,
    isActive: false,
  };

  const defaultProps = {
    messages: [] as AIMessage[],
    setMessages: vi.fn(),
    isAiTyping: false,
    aiStatus: undefined,
    userId: "123",
    handleCopy: vi.fn(),
    handleRegenerate: vi.fn(),
    handleRetry: vi.fn(),
    handleDeleteMessage: vi.fn(),
    pendingConfirmation: null,
    confirmAndResend: vi.fn(),
    dismissConfirmation: vi.fn(),
    pendingQuestion: null,
    answerQuestion: vi.fn(),
    dismissQuestion: vi.fn(),
    showTrace: false,
    setShowTrace: vi.fn(),
    trace: mockAgentTrace,
    messagesEndRef: { current: null } as unknown as React.RefObject<HTMLDivElement>,
  };

  it("should have role='log' for accessibility announcements", () => {
    render(
      <TooltipProvider>
        <ChatMessageList {...defaultProps} />
      </TooltipProvider>
    );
    
    // The container should have the log role for live region announcements
    const logRegion = screen.getByRole("log");
    expect(logRegion).toBeInTheDocument();
  });

  it("should have a proper label for the chat messages area", () => {
    render(
      <TooltipProvider>
        <ChatMessageList {...defaultProps} />
      </TooltipProvider>
    );

    const messageList = screen.getByLabelText("聊天消息列表");
    expect(messageList).toBeInTheDocument();
  });
});
