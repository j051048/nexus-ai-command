import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ChatMessageList from "../ChatMessageList";
import { TooltipProvider } from "@/components/ui/tooltip";

// Mock essential hooks for ChatMessageList
vi.mock("@/contexts/UserContext", () => ({
  useUser: () => ({ user: null }),
}));

vi.mock("@/components/auth/AuthContext", () => ({
  useAuth: () => ({ user: { id: "123" } }),
}));

describe("ChatMessageList A11y", () => {
  const mockAgentTrace = {
    steps: [],
    isActive: false,
  } as any;

  it("should have role='log' for accessibility announcements", () => {
    render(
      <TooltipProvider>
        <ChatMessageList 
          messages={[]} 
          agentTrace={mockAgentTrace}
          isTyping={false}
        />
      </TooltipProvider>
    );
    
    // The container should have the log role for live region announcements
    const logRegion = screen.getByRole("log");
    expect(logRegion).toBeInTheDocument();
    expect(logRegion).toHaveAttribute("aria-live", "polite");
  });

  it("should have a proper label for the chat messages area", () => {
    render(
      <TooltipProvider>
        <ChatMessageList 
          messages={[]} 
          agentTrace={mockAgentTrace}
          isTyping={false}
        />
      </TooltipProvider>
    );

    const messageList = screen.getByLabelText("聊天消息列表");
    expect(messageList).toBeInTheDocument();
  });
});
