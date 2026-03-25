import React, { useState, useEffect, useCallback } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useUser } from "@/contexts/UserContext";
import { useAuth } from "@/components/auth/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { cn } from "@/lib/utils";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useConfirmDialog } from "@/hooks/useConfirmDialog";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { prefetchRoute } from "@/lib/lazyPreload";
import * as LazyRoutes from "@/routes/lazyImports";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import {
  LayoutDashboard,
  Users,
  FileCheck,
  BookOpen,
  Gift,
  Settings,
  Bot,
  TrendingUp,
  AlertTriangle,
  Crown,
  LogOut,
  ChevronRight,
  ChevronDown,
  User as UserIcon,
  Briefcase,
  FileSearch,
  Swords,
  Target,
  Calendar,
  DollarSign,
  Clock,
  ChevronLeft,
  Upload,
  Building2,
  Contact,
  FileSignature,
  BarChart3,
  CreditCard,
  Puzzle,
  GraduationCap,
  ClipboardList,
  Key,
  Rocket,
  ListTodo,
  Bot as BotIcon,
  ShieldCheck,
  Cpu,
  Bug,
  Inbox,
  Wrench,
  Package,
  Award,
  Warehouse,
  Fingerprint,
  Workflow,
  FileEdit,
  LayoutTemplate,
  Pin,
  PinOff,
  Star,
  Library,
  Network,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { useExceptions } from "@/hooks/useExceptions";
import { usePendingApprovalsCount } from "@/hooks/useApprovals";
import { useUnreadCount } from "@/hooks/useNotificationCenter";

type AppRole = "boss" | "manager" | "ai_assistant" | "employee" | "founder";

interface NavItem {
  icon: React.ReactNode;
  label: string;
  href: string;
  badge?: string;
  badgeType?: "primary" | "success" | "warning";
  roles?: AppRole[];
  group: string;
}

// ── localStorage keys ──
const COLLAPSED_GROUPS_KEY = "nexus:sidebar-collapsed-groups";
const PINNED_ITEMS_KEY = "nexus:sidebar-pinned-items";

function loadCollapsedGroups(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(COLLAPSED_GROUPS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function loadPinnedItems(): string[] {
  try {
    const raw = localStorage.getItem(PINNED_ITEMS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveCollapsedGroups(state: Record<string, boolean>) {
  localStorage.setItem(COLLAPSED_GROUPS_KEY, JSON.stringify(state));
}

function savePinnedItems(items: string[]) {
  localStorage.setItem(PINNED_ITEMS_KEY, JSON.stringify(items));
}

// ── Navigation config — reorganized & merged ──
const NAV_CONFIG: NavItem[] = [
  // AI 核心
  {
    icon: <Crown size={20} />,
    label: "总控中心",
    href: "boss-dashboard",
    roles: ["boss", "founder"],
    group: "AI 核心",
  },
  {
    icon: <LayoutDashboard size={20} />,
    label: "战绩中心",
    href: "dashboard",
    group: "AI 核心",
  },
  {
    icon: <Inbox size={20} />,
    label: "待办中心",
    href: "inbox",
    group: "AI 核心",
  },

  // 销售与客关
  {
    icon: <TrendingUp size={20} />,
    label: "销售AI管理",
    href: "sales",
    roles: ["employee", "manager", "boss", "founder"],
    group: "销售与客关",
  },
  {
    icon: <Contact size={20} />,
    label: "CRM管理",
    href: "crm",
    roles: ["employee", "manager", "boss", "founder"],
    group: "销售与客关",
  },
  {
    icon: <FileSearch size={20} />,
    label: "标书审阅",
    href: "tender-analysis",
    roles: ["employee", "manager", "boss", "founder"],
    group: "销售与客关",
  },
  {
    icon: <Swords size={20} />,
    label: "竞品库",
    href: "battlecards",
    group: "销售与客关",
  },
  {
    icon: <FileSignature size={20} />,
    label: "合同管理",
    href: "contracts",
    roles: ["manager", "boss", "founder"],
    group: "销售与客关",
  },
  {
    icon: <Warehouse size={20} />,
    label: "库存管理",
    href: "inventory",
    roles: ["manager", "boss", "founder"],
    group: "销售与客关",
  },

  // 项目与目标
  {
    icon: <Briefcase size={20} />,
    label: "项目管理",
    href: "projects",
    roles: ["employee", "manager", "boss", "founder"],
    group: "项目与目标",
  },
  {
    icon: <Target size={20} />,
    label: "目标看板",
    href: "target-dashboard",
    group: "项目与目标",
  },
  {
    icon: <TrendingUp size={20} />,
    label: "目标管理",
    href: "targets",
    roles: ["boss", "founder"],
    group: "项目与目标",
  },
  {
    icon: <BarChart3 size={20} />,
    label: "数据报表",
    href: "reports",
    group: "项目与目标",
  },

  // OA/HR/财务
  {
    icon: <Calendar size={20} />,
    label: "OA办公",
    href: "oa",
    group: "OA/HR/财务",
  },
  {
    icon: <Fingerprint size={20} />,
    label: "考勤打卡",
    href: "oa?tab=attendance",
    group: "OA/HR/财务",
  },
  {
    icon: <Clock size={20} />,
    label: "人事中心",
    href: "hr",
    roles: ["manager", "boss", "founder"],
    group: "OA/HR/财务",
  },
  {
    icon: <DollarSign size={20} />,
    label: "财务中心",
    href: "finance",
    group: "OA/HR/财务",
  },
  {
    icon: <FileCheck size={20} />,
    label: "审批中心",
    href: "approval",
    roles: ["employee", "manager", "boss", "founder"],
    group: "OA/HR/财务",
  },
  {
    icon: <Workflow size={20} />,
    label: "流程设计",
    href: "workflows",
    roles: ["boss", "founder"],
    group: "OA/HR/财务",
  },
  {
    icon: <LayoutTemplate size={20} />,
    label: "流程模板",
    href: "workflow-templates",
    roles: ["boss", "founder"],
    group: "OA/HR/财务",
  },
  {
    icon: <FileEdit size={20} />,
    label: "表单设计",
    href: "form-designer",
    roles: ["boss", "founder"],
    group: "OA/HR/财务",
  },
  {
    icon: <Wrench size={20} />,
    label: "工单管理",
    href: "work-orders",
    group: "OA/HR/财务",
  },
  {
    icon: <Package size={20} />,
    label: "资产管理",
    href: "assets",
    roles: ["manager", "boss", "founder"],
    group: "OA/HR/财务",
  },

  // 知识与培训
  {
    icon: <BookOpen size={20} />,
    label: "知识库",
    href: "knowledge",
    group: "知识与培训",
  },
  {
    icon: <GraduationCap size={20} />,
    label: "培训中心",
    href: "training",
    group: "知识与培训",
  },
  {
    icon: <Gift size={20} />,
    label: "激励钱包",
    href: "rewards",
    group: "知识与培训",
  },
  {
    icon: <Award size={20} />,
    label: "企业证照",
    href: "certificates",
    roles: ["manager", "boss", "founder"],
    group: "知识与培训",
  },

  // 虚拟市场部
  {
    icon: <Rocket size={20} />,
    label: "虚拟市场部",
    href: "vmd",
    group: "虚拟市场部",
  },
  {
    icon: <ListTodo size={20} />,
    label: "任务中心",
    href: "vmd/tasks",
    group: "虚拟市场部",
  },
  {
    icon: <BotIcon size={20} />,
    label: "Agent配置",
    href: "vmd/agents",
    roles: ["boss", "manager", "founder"],
    group: "虚拟市场部",
  },
  {
    icon: <Target size={20} />,
    label: "线索管理",
    href: "vmd/clues",
    group: "虚拟市场部",
  },
  {
    icon: <ShieldCheck size={20} />,
    label: "合规校验",
    href: "vmd/compliance",
    group: "虚拟市场部",
  },
  {
    icon: <BarChart3 size={20} />,
    label: "VMD看板",
    href: "vmd/dashboard",
    group: "虚拟市场部",
  },

  // 组织管理 (merged: 团队管理 + 部门管理 + 组织架构 + 企业设置)
  {
    icon: <Users size={20} />,
    label: "员工管理",
    href: "employees",
    roles: ["boss", "founder"],
    group: "组织管理",
  },
  {
    icon: <Library size={20} />,
    label: "部门管理",
    href: "departments",
    roles: ["boss", "founder"],
    group: "组织管理",
  },
  {
    icon: <Network size={20} />,
    label: "组织架构",
    href: "org-chart",
    roles: ["boss", "founder"],
    group: "组织管理",
  },
  {
    icon: <Settings size={20} />,
    label: "企业设置",
    href: "company-settings",
    roles: ["boss", "founder"],
    group: "组织管理",
  },

  // 系统管理 (merged: 原系统管理 + 系统设置 + 数据导入)
  {
    icon: <Settings size={20} />,
    label: "系统设置",
    href: "settings",
    group: "系统管理",
  },
  {
    icon: <Cpu size={20} />,
    label: "模型管理",
    href: "llm/models",
    roles: ["boss", "founder"],
    group: "系统管理",
  },
  {
    icon: <DollarSign size={20} />,
    label: "LLM成本",
    href: "llm/costs",
    roles: ["boss", "founder"],
    group: "系统管理",
  },
  {
    icon: <Upload size={20} />,
    label: "数据导入",
    href: "import",
    roles: ["boss", "founder"],
    group: "系统管理",
  },
  {
    icon: <ClipboardList size={20} />,
    label: "审计日志",
    href: "audit",
    roles: ["boss", "founder"],
    group: "系统管理",
  },
  {
    icon: <Puzzle size={20} />,
    label: "插件市场",
    href: "plugins",
    roles: ["boss", "founder"],
    group: "系统管理",
  },
  {
    icon: <Key size={20} />,
    label: "API密钥",
    href: "api-keys",
    roles: ["boss", "founder"],
    group: "系统管理",
  },
  {
    icon: <CreditCard size={20} />,
    label: "订阅支付",
    href: "payments",
    roles: ["boss", "founder"],
    group: "系统管理",
  },
  {
    icon: <Bug size={20} />,
    label: "Agent调试",
    href: "agent-debug",
    roles: ["boss", "founder"],
    group: "系统管理",
  },
  {
    icon: <Clock size={20} />,
    label: "定时任务",
    href: "scheduled-tasks",
    group: "系统管理",
  },
];

// Group order
const NAV_GROUPS = [
  "AI 核心",
  "销售与客关",
  "项目与目标",
  "OA/HR/财务",
  "知识与培训",
  "虚拟市场部",
  "组织管理",
  "系统管理",
];

// href → lazy component mapping for hover preload (core high-traffic routes only)
const PRELOAD_MAP: Record<string, { preload?: () => Promise<void> }> = {
  dashboard: LazyRoutes.EmployeeDashboard,
  'boss-dashboard': LazyRoutes.BossDashboard,
  inbox: LazyRoutes.InboxPage,
  sales: LazyRoutes.SalesPipeline,
  projects: LazyRoutes.ProjectManagement,
  approval: LazyRoutes.ApprovalCenter,
  crm: LazyRoutes.CRMPage,
  'org-chart': LazyRoutes.OrgChartPage,
};

interface SidebarProps {
  onNavClick?: () => void;
}

export function Sidebar({ onNavClick }: SidebarProps) {
  const { user } = useUser();
  const { role, signOut, profile } = useAuth();
  const [orgName, setOrgName] = useState("企业名称");

  // Preload route chunk on hover (best-effort, fire-and-forget)
  const handleLinkHover = useCallback((href: string) => {
    const component = PRELOAD_MAP[href];
    if (component) prefetchRoute(component);
  }, []);

  useEffect(() => {
    const fetchOrgName = async () => {
      try {
        if (profile?.organization_id) {
          const { data, error } = await supabase
            .from("organizations")
            .select("name")
            .eq("id", profile.organization_id)
            .single();

          const orgData = data as { name: unknown } | null;
          if (!error && orgData?.name) {
            const safeName = typeof orgData.name === 'string' ? orgData.name : String(orgData.name);
            setOrgName(safeName);
          }
        }
      } catch (e) {
        console.error("Failed to load org name in Sidebar", e);
      }
    };

    fetchOrgName();
  }, [profile?.organization_id]);
  const { theme } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>(loadCollapsedGroups);
  const [pinnedHrefs, setPinnedHrefs] = useState<string[]>(loadPinnedItems);

  const togglePin = (href: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const next = pinnedHrefs.includes(href) 
      ? pinnedHrefs.filter(h => h !== href) 
      : [...pinnedHrefs, href];
    setPinnedHrefs(next);
    savePinnedItems(next);
  };

  // Badge data
  const { data: exceptions = [] } = useExceptions();
  const exceptionCount = exceptions.length;
  const pendingApprovalsQuery = usePendingApprovalsCount();
  const pendingCount = pendingApprovalsQuery.data ?? 0;
  const unreadCountQuery = useUnreadCount();
  const unreadCount = unreadCountQuery.data ?? 0;

  // Total inbox badge = approvals + exceptions + unread notifications
  const inboxBadgeCount = pendingCount + exceptionCount + unreadCount;

  const getRoleDisplayName = (role: string) => {
    switch (role) {
      case "boss":
      case "founder":
        return "企业管理员";
      case "manager":
        return "部门经理";
      case "sales":
      case "employee":
      default:
        return "销售精英";
    }
  };

  const isActive = (href: string) => {
    // Strip query params for path matching
    const hrefPath = href.split("?")[0];
    if (hrefPath === "dashboard" && location.pathname === "/dashboard") return true;
    if (hrefPath === "boss-dashboard" && location.pathname === "/boss-dashboard")
      return true;
    if (hrefPath === "vmd" && location.pathname === "/vmd") return true;
    if (hrefPath === "vmd") return false;
    // For items with query params, check both path and search
    if (href.includes("?")) {
      const [path, search] = href.split("?");
      return location.pathname === "/" + path && location.search.includes(search);
    }
    return location.pathname.startsWith("/" + hrefPath);
  };

  // Inject dynamic badges
  const navWithBadges = NAV_CONFIG.map((item) => {
    if (item.href === "exceptions" && exceptionCount > 0) {
      return { ...item, badge: String(exceptionCount) };
    }
    if (item.href === "inbox" && inboxBadgeCount > 0) {
      return { ...item, badge: String(inboxBadgeCount), badgeType: "warning" as const };
    }
    return item;
  });

  // Role-based filtering
  const currentRole = (role || user.role || "employee") as AppRole;
  const effectiveRole = currentRole === "founder" ? "founder" : currentRole;
  const navItems = navWithBadges.filter(
    (item) =>
      !item.roles ||
      item.roles.includes(effectiveRole) ||
      (effectiveRole === "founder" && item.roles.includes("boss")),
  );

  const { confirm, ConfirmDialogProps } = useConfirmDialog();

  const handleLogout = async () => {
    const ok = await confirm({
      title: "确认退出登录",
      description: "退出后需要重新登录才能访问系统，确定要继续吗？",
      confirmText: "退出登录",
      variant: "destructive",
    });
    if (ok) {
      await signOut();
    }
  };

  const toggleGroup = (group: string) => {
    setCollapsedGroups((prev) => {
      const next = { ...prev, [group]: !prev[group] };
      saveCollapsedGroups(next);
      return next;
    });
  };

  // Check if any item in a group is active (auto-expand active group)
  const isGroupActive = (items: NavItem[]) =>
    items.some((item) => isActive(item.href));

  const renderNavGroup = (title: string, items: NavItem[]) => {
    if (items.length === 0) return null;

    const groupActive = isGroupActive(items);
    // If collapsed by user, respect it; but if the active route is in this group, force expand
    const isOpen = groupActive || !collapsedGroups[title];

    if (isCollapsed) {
      // When sidebar is collapsed, just render icons without groups
      return (
        <div key={title} className="px-2 mb-2">
          <ul className="space-y-1">
            {items.map((item) => (
              <li key={item.href}>
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <Link
                        to={`/${item.href}`}
                        onClick={onNavClick}
                        onMouseEnter={() => handleLinkHover(item.href)}
                        aria-current={isActive(item.href) ? "page" : undefined}
                        className={cn(
                          "flex items-center justify-center p-2 rounded-lg text-sm font-medium transition-all group relative",
                          isActive(item.href)
                            ? "bg-sidebar-accent text-primary shadow-sm"
                            : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-foreground",
                        )}
                      >
                        <span
                          className={cn(
                            "transition-transform duration-200",
                            !isActive(item.href) && "group-hover:scale-110",
                          )}
                        >
                          {item.icon}
                        </span>
                        {item.badge && (
                          <span
                            className={cn(
                              "absolute top-1 right-1 w-2 h-2 rounded-full border-2 border-background",
                              item.badgeType === "primary" && "bg-primary",
                              item.badgeType === "success" && "bg-success",
                              item.badgeType === "warning" && "bg-warning",
                            )}
                          />
                        )}
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent side="right" className="font-medium">
                      {item.label}
                      {item.badge && (
                        <span className="ml-2 text-xs opacity-70">
                          ({item.badge})
                        </span>
                      )}
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </li>
            ))}
          </ul>
        </div>
      );
    }

    return (
      <Collapsible
        key={title}
        open={isOpen}
        onOpenChange={() => toggleGroup(title)}
        className="mb-1 px-4"
      >
        <CollapsibleTrigger className="flex items-center justify-between w-full px-2 py-1.5 rounded-md hover:bg-sidebar-accent/50 transition-colors group/trigger">
          <h3 className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
            {title}
          </h3>
          {isOpen ? (
            <ChevronDown className="h-3 w-3 text-muted-foreground transition-transform" />
          ) : (
            <ChevronRight className="h-3 w-3 text-muted-foreground transition-transform" />
          )}
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-1">
          <ul className="space-y-1">
            {items.map((item) => (
              <li key={item.href}>
                <Link
                  to={`/${item.href}`}
                  onClick={onNavClick}
                  onMouseEnter={() => handleLinkHover(item.href)}
                  aria-current={isActive(item.href) ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-lg text-sm font-medium transition-all group relative px-3 py-2",
                    isActive(item.href)
                      ? "bg-sidebar-accent text-primary shadow-sm"
                      : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-foreground",
                  )}
                >
                  <span
                    className={cn(
                      "transition-transform duration-200",
                      !isActive(item.href) && "group-hover:scale-110",
                    )}
                  >
                    {item.icon}
                  </span>
                  <span className="flex-1 text-left truncate">
                    {item.label}
                  </span>
                  
                  {/* Pin Button */}
                  <button
                    onClick={(e) => togglePin(item.href, e)}
                    className={cn(
                      "opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-background/50 transition-all",
                      pinnedHrefs.includes(item.href) && "opacity-100 text-primary"
                    )}
                    title={pinnedHrefs.includes(item.href) ? "取消收藏" : "加入收藏"}
                  >
                    {pinnedHrefs.includes(item.href) ? <PinOff size={12} /> : <Pin size={12} />}
                  </button>

                  {item.badge && (
                    <span
                      className={cn(
                        "px-1.5 py-0.5 rounded-full text-[10px] font-bold ml-auto",
                        item.badgeType === "primary" &&
                          "bg-primary/10 text-primary",
                        item.badgeType === "success" &&
                          "bg-success/10 text-success",
                        item.badgeType === "warning" &&
                          "bg-warning/10 text-warning",
                      )}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </CollapsibleContent>
      </Collapsible>
    );
  };

  return (
    <aside
      aria-label="主导航"
      className={cn(
        "bg-sidebar border-r border-sidebar-border flex flex-col transition-all duration-300 ease-in-out h-full z-40 relative group/sidebar",
        isCollapsed ? "w-[70px]" : "w-64",
      )}
    >
      {/* Collapse Toggle Button */}
      <Button
        onClick={() => setIsCollapsed(!isCollapsed)}
        variant="ghost"
        size="icon"
        aria-expanded={isCollapsed ? "false" : "true"}
        aria-label="折叠菜单"
        className="absolute -right-3 top-6 h-6 w-6 rounded-full border bg-background shadow-md hover:bg-accent z-50 hidden md:flex items-center justify-center p-0"
      >
        {isCollapsed ? (
          <ChevronRight className="h-3 w-3" />
        ) : (
          <ChevronLeft className="h-3 w-3" />
        )}
      </Button>

      {/* Logo */}
      <div
        className={cn(
          "flex items-center gap-3 py-5 border-b border-sidebar-border transition-all duration-300",
          isCollapsed ? "justify-center px-0" : "px-6",
        )}
      >
        <div
          className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center glow-primary shrink-0 transition-all duration-300 hover:scale-105 cursor-pointer"
          onClick={() => navigate("/")}
        >
          <Bot className="w-6 h-6 text-primary-foreground" />
        </div>
        {!isCollapsed && (
          <div className="overflow-hidden transition-all duration-300 opacity-100 w-auto">
            <h1 className="font-bold text-foreground tracking-tight whitespace-nowrap">
              {orgName}
            </h1>
            <p className="text-xs text-muted-foreground whitespace-nowrap">
              企业智能中枢系统
            </p>
          </div>
        )}
      </div>

      {/* Theme Toggle */}
      <div className={cn("py-4 transition-all", isCollapsed ? "px-2" : "px-4")}>
        <div
          className={cn(
            "flex items-center rounded-lg bg-secondary/50 transition-all",
            isCollapsed ? "justify-center p-2" : "justify-between p-2",
          )}
          title={isCollapsed ? (theme === "dark" ? "夜间模式" : "日间模式") : undefined}
        >
          {!isCollapsed && (
            <span className="text-xs text-muted-foreground pl-1 whitespace-nowrap overflow-hidden">
              {theme === "dark" ? "夜间模式" : "日间模式"}
            </span>
          )}
          <ThemeToggle />
        </div>
      </div>

      {/* Navigation */}
      <nav
        role="navigation"
        aria-label="功能菜单"
        className="flex-1 py-2 overflow-y-auto overflow-x-hidden space-y-1 custom-scrollbar"
      >
        {/* 收藏夹 (Pinned Items) */}
        {!isCollapsed && pinnedHrefs.length > 0 && (
          <div className="mb-4 px-4">
             <div className="flex items-center gap-2 px-2 py-1.5 opacity-60">
                <Star size={12} className="text-primary fill-primary" />
                <h3 className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">我的收藏</h3>
             </div>
             <ul className="space-y-1 mt-1">
                {navItems.filter(i => pinnedHrefs.includes(i.href)).map(item => (
                  <li key={`pinned-${item.href}`}>
                    <Link
                      to={`/${item.href}`}
                      onClick={onNavClick}
                      className={cn(
                        "flex items-center gap-3 rounded-lg text-sm font-medium transition-all group relative px-3 py-2 border border-transparent",
                        isActive(item.href)
                          ? "bg-primary/5 text-primary border-primary/10 shadow-sm"
                          : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-foreground",
                      )}
                    >
                      <span className="shrink-0">{item.icon}</span>
                      <span className="flex-1 text-left truncate">{item.label}</span>
                    </Link>
                  </li>
                ))}
             </ul>
          </div>
        )}

        {NAV_GROUPS.map((group) => {
          const groupItems = navItems.filter((i) => i.group === group);
          return renderNavGroup(group, groupItems);
        })}
      </nav>

      {/* User Profile with Dropdown */}
      <div className="p-4 border-t border-sidebar-border mt-auto">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className={cn(
                "w-full flex items-center gap-3 rounded-lg hover:bg-sidebar-accent transition-colors outline-none group",
                isCollapsed ? "justify-center p-0" : "p-2",
              )}
            >
              <div className="w-9 h-9 rounded-full bg-gradient-primary flex items-center justify-center text-primary-foreground font-semibold shrink-0 group-hover:scale-105 transition-transform overflow-hidden ring-2 ring-background">
                {user.avatar ? (
                  <img
                    src={typeof user.avatar === 'string' ? user.avatar : ''}
                    alt={typeof user.name === 'string' ? user.name : ''}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  typeof user.name === 'string' ? user.name[0] : '?'
                )}
              </div>
              {!isCollapsed && (
                <div className="flex-1 min-w-0 text-left transition-all duration-300 opacity-100">
                  <p className="text-sm font-medium text-foreground truncate">
                    {typeof user.name === 'string' ? user.name : String(user.name ?? '')}
                  </p>
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground truncate max-w-[80px]">
                      {getRoleDisplayName(user.role)}
                    </p>
                    <ChevronRight className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </div>
              )}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            side="right"
            align={isCollapsed ? "center" : "end"}
            className="w-56"
            sideOffset={10}
          >
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium leading-none">{typeof user.name === 'string' ? user.name : String(user.name ?? '')}</p>
                <p className="text-xs leading-none text-muted-foreground">
                  {getRoleDisplayName(user.role)}
                </p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {user.role === "employee" && (
              <DropdownMenuItem className="cursor-default focus:bg-transparent">
                <div className="flex flex-1 items-center justify-between">
                  <span className="text-muted-foreground">当前绩效</span>
                  <span className="font-bold text-success">{user.score}</span>
                </div>
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate("/profile")}>
              <UserIcon className="mr-2 h-4 w-4" />
              <span>个人中心</span>
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={handleLogout}
              className="text-destructive focus:text-destructive focus:bg-destructive/10"
            >
              <LogOut className="mr-2 h-4 w-4" />
              <span>退出登录</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <ConfirmDialog {...ConfirmDialogProps} />
    </aside>
  );
}
