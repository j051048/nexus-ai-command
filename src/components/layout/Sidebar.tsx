import React, { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useUser } from "@/contexts/UserContext";
import { useAuth } from "@/components/auth/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { cn } from "@/lib/utils";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useConfirmDialog } from "@/hooks/useConfirmDialog";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
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
  User as UserIcon,
  Briefcase,
  FileSearch,
  Swords,
  Target,
  Calendar,
  DollarSign,
  Clock,
  ChevronLeft,
  Menu,
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

type AppRole = "boss" | "manager" | "ai_assistant" | "employee" | "founder";

interface NavItem {
  icon: React.ReactNode;
  label: string;
  href: string;
  badge?: string;
  badgeType?: "primary" | "success" | "warning";
  roles?: AppRole[]; // undefined = 所有人可见
  group: string; // 菜单分组
}

// 统一导航配置 — 单一数据源，通过 roles 和 group 控制可见性
const NAV_CONFIG: NavItem[] = [
  // AI 核心指挥
  {
    icon: <Crown size={20} />,
    label: "总控中心",
    href: "boss-dashboard",
    roles: ["boss", "founder"],
    group: "AI 核心指挥",
  },
  {
    icon: <LayoutDashboard size={20} />,
    label: "战绩中心",
    href: "dashboard",
    group: "AI 核心指挥",
  },
  {
    icon: <FileSearch size={20} />,
    label: "标书审阅",
    href: "tender-analysis",
    roles: ["employee", "manager", "boss", "founder"],
    group: "AI 核心指挥",
  },
  {
    icon: <Swords size={20} />,
    label: "竞品库",
    href: "battlecards",
    group: "AI 核心指挥",
  },
  {
    icon: <TrendingUp size={20} />,
    label: "销售AI管理",
    href: "sales",
    badge: "5",
    badgeType: "primary",
    roles: ["employee", "manager", "boss", "founder"],
    group: "AI 核心指挥",
  },
  {
    icon: <Contact size={20} />,
    label: "CRM管理",
    href: "crm",
    roles: ["employee", "manager", "boss", "founder"],
    group: "AI 核心指挥",
  },

  // 业务与日常
  {
    icon: <Briefcase size={20} />,
    label: "项目管理",
    href: "projects",
    roles: ["employee", "manager", "boss", "founder"],
    group: "业务与日常",
  },
  {
    icon: <Target size={20} />,
    label: "目标看板",
    href: "target-dashboard",
    group: "业务与日常",
  },
  {
    icon: <TrendingUp size={20} />,
    label: "目标管理",
    href: "targets",
    roles: ["boss", "founder"],
    group: "业务与日常",
  },
  {
    icon: <AlertTriangle size={20} />,
    label: "异常待办",
    href: "exceptions",
    roles: ["boss", "founder"],
    group: "业务与日常",
  },
  {
    icon: <FileCheck size={20} />,
    label: "审批中心",
    href: "approval",
    roles: ["employee", "manager", "boss", "founder"],
    group: "业务与日常",
  },
  {
    icon: <Users size={20} />,
    label: "团队管理",
    href: "employees",
    roles: ["manager", "boss", "founder"],
    group: "业务与日常",
  },
  {
    icon: <Building2 size={20} />,
    label: "部门管理",
    href: "departments",
    roles: ["boss", "founder"],
    group: "业务与日常",
  },
  {
    icon: <FileSignature size={20} />,
    label: "合同管理",
    href: "contracts",
    roles: ["manager", "boss", "founder"],
    group: "业务与日常",
  },
  {
    icon: <BarChart3 size={20} />,
    label: "数据报表",
    href: "reports",
    group: "业务与日常",
  },

  // OA/HR/财务
  {
    icon: <Calendar size={20} />,
    label: "OA办公",
    href: "oa",
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

  // 知识与个人
  {
    icon: <BookOpen size={20} />,
    label: "知识库",
    href: "knowledge",
    group: "知识与个人",
  },
  {
    icon: <Upload size={20} />,
    label: "数据导入",
    href: "import",
    roles: ["boss", "founder"],
    group: "知识与个人",
  },
  {
    icon: <GraduationCap size={20} />,
    label: "培训中心",
    href: "training",
    group: "知识与个人",
  },
  {
    icon: <Gift size={20} />,
    label: "激励钱包",
    href: "rewards",
    badge: "¥200",
    badgeType: "success",
    group: "知识与个人",
  },
  {
    icon: <Settings size={20} />,
    label: "系统设置",
    href: "settings",
    group: "知识与个人",
  },

  // 虚拟市场部
  {
    icon: <Rocket size={20} />,
    label: "虚拟市场部",
    href: "vmd",
    badge: "AI",
    badgeType: "primary",
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

  // 系统管理
  {
    icon: <Building2 size={20} />,
    label: "企业设置",
    href: "company-settings",
    roles: ["boss", "founder"],
    group: "系统管理",
  },
  {
    icon: <Users size={20} />,
    label: "组织架构",
    href: "org-chart",
    roles: ["boss", "founder"],
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

// 分组顺序
const NAV_GROUPS = [
  "AI 核心指挥",
  "业务与日常",
  "OA/HR/财务",
  "知识与个人",
  "虚拟市场部",
  "系统管理",
];

interface SidebarProps {
  onNavClick?: () => void; // For mobile close
}

export function Sidebar({ onNavClick }: SidebarProps) {
  const { user } = useUser();
  const { role, signOut, profile } = useAuth();
  const [orgName, setOrgName] = useState("企业名称");

  useEffect(() => {
    const fetchOrgName = async () => {
      try {
        if (profile?.organization_id) {
          const { data, error } = await supabase
            .from("organizations")
            .select("name")
            .eq("id", profile.organization_id)
            .single();

          const orgData = data as { name: string } | null;
          if (!error && orgData?.name) {
            setOrgName(orgData.name);
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
  const { data: exceptions = [] } = useExceptions();
  const exceptionCount = exceptions.length;

  // 获取角色显示名称
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

  // Helper to check if link is active
  const isActive = (href: string) => {
    if (href === "dashboard" && location.pathname === "/dashboard") return true;
    if (href === "boss-dashboard" && location.pathname === "/boss-dashboard")
      return true;
    // Exact match for parent items that have sub-pages (e.g. 'vmd' shouldn't match 'vmd/tasks')
    if (href === "vmd" && location.pathname === "/vmd") return true;
    if (href === "vmd") return false;
    return location.pathname.startsWith("/" + href);
  };

  // 动态设置异常待办 badge
  const navWithBadges = NAV_CONFIG.map((item) => {
    if (item.href === "exceptions" && exceptionCount > 0) {
      return { ...item, badge: String(exceptionCount) };
    }
    return item;
  });

  // 基于角色过滤导航项 — 单一过滤逻辑，不再区分 boss/employee 两套数组
  const currentRole = (role || user.role || "employee") as AppRole;
  // founder 可以看到所有 boss 权限的菜单
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

  const renderNavGroup = (title: string, items: NavItem[]) => {
    if (items.length === 0) return null;
    return (
      <div className={cn("mb-4", isCollapsed ? "px-2" : "px-4")}>
        {!isCollapsed && (
          <h3 className="px-2 text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2 transition-all duration-300">
            {title}
          </h3>
        )}
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item.href}>
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Link
                      to={`/${item.href}`}
                      onClick={onNavClick}
                      aria-current={isActive(item.href) ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-3 rounded-lg text-sm font-medium transition-all group relative",
                        isCollapsed ? "justify-center p-2" : "px-3 py-2",
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

                      {!isCollapsed && (
                        <span className="flex-1 text-left truncate transition-all duration-300 origin-left">
                          {item.label}
                        </span>
                      )}

                      {/* Badge Handling */}
                      {item.badge && !isCollapsed && (
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

                      {/* Collapsed Badge Indicator (Dot) */}
                      {item.badge && isCollapsed && (
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
                  {isCollapsed && (
                    <TooltipContent side="right" className="font-medium">
                      {item.label}
                      {item.badge && (
                        <span className="ml-2 text-xs opacity-70">
                          ({item.badge})
                        </span>
                      )}
                    </TooltipContent>
                  )}
                </Tooltip>
              </TooltipProvider>
            </li>
          ))}
        </ul>
      </div>
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

      {/* Theme Toggle (Simplified when collapsed) */}
      <div className={cn("py-4 transition-all", isCollapsed ? "px-2" : "px-4")}>
        <div
          className={cn(
            "flex items-center rounded-lg bg-secondary/50 transition-all",
            isCollapsed ? "justify-center p-2" : "justify-between p-2",
          )}
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
        className="flex-1 py-4 overflow-y-auto overflow-x-hidden space-y-2 custom-scrollbar"
      >
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
                    src={user.avatar}
                    alt={user.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  user.name[0]
                )}
              </div>
              {!isCollapsed && (
                <div className="flex-1 min-w-0 text-left transition-all duration-300 opacity-100">
                  <p className="text-sm font-medium text-foreground truncate">
                    {user.name}
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
                <p className="text-sm font-medium leading-none">{user.name}</p>
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
