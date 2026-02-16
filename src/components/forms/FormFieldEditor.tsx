import React, { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import {
  ChevronDown,
  ChevronUp,
  Trash2,
  ArrowUp,
  ArrowDown,
  Plus,
  X,
  GripVertical,
} from 'lucide-react';
import type { FormField } from './DynamicFormRenderer';

// ─── 类型定义 ──────────────────────────────────────────────

const fieldTypeLabels: Record<FormField['type'], string> = {
  text: '单行文本',
  number: '数字',
  date: '日期',
  daterange: '日期范围',
  select: '下拉选择',
  multiselect: '多选',
  file: '文件上传',
  textarea: '多行文本',
};

interface FormFieldEditorProps {
  field: FormField;
  index: number;
  total: number;
  onUpdate: (field: FormField) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}

// ─── 选项编辑器 ─────────────────────────────────────────────

function OptionsEditor({
  options,
  onChange,
}: {
  options: string[];
  onChange: (opts: string[]) => void;
}) {
  const [newOption, setNewOption] = useState('');

  const handleAdd = () => {
    const trimmed = newOption.trim();
    if (!trimmed) return;
    if (options.includes(trimmed)) return;
    onChange([...options, trimmed]);
    setNewOption('');
  };

  const handleRemove = (index: number) => {
    onChange(options.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAdd();
    }
  };

  return (
    <div className="space-y-2">
      <label className="text-xs font-medium text-muted-foreground">选项列表</label>
      {options.length > 0 && (
        <div className="space-y-1">
          {options.map((opt, idx) => (
            <div
              key={idx}
              className="flex items-center gap-2 p-1.5 rounded bg-secondary/50"
            >
              <span className="text-sm text-foreground flex-1">{opt}</span>
              <button
                type="button"
                onClick={() => handleRemove(idx)}
                className="text-muted-foreground hover:text-destructive transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        <Input
          value={newOption}
          onChange={(e) => setNewOption(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入选项后回车添加"
          className="flex-1 h-8 text-sm"
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleAdd}
          disabled={!newOption.trim()}
          className="h-8 px-2"
        >
          <Plus className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}

// ─── 文件类型编辑器 ─────────────────────────────────────────

function FileTypesEditor({
  fileTypes,
  onChange,
}: {
  fileTypes: string[];
  onChange: (types: string[]) => void;
}) {
  const [newType, setNewType] = useState('');

  const handleAdd = () => {
    const trimmed = newType.trim().replace(/^\./, '');
    if (!trimmed) return;
    if (fileTypes.includes(trimmed)) return;
    onChange([...fileTypes, trimmed]);
    setNewType('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAdd();
    }
  };

  return (
    <div className="space-y-2">
      <label className="text-xs font-medium text-muted-foreground">
        允许的文件类型
      </label>
      {fileTypes.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {fileTypes.map((ft, idx) => (
            <span
              key={idx}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-secondary text-xs text-foreground"
            >
              .{ft}
              <button
                type="button"
                onClick={() => onChange(fileTypes.filter((_, i) => i !== idx))}
                className="text-muted-foreground hover:text-destructive"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        <Input
          value={newType}
          onChange={(e) => setNewType(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="如 pdf, docx, png"
          className="flex-1 h-8 text-sm"
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleAdd}
          disabled={!newType.trim()}
          className="h-8 px-2"
        >
          <Plus className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}

// ─── 主组件 ──────────────────────────────────────────────────

export function FormFieldEditor({
  field,
  index,
  total,
  onUpdate,
  onDelete,
  onMoveUp,
  onMoveDown,
}: FormFieldEditorProps) {
  const [expanded, setExpanded] = useState(false);

  const update = (partial: Partial<FormField>) => {
    onUpdate({ ...field, ...partial });
  };

  const handleTypeChange = (newType: FormField['type']) => {
    const updated: Partial<FormField> = { type: newType };
    // 切换类型时清理不相关属性
    if (newType !== 'select' && newType !== 'multiselect') {
      updated.options = undefined;
    }
    if (newType !== 'number') {
      updated.min = undefined;
      updated.max = undefined;
    }
    if (newType !== 'file') {
      updated.file_types = undefined;
      updated.max_files = undefined;
    }
    // 若切换到 select/multiselect 且没有 options，初始化空数组
    if ((newType === 'select' || newType === 'multiselect') && !field.options) {
      updated.options = [];
    }
    if (newType === 'file') {
      updated.file_types = field.file_types || [];
      updated.max_files = field.max_files || 5;
    }
    update(updated);
  };

  return (
    <div
      className={cn(
        'border rounded-xl transition-colors',
        expanded ? 'border-primary/30 bg-primary/5' : 'border-border bg-card'
      )}
    >
      {/* 折叠头部 */}
      <div
        className="flex items-center gap-3 p-3 cursor-pointer select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <GripVertical className="w-4 h-4 text-muted-foreground shrink-0" />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-foreground truncate">
              {field.label || '未命名字段'}
            </span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-secondary text-muted-foreground">
              {fieldTypeLabels[field.type] || field.type}
            </span>
            {field.required && (
              <span className="text-xs text-destructive font-medium">必填</span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            字段标识: {field.key}
          </p>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onMoveUp();
            }}
            disabled={index === 0}
            className="h-7 w-7 p-0"
            data-compact
          >
            <ArrowUp className="w-3.5 h-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onMoveDown();
            }}
            disabled={index === total - 1}
            className="h-7 w-7 p-0"
            data-compact
          >
            <ArrowDown className="w-3.5 h-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="h-7 w-7 p-0 text-destructive hover:text-destructive"
            data-compact
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>

          {expanded ? (
            <ChevronUp className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          )}
        </div>
      </div>

      {/* 展开内容 */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-border/50 pt-4">
          {/* 基础属性行 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                字段标识 (key)
              </label>
              <Input
                value={field.key}
                onChange={(e) => update({ key: e.target.value })}
                placeholder="field_key"
                className="h-8 text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                字段名称 (label)
              </label>
              <Input
                value={field.label}
                onChange={(e) => update({ label: e.target.value })}
                placeholder="字段名称"
                className="h-8 text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                字段类型
              </label>
              <Select
                value={field.type}
                onValueChange={(val) =>
                  handleTypeChange(val as FormField['type'])
                }
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(fieldTypeLabels).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                占位提示
              </label>
              <Input
                value={field.placeholder || ''}
                onChange={(e) => update({ placeholder: e.target.value })}
                placeholder="占位提示文字"
                className="h-8 text-sm"
              />
            </div>
          </div>

          {/* 必填开关 */}
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-muted-foreground">
              必填字段
            </label>
            <Switch
              checked={!!field.required}
              onCheckedChange={(checked) => update({ required: checked })}
            />
          </div>

          {/* 帮助文本 */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              帮助描述
            </label>
            <Input
              value={field.description || ''}
              onChange={(e) => update({ description: e.target.value })}
              placeholder="可选，字段帮助描述"
              className="h-8 text-sm"
            />
          </div>

          {/* 默认值 */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              默认值
            </label>
            <Input
              value={field.default_value ?? ''}
              onChange={(e) => update({ default_value: e.target.value })}
              placeholder="可选，默认值"
              className="h-8 text-sm"
            />
          </div>

          {/* number 类型: min/max */}
          {field.type === 'number' && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  最小值
                </label>
                <Input
                  type="number"
                  value={field.min ?? ''}
                  onChange={(e) =>
                    update({
                      min: e.target.value === '' ? undefined : Number(e.target.value),
                    })
                  }
                  placeholder="不限"
                  className="h-8 text-sm"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  最大值
                </label>
                <Input
                  type="number"
                  value={field.max ?? ''}
                  onChange={(e) =>
                    update({
                      max: e.target.value === '' ? undefined : Number(e.target.value),
                    })
                  }
                  placeholder="不限"
                  className="h-8 text-sm"
                />
              </div>
            </div>
          )}

          {/* select / multiselect: options */}
          {(field.type === 'select' || field.type === 'multiselect') && (
            <OptionsEditor
              options={field.options || []}
              onChange={(opts) => update({ options: opts })}
            />
          )}

          {/* file: file_types + max_files */}
          {field.type === 'file' && (
            <>
              <FileTypesEditor
                fileTypes={field.file_types || []}
                onChange={(types) => update({ file_types: types })}
              />
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  最大文件数
                </label>
                <Input
                  type="number"
                  value={field.max_files ?? 5}
                  onChange={(e) =>
                    update({
                      max_files:
                        e.target.value === ''
                          ? undefined
                          : Math.max(1, Number(e.target.value)),
                    })
                  }
                  min={1}
                  max={20}
                  className="h-8 text-sm w-24"
                />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
