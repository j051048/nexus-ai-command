import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useCreateCustomer } from '@/hooks/useCRM';
import { toast } from 'sonner';
import { STAGES } from './constants';
import { SCIENTIFIC_INSTRUMENT_LINES, type InstrumentLineCode } from '@/config/growthOperatingModel';

export interface CustomerFormDialogProps {
  open: boolean;
  onClose: () => void;
}

export default function CustomerFormDialog({
  open,
  onClose,
}: CustomerFormDialogProps) {
  const createMutation = useCreateCustomer();
  const [form, setForm] = useState({
    name: '',
    company: '',
    industry: '',
    stage: 'lead',
    source: '',
    estimated_value: '',
    instrument_line_code: 'unclassified',
    application_field: '',
    purchase_stage: '',
  });

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      toast.error('请输入客户名称');
      return;
    }
    try {
      await createMutation.mutateAsync({
        name: form.name,
        company: form.company,
        industry: form.industry,
        stage: form.stage,
        source: form.source,
        estimated_value: form.estimated_value ? Number(form.estimated_value) : 0,
        instrument_line_code:
          form.instrument_line_code === 'unclassified'
            ? undefined
            : (form.instrument_line_code as InstrumentLineCode),
        instrument_line_codes:
          form.instrument_line_code === 'unclassified'
            ? []
            : [form.instrument_line_code as InstrumentLineCode],
        application_fields: form.application_field.trim()
          ? [form.application_field.trim()]
          : [],
        purchase_stage: form.purchase_stage || undefined,
      });
      setForm({ name: '', company: '', industry: '', stage: 'lead', source: '', estimated_value: '', instrument_line_code: 'unclassified', application_field: '', purchase_stage: '' });
      onClose();
    } catch {
      // error toast handled in hook
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建客户</DialogTitle>
          <DialogDescription>填写客户基本信息</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>客户名称 *</Label>
            <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="项目或客户名称" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>公司</Label>
              <Input value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} placeholder="公司名称" />
            </div>
            <div className="space-y-2">
              <Label>行业</Label>
              <Input value={form.industry} onChange={e => setForm({ ...form, industry: e.target.value })} placeholder="行业领域" />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>主营产品线</Label>
              <Select
                value={form.instrument_line_code}
                onValueChange={instrument_line_code => setForm({ ...form, instrument_line_code })}
              >
                <SelectTrigger><SelectValue placeholder="选择产品线" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="unclassified">暂不分类</SelectItem>
                  {SCIENTIFIC_INSTRUMENT_LINES.map(line => (
                    <SelectItem key={line.code} value={line.code}>{line.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>应用场景</Label>
              <Input
                value={form.application_field}
                onChange={event => setForm({ ...form, application_field: event.target.value })}
                placeholder="如环境检测、半导体失效分析"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>采购进度</Label>
            <Select value={form.purchase_stage} onValueChange={purchase_stage => setForm({ ...form, purchase_stage })}>
              <SelectTrigger><SelectValue placeholder="选择当前采购进度" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="requirement">需求确认</SelectItem>
                <SelectItem value="budget">预算申请</SelectItem>
                <SelectItem value="technical_validation">技术验证</SelectItem>
                <SelectItem value="tender">招投标</SelectItem>
                <SelectItem value="contract">合同审批</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>阶段</Label>
              <Select value={form.stage} onValueChange={v => setForm({ ...form, stage: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(STAGES).map(([key, val]) => (
                    <SelectItem key={key} value={key}>{val.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>来源</Label>
              <Select value={form.source} onValueChange={v => setForm({ ...form, source: v })}>
                <SelectTrigger><SelectValue placeholder="选择来源" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="website">网站</SelectItem>
                  <SelectItem value="referral">转介绍</SelectItem>
                  <SelectItem value="exhibition">展会</SelectItem>
                  <SelectItem value="cold_call">Cold Call</SelectItem>
                  <SelectItem value="other">其他</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label>预估金额</Label>
            <Input type="number" value={form.estimated_value} onChange={e => setForm({ ...form, estimated_value: e.target.value })} placeholder="预估交易金额" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={createMutation.isPending}>
            {createMutation.isPending ? '创建中...' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
