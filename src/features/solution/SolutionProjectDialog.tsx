import { useEffect, useState } from 'react';

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
import { Textarea } from '@/components/ui/textarea';
import { SCIENTIFIC_INSTRUMENT_LINES } from '@/config/growthOperatingModel';

import type { SolutionBrief, SolutionContextOptions } from './types';

interface SolutionProjectDialogProps {
  open: boolean;
  options?: SolutionContextOptions;
  initialCustomerId?: string | null;
  isSubmitting?: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (input: SolutionBrief) => Promise<void>;
}

const EMPTY_BRIEF: SolutionBrief = { title: '', customer_id: null, template_id: null };

export function SolutionProjectDialog({
  open,
  options,
  initialCustomerId,
  isSubmitting,
  onOpenChange,
  onSubmit,
}: SolutionProjectDialogProps) {
  const [form, setForm] = useState<SolutionBrief>(EMPTY_BRIEF);

  useEffect(() => {
    if (!open) return;
    const customer = options?.customers.find((item) => item.id === initialCustomerId);
    setForm({
      ...EMPTY_BRIEF,
      title: customer ? `${customer.company || customer.name}解决方案` : '',
      customer_id: customer?.id || null,
      customer_name: customer?.company || customer?.name || '',
      industry: customer?.industry || '',
      instrument_line_code: customer?.instrument_line_code || '',
      application_scenario: customer?.application_fields?.join('、') || '',
    });
  }, [initialCustomerId, open, options]);

  const update = <K extends keyof SolutionBrief>(key: K, value: SolutionBrief[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  const selectCustomer = (customerId: string) => {
    const customer = options?.customers.find((item) => item.id === customerId);
    setForm((current) => ({
      ...current,
      customer_id: customerId || null,
      customer_name: customer?.company || customer?.name || '',
      industry: customer?.industry || current.industry,
      instrument_line_code: customer?.instrument_line_code || current.instrument_line_code,
      application_scenario: customer?.application_fields?.join('、') || current.application_scenario,
    }));
  };

  const selectScenarioPack = (code: string) => {
    const pack = options?.scenario_packs?.find((item) => item.code === code);
    setForm((current) => ({
      ...current,
      scenario_pack_code: code || null,
      instrument_line_code: pack?.instrument_line_code || current.instrument_line_code,
      industry: pack?.industry || current.industry,
    }));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>新建客户方案</DialogTitle>
          <DialogDescription>先录入已知事实。缺失信息可以稍后补齐，AI 不会替你虚构参数或预算。</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2 md:grid-cols-2">
          <label className="space-y-1.5 text-sm font-medium md:col-span-2">
            方案名称
            <Input value={form.title} onChange={(event) => update('title', event.target.value)} placeholder="例如：华东制药实验室液相色谱升级方案" />
          </label>
          <label className="space-y-1.5 text-sm font-medium md:col-span-2">
            行业场景包
            <select value={form.scenario_pack_code || ''} onChange={(event) => selectScenarioPack(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
              <option value="">不使用场景包</option>
              {options?.scenario_packs?.map((pack) => <option key={pack.code} value={pack.code}>{pack.name}</option>)}
            </select>
            {form.scenario_pack_code && <span className="block text-xs font-normal text-muted-foreground">场景包只预置核验清单和章节结构，不会填入未经确认的客户事实。</span>}
          </label>
          <label className="space-y-1.5 text-sm font-medium">
            关联客户
            <select value={form.customer_id || ''} onChange={(event) => selectCustomer(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
              <option value="">暂不关联</option>
              {options?.customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.company || customer.name}</option>)}
            </select>
          </label>
          <label className="space-y-1.5 text-sm font-medium">
            客户名称
            <Input value={form.customer_name || ''} onChange={(event) => update('customer_name', event.target.value)} />
          </label>
          <label className="space-y-1.5 text-sm font-medium">
            行业
            <Input value={form.industry || ''} onChange={(event) => update('industry', event.target.value)} placeholder="制药、半导体、科研院所等" />
          </label>
          <label className="space-y-1.5 text-sm font-medium">
            地区
            <Input value={form.region || ''} onChange={(event) => update('region', event.target.value)} placeholder="省市或服务区域" />
          </label>
          <label className="space-y-1.5 text-sm font-medium">
            仪器谱系
            <select value={form.instrument_line_code || ''} onChange={(event) => update('instrument_line_code', event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
              <option value="">待确认</option>
              {SCIENTIFIC_INSTRUMENT_LINES.map((line) => <option key={line.code} value={line.code}>{line.name}</option>)}
            </select>
          </label>
          <label className="space-y-1.5 text-sm font-medium">
            使用企业模板
            <select value={form.template_id || ''} onChange={(event) => update('template_id', event.target.value || null)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
              <option value="">不套用模板</option>
              {options?.templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
            </select>
          </label>
          <label className="space-y-1.5 text-sm font-medium">
            最低预算
            <Input type="number" min={0} value={form.budget_min ?? ''} onChange={(event) => update('budget_min', event.target.value ? Number(event.target.value) : undefined)} />
          </label>
          <label className="space-y-1.5 text-sm font-medium">
            最高预算
            <Input type="number" min={0} value={form.budget_max ?? ''} onChange={(event) => update('budget_max', event.target.value ? Number(event.target.value) : undefined)} />
          </label>
          <label className="space-y-1.5 text-sm font-medium md:col-span-2">
            应用场景与客户目标
            <Textarea value={form.application_scenario || ''} onChange={(event) => update('application_scenario', event.target.value)} placeholder="样品类型、检测目标、通量、精度、现有设备、安装环境与期望交付时间" />
          </label>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button disabled={isSubmitting || form.title.trim().length < 2} onClick={() => onSubmit(form)}>
            {isSubmitting ? '正在创建...' : '创建并进入需求澄清'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
