import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { EnhancedAIChatPanel } from "../EnhancedAIChatPanel";

// Mock sub-components
vi.mock("../ChatHeader", () => ({ 
  ChatHeader: () => <div aria-label="对话窗口顶部工具栏">Header</div> 
}));
vi.mock("../ChatMessageList", () => ({ ChatMessageList: () => <div>List</div> }));
vi.mock("../ChatInputArea", () => ({ ChatInputArea: () => <div>Input</div> }));
vi.mock("../ChatHistorySidebar", () => ({ ChatHistorySidebar: () => <div>History</div> }));
vi.mock("../ChatSuggestions", () => ({ ChatSuggestions: () => <div>Suggestions</div> }));
vi.mock("../QuotaDisplay", () => ({ QuotaDisplay: () => <div>Quota</div> }));
vi.mock("../../EntityProfileDialog", () => ({ EntityProfileDialog: () => <div>Entity</div> }));

// Use relative paths to ensure Vitest picks up the mocks
vi.mock("../../../../contexts/UserContext", () => ({
  useUser: () => ({ user: { id: "123", name: "Tester" } }),
}));

vi.mock("../../../auth/AuthContext", () => ({
  useAuth: () => ({ user: { id: "123" } }),
}));

vi.mock("../../../../hooks/use-mobile", () => ({
  useIsMobile: () => false,
}));

vi.mock("../../../../hooks/useToolMetadata", () => ({
  useToolMetadata: () => ({ tools: [], isLoading: false }),
}));

vi.mock("../../../../hooks/useSavedPrompts", () => ({
  useSavedPrompts: () => ({ prompts: [], isLoading: false }),
}));

vi.mock("../../../../hooks/useAISettings", () => ({
  useAISettings: () => ({ settings: {} }),
}));

vi.mock("../../../../services/ai/useAIStream", () => ({
  useAIStream: () => ({
    isTyping: false,
    aiStatus: "ready",
    streamChat: vi.fn(),
    sessionId: "123",
  }),
}));

vi.mock("../../../../services/ai/useAgentTrace", () => ({
  useAgentTrace: () => ({
    trace: { steps: [] },
  }),
}));

vi.mock("../../../../services/ai/useOrchestrationTrace", () => ({
  useOrchestrationTrace: () => ({
    orchestration: {},
  }),
}));

describe("EnhancedAIChatPanel A11y & Navigation", () => {
  beforeEach(() => {
    document.body.style.overflow = "";
  });

  const renderPanel = (props = {}) =>
    render(
      <EnhancedAIChatPanel 
        isExpanded={true} 
        onToggle={vi.fn()} 
        {...props} 
      />
    );

  it("should have an accessible header toolbar", () => {
    renderPanel();
    const toolbar = screen.getByLabelText("对话窗口顶部工具栏");
    expect(toolbar).toBeInTheDocument();
  });

  it("should respond to Escape key by calling onToggle", () => {
    const onToggleMock = vi.fn();
    renderPanel({ onToggle: onToggleMock, isExpanded: true });
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onToggleMock).toHaveBeenCalled();
  });
});
