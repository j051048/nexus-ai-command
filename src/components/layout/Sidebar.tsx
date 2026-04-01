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
  { icon: <FileSearch size={18} />, label: "标书审阅", href: "tender-analysis", group: "销售与客关" },
  { icon: <Swords size={18} />, label: "竞品库", href: "battlecards", group: "销售与客关" },
  { icon: <FileSignature size={18} />, label: "合同管理", href: "contracts", roles: ["manager", "boss", "founder"], group: "销售与客关" },
  { icon: <Warehouse size={18} />, label: "库存管理", href: "inventory", group: "销售与客关" },
  { icon: <Briefcase size={18} />, label: "项目管理", href: "projects", group: "项目与目标" },
  { icon: <Target size={18} />, label: "目标看板", href: "target-dashboard", group: "项目与目标" },
  { icon: <TrendingUp size={18} />, label: "目标管理", href: "targets", roles: ["boss", "founder"], group: "项目与目标" },
  { icon: <BarChart3 size={18} />, label: "数据报表", href: "reports", group: "项目与目标" },
  { icon: <Calendar size={18} />, label: "OA办公", href: "oa", group: "OA/HR/财务" },
  { icon: <Fingerprint size={18} />, label: "考勤打卡", href: "oa?tab=attendance", group: "OA/HR/财务" },
  { icon: <Clock size={18} />, label: "人事中心", href: "hr", roles: ["manager", "boss", "founder"], group: "OA/HR/财务" },
  { icon: <DollarSign size={18} />, label: "财务中心", href: "finance", group: "OA/HR/财务" },
  { icon: <FileCheck size={18} />, label: "审批中心", href: "approval", group: "OA/HR/财务" },
  { icon: <Workflow size={18} />, label: "流程设计", href: "workflows", roles: ["boss", "founder"], group: "OA/HR/财务" },
  { icon: <LayoutTemplate size={18} />, label: "流程模板", href: "workflow-templates", roles: ["boss", "founder"], group: "OA/HR/财务" },
  { icon: <FileEdit size={18} />, label: "表单设计", href: "form-designer", roles: ["boss", "founder"], group: "OA/HR/财务" },
  { icon: <Wrench size={18} />, label: "工单管理", href: "work-orders", group: "OA/HR/财务" },
  { icon: <Package size={18} />, label: "资产管理", href: "assets", group: "OA/HR/财务" },
  { icon: <BookOpen size={18} />, label: "知识库", href: "knowledge", group: "知识与培训" },
  { icon: <GraduationCap size={18} />, label: "培训中心", href: "training", group: "知识与培训" },
  { icon: <Gift size={18} />, label: "激励钱包", href: "rewards", group: "知识与培训" },
  { icon: <Award size={18} />, label: "企业证照", href: "certificates", group: "知识与培训" },
  { icon: <Rocket size={18} />, label: "虚拟市场部", href: "vmd", group: "虚拟市场部" },
  { icon: <ListTodo size={18} />, label: "任务中心", href: "vmd/tasks", group: "虚拟市场部" },
  { icon: <BotIcon size={18} />, label: "Agent配置", href: "vmd/agents", group: "虚拟市场部" },
  { icon: <Target size={18} />, label: "线索管理", href: "vmd/clues", group: "虚拟市场部" },
  { icon: <ShieldCheck size={18} />, label: "合规校验", href: "vmd/compliance", group: "虚拟市场部" },
  { icon: <BarChart3 size={18} />, label: "VMD看板", href: "vmd/dashboard", group: "虚拟市场部" },
  { icon: <Network size={18} />, label: "组织架构", href: "org-chart", roles: ["boss", "founder"], group: "组织管理" },
  { icon: <Settings size={18} />, label: "企业设置", href: "company-settings", roles: ["boss", "founder"], group: "组织管理" },
  { icon: <Settings size={18} />, label: "系统设置", href: "settings", group: "系统管理" },
  { icon: <Cpu size={18} />, label: "模型管理", href: "llm/models", roles: ["boss", "founder"], group: "系统管理" },
  { icon: <DollarSign size={18} />, label: "LLM成本", href: "llm/costs", roles: ["boss", "founder"], group: "系统管理" },
  { icon: <Upload size={18} />, label: "数据导入", href: "import", roles: ["boss", "founder"], group: "系统管理" },
  { icon: <ClipboardList size={18} />, label: "审计日志", href: "audit", group: "系统管理" },
  { icon: <Puzzle size={18} />, label: "插件市场", href: "plugins", group: "系统管理" },
  { icon: <Key size={18} />, label: "API密钥", href: "api-keys", group: "系统管理" },
  { icon: <CreditCard size={18} />, label: "订阅支付", href: "payments", group: "系统管理" },
  { icon: <Bug size={18} />, label: "Agent调试", href: "agent-debug", group: "系统管理" },
  { icon: <Clock size={18} />, label: "定时任务", href: "scheduled-tasks", group: "系统管理" },
];

const NAV_GROUPS = ["AI 核心", "销售与客关", "项目与目标", "OA/HR/财务", "知识与培训", "虚拟市场部", "组织管理", "系统管理"];

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
    if (items.length === 0) return null;
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
            className="flex items-center justify-between w-full px-3 py-2 text-[10px] font-black text-white/20 uppercase tracking-[0.2em] hover:text-white/40 transition-colors"
          >
            {title}
            {isOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          </button>
        )}
        
        <ul className={cn("space-y-0.5 mt-1 transition-all", !isOpen && !isCollapsed && "hidden")}>
          {items.map((item) => {
            let badge = item.badge;
            if (item.href === 'inbox' && inboxBadgeCount > 0) badge = String(inboxBadgeCount);
            return (
              <li key={item.href}>
                <Link
                  to={`/${item.href}`}
                  onClick={onNavClick}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-xl transition-all duration-300 relative group border border-transparent",
                    isActive(item.href) 
                      ? "bg-primary/10 text-primary shadow-[inset_0_0_20px_rgba(var(--primary-rgb),0.05)] border-primary/20" 
                      : "text-white/40 hover:text-white hover:bg-white/5"
                  )}
                >
                  {isActive(item.href) && (
                    <div className="absolute left-0 top-1/4 bottom-1/4 w-1 bg-primary rounded-r-full shadow-[0_0_10px_rgba(var(--primary-rgb),0.5)]" />
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
      "bg-[#050510] border-r border-white/5 flex flex-col transition-all duration-500 ease-in-out h-full z-40 relative group/sidebar",
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

      <div className="flex-1 overflow-y-auto no-scrollbar py-2">
        {NAV_GROUPS.map(group => 
          renderNavGroup(group, NAV_CONFIG.filter(i => {
            const hasRole = !i.roles || i.roles.includes((role || user?.role || "employee") as AppRole);
            return i.group === group && hasRole;
          }))
        )}
      </div>

      <div className="p-4 border-t border-white/5 bg-white/[0.02]">
        <div className={cn("flex items-center gap-3 px-2", isCollapsed && "justify-center")}>
          <div className="w-8 h-8 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center overflow-hidden">
            {profile?.avatar ? (
              <img src={profile.avatar} alt="avatar" className="w-full h-full object-cover" />
            ) : (
              <UserIcon className="w-4 h-4 text-primary" />
            )}
          </div>
          {!isCollapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold text-white truncate">{profile?.name || "用户"}</p>
              <p className="text-[10px] text-white/40 uppercase font-bold tracking-tighter italic">{role || "销售精英"}</p>
            </div>
          )}
          {!isCollapsed && (
            <button onClick={signOut} className="p-2 text-white/30 hover:text-red-400 transition-colors">
              <LogOut size={16} />
            </button>
          )}
        </div>
      </div>
      
      <button 
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="absolute -right-3 top-20 w-6 h-6 bg-primary rounded-full md:flex items-center justify-center text-white shadow-xl hover:scale-110 active:scale-95 transition-all z-50 border-4 border-[#050510] hidden"
      >
        {isCollapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </aside>
  );
}
