import React from 'react';
import { useUser } from '@/contexts/UserContext';
import { useAuth } from '@/components/auth/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { cn } from '@/lib/utils';
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
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";


interface NavItem {
  icon: React.ReactNode;
  label: string;
  href: string;
  badge?: string;
  badgeType?: 'primary' | 'success' | 'warning';
}

interface SidebarProps {
  activeNav: string;
  onNavChange: (nav: string) => void;
}

export function Sidebar({ activeNav, onNavChange }: SidebarProps) {
  const { user } = useUser();
  const { signOut } = useAuth();
  const { theme } = useTheme();

  const employeeNav: NavItem[] = [
    { icon: <LayoutDashboard size={20} />, label: '战绩中心', href: 'dashboard' },
    { icon: <Briefcase size={20} />, label: '项目管理', href: 'projects' },
    { icon: <TrendingUp size={20} />, label: '销售AI管理', href: 'sales', badge: '5', badgeType: 'primary' },
    { icon: <FileCheck size={20} />, label: '智能审批', href: 'approval' },
    { icon: <BookOpen size={20} />, label: '知识库', href: 'knowledge' },
    { icon: <Gift size={20} />, label: '激励钱包', href: 'rewards', badge: '¥200', badgeType: 'success' },
    { icon: <Settings size={20} />, label: 'AI配置中心', href: 'settings' },
  ];

  const bossNav: NavItem[] = [
    { icon: <Crown size={20} />, label: '总控中心', href: 'boss-dashboard' },
    { icon: <AlertTriangle size={20} />, label: '异常待办', href: 'exceptions', badge: '3', badgeType: 'warning' },
    { icon: <TrendingUp size={20} />, label: '目标管理', href: 'targets' },
    { icon: <BookOpen size={20} />, label: '知识库管理', href: 'documents', badge: 'AI', badgeType: 'primary' },
    { icon: <Users size={20} />, label: '员工管理', href: 'employees' },
    { icon: <FileCheck size={20} />, label: '审批中心', href: 'approval' },
    { icon: <Settings size={20} />, label: '系统设置', href: 'settings' },
  ];

  // Strictly use account role logic
  const navItems = user.role === 'boss' ? bossNav : employeeNav;

  const handleLogout = async () => {
    await signOut();
    // Redirect is handled by AuthContext/App state change
  };

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 bg-sidebar border-r border-sidebar-border flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-sidebar-border">
        <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center glow-primary">
          <Bot className="w-6 h-6 text-primary-foreground" />
        </div>
        <div>
          <h1 className="font-bold text-foreground tracking-tight">Project Nexus</h1>
          <p className="text-xs text-muted-foreground">AI-Driven OS</p>
        </div>
      </div>

      {/* Theme Toggle */}
      <div className="px-4 py-4">
        <div className="flex items-center justify-between p-2 rounded-lg bg-secondary/50">
          <span className="text-xs text-muted-foreground pl-1">
            {theme === 'dark' ? '夜间模式' : '日间模式'}
          </span>
          <ThemeToggle />
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-2 overflow-y-auto">
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.href}>
              <button
                onClick={() => onNavChange(item.href)}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all",
                  activeNav === item.href
                    ? "bg-sidebar-accent text-primary"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-foreground"
                )}
              >
                {item.icon}
                <span className="flex-1 text-left">{item.label}</span>
                {item.badge && (
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded-full text-xs font-semibold",
                      item.badgeType === 'primary' && "bg-primary/20 text-primary",
                      item.badgeType === 'success' && "bg-success/20 text-success",
                      item.badgeType === 'warning' && "bg-warning/20 text-warning"
                    )}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* User Profile with Dropdown */}
      <div className="p-4 border-t border-sidebar-border">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-sidebar-accent transition-colors outline-none group">
              <div className="w-10 h-10 rounded-full bg-gradient-primary flex items-center justify-center text-primary-foreground font-semibold shrink-0 group-hover:scale-105 transition-transform">
                {user.avatar ? <img src={user.avatar} alt={user.name} className="w-full h-full rounded-full object-cover" /> : user.name[0]}
              </div>
              <div className="flex-1 min-w-0 text-left">
                <p className="text-sm font-medium text-foreground truncate">{user.name}</p>
                <div className="flex items-center justify-between">
                  <p className="text-xs text-muted-foreground">{user.department}</p>
                  <ChevronRight className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </div>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="right" align="end" className="w-56" sideOffset={8}>
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium leading-none">{user.name}</p>
                <p className="text-xs leading-none text-muted-foreground">{user.role === 'boss' ? '企业管理员' : '销售精英'}</p>
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
            <DropdownMenuItem onClick={() => console.log("Profile clicked")}>
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
