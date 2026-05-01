import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";
import { Sidebar } from "../Sidebar";

// ── Stub lucide-react icons ────────────────────────────────────────────
// vi.mock is hoisted — factory can reference top-level imports (React)
// but NOT top-level variable declarations.
vi.mock("lucide-react", () => {
  const stub = (name: string) => {
    const C = (p: Record<string, unknown>) =>
      React.createElement("span", { "data-testid": `icon-${name}`, ...p });
    C.displayName = name;
    return C;
  };
  const names = [
    "LayoutDashboard","Users","FileCheck","BookOpen","Gift","Settings",
    "Bot","TrendingUp","AlertTriangle","Crown","LogOut","ChevronRight",
    "ChevronDown","User","Briefcase","FileSearch","Swords","Target",
    "Calendar","DollarSign","Clock","ChevronLeft","Upload","Building2",
    "Contact","FileSignature","BarChart3","CreditCard","Puzzle",
    "GraduationCap","ClipboardList","Key","Rocket","ListTodo",
    "ShieldCheck","Cpu","Bug","Inbox","Wrench","Package","Award",
    "Warehouse","Fingerprint","Workflow","FileEdit","LayoutTemplate",
    "Pin","PinOff","Star","Network","Search","Sparkles","Brain",
  ];
  const out: Record<string, unknown> = {};
  for (const n of names) out[n] = stub(n);
  return out;
});

// ── Stub sub-components & hooks ────────────────────────────────────────
vi.mock("../SearchPanel", () => ({ default: () => React.createElement("div", null, "Search") }));
vi.mock("../FavoriteAgents", () => ({ default: () => React.createElement("div", null, "Favorites") }));
vi.mock("../RecentAgents", () => ({ default: () => React.createElement("div", null, "Recent") }));
vi.mock("../ProfileSummary", () => ({ default: () => React.createElement("div", null, "Profile") }));
vi.mock("../../auth/AuthContext", () => ({ useAuth: () => ({ profile: {} }) }));
vi.mock("../../../contexts/UserContext", () => ({ useUser: () => ({ user: {} }) }));
vi.mock("react-router-dom", () => ({
  Link: ({ children, ...props }: { children: React.ReactNode; to: string }) =>
    React.createElement("a", { href: props.to }, children),
  useLocation: () => ({ pathname: "/" }),
  useNavigate: () => vi.fn(),
}));
vi.mock("@/contexts/ThemeContext", () => ({
  useTheme: () => ({ theme: "light" }),
}));
vi.mock("@/components/ui/ThemeToggle", () => ({
  ThemeToggle: () => null,
}));
vi.mock("@/hooks/useConfirmDialog", () => ({
  useConfirmDialog: () => ({
    isOpen: false,
    open: vi.fn(),
    close: vi.fn(),
    onConfirm: vi.fn(),
    dialogProps: {},
  }),
}));
vi.mock("@/components/common/ConfirmDialog", () => ({
  ConfirmDialog: () => null,
}));
vi.mock("@/lib/lazyPreload", () => ({
  prefetchRoute: vi.fn(),
}));
vi.mock("@/routes/lazyImports", () => ({}));
vi.mock("@/integrations/supabase/client", () => ({
  supabase: {
    auth: { signOut: vi.fn() },
  },
}));
vi.mock("@/hooks/useExceptions", () => ({
  useExceptions: () => ({ data: [], isLoading: false }),
}));
vi.mock("@/hooks/useApprovals", () => ({
  usePendingApprovalsCount: () => 0,
}));
vi.mock("@/hooks/useNotificationCenter", () => ({
  useUnreadCount: () => 0,
}));
vi.mock("@/components/ui/collapsible", () => {
  const F = ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children);
  return { Collapsible: F, CollapsibleTrigger: F, CollapsibleContent: F };
});
vi.mock("@/components/ui/dropdown-menu", () => {
  const F = ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children);
  return {
    DropdownMenu: F, DropdownMenuContent: F, DropdownMenuItem: F,
    DropdownMenuLabel: F, DropdownMenuSeparator: () => null, DropdownMenuTrigger: F,
  };
});
vi.mock("@/components/ui/tooltip", () => {
  const F = ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children);
  return { Tooltip: F, TooltipContent: F, TooltipProvider: F, TooltipTrigger: F };
});
vi.mock("@/components/ui/button", () => ({
  Button: React.forwardRef(
    ({ children, ...props }: { children?: React.ReactNode }, ref: React.Ref<HTMLButtonElement>) =>
      React.createElement("button", { ...props, ref }, children)
  ),
}));

describe("Sidebar Accessibility", () => {
  it("should render with correct ARIA roles", () => {
    render(<Sidebar />);
    const aside = screen.getByRole("complementary");
    expect(aside).toBeInTheDocument();
    expect(aside).toHaveAttribute("aria-label", "主要系统导航");
  });

  it("should have an accessible search input", () => {
    render(<Sidebar />);
    const searchInput = screen.getByRole("textbox", { name: /搜索系统功能/ });
    expect(searchInput).toBeInTheDocument();
  });
});
