import React, { useRef } from 'react';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { Upload, X, FileText, AlertCircle } from 'lucide-react';

// ─── 类型定义 ──────────────────────────────────────────────

export interface FormField {
  key: string;
  label: string;
  type:
    | 'text'
    | 'number'
    | 'date'
    | 'daterange'
    | 'select'
    | 'multiselect'
    | 'file'
    | 'textarea';
  required?: boolean;
  placeholder?: string;
  options?: string[];
  min?: number;
  max?: number;
  file_types?: string[];
  max_files?: number;
  default_value?: any;
  description?: string;
}

export interface DynamicFormRendererProps {
  fields: FormField[];
  values: Record<string, any>;
  onChange: (key: string, value: any) => void;
  errors?: Record<string, string>;
  readOnly?: boolean;
  layout?: 'vertical' | 'grid';
}

// ─── 只读值显示 ─────────────────────────────────────────────

function ReadOnlyValue({ field, value }: { field: FormField; value: any }) {
  if (value === undefined || value === null || value === '') {
    return <span className="text-muted-foreground text-sm italic">未填写</span>;
  }

  switch (field.type) {
    case 'multiselect':
      if (Array.isArray(value) && value.length > 0) {
        return (
          <div className="flex flex-wrap gap-1.5">
            {value.map((v: string) => (
              <Badge key={v} variant="secondary" className="text-xs">
                {v}
              </Badge>
            ))}
          </div>
        );
      }
      return <span className="text-muted-foreground text-sm italic">未选择</span>;

    case 'daterange':
      if (value && typeof value === 'object') {
        const start = value.start || '未设置';
        const end = value.end || '未设置';
        return (
          <span className="text-sm text-foreground">
            {start} ~ {end}
          </span>
        );
      }
      return <span className="text-muted-foreground text-sm italic">未填写</span>;

    case 'file':
      if (Array.isArray(value) && value.length > 0) {
        return (
          <div className="space-y-1">
            {value.map((file: File | string, idx: number) => (
              <div
                key={idx}
                className="flex items-center gap-2 text-sm text-foreground"
              >
                <FileText className="w-4 h-4 text-muted-foreground" />
                <span>{typeof file === 'string' ? file : file.name}</span>
              </div>
            ))}
          </div>
        );
      }
      return <span className="text-muted-foreground text-sm italic">未上传</span>;

    case 'number':
      return <span className="text-sm text-foreground font-medium">{value}</span>;

    default:
      return <span className="text-sm text-foreground">{String(value)}</span>;
  }
}

// ─── 字段渲染器 ─────────────────────────────────────────────

function TextFieldRenderer({
  field,
  value,
  onChange,
}: {
  field: FormField;
  value: any;
  onChange: (val: any) => void;
}) {
  return (
    <Input
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={field.placeholder || `请输入${field.label}`}
      className="bg-background/50"
    />
  );
}

function NumberFieldRenderer({
  field,
  value,
  onChange,
}: {
  field: FormField;
  value: any;
  onChange: (val: any) => void;
}) {
  return (
    <Input
      type="number"
      value={value ?? ''}
      onChange={(e) => {
        const num = e.target.value === '' ? '' : Number(e.target.value);
        onChange(num);
      }}
      placeholder={field.placeholder || `请输入${field.label}`}
      min={field.min}
      max={field.max}
      className="bg-background/50"
    />
  );
}

function DateFieldRenderer({
  field,
  value,
  onChange,
}: {
  field: FormField;
  value: any;
  onChange: (val: any) => void;
}) {
  return (
    <Input
      type="date"
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      className="bg-background/50"
    />
  );
}

function DateRangeFieldRenderer({
  field,
  value,
  onChange,
}: {
  field: FormField;
  value: any;
  onChange: (val: any) => void;
}) {
  const rangeValue = value || { start: '', end: '' };

  return (
    <div className="flex items-center gap-2">
      <Input
        type="date"
        value={rangeValue.start || ''}
        onChange={(e) =>
          onChange({ ...rangeValue, start: e.target.value })
        }
        className="bg-background/50 flex-1"
      />
      <span className="text-muted-foreground text-sm shrink-0">至</span>
      <Input
        type="date"
        value={rangeValue.end || ''}
        onChange={(e) =>
          onChange({ ...rangeValue, end: e.target.value })
        }
        className="bg-background/50 flex-1"
      />
    </div>
  );
}

function SelectFieldRenderer({
  field,
  value,
  onChange,
}: {
  field: FormField;
  value: any;
  onChange: (val: any) => void;
}) {
  return (
    <Select value={value || ''} onValueChange={onChange}>
      <SelectTrigger className="bg-background/50">
        <SelectValue placeholder={field.placeholder || `请选择${field.label}`} />
      </SelectTrigger>
      <SelectContent>
        {(field.options || []).map((option) => (
          <SelectItem key={option} value={option}>
            {option}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function MultiselectFieldRenderer({
  field,
  value,
  onChange,
}: {
  field: FormField;
  value: any;
  onChange: (val: any) => void;
}) {
  const selectedValues: string[] = Array.isArray(value) ? value : [];

  const handleToggle = (option: string) => {
    if (selectedValues.includes(option)) {
      onChange(selectedValues.filter((v) => v !== option));
    } else {
      onChange([...selectedValues, option]);
    }
  };

  return (
    <div className="space-y-2">
      {(field.options || []).map((option) => (
        <label
          key={option}
          className="flex items-center gap-2 cursor-pointer group"
        >
          <Checkbox
            checked={selectedValues.includes(option)}
            onCheckedChange={() => handleToggle(option)}
          />
          <span className="text-sm text-foreground group-hover:text-primary transition-colors">
            {option}
          </span>
        </label>
      ))}
      {(!field.options || field.options.length === 0) && (
        <p className="text-sm text-muted-foreground italic">暂无可选项</p>
      )}
    </div>
  );
}

function FileFieldRenderer({
  field,
  value,
  onChange,
}: {
  field: FormField;
  value: any;
  onChange: (val: any) => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const files: File[] = Array.isArray(value) ? value : [];
  const maxFiles = field.max_files || 5;

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newFiles = Array.from(e.target.files || []);
    const combined = [...files, ...newFiles].slice(0, maxFiles);
    onChange(combined);
    // 重置 input，允许重复选同一文件
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleRemoveFile = (index: number) => {
    const updated = files.filter((_, i) => i !== index);
    onChange(updated);
  };

  const acceptTypes = field.file_types?.map((t) =>
    t.startsWith('.') ? t : `.${t}`
  ).join(',');

  return (
    <div className="space-y-3">
      <div
        className={cn(
          'border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors',
          'hover:border-primary/50 hover:bg-primary/5',
          files.length >= maxFiles
            ? 'opacity-50 pointer-events-none'
            : 'border-border'
        )}
        onClick={() => fileInputRef.current?.click()}
      >
        <Upload className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
        <p className="text-sm text-muted-foreground">
          点击上传文件
          {field.file_types && field.file_types.length > 0 && (
            <span className="block text-xs mt-1">
              支持格式: {field.file_types.join(', ')}
            </span>
          )}
          <span className="block text-xs mt-1">
            最多 {maxFiles} 个文件
          </span>
        </p>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        multiple={maxFiles > 1}
        accept={acceptTypes}
        onChange={handleFileSelect}
      />

      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((file, idx) => (
            <div
              key={idx}
              className="flex items-center gap-2 p-2 rounded-lg bg-secondary/50 border border-border"
            >
              <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
              <span className="text-sm text-foreground flex-1 truncate">
                {file.name}
              </span>
              <span className="text-xs text-muted-foreground shrink-0">
                {(file.size / 1024).toFixed(1)} KB
              </span>
              <button
                type="button"
                onClick={() => handleRemoveFile(idx)}
                className="text-muted-foreground hover:text-destructive transition-colors shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TextareaFieldRenderer({
  field,
  value,
  onChange,
}: {
  field: FormField;
  value: any;
  onChange: (val: any) => void;
}) {
  return (
    <Textarea
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={field.placeholder || `请输入${field.label}`}
      className="min-h-24 resize-none bg-background/50"
    />
  );
}

// ─── 字段分发渲染 ────────────────────────────────────────────

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: FormField;
  value: any;
  onChange: (val: any) => void;
}) {
  switch (field.type) {
    case 'text':
      return <TextFieldRenderer field={field} value={value} onChange={onChange} />;
    case 'number':
      return <NumberFieldRenderer field={field} value={value} onChange={onChange} />;
    case 'date':
      return <DateFieldRenderer field={field} value={value} onChange={onChange} />;
    case 'daterange':
      return <DateRangeFieldRenderer field={field} value={value} onChange={onChange} />;
    case 'select':
      return <SelectFieldRenderer field={field} value={value} onChange={onChange} />;
    case 'multiselect':
      return <MultiselectFieldRenderer field={field} value={value} onChange={onChange} />;
    case 'file':
      return <FileFieldRenderer field={field} value={value} onChange={onChange} />;
    case 'textarea':
      return <TextareaFieldRenderer field={field} value={value} onChange={onChange} />;
    default:
      return <TextFieldRenderer field={field} value={value} onChange={onChange} />;
  }
}

// ─── 主组件 ──────────────────────────────────────────────────

export function DynamicFormRenderer({
  fields,
  values,
  onChange,
  errors,
  readOnly = false,
  layout = 'vertical',
}: DynamicFormRendererProps) {
  if (!fields || fields.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground text-sm">
        暂无表单字段
      </div>
    );
  }

  return (
    <div
      className={cn(
        layout === 'grid'
          ? 'grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5'
          : 'space-y-5'
      )}
    >
      {fields.map((field) => {
        const error = errors?.[field.key];
        const value = values[field.key];

        return (
          <div
            key={field.key}
            className={cn(
              'space-y-1.5',
              // daterange 和 textarea 跨两列
              layout === 'grid' &&
                (field.type === 'daterange' || field.type === 'textarea' || field.type === 'file') &&
                'md:col-span-2'
            )}
          >
            {/* 标签 */}
            <label className="text-sm font-medium text-foreground flex items-center gap-1">
              {field.label}
              {field.required && (
                <span className="text-destructive">*</span>
              )}
            </label>

            {/* 帮助文本 */}
            {field.description && (
              <p className="text-xs text-muted-foreground">
                {field.description}
              </p>
            )}

            {/* 输入 / 只读展示 */}
            {readOnly ? (
              <div className="py-1">
                <ReadOnlyValue field={field} value={value} />
              </div>
            ) : (
              <FieldInput
                field={field}
                value={value}
                onChange={(val) => onChange(field.key, val)}
              />
            )}

            {/* 错误信息 */}
            {error && (
              <p className="text-xs text-destructive flex items-center gap-1 mt-1">
                <AlertCircle className="w-3 h-3" />
                {error}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
