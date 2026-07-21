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
  Building2,
  Contact,
  FileSignature,
  BarChart3,
  Puzzle,
  GraduationCap,
  Rocket,
  ShieldCheck,
  Shield,
  Cpu,
  Brain,
  Bug,
  Inbox,
  Wrench,
  Package,
  Warehouse,
  Workflow,
  Network,
  Search,
  Activity,
  Crosshair,
  Radar,
  Server,
  PanelsTopLeft,
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
import { activationProgress } from "@/features/activation/activationState";
import { useActivationState } from "@/hooks/useActivationState";

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
const ENABLED_MODULES_KEY = "nexus:enabled-modules";

function loadCollapsedGroups(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(COLLAPSED_GROUPS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveCollapsedGroups(state: Record<string, boolean>) {
  localStorage.setItem(COLLAPSED_GROUPS_KEY, JSON.stringify(state));
}

function loadEnabledModules(): string[] {
  try {
    const raw = localStorage.getItem(ENABLED_MODULES_KEY);
    const modules = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(modules)) return [];
    return modules.map((item) => (item === "AI 中心" ? "智能助手" : item));
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
  if (path === "knowledge" || path.startsWith("knowledge/")) return "knowledge";
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
  if (path === "growth/tenders") return "tender";
  if (path === "battlecards") return "battlecards";
  if (path === "training") return "training";
  if (path === "vmd" || path.startsWith("vmd/")) return "vmd";
  if (path === "dashboard" || path.startsWith("growth/")) return "vmd";
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
  // 一级导航围绕科学仪器销售闭环，其它模块通过二级分组和命令面板触达。
  { icon: <Crosshair size={18} />, label: "今日作战", href: "dashboard", group: "primary" },
  { icon: <Contact size={18} />, label: "客户与项目", href: "growth/accounts", group: "primary" },
  { icon: <PanelsTopLeft size={18} />, label: "方案作战", href: "growth/solutions", group: "primary" },
  { icon: <FileSearch size={18} />, label: "投标作战", href: "growth/tenders", group: "primary" },
  { icon: <BookOpen size={18} />, label: "企业资料", href: "knowledge", group: "primary" },

  // 业务域分组
  { icon: <Radar size={18} />, label: "线索雷达", href: "growth/radar", group: "客户增长" },
  { icon: <TrendingUp size={18} />, label: "销售管道", href: "sales", group: "客户增长" },
  { icon: <FileSignature size={18} />, label: "合同", href: "contracts", roles: ["manager", "boss", "founder"], group: "客户增长" },
  { icon: <Swords size={18} />, label: "竞品库", href: "battlecards", group: "客户增长" },

  // 办公域分组
  { icon: <Calendar size={18} />, label: "OA 办公", href: "oa", group: "协作" },
  { icon: <Clock size={18} />, label: "人事", href: "hr", roles: ["manager", "boss", "founder"], group: "协作" },
  { icon: <DollarSign size={18} />, label: "财务", href: "finance", group: "协作" },
  { icon: <Wrench size={18} />, label: "工单", href: "work-orders", group: "协作" },
  { icon: <Workflow size={18} />, label: "流程", href: "workflows", roles: ["boss", "founder"], group: "协作" },

  // 数据域分组
  { icon: <BarChart3 size={18} />, label: "经营复盘", href: "growth/review", group: "经营数据" },
  { icon: <BarChart3 size={18} />, label: "数据报表", href: "reports", group: "经营数据" },
  { icon: <Target size={18} />, label: "目标看板", href: "target-dashboard", group: "经营数据" },
  { icon: <BarChart3 size={18} />, label: "AI 报表引擎", href: "report-builder", roles: ["boss", "founder", "manager"], group: "经营数据" },
  { icon: <Crown size={18} />, label: "老板看板", href: "boss-dashboard", roles: ["boss", "founder"], group: "经营数据" },
  { icon: <BarChart3 size={18} />, label: "客户成功", href: "customer-success", roles: ["boss", "founder", "manager"], group: "经营数据" },

  // 资产域分组
  { icon: <Warehouse size={18} />, label: "库存", href: "inventory", group: "资产" },
  { icon: <Package size={18} />, label: "资产", href: "assets", group: "资产" },

  // AI 能力域
  { icon: <Bot size={18} />, label: "助手工作台", href: "ai-operating-system", group: "智能助手" },
  { icon: <Brain size={18} />, label: "Agent 进化中心", href: "agent-improvement-center", roles: ["boss", "founder"], group: "智能助手" },
  { icon: <Rocket size={18} />, label: "增长作战配置", href: "vmd", group: "智能助手" },
  { icon: <Puzzle size={18} />, label: "插件", href: "plugins", group: "智能助手" },
  { icon: <Cpu size={18} />, label: "模型", href: "llm/models", roles: ["boss", "founder"], group: "智能助手" },
  { icon: <ShieldCheck size={18} />, label: "工具治理", href: "tools/governance", roles: ["boss", "founder"], group: "智能助手" },
  { icon: <Activity size={18} />, label: "运行记录", href: "agent-runs", roles: ["boss", "founder"], group: "智能助手" },

  // 管理域分组
  { icon: <GraduationCap size={18} />, label: "培训", href: "training", group: "管理" },
  { icon: <Network size={18} />, label: "组织", href: "org-chart", roles: ["boss", "founder"], group: "管理" },
  { icon: <Building2 size={18} />, label: "公司设置", href: "company-settings", roles: ["boss", "founder"], group: "管理" },
  { icon: <Server size={18} />, label: "上线交付", href: "deployment-readiness", roles: ["boss", "founder"], group: "管理" },
  { icon: <Shield size={18} />, label: "权限矩阵", href: "permissions-matrix", roles: ["boss", "founder"], group: "管理" },
  { icon: <Brain size={18} />, label: "意图规则", href: "admin/intent-rules", roles: ["boss", "founder"], group: "管理" },
  { icon: <Settings size={18} />, label: "系统设置", href: "settings", roles: ["boss", "founder"], group: "管理" },
];

const NAV_GROUPS = ["primary", "客户增长", "协作", "经营数据", "资产", "智能助手", "管理"];

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
  const [enabledModules, setEnabledModules] = useState<string[]>(loadEnabledModules);
  const [showModuleManager, setShowModuleManager] = useState(false);
  const { state: activationState, isComplete: activationComplete, open: openActivation } = useActivationState();

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
    const displayTitle = title === 'primary' ? '核心空间' : title;

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
            aria-label={`${displayTitle} 分组 ${isOpen ? "收起" : "展开"}`}
            className="flex w-full items-center justify-between px-2 py-1.5 text-xs font-medium text-sidebar-foreground/45 transition-colors hover:text-sidebar-foreground/70"
          >
            {displayTitle}
            {isOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          </button>
        )}
        
        <ul className={cn("space-y-0.5 mt-1 transition-all", !isOpen && !isCollapsed && "hidden")}>
          {items.map((item) => {
            let badge = item.badge;
            if ((item.href === 'dashboard' || item.href === 'inbox') && inboxBadgeCount > 0) badge = String(inboxBadgeCount);

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
                    "group relative flex items-center gap-3 rounded-md border border-transparent px-3 py-2 text-sm transition-colors duration-150",
                    isActive(item.href)
                      ? "border-sidebar-border bg-sidebar-accent text-sidebar-foreground font-medium"
                      : "text-sidebar-foreground/65 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
                  )}
                >
                  {isActive(item.href) && (
                    <div className="absolute bottom-2 left-0 top-2 w-0.5 bg-sidebar-primary" />
                  )}
                  <span className="shrink-0">
                    {item.icon}
                  </span>
                  {!isCollapsed && (
                    <>
                      <span className="flex-1 truncate">{item.label}</span>
                      {badge && (
                        <span className="rounded border border-sidebar-border bg-background px-1.5 py-0.5 text-[10px] font-medium text-sidebar-foreground/80">{badge}</span>
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
      data-app-role={role || user?.role || "employee"}
      aria-label="主要系统导航"
      className={cn(
        "relative z-40 flex h-full flex-col border-r border-sidebar-border bg-sidebar shadow-[4px_0_20px_hsl(220_28%_12%/0.035)] transition-[width] duration-200",
        isCollapsed ? "w-16" : "w-60"
      )}
    >
      <div className={cn("flex h-14 items-center gap-3 border-b border-sidebar-border px-4", isCollapsed && "justify-center")}>
        <div 
          onClick={() => navigate("/")}
          className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-md border border-primary/70 bg-primary text-primary-foreground shadow-[0_3px_10px_hsl(var(--primary)/0.18)]"
        >
          <Bot className="h-4 w-4" />
        </div>
        {!isCollapsed && (
          <div>
            <h1 className="text-sm font-semibold text-sidebar-foreground">Nexus AI</h1>
            <p className="text-[10px] text-sidebar-foreground/45">企业工作台</p>
          </div>
        )}
      </div>

      {/* 搜索框 */}
      {!isCollapsed && (
        <div className="px-3 py-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              aria-label="搜索系统功能 (快捷键 ⌘K)"
              placeholder="搜索功能 (⌘K)"
              className="h-9 w-full rounded-md border border-sidebar-border bg-[hsl(var(--panel-strong))] pl-9 pr-3 text-sm text-sidebar-foreground shadow-[inset_0_1px_0_hsl(0_0%_100%/0.65)] placeholder:text-sidebar-foreground/40 focus:border-sidebar-primary focus:outline-none focus:ring-2 focus:ring-sidebar-primary/10"
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
          group === "primary" || (activationComplete && enabledModules.includes(group))
        ).map(group =>
          renderNavGroup(group, NAV_CONFIG.filter(i => {
            const hasRole = !i.roles || i.roles.includes((role || user?.role || "employee") as AppRole);
            return i.group === group && hasRole && isNavFeatureEnabled(i);
          }))
        )}

        {!isCollapsed && !activationComplete && (
          <div className="mx-3 mt-2 border-t border-sidebar-border pt-3">
            <button
              type="button"
              onClick={openActivation}
              className="w-full rounded-md border border-primary/20 bg-primary/[0.035] px-3 py-3 text-left transition-colors hover:bg-primary/[0.06]"
            >
              <span className="flex items-center justify-between text-xs font-medium text-sidebar-foreground">
                完成企业资料设置
                <span className="text-primary">{Math.min(activationProgress(activationState.step) + 1, 4)}/4</span>
              </span>
              <span className="mt-2 block h-1 overflow-hidden rounded-full bg-sidebar-accent">
                <span className="block h-full bg-primary" style={{ width: `${Math.min((activationProgress(activationState.step) + 1) * 25, 100)}%` }} />
              </span>
            </button>
          </div>
        )}

        {/* 模块管理器 */}
        {!isCollapsed && activationComplete && (
          <div className="px-3 mt-2 border-t border-sidebar-border pt-2">
            <button
              onClick={() => setShowModuleManager(!showModuleManager)}
              className="flex w-full items-center justify-between rounded-md px-3 py-2 text-xs font-medium text-sidebar-foreground/50 transition-colors hover:bg-sidebar-accent/40 hover:text-sidebar-foreground/75"
            >
              <span className="flex items-center gap-1.5">
                <Puzzle size={10} />
                更多应用
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
                        "flex w-full items-center justify-between rounded-md px-3 py-2 text-xs transition-colors",
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

      <div className="border-t border-sidebar-border p-3">
        <div className={cn("flex flex-col gap-3", !isCollapsed && "px-2")}>
          <div className={cn("flex", isCollapsed ? "justify-center" : "justify-end mb-2")}>
            <ThemeToggle />
          </div>
          <div 
            onClick={() => navigate("/personal-settings")}
            className={cn(
              "group flex cursor-pointer items-center gap-3 rounded-md p-2 transition-colors hover:bg-sidebar-accent",
              isCollapsed && "justify-center"
            )}
          >
            <div className="relative flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full border border-sidebar-border bg-sidebar-accent/50 transition-colors group-hover:border-sidebar-primary/30">
              {profile?.avatar ? (
                <img src={profile.avatar} alt="avatar" className="w-full h-full object-cover" />
              ) : (
                <UserIcon className="w-5 h-5 text-primary" />
              )}
              <div className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-sidebar bg-success"></div>
            </div>
            {!isCollapsed && (
              <div className="flex-1 min-w-0 transition-opacity duration-300">
                <p className="truncate text-xs font-medium text-sidebar-foreground transition-colors group-hover:text-sidebar-primary">
                  {profile?.name || "用户"}
                </p>
                <div className="flex items-center gap-1">
                  <p className="truncate text-[11px] text-sidebar-foreground/50">
                    {role === 'boss' || role === 'founder' ? '管理者' : role === 'manager' ? '团队负责人' : '成员'}
                  </p>
                  <Settings size={10} className="text-sidebar-foreground/20 group-hover:text-sidebar-primary/60 transition-colors" />
                </div>
              </div>
            )}
          </div>
          
          {!isCollapsed && (
            <button 
              onClick={signOut}
              className="mt-1 flex items-center gap-2 rounded-md px-3 py-2 text-xs text-sidebar-foreground/50 transition-colors hover:bg-destructive/10 hover:text-destructive"
            >
              <LogOut size={12} />
              <span>退出登录</span>
            </button>
          )}
        </div>
      </div>
      
      <button 
        onClick={() => setIsCollapsed(!isCollapsed)}
        aria-label={isCollapsed ? "展开侧边栏" : "折叠侧边栏"}
        aria-expanded={!isCollapsed}
        className="absolute -right-3 top-20 z-50 hidden h-6 w-6 items-center justify-center rounded-md border bg-background text-muted-foreground shadow-sm transition-colors hover:text-foreground md:flex"
      >
        {isCollapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </aside>
  );
}

export const Sidebar = React.memo(SidebarComponent);
