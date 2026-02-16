/**
 * P2 UX Enhancement: Dashboard Customizer
 * 仪表盘自定义组件 - 支持小部件管理和布局配置
 */

import React, { useState, useCallback, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  SheetFooter,
} from '@/components/ui/sheet';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  LayoutGrid,
  Plus,
  Minus,
  GripVertical,
  Eye,
  EyeOff,
  RotateCcw,
  Settings2,
  ChevronUp,
  ChevronDown,
  Trash2,
  Save,
  TrendingUp,
  Users,
  DollarSign,
  Target,
  Calendar,
  Bell,
  FileCheck,
  BarChart3,
  PieChart,
  Activity,
  Clock,
  Zap,
  Award,
} from 'lucide-react';
import { toast } from 'sonner';

// ==================== 类型定义 ====================

export interface Widget {
  id: string;
  type: string;
  title: string;
  description?: string;
  icon: React.ReactNode;
  category: 'stats' | 'charts' | 'lists' | 'other';
  defaultSize: 'small' | 'medium' | 'large';
  minSize?: 'small' | 'medium' | 'large';
  resizable?: boolean;
}

export interface WidgetInstance {
  id: string;
  widgetId: string;
  visible: boolean;
  order: number;
  size: 'small' | 'medium' | 'large';
  settings?: Record<string, unknown>;
}

export interface DashboardLayout {
  id: string;
  name: string;
  widgets: WidgetInstance[];
  columns: 1 | 2 | 3 | 4;
}

// ==================== 可用小部件 ====================

const availableWidgets: Widget[] = [
  // 统计卡片
  {
    id: 'sales-overview',
    type: 'stats',
    title: '销售概览',
    description: '显示销售总额和同比变化',
    icon: <DollarSign className="w-4 h-4" />,
    category: 'stats',
    defaultSize: 'small',
  },
  {
    id: 'target-progress',
    type: 'stats',
    title: '目标进度',
    description: '显示目标完成进度',
    icon: <Target className="w-4 h-4" />,
    category: 'stats',
    defaultSize: 'small',
  },
  {
    id: 'active-projects',
    type: 'stats',
    title: '活跃项目',
    description: '显示进行中的项目数量',
    icon: <Activity className="w-4 h-4" />,
    category: 'stats',
    defaultSize: 'small',
  },
  {
    id: 'pending-approvals',
    type: 'stats',
    title: '待审批',
    description: '显示待处理的审批数量',
    icon: <FileCheck className="w-4 h-4" />,
    category: 'stats',
    defaultSize: 'small',
  },
  {
    id: 'team-performance',
    type: 'stats',
    title: '团队绩效',
    description: '团队整体绩效评分',
    icon: <Users className="w-4 h-4" />,
    category: 'stats',
    defaultSize: 'small',
  },
  {
    id: 'rewards-balance',
    type: 'stats',
    title: '奖励余额',
    description: '当前可用奖励金额',
    icon: <Award className="w-4 h-4" />,
    category: 'stats',
    defaultSize: 'small',
  },

  // 图表
  {
    id: 'sales-trend',
    type: 'chart',
    title: '销售趋势',
    description: '近期销售趋势图表',
    icon: <TrendingUp className="w-4 h-4" />,
    category: 'charts',
    defaultSize: 'large',
    resizable: true,
  },
  {
    id: 'revenue-chart',
    type: 'chart',
    title: '收入分布',
    description: '收入来源分布图',
    icon: <PieChart className="w-4 h-4" />,
    category: 'charts',
    defaultSize: 'medium',
    resizable: true,
  },
  {
    id: 'performance-chart',
    type: 'chart',
    title: '绩效分析',
    description: '绩效指标对比图',
    icon: <BarChart3 className="w-4 h-4" />,
    category: 'charts',
    defaultSize: 'medium',
    resizable: true,
  },

  // 列表
  {
    id: 'recent-activities',
    type: 'list',
    title: '最近活动',
    description: '显示最近的操作记录',
    icon: <Clock className="w-4 h-4" />,
    category: 'lists',
    defaultSize: 'medium',
  },
  {
    id: 'upcoming-tasks',
    type: 'list',
    title: '待办事项',
    description: '显示即将到期的任务',
    icon: <Calendar className="w-4 h-4" />,
    category: 'lists',
    defaultSize: 'medium',
  },
  {
    id: 'notifications',
    type: 'list',
    title: '通知列表',
    description: '显示最新通知',
    icon: <Bell className="w-4 h-4" />,
    category: 'lists',
    defaultSize: 'medium',
  },

  // 其他
  {
    id: 'ai-insights',
    type: 'other',
    title: 'AI 洞察',
    description: 'AI 生成的智能建议',
    icon: <Zap className="w-4 h-4" />,
    category: 'other',
    defaultSize: 'large',
  },
];

const defaultLayout: DashboardLayout = {
  id: 'default',
  name: '默认布局',
  columns: 4,
  widgets: [
    { id: '1', widgetId: 'sales-overview', visible: true, order: 0, size: 'small' },
    { id: '2', widgetId: 'target-progress', visible: true, order: 1, size: 'small' },
    { id: '3', widgetId: 'active-projects', visible: true, order: 2, size: 'small' },
    { id: '4', widgetId: 'pending-approvals', visible: true, order: 3, size: 'small' },
    { id: '5', widgetId: 'sales-trend', visible: true, order: 4, size: 'large' },
    { id: '6', widgetId: 'recent-activities', visible: true, order: 5, size: 'medium' },
  ],
};

// ==================== 存储 ====================

const STORAGE_KEY = 'nexus-dashboard-layout';

function loadLayout(): DashboardLayout {
  if (typeof window === 'undefined') return defaultLayout;
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      return JSON.parse(saved);
    } catch {
      return defaultLayout;
    }
  }
  return defaultLayout;
}

function saveLayout(layout: DashboardLayout) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
}

// ==================== 子组件 ====================

interface WidgetCardProps {
  widget: Widget;
  instance?: WidgetInstance;
  onAdd?: () => void;
  onRemove?: () => void;
  onToggle?: (visible: boolean) => void;
  onSizeChange?: (size: 'small' | 'medium' | 'large') => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  mode: 'add' | 'manage';
  isFirst?: boolean;
  isLast?: boolean;
}

function WidgetCard({
  widget,
  instance,
  onAdd,
  onRemove,
  onToggle,
  onSizeChange,
  onMoveUp,
  onMoveDown,
  mode,
  isFirst,
  isLast,
}: WidgetCardProps) {
  const sizes = ['small', 'medium', 'large'] as const;
  const currentSizeIndex = instance ? sizes.indexOf(instance.size) : 0;

  return (
    <div
      className={cn(
        'flex items-center gap-3 p-3 rounded-lg border transition-all',
        'hover:bg-muted/50',
        instance && !instance.visible && 'opacity-50'
      )}
    >
      {mode === 'manage' && (
        <div className="flex flex-col gap-0.5">
          <button
            onClick={onMoveUp}
            disabled={isFirst}
            className="p-0.5 hover:bg-muted rounded disabled:opacity-30"
          >
            <ChevronUp className="w-3 h-3" />
          </button>
          <GripVertical className="w-3 h-3 text-muted-foreground" />
          <button
            onClick={onMoveDown}
            disabled={isLast}
            className="p-0.5 hover:bg-muted rounded disabled:opacity-30"
          >
            <ChevronDown className="w-3 h-3" />
          </button>
        </div>
      )}

      <div className="p-2 rounded-md bg-primary/10 text-primary">
        {widget.icon}
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{widget.title}</p>
        {widget.description && (
          <p className="text-xs text-muted-foreground truncate">
            {widget.description}
          </p>
        )}
      </div>

      {mode === 'add' ? (
        <Button size="sm" variant="outline" onClick={onAdd}>
          <Plus className="w-4 h-4" />
        </Button>
      ) : (
        <div className="flex items-center gap-2">
          {widget.resizable && (
            <div className="flex items-center gap-1">
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6"
                data-compact
                onClick={() => {
                  const newIndex = Math.max(0, currentSizeIndex - 1);
                  onSizeChange?.(sizes[newIndex]);
                }}
                disabled={currentSizeIndex === 0}
              >
                <Minus className="w-3 h-3" />
              </Button>
              <span className="text-xs text-muted-foreground w-8 text-center">
                {instance?.size === 'small' ? '小' : instance?.size === 'medium' ? '中' : '大'}
              </span>
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6"
                data-compact
                onClick={() => {
                  const newIndex = Math.min(sizes.length - 1, currentSizeIndex + 1);
                  onSizeChange?.(sizes[newIndex]);
                }}
                disabled={currentSizeIndex === sizes.length - 1}
              >
                <Plus className="w-3 h-3" />
              </Button>
            </div>
          )}

          <Switch
            checked={instance?.visible}
            onCheckedChange={onToggle}
          />

          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-destructive hover:text-destructive"
            onClick={onRemove}
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

// ==================== 主组件 ====================

interface DashboardCustomizerProps {
  onLayoutChange?: (layout: DashboardLayout) => void;
  trigger?: React.ReactNode;
}

export function DashboardCustomizer({
  onLayoutChange,
  trigger,
}: DashboardCustomizerProps) {
  const [open, setOpen] = useState(false);
  const [layout, setLayout] = useState<DashboardLayout>(loadLayout);
  const [hasChanges, setHasChanges] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);

  const widgetInstances = useMemo(() => {
    return layout.widgets
      .map((instance) => ({
        instance,
        widget: availableWidgets.find((w) => w.id === instance.widgetId)!,
      }))
      .filter((item) => item.widget)
      .sort((a, b) => a.instance.order - b.instance.order);
  }, [layout.widgets]);

  const unusedWidgets = useMemo(() => {
    const usedIds = new Set(layout.widgets.map((w) => w.widgetId));
    return availableWidgets.filter((w) => !usedIds.has(w.id));
  }, [layout.widgets]);

  const updateLayout = useCallback((newLayout: DashboardLayout) => {
    setLayout(newLayout);
    setHasChanges(true);
  }, []);

  const handleAddWidget = useCallback(
    (widgetId: string) => {
      const widget = availableWidgets.find((w) => w.id === widgetId);
      if (!widget) return;

      const newInstance: WidgetInstance = {
        id: Date.now().toString(),
        widgetId,
        visible: true,
        order: layout.widgets.length,
        size: widget.defaultSize,
      };

      updateLayout({
        ...layout,
        widgets: [...layout.widgets, newInstance],
      });

      toast.success(`已添加 "${widget.title}"`);
    },
    [layout, updateLayout]
  );

  const handleRemoveWidget = useCallback(
    (instanceId: string) => {
      updateLayout({
        ...layout,
        widgets: layout.widgets.filter((w) => w.id !== instanceId),
      });
    },
    [layout, updateLayout]
  );

  const handleToggleWidget = useCallback(
    (instanceId: string, visible: boolean) => {
      updateLayout({
        ...layout,
        widgets: layout.widgets.map((w) =>
          w.id === instanceId ? { ...w, visible } : w
        ),
      });
    },
    [layout, updateLayout]
  );

  const handleSizeChange = useCallback(
    (instanceId: string, size: 'small' | 'medium' | 'large') => {
      updateLayout({
        ...layout,
        widgets: layout.widgets.map((w) =>
          w.id === instanceId ? { ...w, size } : w
        ),
      });
    },
    [layout, updateLayout]
  );

  const handleMove = useCallback(
    (instanceId: string, direction: 'up' | 'down') => {
      const sortedWidgets = [...layout.widgets].sort((a, b) => a.order - b.order);
      const index = sortedWidgets.findIndex((w) => w.id === instanceId);
      if (index === -1) return;

      const newIndex = direction === 'up' ? index - 1 : index + 1;
      if (newIndex < 0 || newIndex >= sortedWidgets.length) return;

      const temp = sortedWidgets[index].order;
      sortedWidgets[index].order = sortedWidgets[newIndex].order;
      sortedWidgets[newIndex].order = temp;

      updateLayout({ ...layout, widgets: sortedWidgets });
    },
    [layout, updateLayout]
  );

  const handleSave = useCallback(() => {
    saveLayout(layout);
    onLayoutChange?.(layout);
    setHasChanges(false);
    toast.success('布局已保存');
  }, [layout, onLayoutChange]);

  const handleReset = useCallback(() => {
    setLayout(defaultLayout);
    saveLayout(defaultLayout);
    onLayoutChange?.(defaultLayout);
    setHasChanges(false);
    setConfirmReset(false);
    toast.success('已恢复默认布局');
  }, [onLayoutChange]);

  const groupedUnusedWidgets = useMemo(() => {
    const groups: Record<string, Widget[]> = {
      stats: [],
      charts: [],
      lists: [],
      other: [],
    };
    unusedWidgets.forEach((w) => {
      groups[w.category].push(w);
    });
    return groups;
  }, [unusedWidgets]);

  const categoryLabels: Record<string, string> = {
    stats: '统计卡片',
    charts: '图表',
    lists: '列表',
    other: '其他',
  };

  return (
    <>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          {trigger || (
            <Button variant="outline" size="sm">
              <LayoutGrid className="w-4 h-4 mr-2" />
              自定义布局
            </Button>
          )}
        </SheetTrigger>
        <SheetContent className="w-full sm:max-w-lg p-0">
          <SheetHeader className="p-6 pb-0">
            <SheetTitle className="flex items-center gap-2">
              <LayoutGrid className="w-5 h-5" />
              自定义仪表盘
            </SheetTitle>
            <SheetDescription>
              添加、移除或重新排列仪表盘小部件
            </SheetDescription>
          </SheetHeader>

          <Tabs defaultValue="widgets" className="flex-1">
            <div className="px-6 py-2">
              <TabsList className="w-full">
                <TabsTrigger value="widgets" className="flex-1">
                  当前小部件
                  <Badge variant="secondary" className="ml-2">
                    {layout.widgets.length}
                  </Badge>
                </TabsTrigger>
                <TabsTrigger value="add" className="flex-1">
                  添加小部件
                  <Badge variant="secondary" className="ml-2">
                    {unusedWidgets.length}
                  </Badge>
                </TabsTrigger>
              </TabsList>
            </div>

            <ScrollArea className="h-[calc(100dvh-16rem)] px-6">
              <TabsContent value="widgets" className="mt-0 space-y-2">
                {widgetInstances.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <LayoutGrid className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>暂无小部件</p>
                    <p className="text-sm">切换到"添加小部件"选项卡添加</p>
                  </div>
                ) : (
                  widgetInstances.map(({ widget, instance }, index) => (
                    <WidgetCard
                      key={instance.id}
                      widget={widget}
                      instance={instance}
                      mode="manage"
                      onToggle={(visible) => handleToggleWidget(instance.id, visible)}
                      onSizeChange={(size) => handleSizeChange(instance.id, size)}
                      onRemove={() => handleRemoveWidget(instance.id)}
                      onMoveUp={() => handleMove(instance.id, 'up')}
                      onMoveDown={() => handleMove(instance.id, 'down')}
                      isFirst={index === 0}
                      isLast={index === widgetInstances.length - 1}
                    />
                  ))
                )}
              </TabsContent>

              <TabsContent value="add" className="mt-0 space-y-6">
                {Object.entries(groupedUnusedWidgets).map(
                  ([category, widgets]) =>
                    widgets.length > 0 && (
                      <div key={category}>
                        <h4 className="text-sm font-medium text-muted-foreground mb-2">
                          {categoryLabels[category]}
                        </h4>
                        <div className="space-y-2">
                          {widgets.map((widget) => (
                            <WidgetCard
                              key={widget.id}
                              widget={widget}
                              mode="add"
                              onAdd={() => handleAddWidget(widget.id)}
                            />
                          ))}
                        </div>
                      </div>
                    )
                )}
                {unusedWidgets.length === 0 && (
                  <div className="text-center py-12 text-muted-foreground">
                    <Plus className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>所有小部件都已添加</p>
                  </div>
                )}
              </TabsContent>
            </ScrollArea>
          </Tabs>

          <SheetFooter className="p-6 pt-0 border-t mt-auto flex-row gap-2">
            <Button
              variant="outline"
              onClick={() => setConfirmReset(true)}
              className="flex-1"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              重置
            </Button>
            <Button
              onClick={handleSave}
              disabled={!hasChanges}
              className="flex-1"
            >
              <Save className="w-4 h-4 mr-2" />
              保存布局
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* 确认重置对话框 */}
      <Dialog open={confirmReset} onOpenChange={setConfirmReset}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认重置布局？</DialogTitle>
            <DialogDescription>
              这将恢复仪表盘到默认布局，您的自定义设置将会丢失。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmReset(false)}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleReset}>
              确认重置
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default DashboardCustomizer;