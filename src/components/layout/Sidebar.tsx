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
  Settings,
  Bot,
  LogOut,
  ChevronRight,
  ChevronDown,
  User as UserIcon,
  ChevronLeft,
  Puzzle,
  Search,
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
import { activationProgress } from "@/features/activation/activationState";
import { useActivationState } from "@/hooks/useActivationState";
import {
  isNavFeatureEnabled,
  NAV_CONFIG,
  NAV_GROUPS,
  SPACE_MATCH_PREFIXES,
  type AppRole,
  type NavItem,
} from "@/config/navigation";

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
        
        <ul className={cn("mt-1 space-y-0.5", !isOpen && !isCollapsed && "hidden")}>
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
