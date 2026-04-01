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
  { icon: <Crown size={18} />, label: "总控中心", href: "boss-dashboard", roles: ["boss", "founder"], group: "AI 核心" },
  { icon: <LayoutDashboard size={18} />, label: "战绩中心", href: "dashboard", group: "AI 核心" },
  { icon: <Inbox size={18} />, label: "待办中心", href: "inbox", group: "AI 核心" },
  { icon: <TrendingUp size={18} />, label: "销售AI管理", href: "sales", roles: ["employee", "manager", "boss", "founder"], group: "销售与客关" },
  { icon: <Contact size={18} />, label: "CRM管理", href: "crm", group: "销售与客关" },
  { icon: <Briefcase size={18} />, label: "项目管理", href: "projects", group: "项目与目标" },
  { icon: <Target size={18} />, label: "目标看板", href: "target-dashboard", group: "项目与目标" },
  { icon: <Calendar size={18} />, label: "OA办公", href: "oa", group: "OA/HR/财务" },
  { icon: <DollarSign size={18} />, label: "财务中心", href: "finance", group: "OA/HR/财务" },
  { icon: <BookOpen size={18} />, label: "知识库", href: "knowledge", group: "知识与培训" },
  { icon: <Rocket size={18} />, label: "虚拟市场部", href: "vmd", group: "虚拟市场部" },
  { icon: <Network size={18} />, label: "组织架构", href: "org-chart", roles: ["boss", "founder"], group: "组织管理" },
  { icon: <Settings size={18} />, label: "系统设置", href: "settings", group: "系统管理" }
];

const NAV_GROUPS = ["AI 核心", "销售与客关", "项目与目标", "OA/HR/财务", "知识与培训", "虚拟市场部", "组织管理", "系统管理"];

export function Sidebar({ onNavClick }: { onNavClick?: () => void }) {
  const { user } = useUser();
  const { role, signOut, profile } = useAuth();
  const [orgName, setOrgName] = useState("Nexus AI");
  const location = useLocation();
  const navigate = useNavigate();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>(loadCollapsedGroups);
  const [pinnedHrefs, setPinnedHrefs] = useState<string[]>(loadPinnedItems);

  const isActive = (href: string) => {
    const p = location.pathname.replace(/^\//, '');
    return p === href || (href === 'dashboard' && p === '');
  };

  const renderNavGroup = (title: string, items: NavItem[]) => {
    if (items.length === 0) return null;
    const isOpen = !collapsedGroups[title];

    return (
      <div key={title} className="mb-4 px-3">
        {!isCollapsed && (
          <button 
            onClick={() => {
              const next = { ...collapsedGroups, [title]: !collapsedGroups[title] };
              setCollapsedGroups(next);
              saveCollapsedGroups(next);
            }}
            className="flex items-center justify-between w-full px-3 py-2 text-[10px] font-black text-white/30 uppercase tracking-[0.2em] hover:text-white/60 transition-colors"
          >
            {title}
            {isOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          </button>
        )}
        
        <ul className={cn("space-y-1 mt-1", !isOpen && !isCollapsed && "hidden")}>
          {items.map((item) => (
            <li key={item.href}>
              <Link
                to={`/${item.href}`}
                onClick={onNavClick}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-300 relative group",
                  isActive(item.href) 
                    ? "bg-primary/10 text-primary shadow-[inset_0_0_20px_rgba(var(--primary-rgb),0.05)] border border-primary/20" 
                    : "text-white/50 hover:text-white hover:bg-white/5 border border-transparent"
                )}
              >
                {isActive(item.href) && (
                  <div className="absolute left-0 top-1/4 bottom-1/4 w-1 bg-primary rounded-r-full shadow-[0_0_10px_rgba(var(--primary-rgb),0.5)]" />
                )}
                <span className={cn("shrink-0 transition-transform duration-300", !isActive(item.href) && "group-hover:scale-110")}>
                  {item.icon}
                </span>
                {!isCollapsed && <span className="text-sm font-bold tracking-tight truncate">{item.label}</span>}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <aside className={cn(
      "bg-[#050510] border-r border-white/5 flex flex-col transition-all duration-500 ease-in-out h-full z-40 relative",
      isCollapsed ? "w-[80px]" : "w-64"
    )}>
      {/* Logo Area */}
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

      <div className="flex-1 overflow-y-auto no-scrollbar py-2">
        {NAV_GROUPS.map(group => 
          renderNavGroup(group, NAV_CONFIG.filter(i => i.group === group))
        )}
      </div>

      {/* Footer / User Profile */}
      <div className="p-4 border-t border-white/5 bg-white/[0.02]">
        <div className={cn("flex items-center gap-3 px-2", isCollapsed && "justify-center")}>
          <div className="w-8 h-8 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center overflow-hidden">
            {profile?.avatar_url ? (
              <img src={profile.avatar_url} alt="avatar" className="w-full h-full object-cover" />
            ) : (
              <UserIcon className="w-4 h-4 text-primary" />
            )}
          </div>
          {!isCollapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold text-white truncate">{profile?.full_name || "用户"}</p>
              <p className="text-[10px] text-white/40 uppercase font-bold tracking-tighter italic">创始人</p>
            </div>
          )}
          {!isCollapsed && (
            <button onClick={signOut} className="p-2 text-white/30 hover:text-red-400 transition-colors">
              <LogOut size={16} />
            </button>
          )}
        </div>
      </div>
      
      {/* Collapse Trigger Tooltip-like Button */}
      <button 
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="absolute -right-3 top-20 w-6 h-6 bg-primary rounded-full flex items-center justify-center text-white shadow-xl hover:scale-110 active:scale-95 transition-all z-50 border-4 border-[#050510]"
      >
        {isCollapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </aside>
  );
}
