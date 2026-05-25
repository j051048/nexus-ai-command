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
  Shield,
  Cpu,
  Brain,
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
  Network,
  Search,
  Sparkles,
  Activity,
  Server,
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
import { isModuleEnabled, type ModuleFlag } from "@/config/featureFlags";

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

const COLLAPSED_GROUPS_KEY = "nexus:sidebar-collapsed-groups";
const PINNED_ITEMS_KEY = "nexus:sidebar-pinned-items";
const ENABLED_MODULES_KEY = "nexus:enabled-modules";

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

function loadEnabledModules(): string[] {
  try {
    const raw = localStorage.getItem(ENABLED_MODULES_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveEnabledModules(modules: string[]) {
  localStorage.setItem(ENABLED_MODULES_KEY, JSON.stringify(modules));
}

function moduleForHref(href: string): ModuleFlag | null {
  const path = href.split("?")[0].replace(/^\/+/, "");
  if (path === "crm") return "crm";
  if (path === "contracts" || path === "documents") return "documents";
  if (path === "knowledge") return "knowledge";
  if (path === "approval") return "approval";
  if (path === "sales") return "sales";
  if (path === "projects") return "projects";
  if (path === "oa") return "oa";
  if (path === "hr") return "hr";
  if (path === "finance") return "finance";
  if (path === "work-orders") return "work_orders";
  if (path === "reports") return "reports";
  if (path === "report-builder") return "report_builder";
  if (path === "inventory") return "inventory";
  if (path === "assets") return "assets";
  if (path === "certificates") return "certificates";
  if (path === "workflows" || path.startsWith("workflows/") || path === "workflow-templates") return "workflow_designer";
  if (path === "form-designer" || path.startsWith("form-designer/")) return "form_designer";
  if (path === "custom-dashboard") return "custom_dashboard";
  if (path === "tender-analysis") return "tender";
  if (path === "battlecards") return "battlecards";
  if (path === "training") return "training";
  if (path === "vmd" || path.startsWith("vmd/")) return "vmd";
  if (path === "plugins") return "plugins";
  if (path === "soul-document") return "soul_document";
  if (path === "dev/animations" || path === "agent-debug") return "dev_tools";
  return null;
}

function isNavFeatureEnabled(item: NavItem): boolean {
  const moduleFlag = moduleForHref(item.href);
  return moduleFlag ? isModuleEnabled(moduleFlag) : true;
}

const NAV_CONFIG: NavItem[] = [
  // 一级导航：默认只暴露 5 个产品空间，其它模块通过“更多模块”和命令面板触达。
  { icon: <Inbox size={18} />, label: "行动台", href: "dashboard", group: "primary" },
  { icon: <Contact size={18} />, label: "CRM", href: "crm", group: "primary" },
  { icon: <Briefcase size={18} />, label: "工作台", href: "workbench", group: "primary" },
  { icon: <BarChart3 size={18} />, label: "数据", href: "data", group: "primary" },
  { icon: <Bot size={18} />, label: "AI 中心", href: "ai-center", group: "primary" },
  { icon: <Sparkles size={18} />, label: "AI 作战系统", href: "ai-operating-system", group: "primary" },
  { icon: <Brain size={18} />, label: "Agent 进化中心", href: "agent-improvement-center", roles: ["boss", "founder"], group: "primary" },

  // 业务域分组
  { icon: <TrendingUp size={18} />, label: "销售管道", href: "sales", group: "业务" },
  { icon: <FileSignature size={18} />, label: "合同", href: "contracts", roles: ["manager", "boss", "founder"], group: "业务" },
  { icon: <FileSearch size={18} />, label: "标书", href: "tender-analysis", group: "业务" },
  { icon: <Swords size={18} />, label: "竞品库", href: "battlecards", group: "业务" },

  // 办公域分组
  { icon: <Calendar size={18} />, label: "OA办公", href: "oa", group: "办公" },
  { icon: <Clock size={18} />, label: "人事", href: "hr", roles: ["manager", "boss", "founder"], group: "办公" },
  { icon: <DollarSign size={18} />, label: "财务", href: "finance", group: "办公" },
  { icon: <Wrench size={18} />, label: "工单", href: "work-orders", group: "办公" },

  // 数据域分组
  { icon: <BarChart3 size={18} />, label: "数据报表", href: "reports", group: "数据" },
  { icon: <Target size={18} />, label: "目标看板", href: "target-dashboard", group: "数据" },
  { icon: <Sparkles size={18} />, label: "AI 报表引擎", href: "report-builder", roles: ["boss", "founder", "manager"], group: "数据" },
  { icon: <Crown size={18} />, label: "总控中心", href: "boss-dashboard", roles: ["boss", "founder"], group: "数据" },

  // 资产域分组
  { icon: <Warehouse size={18} />, label: "库存", href: "inventory", group: "资产" },
  { icon: <Package size={18} />, label: "资产", href: "assets", group: "资产" },

  // 管理域分组
  { icon: <Workflow size={18} />, label: "流程", href: "workflows", roles: ["boss", "founder"], group: "管理" },
  { icon: <BookOpen size={18} />, label: "知识库", href: "knowledge", group: "管理" },
  { icon: <GraduationCap size={18} />, label: "培训", href: "training", group: "管理" },
  { icon: <Rocket size={18} />, label: "VMD", href: "vmd", group: "管理" },
  { icon: <Network size={18} />, label: "组织", href: "org-chart", roles: ["boss", "founder"], group: "管理" },
  { icon: <Building2 size={18} />, label: "公司设置", href: "company-settings", roles: ["boss", "founder"], group: "管理" },
  { icon: <Cpu size={18} />, label: "模型", href: "llm/models", roles: ["boss", "founder"], group: "管理" },
  { icon: <Activity size={18} />, label: "Agent Runs", href: "agent-runs", roles: ["boss", "founder"], group: "管理" },
  { icon: <Server size={18} />, label: "上线交付", href: "deployment-readiness", roles: ["boss", "founder"], group: "管理" },
  { icon: <BarChart3 size={18} />, label: "客户成功", href: "customer-success", roles: ["boss", "founder", "manager"], group: "管理" },
  { icon: <Shield size={18} />, label: "权限矩阵", href: "permissions-matrix", roles: ["boss", "founder"], group: "管理" },
  { icon: <ShieldCheck size={18} />, label: "Tool 治理", href: "tools/governance", roles: ["boss", "founder"], group: "管理" },
  { icon: <Brain size={18} />, label: "意图规则", href: "admin/intent-rules", roles: ["boss", "founder"], group: "管理" },
  { icon: <Settings size={18} />, label: "系统设置", href: "settings", roles: ["boss", "founder"], group: "管理" },
];

const NAV_GROUPS = ["primary", "业务", "办公", "数据", "资产", "管理"];

const SPACE_MATCH_PREFIXES: Record<string, string[]> = {
  workbench: [
    "projects",
    "approval",
    "contracts",
    "oa",
    "hr",
    "finance",
    "work-orders",
    "workflows",
    "workflow-templates",
    "form-designer",
    "org-chart",
  ],
  data: [
    "reports",
    "report-builder",
    "target-dashboard",
    "performance-dashboard",
    "boss-dashboard",
    "custom-dashboard",
    "customer-success",
  ],
  "ai-center": [
    "knowledge",
    "ai-operating-system",
    "agent-improvement-center",
    "vmd",
    "plugins",
    "llm",
    "tools",
    "agent-runs",
    "agent-debug",
    "scheduled-tasks",
    "admin",
  ],
};

function SidebarComponent({ onNavClick }: { onNavClick?: () => void }) {
  const { user } = useUser();
  const { role, signOut, profile } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>(loadCollapsedGroups);
  const [pinnedHrefs, setPinnedHrefs] = useState<string[]>(loadPinnedItems);
  const [enabledModules, setEnabledModules] = useState<string[]>(loadEnabledModules);
  const [showModuleManager, setShowModuleManager] = useState(false);

  const { data: exceptions = [] } = useExceptions();
  const pendingApprovalsQuery = usePendingApprovalsCount();
  const unreadCountQuery = useUnreadCount();
  const inboxBadgeCount = (pendingApprovalsQuery.data ?? 0) + exceptions.length + (unreadCountQuery.data ?? 0);

  const isActive = (href: string) => {
    const p = location.pathname.replace(/^\//, '');
    const hrefPath = href.split("?")[0];
    const spaceMatches = SPACE_MATCH_PREFIXES[hrefPath]?.some(
      (prefix) => p === prefix || p.startsWith(`${prefix}/`),
    );
    return p === hrefPath || (hrefPath === 'dashboard' && p === '') || p.startsWith(hrefPath + '/') || Boolean(spaceMatches);
  };

  const renderNavGroup = (title: string, items: NavItem[]) => {
    if (!items || items.length === 0) return null;
    const groupActive = items.some(i => isActive(i.href));
    const isOpen = groupActive || !collapsedGroups[title];

    return (
      <div key={title} className="mb-2 px-3">
        {!isCollapsed && (
          <button 
            onClick={() => {
              const next = { ...collapsedGroups, [title]: !collapsedGroups[title] };
              setCollapsedGroups(next);
              saveCollapsedGroups(next);
            }}
            aria-expanded={isOpen}
            aria-label={`${title} 分组 ${isOpen ? "收起" : "展开"}`}
            className="flex items-center justify-between w-full px-3 py-2 text-micro font-black text-sidebar-foreground/30 uppercase tracking-[0.2em] hover:text-sidebar-foreground/50 transition-colors"
          >
            {title}
            {isOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          </button>
        )}
        
        <ul className={cn("space-y-0.5 mt-1 transition-all", !isOpen && !isCollapsed && "hidden")}>
          {items.map((item) => {
            let badge = item.badge;
            if (item.href === 'inbox' && inboxBadgeCount > 0) badge = String(inboxBadgeCount);

            const handleClick = (e: React.MouseEvent) => {
              if (item.href === '#ai-chat') {
                e.preventDefault();
                window.dispatchEvent(new CustomEvent('proactive-chat'));
                onNavClick?.();
              } else {
                onNavClick?.();
              }
            };

            return (
              <li key={item.href}>
                <Link
                  to={`/${item.href}`}
                  onClick={handleClick}
                  className={cn(
                    "flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition-all duration-300 relative group border border-transparent",
                    isActive(item.href)
                      ? "bg-sidebar-accent text-sidebar-foreground shadow-[var(--shadow-card)] border-sidebar-border font-bold"
                      : "text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 hover:border-sidebar-border/50"
                  )}
                >
                  {isActive(item.href) && (
                    <div className="absolute left-0 top-1/4 bottom-1/4 w-1 bg-sidebar-primary rounded-r-full shadow-[0_0_6px_hsl(var(--sidebar-primary)/0.5)]" />
                  )}
                  <span className={cn("shrink-0 transition-transform duration-300", !isActive(item.href) && "group-hover:scale-110")}>
                    {item.icon}
                  </span>
                  {!isCollapsed && (
                    <>
                      <span className="text-sm font-semibold tracking-tight truncate flex-1">{item.label}</span>
                      {badge && (
                        <span className="px-1.5 py-0.5 rounded-full bg-sidebar-accent text-sidebar-foreground/90 text-micro font-bold border border-sidebar-border">{badge}</span>
                      )}
                    </>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    );
  };

  return (
    <aside 
      data-testid="sidebar-main" 
      aria-label="主要系统导航"
      className={cn(
        "bg-sidebar/95 backdrop-blur-xl border-r border-sidebar-border/30 flex flex-col transition-all duration-500 ease-in-out h-full z-40 relative group/sidebar shadow-2xl",
        isCollapsed ? "w-[80px]" : "w-64"
      )}
    >
      <div className={cn("p-6 flex items-center gap-3", isCollapsed && "justify-center")}>
        <div 
          onClick={() => navigate("/")}
          className="w-10 h-10 rounded-2xl bg-gradient-to-br from-primary via-primary/80 to-primary/60 flex items-center justify-center shadow-md shadow-primary/10 cursor-pointer hover:rotate-6 transition-transform"
        >
          <Bot className="w-6 h-6 text-sidebar-primary-foreground" />
        </div>
        {!isCollapsed && (
          <div className="animate-fade-in">
            <h1 className="text-sm font-extrabold text-sidebar-foreground tracking-tight uppercase">Nexus AI</h1>
            <p className="text-micro text-sidebar-foreground/40 font-mono font-bold tracking-wider">COMMAND CENTER</p>
          </div>
        )}
      </div>

      {/* 搜索框 */}
      {!isCollapsed && (
        <div className="px-6 pb-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              aria-label="搜索系统功能 (快捷键 ⌘K)"
              placeholder="搜索功能 (⌘K)"
              className="w-full pl-9 pr-3 h-10 bg-sidebar-accent/30 border border-sidebar-border rounded-xl text-sm text-sidebar-foreground placeholder:text-sidebar-foreground/40 focus:outline-none focus:border-sidebar-primary/30 focus:bg-sidebar-accent/50 transition-all shadow-inner"
              onFocus={() => {
                const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true });
                document.dispatchEvent(event);
              }}
            />
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto no-scrollbar py-2">
        {NAV_GROUPS.filter(group =>
          group === "primary" || enabledModules.includes(group)
        ).map(group =>
          renderNavGroup(group, NAV_CONFIG.filter(i => {
            const hasRole = !i.roles || i.roles.includes((role || user?.role || "employee") as AppRole);
            return i.group === group && hasRole && isNavFeatureEnabled(i);
          }))
        )}

        {/* 模块管理器 */}
        {!isCollapsed && (
          <div className="px-3 mt-2 border-t border-sidebar-border pt-2">
            <button
              onClick={() => setShowModuleManager(!showModuleManager)}
              className="flex items-center justify-between w-full px-3 py-2 text-micro font-black text-sidebar-foreground/30 uppercase tracking-[0.2em] hover:text-sidebar-foreground/50 transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <Puzzle size={10} />
                更多模块
              </span>
              {showModuleManager ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
            </button>
            {showModuleManager && (
              <div className="space-y-1 mt-1">
                {NAV_GROUPS.filter(g => g !== "primary").map(group => {
                  const enabled = enabledModules.includes(group);
                  const groupItems = NAV_CONFIG.filter(i => {
                    const hasRole = !i.roles || i.roles.includes((role || user?.role || "employee") as AppRole);
                    return i.group === group && hasRole && isNavFeatureEnabled(i);
                  });
                  if (groupItems.length === 0) return null;
                  return (
                    <button
                      key={group}
                      onClick={() => {
                        const next = enabled
                          ? enabledModules.filter(m => m !== group)
                          : [...enabledModules, group];
                        setEnabledModules(next);
                        saveEnabledModules(next);
                      }}
                      className={cn(
                        "flex items-center justify-between w-full px-3 py-2 rounded-lg text-xs transition-all",
                        enabled
                          ? "text-sidebar-foreground/80 bg-sidebar-accent/50"
                          : "text-sidebar-foreground/40 hover:text-sidebar-foreground/60 hover:bg-sidebar-accent/20"
                      )}
                    >
                      <span>{group} ({groupItems.length})</span>
                      <div className={cn(
                        "w-7 h-4 rounded-full transition-colors flex items-center px-0.5",
                        enabled ? "bg-primary" : "bg-sidebar-accent"
                      )}>
                        <div className={cn(
                          "w-3 h-3 rounded-full bg-sidebar-foreground transition-transform",
                          enabled ? "translate-x-3" : "translate-x-0"
                        )} />
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="p-element border-t border-sidebar-border bg-gradient-to-t from-sidebar/40 to-transparent backdrop-blur-sm">
        <div className={cn("flex flex-col gap-3", !isCollapsed && "px-2")}>
          <div className={cn("flex", isCollapsed ? "justify-center" : "justify-end mb-2")}>
            <ThemeToggle />
          </div>
          <div 
            onClick={() => navigate("/personal-settings")}
            className={cn(
              "flex items-center gap-3 p-2 rounded-2xl cursor-pointer hover:bg-sidebar-accent transition-all duration-300 group",
              isCollapsed && "justify-center"
            )}
          >
            <div className="relative shrink-0 w-9 h-9 rounded-full bg-sidebar-accent/50 border border-sidebar-border flex items-center justify-center overflow-hidden group-hover:border-sidebar-primary/30 group-hover:shadow-[var(--shadow-card)] transition-all">
              {profile?.avatar ? (
                <img src={profile.avatar} alt="avatar" className="w-full h-full object-cover" />
              ) : (
                <UserIcon className="w-5 h-5 text-primary" />
              )}
              <div className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-success border-2 border-sidebar rounded-full shadow-[0_0_8px_hsl(var(--success)/0.6)]"></div>
            </div>
            {!isCollapsed && (
              <div className="flex-1 min-w-0 transition-opacity duration-300">
                <p className="text-xs font-bold text-sidebar-foreground group-hover:text-sidebar-primary transition-colors truncate">
                  {(() => {
                    if (import.meta.env.DEV) console.log('[Sidebar] Rendering name with profile:', profile?.name);
                    return profile?.name || "BOSS";
                  })()}
                </p>
                <div className="flex items-center gap-1">
                  <p className="text-micro text-sidebar-foreground/50 uppercase font-bold tracking-tighter italic truncate">
                    {role || "顶级精英"}
                  </p>
                  <Settings size={10} className="text-sidebar-foreground/20 group-hover:text-sidebar-primary/60 transition-colors" />
                </div>
              </div>
            )}
          </div>
          
          {!isCollapsed && (
            <button 
              onClick={signOut}
              className="flex items-center gap-2 mt-1 px-3 py-2 text-micro font-bold uppercase tracking-widest text-sidebar-foreground/50 hover:text-destructive hover:bg-destructive/10 rounded-xl transition-all duration-300 group/logout"
            >
              <LogOut size={12} className="group-hover:rotate-12 transition-transform" />
              <span>Sign Out Safely</span>
            </button>
          )}
        </div>
      </div>
      
      <button 
        onClick={() => setIsCollapsed(!isCollapsed)}
        aria-label={isCollapsed ? "展开侧边栏" : "折叠侧边栏"}
        aria-expanded={!isCollapsed}
        className="absolute -right-3 top-20 w-6 h-6 bg-sidebar-primary rounded-full md:flex items-center justify-center text-sidebar-primary-foreground shadow-sm shadow-primary/20 hover:scale-110 hover:shadow-md hover:shadow-primary/30 active:scale-95 transition-all z-50 border-4 border-sidebar hidden"
      >
        {isCollapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </aside>
  );
}

export const Sidebar = React.memo(SidebarComponent);
