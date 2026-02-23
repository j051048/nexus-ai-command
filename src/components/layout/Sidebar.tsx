import React, { useState } from 'react';
import { useUser } from '@/contexts/UserContext';
import { useAuth } from '@/components/auth/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { cn } from '@/lib/utils';
import { Link, useLocation, useNavigate } from 'react-router-dom';
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
  Shield,
  Building2,
  Contact,
  FileSignature,
  BarChart3,
  CreditCard,
  Puzzle,
  GraduationCap,
  ClipboardList,
  Key,
} from 'lucide-react';
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
import { Button } from '@/components/ui/button';
import { useExceptions } from '@/hooks/useExceptions';

type AppRole = 'boss' | 'manager' | 'ai_assistant' | 'employee';

interface NavItem {
  icon: React.ReactNode;
  label: string;
  href: string;
  badge?: string;
  badgeType?: 'primary' | 'success' | 'warning';
  roles?: AppRole[]; // undefined = 所有人可见
}

interface SidebarProps {
  onNavClick?: () => void; // For mobile close
}

export function Sidebar({ onNavClick }: SidebarProps) {
  const { user } = useUser();
  const { role, signOut } = useAuth();
  const { theme } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { data: exceptions = [] } = useExceptions();
  const exceptionCount = exceptions.length;

  // 获取角色显示名称
  const getRoleDisplayName = (role: string) => {
    switch (role) {
      case 'boss':
      case 'founder':
        return '企业管理员';
      case 'manager':
        return '部门经理';
      case 'sales':
      case 'employee':
      default:
        return '销售精英';
    }
  };

  // Helper to check if link is active
  const isActive = (href: string) => {
    if (href === 'dashboard' && location.pathname === '/dashboard') return true;
    if (href === 'boss-dashboard' && location.pathname === '/boss-dashboard') return true;
    return location.pathname.startsWith('/' + href);
  };

  const employeeNav: NavItem[] = [
    { icon: <LayoutDashboard size={20} />, label: '战绩中心', href: 'dashboard', roles: undefined }, // 所有人
    { icon: <Briefcase size={20} />, label: '项目管理', href: 'projects', roles: ['employee', 'manager', 'boss'] },
    { icon: <FileSearch size={20} />, label: '标书审阅', href: 'tender-analysis', roles: ['employee', 'manager', 'boss'] },
    { icon: <Swords size={20} />, label: '竞品库', href: 'battlecards', roles: undefined },
    { icon: <Target size={20} />, label: '目标看板', href: 'target-dashboard', roles: undefined },
    { icon: <TrendingUp size={20} />, label: '销售AI管理', href: 'sales', badge: '5', badgeType: 'primary', roles: ['employee', 'manager', 'boss'] },
    { icon: <Contact size={20} />, label: 'CRM管理', href: 'crm', roles: ['employee', 'manager', 'boss'] },
    { icon: <FileCheck size={20} />, label: '智能审批', href: 'approval', roles: ['employee', 'manager', 'boss'] },
    { icon: <FileSignature size={20} />, label: '合同管理', href: 'contracts', roles: ['manager', 'boss'] },
    { icon: <BarChart3 size={20} />, label: '数据报表', href: 'reports', roles: undefined },
    { icon: <Calendar size={20} />, label: 'OA办公', href: 'oa', roles: undefined },
    { icon: <Clock size={20} />, label: '人事中心', href: 'hr', roles: ['manager', 'boss'] },
    { icon: <DollarSign size={20} />, label: '财务中心', href: 'finance', roles: undefined },
    { icon: <Upload size={20} />, label: '数据导入', href: 'import', roles: ['boss'] },
    { icon: <BookOpen size={20} />, label: '知识库', href: 'knowledge', roles: undefined },
    { icon: <GraduationCap size={20} />, label: '培训中心', href: 'training', roles: undefined },
    { icon: <Gift size={20} />, label: '激励钱包', href: 'rewards', badge: '¥200', badgeType: 'success', roles: undefined },
    { icon: <Settings size={20} />, label: 'AI配置中心', href: 'settings', roles: undefined },
    { icon: <CreditCard size={20} />, label: '订阅支付', href: 'payments', roles: ['boss'] },
    { icon: <Puzzle size={20} />, label: '插件市场', href: 'plugins', roles: ['boss'] },
    { icon: <ClipboardList size={20} />, label: '审计日志', href: 'audit', roles: ['boss'] },
    { icon: <Key size={20} />, label: 'API密钥', href: 'api-keys', roles: ['boss'] },
  ];

  const bossNav: NavItem[] = [
    { icon: <Crown size={20} />, label: '总控中心', href: 'boss-dashboard', roles: ['boss'] },
    { icon: <AlertTriangle size={20} />, label: '异常待办', href: 'exceptions', badge: exceptionCount > 0 ? String(exceptionCount) : undefined, badgeType: 'warning', roles: ['boss'] },
    { icon: <TrendingUp size={20} />, label: '目标管理', href: 'targets', roles: ['boss'] },
    { icon: <Contact size={20} />, label: 'CRM管理', href: 'crm', roles: ['employee', 'manager', 'boss'] },
    { icon: <BookOpen size={20} />, label: '知识库管理', href: 'documents', badge: 'AI', badgeType: 'primary', roles: undefined },
    { icon: <Users size={20} />, label: '员工管理', href: 'employees', roles: ['manager', 'boss'] },
    { icon: <Shield size={20} />, label: '角色管理', href: 'roles', roles: ['boss'] },
    { icon: <Building2 size={20} />, label: '部门管理', href: 'departments', roles: ['boss'] },
    { icon: <Upload size={20} />, label: '数据导入', href: 'import', roles: ['boss'] },
    { icon: <FileCheck size={20} />, label: '审批中心', href: 'approval', roles: ['employee', 'manager', 'boss'] },
    { icon: <FileSignature size={20} />, label: '合同管理', href: 'contracts', roles: ['manager', 'boss'] },
    { icon: <BarChart3 size={20} />, label: '数据报表', href: 'reports', roles: undefined },
    { icon: <Calendar size={20} />, label: 'OA办公', href: 'oa', roles: undefined },
    { icon: <Clock size={20} />, label: '人事中心', href: 'hr', roles: ['manager', 'boss'] },
    { icon: <DollarSign size={20} />, label: '财务中心', href: 'finance', roles: undefined },
    { icon: <GraduationCap size={20} />, label: '培训中心', href: 'training', roles: undefined },
    { icon: <Settings size={20} />, label: '系统设置', href: 'settings', roles: undefined },
    { icon: <CreditCard size={20} />, label: '订阅支付', href: 'payments', roles: ['boss'] },
    { icon: <Puzzle size={20} />, label: '插件市场', href: 'plugins', roles: ['boss'] },
    { icon: <ClipboardList size={20} />, label: '审计日志', href: 'audit', roles: ['boss'] },
    { icon: <Key size={20} />, label: 'API密钥', href: 'api-keys', roles: ['boss'] },
  ];

  // Use bossNav if user is manager or boss to ensure they see management links
  const allNavItems = (user.role === 'boss' || user.role === 'manager') ? bossNav : employeeNav;
  
  // Filter menu items based on current user role
  const currentRole = (role || 'employee') as AppRole;
  const navItems = allNavItems.filter(item => 
    !item.roles || item.roles.includes(currentRole)
  );

  const handleLogout = async () => {
    await signOut();
    // Redirect is handled by AuthContext/App state change
  };

  const renderNavGroup = (title: string, items: NavItem[]) => (
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
                        : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-foreground"
                    )}
                  >
                    <span className={cn("transition-transform duration-200", !isActive(item.href) && "group-hover:scale-110")}>
                      {item.icon}
                    </span>
                    
                    {!isCollapsed && (
                      <span className="flex-1 text-left truncate transition-all duration-300 origin-left">
                        {item.label}
                      </span>
                    )}

                    {/* Badge Handling */}
                    {item.badge && !isCollapsed && (
                      <span className={cn(
                        "px-1.5 py-0.5 rounded-full text-[10px] font-bold ml-auto",
                        item.badgeType === 'primary' && "bg-primary/10 text-primary",
                        item.badgeType === 'success' && "bg-success/10 text-success",
                        item.badgeType === 'warning' && "bg-warning/10 text-warning"
                      )}>
                        {item.badge}
                      </span>
                    )}
                    
                    {/* Collapsed Badge Indicator (Dot) */}
                    {item.badge && isCollapsed && (
                       <span className={cn(
                        "absolute top-1 right-1 w-2 h-2 rounded-full border-2 border-background",
                         item.badgeType === 'primary' && "bg-primary",
                        item.badgeType === 'success' && "bg-success",
                        item.badgeType === 'warning' && "bg-warning"
                       )} />
                    )}
                  </Link>
                </TooltipTrigger>
                {isCollapsed && (
                  <TooltipContent side="right" className="font-medium">
                    {item.label}
                    {item.badge && <span className="ml-2 text-xs opacity-70">({item.badge})</span>}
                  </TooltipContent>
                )}
              </Tooltip>
            </TooltipProvider>
          </li>
        ))}
      </ul>
    </div>
  );

  return (
    <aside
      aria-label="主导航"
      className={cn(
        "bg-sidebar border-r border-sidebar-border flex flex-col transition-all duration-300 ease-in-out h-full z-40 relative group/sidebar",
        isCollapsed ? "w-[70px]" : "w-64"
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
        {isCollapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
      </Button>

      {/* Logo */}
      <div className={cn(
        "flex items-center gap-3 py-5 border-b border-sidebar-border transition-all duration-300",
        isCollapsed ? "justify-center px-0" : "px-6"
      )}>
        <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center glow-primary shrink-0 transition-all duration-300 hover:scale-105 cursor-pointer" onClick={() => navigate('/')}>
          <Bot className="w-6 h-6 text-primary-foreground" />
        </div>
        {!isCollapsed && (
          <div className="overflow-hidden transition-all duration-300 opacity-100 w-auto">
            <h1 className="font-bold text-foreground tracking-tight whitespace-nowrap">Project Nexus</h1>
            <p className="text-xs text-muted-foreground whitespace-nowrap">AI-Driven OS</p>
          </div>
        )}
      </div>

      {/* Theme Toggle (Simplified when collapsed) */}
      <div className={cn("py-4 transition-all", isCollapsed ? "px-2" : "px-4")}>
        <div className={cn(
          "flex items-center rounded-lg bg-secondary/50 transition-all",
          isCollapsed ? "justify-center p-2" : "justify-between p-2"
        )}>
          {!isCollapsed && (
            <span className="text-xs text-muted-foreground pl-1 whitespace-nowrap overflow-hidden">
              {theme === 'dark' ? '夜间模式' : '日间模式'}
            </span>
          )}
          <ThemeToggle />
        </div>
      </div>

      {/* Navigation */}
      <nav role="navigation" aria-label="功能菜单" className="flex-1 py-4 overflow-y-auto overflow-x-hidden space-y-2 custom-scrollbar">
        {renderNavGroup("AI 核心指挥", navItems.filter(i => ['dashboard', 'boss-dashboard', 'tender-analysis', 'battlecards', 'sales', 'crm'].includes(i.href)))}
        {renderNavGroup("业务与日常", navItems.filter(i => ['projects', 'target-dashboard', 'targets', 'approval', 'exceptions', 'employees', 'roles', 'departments', 'contracts', 'reports'].includes(i.href)))}
        {renderNavGroup("OA/HR/财务", navItems.filter(i => ['oa', 'hr', 'finance'].includes(i.href)))}
        {renderNavGroup("知识与个人", navItems.filter(i => ['knowledge', 'documents', 'rewards', 'import', 'settings', 'training'].includes(i.href)))}
        {renderNavGroup("系统管理", navItems.filter(i => ['audit', 'plugins', 'api-keys', 'payments'].includes(i.href)))}
      </nav>

      {/* User Profile with Dropdown */}
      <div className="p-4 border-t border-sidebar-border mt-auto">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className={cn(
              "w-full flex items-center gap-3 rounded-lg hover:bg-sidebar-accent transition-colors outline-none group",
              isCollapsed ? "justify-center p-0" : "p-2"
            )}>
              <div className="w-9 h-9 rounded-full bg-gradient-primary flex items-center justify-center text-primary-foreground font-semibold shrink-0 group-hover:scale-105 transition-transform overflow-hidden ring-2 ring-background">
                {user.avatar ? <img src={user.avatar} alt={user.name} className="w-full h-full object-cover" /> : user.name[0]}
              </div>
              {!isCollapsed && (
                <div className="flex-1 min-w-0 text-left transition-all duration-300 opacity-100">
                  <p className="text-sm font-medium text-foreground truncate">{user.name}</p>
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground truncate max-w-[80px]">{getRoleDisplayName(user.role)}</p>
                    <ChevronRight className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </div>
              )}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="right" align={isCollapsed ? "center" : "end"} className="w-56" sideOffset={10}>
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium leading-none">{user.name}</p>
                <p className="text-xs leading-none text-muted-foreground">{getRoleDisplayName(user.role)}</p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {user.role === 'employee' && (
              <DropdownMenuItem className="cursor-default focus:bg-transparent">
                <div className="flex flex-1 items-center justify-between">
                  <span className="text-muted-foreground">当前绩效</span>
                  <span className="font-bold text-success">{user.score}</span>
                </div>
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate('/profile')}>
              <UserIcon className="mr-2 h-4 w-4" />
              <span>个人中心</span>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive focus:bg-destructive/10">
              <LogOut className="mr-2 h-4 w-4" />
              <span>退出登录</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  );
}
