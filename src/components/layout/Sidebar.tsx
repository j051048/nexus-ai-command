import React from 'react';
import { useUser } from '@/contexts/UserContext';
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
} from 'lucide-react';

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
  const { user, setRole } = useUser();
  const { theme } = useTheme();

  const employeeNav: NavItem[] = [
    { icon: <LayoutDashboard size={20} />, label: '战绩中心', href: 'dashboard' },
    { icon: <TrendingUp size={20} />, label: '销售AI管理', href: 'sales', badge: '5', badgeType: 'primary' },
    { icon: <FileCheck size={20} />, label: '智能审批', href: 'approval' },
    { icon: <BookOpen size={20} />, label: '知识库', href: 'knowledge' },
    { icon: <Gift size={20} />, label: '激励钱包', href: 'rewards', badge: '¥200', badgeType: 'success' },
  ];

  const bossNav: NavItem[] = [
    { icon: <Crown size={20} />, label: '总控中心', href: 'boss-dashboard' },
    { icon: <AlertTriangle size={20} />, label: '异常待办', href: 'exceptions', badge: '3', badgeType: 'warning' },
    { icon: <TrendingUp size={20} />, label: '团队绩效', href: 'team-performance' },
    { icon: <FileCheck size={20} />, label: '审批中心', href: 'approval' },
    { icon: <Settings size={20} />, label: '系统设置', href: 'settings' },
  ];

  const navItems = user.role === 'boss' ? bossNav : employeeNav;

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

      {/* Theme Toggle & Role Switcher */}
      <div className="px-4 py-4 space-y-3">
        {/* Theme Toggle */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {theme === 'dark' ? '夜间模式' : '日间模式'}
          </span>
          <ThemeToggle />
        </div>

        {/* Role Switcher */}
        <div className="bg-secondary rounded-lg p-1 flex">
          <button
            onClick={() => setRole('employee')}
            className={cn(
              "flex-1 py-2 px-3 rounded-md text-sm font-medium transition-all",
              user.role === 'employee'
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            员工视角
          </button>
          <button
            onClick={() => setRole('boss')}
            className={cn(
              "flex-1 py-2 px-3 rounded-md text-sm font-medium transition-all",
              user.role === 'boss'
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            老板视角
          </button>
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

      {/* User Profile */}
      <div className="p-4 border-t border-sidebar-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-primary flex items-center justify-center text-primary-foreground font-semibold">
            {user.name[0]}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{user.name}</p>
            <p className="text-xs text-muted-foreground">{user.department}</p>
          </div>
          {user.role === 'employee' && (
            <div className="text-right">
              <p className="text-lg font-bold text-success mono-number">{user.score}</p>
              <p className="text-xs text-muted-foreground">绩效分</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
