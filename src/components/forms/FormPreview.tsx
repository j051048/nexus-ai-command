import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Eye } from 'lucide-react';
import { DynamicFormRenderer } from './DynamicFormRenderer';
import type { FormField } from './DynamicFormRenderer';

// ─── 类型定义 ──────────────────────────────────────────────

interface FormPreviewProps {
  fields: FormField[];
  formName?: string;
}

// ─── 主组件 ──────────────────────────────────────────────────

export function FormPreview({ fields, formName }: FormPreviewProps) {
  const [previewValues, setPreviewValues] = useState<Record<string, unknown>>({});

  // 当字段列表变化时，初始化默认值
  useEffect(() => {
    const defaults: Record<string, unknown> = {};
    fields.forEach((field) => {
      if (field.default_value !== undefined && field.default_value !== '') {
        defaults[field.key] = field.default_value;
      }
    });
    setPreviewValues((prev) => {
      // 保留已有的值，补充新字段的默认值
      const merged = { ...defaults };
      for (const key of Object.keys(prev)) {
        if (fields.some((f) => f.key === key)) {
          merged[key] = prev[key];
        }
      }
      return merged;
    });
  }, [fields]);

  const handleChange = (key: string, value: unknown) => {
    setPreviewValues((prev) => ({ ...prev, [key]: value }));
  };

  // 简单校验预览
  const errors: Record<string, string> = {};
  fields.forEach((field) => {
    if (field.required) {
      const val = previewValues[field.key];
      if (val === undefined || val === null || val === '' || (Array.isArray(val) && val.length === 0)) {
        // 只在有值被修改过后才展示错误（初始状态不标红）
        // 暂不展示，仅作校验示意
      }
    }
  });

  return (
    <div className="space-y-4">
      {/* 预览模式标签 */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">
          {formName || '表单预览'}
        </h3>
        <Badge variant="outline" className="gap-1">
          <Eye className="w-3 h-3" />
          预览模式
        </Badge>
      </div>

      {/* 预览边框 */}
      <div className="border-2 border-dashed border-primary/20 rounded-xl p-5 bg-background/50">
        {fields.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground text-sm">
            <Eye className="w-10 h-10 mx-auto mb-3 opacity-20" />
            <p>添加字段后将在此处实时预览</p>
          </div>
        ) : (
          <DynamicFormRenderer
            fields={fields}
            values={previewValues}
            onChange={handleChange}
            errors={errors}
            layout="vertical"
          />
        )}
      </div>

      {/* 填写数据预览 */}
      {fields.length > 0 && Object.keys(previewValues).length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">
            填写数据 (JSON)
          </p>
          <pre className="text-xs p-3 rounded-lg bg-secondary/50 border border-border overflow-auto max-h-40 text-muted-foreground">
            {JSON.stringify(previewValues, (_, v) => {
              // File 对象转为名称展示
              if (v instanceof File) return v.name;
              return v;
            }, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
