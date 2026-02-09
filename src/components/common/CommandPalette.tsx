import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from '@/components/ui/command';
import {
  LayoutDashboard,
  Briefcase,
  FileCheck,
  TrendingUp,
  Gift,
  Settings,
  Bot,
  FileSearch,
  Swords,
  Target,
  BookOpen,
  Users,
  Crown,
  AlertTriangle,
  Sun,
  Moon,
  Plus,
  Search,
  MessageSquare,
  HelpCircle,
} from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/components/auth/AuthContext';
import { formatShortcut } from '@/hooks/useKeyboardShortcuts';

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAIChat?: (message: string) => void;
}

interface CommandItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  shortcut?: string;
  action: () => void;
  keywords?: string[];
}

interface CommandGroup {
  heading: string;
  items: CommandItem[];
}

export function CommandPalette({ open, onOpenChange, onAIChat }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { role } = useAuth();
  const [search, setSearch] = useState('');

  const isBoss = role === 'boss';

  // 关闭并执行操作
  const runCommand = useCallback((action: () => void) => {
    onOpenChange(false);
    action();
  }, [onOpenChange]);

  // 导航命令
  const navigationCommands: CommandItem[] = useMemo(() => {
    const baseCommands: CommandItem[] = [
      {
        id: 'dashboard',
        label: isBoss ? '总控中心' : '战绩中心',
        icon: isBoss ? <Crown className="w-4 h-4" /> : <LayoutDashboard className="w-4 h-4" />,
        shortcut: '⌘⇧D',
        action: () => navigate(isBoss ? '/boss-dashboard' : '/dashboard'),
        keywords: ['首页', 'home', 'dashboard'],
      },
      {
        id: 'projects',
        label: '项目管理',
        icon: <Briefcase className="w-4 h-4" />,
        shortcut: '⌘⇧P',
        action: () => navigate('/projects'),
        keywords: ['project', '任务'],
      },
      {
        id: 'approval',
        label: '智能审批',
        icon: <FileCheck className="w-4 h-4" />,
        shortcut: '⌘⇧A',
        action: () => navigate('/approval'),
        keywords: ['审批', 'approve', '报销'],
      },
      {
        id: 'sales',
        label: '销售管理',
        icon: <TrendingUp className="w-4 h-4" />,
        shortcut: '⌘⇧S',
        action: () => navigate('/sales'),
        keywords: ['销售', 'sale', '商机', 'lead'],
      },
    ];

    if (isBoss) {
      baseCommands.push(
        {
          id: 'exceptions',
          label: '异常待办',
          icon: <AlertTriangle className="w-4 h-4" />,
          action: () => navigate('/exceptions'),
          keywords: ['异常', 'exception', '待办'],
        },
        {
          id: 'employees',
          label: '员工管理',
          icon: <Users className="w-4 h-4" />,
          action: () => navigate('/employees'),
          keywords: ['员工', 'employee', '团队'],
        },
        {
          id: 'targets',
          label: '目标管理',
          icon: <Target className="w-4 h-4" />,
          action: () => navigate('/targets'),
          keywords: ['目标', 'target', 'kpi'],
        }
      );
    } else {
      baseCommands.push(
        {
          id: 'tender',
          label: '标书审阅',
          icon: <FileSearch className="w-4 h-4" />,
          action: () => navigate('/tender-analysis'),
          keywords: ['标书', 'tender', '投标'],
        },
        {
          id: 'battlecards',
          label: '竞品库',
          icon: <Swords className="w-4 h-4" />,
          action: () => navigate('/battlecards'),
          keywords: ['竞品', 'competitor', '对手'],
        },
        {
          id: 'rewards',
          label: '激励钱包',
          icon: <Gift className="w-4 h-4" />,
          action: () => navigate('/rewards'),
          keywords: ['奖励', 'reward', '钱包', 'bonus'],
        }
      );
    }

    baseCommands.push(
      {
        id: 'knowledge',
        label: '知识库',
        icon: <BookOpen className="w-4 h-4" />,
        action: () => navigate('/knowledge'),
        keywords: ['知识', 'knowledge', '文档'],
      },
      {
        id: 'settings',
        label: 'AI 配置',
        icon: <Settings className="w-4 h-4" />,
        action: () => navigate('/settings'),
        keywords: ['设置', 'setting', '配置'],
      }
    );

    return baseCommands;
  }, [navigate, isBoss]);

  // AI 快捷指令
  const aiCommands: CommandItem[] = useMemo(() => [
    {
      id: 'ai-summary',
      label: '本周销售汇总',
      icon: <Bot className="w-4 h-4" />,
      action: () => onAIChat?.('帮我汇总本周的销售数据和关键指标'),
      keywords: ['销售', '汇总', 'summary'],
    },
    {
      id: 'ai-pending',
      label: '查看待办事项',
      icon: <MessageSquare className="w-4 h-4" />,
      action: () => onAIChat?.('查看我的待办事项和待审批申请'),
      keywords: ['待办', 'todo', '审批'],
    },
    {
      id: 'ai-target',
      label: '目标完成进度',
      icon: <Target className="w-4 h-4" />,
      action: () => onAIChat?.('查询我的目标完成进度和剩余差距'),
      keywords: ['目标', 'target', '进度'],
    },
    {
      id: 'ai-competitor',
      label: '竞品分析',
      icon: <Swords className="w-4 h-4" />,
      action: () => onAIChat?.('分析主要竞品的最新动态和优劣势'),
      keywords: ['竞品', 'competitor', '分析'],
    },
    {
      id: 'ai-help',
      label: '帮助指南',
      icon: <HelpCircle className="w-4 h-4" />,
      action: () => onAIChat?.('介绍一下这个系统有哪些主要功能'),
      keywords: ['帮助', 'help', '指南'],
    },
  ], [onAIChat]);

  // 操作命令
  const actionCommands: CommandItem[] = useMemo(() => [
    {
      id: 'new-project',
      label: '新建项目',
      icon: <Plus className="w-4 h-4" />,
      shortcut: '⌘N',
      action: () => {
        navigate('/projects');
        // TODO: 打开新建项目对话框
      },
      keywords: ['新建', 'new', 'create', '项目'],
    },
    {
      id: 'toggle-theme',
      label: theme === 'dark' ? '切换到日间模式' : '切换到夜间模式',
      icon: theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />,
      shortcut: '⌘J',
      action: toggleTheme,
      keywords: ['主题', 'theme', '深色', '浅色'],
    },
  ], [navigate, theme, toggleTheme]);

  // 键盘快捷键打开
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onOpenChange(!open);
      }
    };

    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, [open, onOpenChange]);

  // 清理搜索
  useEffect(() => {
    if (!open) {
      setSearch('');
    }
  }, [open]);

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput
        placeholder="搜索命令或输入 AI 指令..."
        value={search}
        onValueChange={setSearch}
      />
      <CommandList>
        <CommandEmpty>
          <div className="py-6 text-center">
            <Search className="w-10 h-10 mx-auto mb-3 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">未找到相关命令</p>
            <p className="text-xs text-muted-foreground mt-1">
              试试输入 "帮助" 或 "新建"
            </p>
          </div>
        </CommandEmpty>

        {/* 快速导航 */}
        <CommandGroup heading="快速导航">
          {navigationCommands.map((item) => (
            <CommandItem
              key={item.id}
              value={`${item.label} ${item.keywords?.join(' ') || ''}`}
              onSelect={() => runCommand(item.action)}
              className="cursor-pointer"
            >
              <span className="mr-3 text-muted-foreground">{item.icon}</span>
              <span>{item.label}</span>
              {item.shortcut && (
                <CommandShortcut>{item.shortcut}</CommandShortcut>
              )}
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        {/* AI 快捷指令 */}
        <CommandGroup heading="AI 快捷指令">
          {aiCommands.map((item) => (
            <CommandItem
              key={item.id}
              value={`${item.label} ${item.keywords?.join(' ') || ''}`}
              onSelect={() => runCommand(item.action)}
              className="cursor-pointer"
            >
              <span className="mr-3 text-primary">{item.icon}</span>
              <span>{item.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        {/* 操作 */}
        <CommandGroup heading="操作">
          {actionCommands.map((item) => (
            <CommandItem
              key={item.id}
              value={`${item.label} ${item.keywords?.join(' ') || ''}`}
              onSelect={() => runCommand(item.action)}
              className="cursor-pointer"
            >
              <span className="mr-3 text-muted-foreground">{item.icon}</span>
              <span>{item.label}</span>
              {item.shortcut && (
                <CommandShortcut>{item.shortcut}</CommandShortcut>
              )}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}

export default CommandPalette;