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
  Network,
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

const NAV_CONFIG: NavItem[] = [
  // 一级导航 (8项高频)
  { icon: <LayoutDashboard size={18} />, label: "工作台", href: "dashboard", group: "primary" },
  { icon: <Inbox size={18} />, label: "待办", href: "inbox", group: "primary" },
  { icon: <TrendingUp size={18} />, label: "销售", href: "sales", group: "primary" },
  { icon: <Contact size={18} />, label: "客户", href: "crm", group: "primary" },
  { icon: <FileCheck size={18} />, label: "审批", href: "approval", group: "primary" },
  { icon: <Briefcase size={18} />, label: "项目", href: "projects", group: "primary" },
  { icon: <Bot size={18} />, label: "AI助手", href: "#ai-chat", group: "primary" },
  { icon: <Settings size={18} />, label: "设置", href: "settings", group: "primary" },

  // 二级导航 (折叠在"更多"中)
  { icon: <Crown size={18} />, label: "总控中心", href: "boss-dashboard", roles: ["boss", "founder"], group: "更多" },
  { icon: <Swords size={18} />, label: "竞品库", href: "battlecards", group: "更多" },
  { icon: <Target size={18} />, label: "目标看板", href: "target-dashboard", group: "更多" },
  { icon: <BarChart3 size={18} />, label: "数据报表", href: "reports", group: "更多" },
  { icon: <Calendar size={18} />, label: "OA办公", href: "oa", group: "更多" },
  { icon: <Clock size={18} />, label: "人事", href: "hr", roles: ["manager", "boss", "founder"], group: "更多" },
  { icon: <DollarSign size={18} />, label: "财务", href: "finance", group: "更多" },
  { icon: <FileSearch size={18} />, label: "标书", href: "tender-analysis", group: "更多" },
  { icon: <FileSignature size={18} />, label: "合同", href: "contracts", roles: ["manager", "boss", "founder"], group: "更多" },
  { icon: <Warehouse size={18} />, label: "库存", href: "inventory", group: "更多" },
  { icon: <Workflow size={18} />, label: "流程", href: "workflows", roles: ["boss", "founder"], group: "更多" },
  { icon: <Wrench size={18} />, label: "工单", href: "work-orders", group: "更多" },
  { icon: <Package size={18} />, label: "资产", href: "assets", group: "更多" },
  { icon: <BookOpen size={18} />, label: "知识库", href: "knowledge", group: "更多" },
  { icon: <GraduationCap size={18} />, label: "培训", href: "training", group: "更多" },
  { icon: <Gift size={18} />, label: "激励", href: "rewards", group: "更多" },
  { icon: <Rocket size={18} />, label: "VMD", href: "vmd", group: "更多" },
  { icon: <Network size={18} />, label: "组织", href: "org-chart", roles: ["boss", "founder"], group: "更多" },
  { icon: <Building2 size={18} />, label: "公司设置", href: "company-settings", roles: ["boss", "founder"], group: "更多" },
  { icon: <Cpu size={18} />, label: "模型", href: "llm/models", roles: ["boss", "founder"], group: "更多" },
];

const NAV_GROUPS = ["primary", "更多"];

export function Sidebar({ onNavClick }: { onNavClick?: () => void }) {
  const { user } = useUser();
  const { role, signOut, profile } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>(loadCollapsedGroups);
  const [pinnedHrefs, setPinnedHrefs] = useState<string[]>(loadPinnedItems);

  const { data: exceptions = [] } = useExceptions();
  const pendingApprovalsQuery = usePendingApprovalsCount();
  const unreadCountQuery = useUnreadCount();
  const inboxBadgeCount = (pendingApprovalsQuery.data ?? 0) + exceptions.length + (unreadCountQuery.data ?? 0);

  const isActive = (href: string) => {
    const p = location.pathname.replace(/^\//, '');
    const hrefPath = href.split("?")[0];
    return p === hrefPath || (hrefPath === 'dashboard' && p === '') || p.startsWith(hrefPath + '/');
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
            className="flex items-center justify-between w-full px-3 py-2 text-[10px] font-black text-white/30 uppercase tracking-[0.2em] hover:text-white/50 transition-colors"
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
                    "flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-300 relative group border border-transparent",
                    isActive(item.href)
                      ? "bg-primary/15 text-white shadow-[0_0_20px_rgba(59,130,246,0.15)] border-primary/30 font-semibold"
                      : "text-white/50 hover:text-white hover:bg-white/8 hover:border-white/10"
                  )}
                >
                  {isActive(item.href) && (
                    <div className="absolute left-0 top-1/4 bottom-1/4 w-1 bg-primary rounded-r-full shadow-[0_0_16px_rgba(59,130,246,0.8)]" />
                  )}
                  <span className={cn("shrink-0 transition-transform duration-300", !isActive(item.href) && "group-hover:scale-110")}>
                    {item.icon}
                  </span>
                  {!isCollapsed && (
                    <>
                      <span className="text-sm font-bold tracking-tight truncate flex-1">{item.label}</span>
                      {badge && (
                        <span className="px-1.5 py-0.5 rounded-full bg-primary/20 text-primary text-[10px] font-black">{badge}</span>
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
    <aside className={cn(
      "bg-gradient-to-b from-[#141b2e] to-[#0d1220] border-r border-white/10 flex flex-col transition-all duration-500 ease-in-out h-full z-40 relative group/sidebar shadow-2xl",
      isCollapsed ? "w-[80px]" : "w-64"
    )}>
      <div className={cn("p-6 flex items-center gap-3", isCollapsed && "justify-center")}>
        <div 
          onClick={() => navigate("/")}
          className="w-10 h-10 rounded-2xl bg-gradient-to-br from-primary via-primary/50 to-purple-600 flex items-center justify-center shadow-lg shadow-primary/20 cursor-pointer hover:rotate-6 transition-transform"
        >
          <Bot className="w-6 h-6 text-white" />
        </div>
        {!isCollapsed && (
          <div className="animate-fade-in">
            <h1 className="text-sm font-black text-white tracking-tighter uppercase">Nexus AI</h1>
            <p className="text-[10px] text-primary/50 font-mono font-bold">COMMAND CENTER</p>
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
              placeholder="搜索功能 (⌘K)"
              className="w-full pl-9 pr-3 h-9 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-primary/50 focus:bg-white/10 transition-all"
              onFocus={() => {
                const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true });
                document.dispatchEvent(event);
              }}
            />
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto no-scrollbar py-2">
        {NAV_GROUPS.map(group => 
          renderNavGroup(group, NAV_CONFIG.filter(i => {
            const hasRole = !i.roles || i.roles.includes((role || user?.role || "employee") as AppRole);
            return i.group === group && hasRole;
          }))
        )}
      </div>

      <div className="p-4 border-t border-white/10 bg-gradient-to-t from-black/20 to-transparent backdrop-blur-sm">
        <div className={cn("flex flex-col gap-3", !isCollapsed && "px-2")}>
          <div className={cn("flex", isCollapsed ? "justify-center" : "justify-end mb-2")}>
            <ThemeToggle />
          </div>
          <div 
            onClick={() => navigate("/personal-settings")}
            className={cn(
              "flex items-center gap-3 p-2 rounded-2xl cursor-pointer hover:bg-white/10 transition-all duration-300 group",
              isCollapsed && "justify-center"
            )}
          >
            <div className="relative shrink-0 w-9 h-9 rounded-full bg-primary/25 border border-primary/40 flex items-center justify-center overflow-hidden group-hover:border-primary/70 group-hover:shadow-[0_0_12px_rgba(59,130,246,0.4)] transition-all">
              {profile?.avatar ? (
                <img src={profile.avatar} alt="avatar" className="w-full h-full object-cover" />
              ) : (
                <UserIcon className="w-5 h-5 text-primary" />
              )}
              <div className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-green-400 border-2 border-[#141b2e] rounded-full shadow-[0_0_8px_rgba(74,222,128,0.6)]"></div>
            </div>
            {!isCollapsed && (
              <div className="flex-1 min-w-0 transition-opacity duration-300">
                <p className="text-xs font-bold text-white group-hover:text-primary transition-colors truncate">
                  {profile?.name || "BOSS"}
                </p>
                <div className="flex items-center gap-1">
                  <p className="text-[10px] text-white/50 uppercase font-bold tracking-tighter italic truncate">
                    {role || "顶级精英"}
                  </p>
                  <Settings size={10} className="text-white/20 group-hover:text-primary/60 transition-colors" />
                </div>
              </div>
            )}
          </div>
          
          {!isCollapsed && (
            <button 
              onClick={signOut}
              className="flex items-center gap-2 mt-1 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-white/30 hover:text-red-400 hover:bg-red-500/15 rounded-xl transition-all duration-300 group/logout"
            >
              <LogOut size={12} className="group-hover:rotate-12 transition-transform" />
              <span>Sign Out Safely</span>
            </button>
          )}
        </div>
      </div>
      
      <button 
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="absolute -right-3 top-20 w-6 h-6 bg-primary rounded-full md:flex items-center justify-center text-white shadow-[0_0_16px_rgba(59,130,246,0.5)] hover:scale-110 hover:shadow-[0_0_24px_rgba(59,130,246,0.7)] active:scale-95 transition-all z-50 border-4 border-[#141b2e] hidden"
      >
        {isCollapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </aside>
  );
}
