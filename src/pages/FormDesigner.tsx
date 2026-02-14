import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import {
  ArrowLeft,
  Save,
  Plus,
  Loader2,
} from 'lucide-react';
import { FormFieldEditor } from '@/components/forms/FormFieldEditor';
import { FormPreview } from '@/components/forms/FormPreview';
import {
  useFormSchema,
  useCreateFormSchema,
  useUpdateFormSchema,
} from '@/hooks/useFormSchemas';
import { approvalTypes } from '@/components/approval/constants';
import type { FormField } from '@/components/forms/DynamicFormRenderer';

// ─── 默认新字段 ─────────────────────────────────────────────

function createDefaultField(index: number): FormField {
  return {
    key: `field_${Date.now()}_${index}`,
    label: `新字段 ${index + 1}`,
    type: 'text',
    required: false,
  };
}

// ─── 主页面 ──────────────────────────────────────────────────

function FormDesigner() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const isEditing = !!id;

  // 数据加载
  const { data: existingSchema, isLoading } = useFormSchema(id || '');
  const createSchema = useCreateFormSchema();
  const updateSchema = useUpdateFormSchema();

  // 表单状态
  const [formName, setFormName] = useState('');
  const [approvalType, setApprovalType] = useState('');
  const [fields, setFields] = useState<FormField[]>([]);

  // 加载已有 schema
  useEffect(() => {
    if (existingSchema) {
      setFormName(existingSchema.name || '');
      setApprovalType(existingSchema.approval_type || '');
      setFields(existingSchema.fields || []);
    }
  }, [existingSchema]);

  // ─── 字段操作 ──────────────────────────────────────────

  const addField = () => {
    setFields((prev) => [...prev, createDefaultField(prev.length)]);
  };

  const updateField = (index: number, updatedField: FormField) => {
    setFields((prev) => prev.map((f, i) => (i === index ? updatedField : f)));
  };

  const deleteField = (index: number) => {
    setFields((prev) => prev.filter((_, i) => i !== index));
  };

  const moveField = (index: number, direction: 'up' | 'down') => {
    setFields((prev) => {
      const next = [...prev];
      const targetIndex = direction === 'up' ? index - 1 : index + 1;
      if (targetIndex < 0 || targetIndex >= next.length) return prev;
      [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
      return next;
    });
  };

  // ─── 保存 ──────────────────────────────────────────────

  const handleSave = async () => {
    if (!formName.trim()) {
      toast.error('请输入表单名称');
      return;
    }
    if (!approvalType) {
      toast.error('请选择审批类型');
      return;
    }
    if (fields.length === 0) {
      toast.error('请至少添加一个字段');
      return;
    }

    // 校验字段 key 唯一性
    const keys = fields.map((f) => f.key);
    const duplicateKeys = keys.filter((k, i) => keys.indexOf(k) !== i);
    if (duplicateKeys.length > 0) {
      toast.error(`字段标识重复: ${duplicateKeys.join(', ')}`);
      return;
    }

    try {
      if (isEditing && id) {
        await updateSchema.mutateAsync({
          id,
          name: formName,
          approval_type: approvalType,
          fields,
        });
        toast.success('表单已更新');
      } else {
        const result = await createSchema.mutateAsync({
          name: formName,
          approval_type: approvalType,
          fields,
        });
        toast.success('表单已创建');
        // 跳转到编辑模式
        navigate(`/form-designer/${result.id}`, { replace: true });
      }
    } catch (error: unknown) {
      const err = error as Error;
      toast.error('保存失败: ' + err.message);
    }
  };

  const isSaving = createSchema.isPending || updateSchema.isPending;

  // ─── 加载状态 ──────────────────────────────────────────

  if (isEditing && isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  // ─── 渲染 ──────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
            className="gap-1"
          >
            <ArrowLeft className="w-4 h-4" />
            返回
          </Button>
          <h1 className="text-xl font-bold text-foreground">
            {isEditing ? '编辑表单' : '创建表单'}
          </h1>
        </div>

        <Button
          onClick={handleSave}
          disabled={isSaving}
          className="gap-1 shadow-lg shadow-primary/20"
        >
          {isSaving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          保存表单
        </Button>
      </div>

      {/* 表单基本信息 */}
      <div className="bg-card rounded-2xl p-5 border border-border shadow-sm">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              表单名称
            </label>
            <Input
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="如: 出差申请表"
              className="bg-background/50"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              审批类型
            </label>
            <Select value={approvalType} onValueChange={setApprovalType}>
              <SelectTrigger className="bg-background/50">
                <SelectValue placeholder="选择关联的审批类型" />
              </SelectTrigger>
              <SelectContent>
                {approvalTypes.map((type) => (
                  <SelectItem key={type.id} value={type.id}>
                    {type.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* 主内容区: 左右分栏 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 左侧: 字段列表 */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">
              字段列表 ({fields.length})
            </h2>
          </div>

          <div className="space-y-3">
            {fields.map((field, index) => (
              <FormFieldEditor
                key={field.key}
                field={field}
                index={index}
                total={fields.length}
                onUpdate={(updated) => updateField(index, updated)}
                onDelete={() => deleteField(index)}
                onMoveUp={() => moveField(index, 'up')}
                onMoveDown={() => moveField(index, 'down')}
              />
            ))}
          </div>

          {/* 添加字段 */}
          <Button
            variant="outline"
            onClick={addField}
            className="w-full border-dashed gap-1"
          >
            <Plus className="w-4 h-4" />
            添加字段
          </Button>
        </div>

        {/* 右侧: 实时预览 */}
        <div className="bg-card rounded-2xl p-5 border border-border shadow-sm">
          <FormPreview fields={fields} formName={formName} />
        </div>
      </div>
    </div>
  );
}

export default FormDesigner;
