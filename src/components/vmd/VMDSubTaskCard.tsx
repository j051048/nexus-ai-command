/**
 * VMDSubTaskCard — 可展开的人类中心子任务卡片
 *
 * 每个子任务由人类负责推进，支持：
 * - 3态状态切换 (todo → in_progress → done)
 * - 进度滑块 (0-100%)
 * - 负责人、日期、工作笔记编辑
 * - AI参考内容只读展示
 * - 向AI咨询入口
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Slider } from '@/components/ui/slider';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import {
  Clock,
  Play,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Bot,
  Trash2,
  User,
  CalendarDays,
  FileText,
} from 'lucide-react';
import type { VMDSubTask } from '@/hooks/useVMD';
import type { UpdateSubTaskPayload } from '@/hooks/useVMD';

const STATUS_CONFIG = {
  todo: { label: '待开始', color: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400', icon: Clock, next: 'in_progress' as const },
  in_progress: { label: '进行中', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300', icon: Play, next: 'done' as const },
  done: { label: '已完成', color: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300', icon: CheckCircle2, next: 'todo' as const },
} as const;

const AGENT_ICONS: Record<string, string> = {
  director: '🎯', content: '✍️', design: '🎨', media: '📢',
  clue: '🔍', compliance: '🛡️', operation: '⚙️', synergy: '🔗',
  pr: '📰', sales: '💰', content_creator: '✍️', data_analyst: '📊',
  market_researcher: '🔍', reviewer: '👁️',
};

interface VMDSubTaskCardProps {
  subTask: VMDSubTask;
  index: number;
  onUpdate: (subTaskId: string, data: UpdateSubTaskPayload) => void;
  onDelete: (subTaskId: string) => void;
  onAIChat: (subTask: VMDSubTask) => void;
}

export function VMDSubTaskCard({ subTask, index, onUpdate, onDelete, onAIChat }: VMDSubTaskCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleValue, setTitleValue] = useState(subTask.title);
  const [notesValue, setNotesValue] = useState(subTask.human_notes || '');
  const titleInputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const status = (subTask.status as keyof typeof STATUS_CONFIG) || 'todo';
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.todo;
  const StatusIcon = cfg.icon;

  // Sync props to local state
  useEffect(() => { setTitleValue(subTask.title); }, [subTask.title]);
  useEffect(() => { setNotesValue(subTask.human_notes || ''); }, [subTask.human_notes]);

  // Focus title input when editing
  useEffect(() => {
    if (editingTitle) titleInputRef.current?.focus();
  }, [editingTitle]);

  // Debounced update helper
  const debouncedUpdate = useCallback((data: UpdateSubTaskPayload) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      onUpdate(subTask.id, data);
    }, 600);
  }, [subTask.id, onUpdate]);

  const handleStatusCycle = (e: React.MouseEvent) => {
    e.stopPropagation();
    onUpdate(subTask.id, { status: cfg.next });
  };

  const handleProgressChange = (value: number[]) => {
    debouncedUpdate({ progress: value[0] });
  };

  const handleTitleSubmit = () => {
    setEditingTitle(false);
    if (titleValue.trim() && titleValue !== subTask.title) {
      onUpdate(subTask.id, { title: titleValue.trim() });
    } else {
      setTitleValue(subTask.title);
    }
  };

  const handleNotesChange = (val: string) => {
    setNotesValue(val);
    debouncedUpdate({ human_notes: val });
  };

  return (
    <Card className={cn(
      "border-border/50 transition-all",
      status === 'done' && "opacity-75",
    )}>
      <CardContent className="p-0">
        {/* Collapsed header row */}
        <div
          className="flex items-center gap-3 p-3 cursor-pointer hover:bg-muted/30 transition-colors"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />
          )}

          <span className="text-lg shrink-0">{AGENT_ICONS[subTask.agent_role] || '📋'}</span>

          <span className="text-xs text-muted-foreground font-mono w-6 shrink-0">#{index + 1}</span>

          {/* Title (double-click to edit) */}
          <div className="flex-1 min-w-0" onClick={(e) => e.stopPropagation()}>
            {editingTitle ? (
              <Input
                ref={titleInputRef}
                value={titleValue}
                onChange={(e) => setTitleValue(e.target.value)}
                onBlur={handleTitleSubmit}
                onKeyDown={(e) => { if (e.key === 'Enter') handleTitleSubmit(); if (e.key === 'Escape') { setEditingTitle(false); setTitleValue(subTask.title); } }}
                className="h-7 text-sm px-2"
              />
            ) : (
              <p
                className={cn("text-sm font-medium truncate", status === 'done' && "line-through text-muted-foreground")}
                onDoubleClick={() => setEditingTitle(true)}
                title="双击编辑标题"
              >
                {subTask.title}
              </p>
            )}
          </div>

          {/* Status badge (click to cycle) */}
          <Badge
            className={cn("text-[10px] cursor-pointer hover:opacity-80 shrink-0", cfg.color)}
            onClick={handleStatusCycle}
            title="点击切换状态"
          >
            <StatusIcon className="w-3 h-3 mr-1" />
            {cfg.label}
          </Badge>

          {/* Progress number */}
          <span className="text-xs text-muted-foreground w-10 text-right shrink-0">
            {subTask.progress}%
          </span>
        </div>

        {/* Mini progress bar */}
        <Progress value={subTask.progress} className="h-[2px] rounded-none" />

        {/* Expanded area */}
        {expanded && (
          <div className="px-4 pb-4 pt-3 space-y-4 border-t border-border/30">
            {/* Progress slider */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-muted-foreground">进度</span>
                <span className="text-xs text-muted-foreground">{subTask.progress}%</span>
              </div>
              <Slider
                value={[subTask.progress]}
                onValueChange={handleProgressChange}
                max={100}
                step={5}
                className="w-full"
              />
            </div>

            {/* Assignee & Dates row */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground flex items-center gap-1">
                  <User className="w-3 h-3" /> 负责人
                </label>
                <Input
                  value={subTask.assignee_name || ''}
                  onChange={(e) => onUpdate(subTask.id, { assignee_name: e.target.value })}
                  placeholder="输入负责人"
                  className="h-8 text-xs"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground flex items-center gap-1">
                  <CalendarDays className="w-3 h-3" /> 开始日期
                </label>
                <Input
                  type="date"
                  value={subTask.start_date || ''}
                  onChange={(e) => onUpdate(subTask.id, { start_date: e.target.value || null })}
                  className="h-8 text-xs"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground flex items-center gap-1">
                  <CalendarDays className="w-3 h-3" /> 截止日期
                </label>
                <Input
                  type="date"
                  value={subTask.due_date || ''}
                  onChange={(e) => onUpdate(subTask.id, { due_date: e.target.value || null })}
                  className="h-8 text-xs"
                />
              </div>
            </div>

            {/* Human notes */}
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground flex items-center gap-1">
                <FileText className="w-3 h-3" /> 工作笔记
              </label>
              <Textarea
                value={notesValue}
                onChange={(e) => handleNotesChange(e.target.value)}
                placeholder="记录您的工作内容和交付物..."
                rows={3}
                className="text-sm resize-none"
              />
            </div>

            {/* AI reference output (read-only) */}
            {subTask.output && (
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground flex items-center gap-1">
                  <Bot className="w-3 h-3" /> AI参考内容
                </label>
                <div className="bg-muted/50 rounded-md p-3 text-xs text-muted-foreground whitespace-pre-wrap max-h-32 overflow-y-auto">
                  {subTask.output}
                </div>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex items-center justify-between pt-1">
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs gap-1"
                onClick={() => onAIChat(subTask)}
              >
                <Bot className="w-3 h-3" /> 向AI咨询
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-xs text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950 gap-1"
                onClick={() => onDelete(subTask.id)}
              >
                <Trash2 className="w-3 h-3" /> 删除
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
