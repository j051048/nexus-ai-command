import { useState } from 'react';
import { Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { SCIENTIFIC_INSTRUMENT_LINES } from '@/config/growthOperatingModel';

import type { TenderProjectInput } from './types';

interface TenderProjectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (input: TenderProjectInput) => Promise<void>;
  pending: boolean;
}

export function TenderProjectDialog({ open, onOpenChange, onSubmit, pending }: TenderProjectDialogProps) {
  const [form, setForm] = useState<TenderProjectInput>({ name: '' });

  const submit = async () => {
    if (form.name.trim().length < 2) return;
    await onSubmit({
      ...form,
      name: form.name.trim(),
      client_name: form.client_name?.trim() || undefined,
      application_field: form.application_field?.trim() || undefined,
      target_product_models: form.target_product_models?.filter(Boolean),
    });
    setForm({ name: '' });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>新建投标项目</DialogTitle>
          <DialogDescription>先记录最少必要信息，招标文件上传后由 AI 补齐要求和风险。</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2 sm:grid-cols-2">
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="tender-project-name">项目名称</Label>
            <Input
              id="tender-project-name"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="如：某高校质谱仪采购项目"
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="tender-client">采购方</Label>
            <Input
              id="tender-client"
              value={form.client_name || ''}
              onChange={(event) => setForm((current) => ({ ...current, client_name: event.target.value }))}
              placeholder="高校、研究院或企业"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="tender-deadline">投标截止</Label>
            <Input
              id="tender-deadline"
              type="datetime-local"
              value={form.deadline || ''}
              onChange={(event) => setForm((current) => ({ ...current, deadline: event.target.value || undefined }))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="tender-line">产品线</Label>
            <select
              id="tender-line"
              value={form.instrument_line_code || ''}
              onChange={(event) => setForm((current) => ({ ...current, instrument_line_code: event.target.value || undefined }))}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">待确认</option>
              {SCIENTIFIC_INSTRUMENT_LINES.map((line) => (
                <option key={line.code} value={line.code}>{line.name}</option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="tender-value">预计金额</Label>
            <Input
              id="tender-value"
              type="number"
              min="0"
              value={form.estimated_value ?? ''}
              onChange={(event) => setForm((current) => ({ ...current, estimated_value: event.target.value ? Number(event.target.value) : undefined }))}
              placeholder="人民币"
            />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="tender-application">应用场景</Label>
            <Input
              id="tender-application"
              value={form.application_field || ''}
              onChange={(event) => setForm((current) => ({ ...current, application_field: event.target.value }))}
              placeholder="如：环境痕量元素检测、药物杂质分析"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={submit} disabled={pending || form.name.trim().length < 2}>
            {pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            创建并进入
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
