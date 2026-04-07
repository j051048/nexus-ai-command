import React, { useState, useEffect } from 'react';
import { Command } from 'cmdk';
import { useNavigate } from 'react-router-dom';
import {
  Calculator,
  Calendar,
  CreditCard,
  Settings,
  Smile,
  User,
  Search,
  FileText,
  Briefcase,
  Users,
  LayoutDashboard,
  MessageSquare,
  Zap,
} from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { useUser } from '@/contexts/UserContext';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAIChat?: (message: string) => void;
}

export function CommandPalette({ open, onOpenChange, onAIChat }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { toggleTheme } = useTheme();
  const { user } = useUser();
  const [search, setSearch] = useState('');

  // 监听键盘事件，除了外部传入的 open，内部也支持 ESC 关闭等
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

  const runCommand = React.useCallback((command: () => void) => {
    onOpenChange(false);
    command();
  }, [onOpenChange]);

  // 根据角色过滤命令
  const isBoss = user?.role === 'boss';
  const isSales = user?.role === 'sales';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0 shadow-2xl sm:max-w-[500px]">
        <DialogTitle className="sr-only">命令面板</DialogTitle>
        <DialogDescription className="sr-only">
          搜索并执行系统命令、跳转页面或与 AI 助手交流。
        </DialogDescription>
        <Command className="flex h-full w-full flex-col overflow-hidden rounded-md bg-popover text-popover-foreground">
          <div className="flex items-center border-b px-3" cmdk-input-wrapper="">
            <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
            <Command.Input
              value={search}
              onValueChange={setSearch}
              placeholder="输入命令或搜索..."
              className="flex h-11 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>
          <Command.List className="max-h-[300px] overflow-y-auto overflow-x-hidden p-2">
            <Command.Empty className="py-6 text-center text-sm">
              <p className="text-muted-foreground">未找到相关命令。</p>
              {search && (
                <button
                  className="mt-2 text-primary hover:underline"
                  onClick={() => runCommand(() => onAIChat?.(search))}
                >
                  问问 AI: "{search}"
                </button>
              )}
            </Command.Empty>

            <Command.Group heading="智能助手">
              <Command.Item
                onSelect={() => runCommand(() => onAIChat?.('打开AI助手'))}
                className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none aria-selected:bg-accent aria-selected:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
              >
                <MessageSquare className="mr-2 h-4 w-4" />
                <span>打开 AI 助手</span>
                <div className="ml-auto text-xs tracking-widest text-muted-foreground">⌘J</div>

              </Command.Item>
              <Command.Item
                onSelect={() => runCommand(() => onAIChat?.('查看今日日报'))}
                className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none aria-selected:bg-accent aria-selected:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
              >
                <FileText className="mr-2 h-4 w-4" />
                <span>生成今日日报</span>
              </Command.Item>
            </Command.Group>

            <Command.Group heading="快速跳转">
              <Command.Item
                onSelect={() => runCommand(() => navigate(isBoss ? '/boss-dashboard' : '/dashboard'))}
                className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none aria-selected:bg-accent aria-selected:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
              >
                <LayoutDashboard className="mr-2 h-4 w-4" />
                <span>回到首页</span>
              </Command.Item>
              
              {isBoss && (
                <>
                  <Command.Item
                    onSelect={() => runCommand(() => navigate('/finance'))}
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none aria-selected:bg-accent aria-selected:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                  >
                    <Briefcase className="mr-2 h-4 w-4" />
                    <span>财务中心</span>
                  </Command.Item>
                  <Command.Item
                    onSelect={() => runCommand(() => navigate('/hr'))}
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none aria-selected:bg-accent aria-selected:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                  >
                    <Users className="mr-2 h-4 w-4" />
                    <span>人力资源</span>
                  </Command.Item>
                </>
              )}

              {(isBoss || isSales) && (
                <Command.Item
                  onSelect={() => runCommand(() => navigate('/sales'))}
                  className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none aria-selected:bg-accent aria-selected:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                >
                  <Zap className="mr-2 h-4 w-4" />
                  <span>销售管道</span>
                </Command.Item>
              )}
              
              <Command.Item
                onSelect={() => runCommand(() => navigate('/settings'))}
                className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none aria-selected:bg-accent aria-selected:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
              >
                <Settings className="mr-2 h-4 w-4" />
                <span>系统设置</span>
              </Command.Item>
            </Command.Group>

            <Command.Group heading="通用">
              <Command.Item
                onSelect={() => runCommand(() => toggleTheme())}
                className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none aria-selected:bg-accent aria-selected:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
              >
                <Smile className="mr-2 h-4 w-4" />
                <span>切换主题</span>
                <div className="ml-auto text-xs tracking-widest text-muted-foreground">⌘T</div>

              </Command.Item>
            </Command.Group>
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}