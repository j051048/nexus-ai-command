import React from 'react';
import {
  Phone,
  Mail,
  Calendar,
  FileText,
  TrendingUp,
} from 'lucide-react';
import type { ExportColumn } from '@/components/common/DataExport';

export const STAGES: Record<string, { name: string; color: string; bg: string }> = {
  lead: { name: '线索', color: 'text-slate-600', bg: 'bg-slate-100 dark:bg-slate-800' },
  prospect: { name: '意向', color: 'text-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/30' },
  opportunity: { name: '商机', color: 'text-amber-600', bg: 'bg-amber-100 dark:bg-amber-900/30' },
  customer: { name: '成交', color: 'text-green-600', bg: 'bg-green-100 dark:bg-green-900/30' },
  churned: { name: '流失', color: 'text-red-600', bg: 'bg-red-100 dark:bg-red-900/30' },
};

export const CRM_EXPORT_COLUMNS: ExportColumn[] = [
  { key: 'name', label: '客户名称' },
  { key: 'company', label: '公司' },
  { key: 'industry', label: '行业' },
  { key: 'stage', label: '阶段', formatter: (value) => STAGES[value as string]?.name || String(value ?? '') },
  { key: 'estimated_value', label: '预估金额', formatter: (value) => value ? `\u00A5${Number(value).toLocaleString()}` : '' },
  { key: 'source', label: '来源' },
];

export const ACTIVITY_ICONS: Record<string, React.ReactNode> = {
  call: React.createElement(Phone, { className: 'w-4 h-4' }),
  email: React.createElement(Mail, { className: 'w-4 h-4' }),
  meeting: React.createElement(Calendar, { className: 'w-4 h-4' }),
  note: React.createElement(FileText, { className: 'w-4 h-4' }),
  deal_update: React.createElement(TrendingUp, { className: 'w-4 h-4' }),
};

export const ACTIVITY_NAMES: Record<string, string> = {
  call: '电话',
  email: '邮件',
  meeting: '会议',
  note: '备注',
  deal_update: '交易更新',
};
