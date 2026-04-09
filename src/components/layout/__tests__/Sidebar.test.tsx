import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";
import { Sidebar } from "../Sidebar";

// ── Stub lucide-react icons ────────────────────────────────────────────
// vi.mock is hoisted, so we CANNOT reference top-level variables.
// All icon stubs must be built inline inside the factory function.
vi.mock("lucide-react", () => {
  const R = require("react");
  const stub = (name: string) => {
    const C = (p: Record<string, unknown>) => R.createElement("span", { "data-testid": `icon-${name}`, ...p });
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
    "Pin","PinOff","Star","Network","Search",
  ];
  const out: Record<string, unknown> = {};
  for (const n of names) out[n] = stub(n);
  return out;
});

// ── Stub sub-components & hooks ────────────────────────────────────────
vi.mock("../SearchPanel", () => ({ default: () => <div>Search</div> }));
vi.mock("../FavoriteAgents", () => ({ default: () => <div>Favorites</div> }));
vi.mock("../RecentAgents", () => ({ default: () => <div>Recent</div> }));
vi.mock("../ProfileSummary", () => ({ default: () => <div>Profile</div> }));
vi.mock("../../auth/AuthContext", () => ({ useAuth: () => ({ profile: {} }) }));
vi.mock("../../../contexts/UserContext", () => ({ useUser: () => ({ user: {} }) }));
vi.mock("react-router-dom", () => {
  const R = require("react");
  return {
    Link: ({ children, ...props }: { children: React.ReactNode; to: string }) =>
      R.createElement("a", { href: props.to }, children),
    useLocation: () => ({ pathname: "/" }),
    useNavigate: () => vi.fn(),
  };
});
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
  const R = require("react");
  const F = ({ children }: { children: React.ReactNode }) => R.createElement("div", null, children);
  return { Collapsible: F, CollapsibleTrigger: F, CollapsibleContent: F };
});
vi.mock("@/components/ui/dropdown-menu", () => {
  const R = require("react");
  const F = ({ children }: { children: React.ReactNode }) => R.createElement("div", null, children);
  return {
    DropdownMenu: F, DropdownMenuContent: F, DropdownMenuItem: F,
    DropdownMenuLabel: F, DropdownMenuSeparator: () => null, DropdownMenuTrigger: F,
  };
});
vi.mock("@/components/ui/tooltip", () => {
  const R = require("react");
  const F = ({ children }: { children: React.ReactNode }) => R.createElement("div", null, children);
  return { Tooltip: F, TooltipContent: F, TooltipProvider: F, TooltipTrigger: F };
});
vi.mock("@/components/ui/button", () => {
  const R = require("react");
  return {
    Button: R.forwardRef(
      ({ children, ...props }: { children?: React.ReactNode }, ref: React.Ref<HTMLButtonElement>) =>
        R.createElement("button", { ...props, ref }, children)
    ),
  };
});

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
