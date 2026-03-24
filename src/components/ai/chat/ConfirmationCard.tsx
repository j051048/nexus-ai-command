import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import {
  AlertTriangle,
  ShieldAlert,
  DollarSign,
  ListChecks,
  ExternalLink,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import type { ConfirmationRequest } from '@/hooks/useAIStream';

/** 常见参数 key → 中文标签映射 */
const ARG_LABEL_MAP: Record<string, string> = {
  content: '内容',
  title: '标题',
  priority: '优先级',
  target: '目标对象',
  message: '消息',
  description: '描述',
  name: '名称',
  email: '邮箱',
  phone: '电话',
  department: '部门',
  role: '角色',
  status: '状态',
  type: '类型',
  amount: '金额',
  reason: '原因',
  date: '日期',
  time: '时间',
  location: '地点',
  assignee: '负责人',
  deadline: '截止日期',
  category: '分类',
  tags: '标签',
  url: '链接',
  id: '编号',
  count: '数量',
  subject: '主题',
  body: '正文',
  recipients: '收件人',
  cc: '抄送',
  attachment: '附件',
  start_time: '开始时间',
  end_time: '结束时间',
  duration: '时长',
  level: '级别',
  scope: '范围',
  notify: '是否通知',
  confirm: '是否确认',
  remark: '备注',
  note: '备注',
  comment: '评论',
  customer_name: '客户姓名',
  customer_id: '客户编号',
  contract_id: '合同编号',
  invoice_id: '发票编号',
  approval_type: '审批类型',
  leave_type: '请假类型',
  start_date: '开始日期',
  end_date: '结束日期',
  total_amount: '总金额',
  tax_rate: '税率',
  account_name: '账户名',
  bank_name: '银行',
  address: '地址',
  description_cn: '详细描述',
  summary: '摘要',
  feedback: '反馈',
  score: '评分',
};

/** 将英文 key 转为中文标签（若无映射则美化显示） */
function localizeArgKey(key: string): string {
  if (ARG_LABEL_MAP[key]) return ARG_LABEL_MAP[key];
  // snake_case → 空格分割并首字母大写，作为 fallback
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

interface ConfirmationCardProps {
  confirmation: ConfirmationRequest;
  onConfirm: (modifiedArgs?: Record<string, unknown>) => void;
  onDismiss: () => void;
}

/** Style config per confirmation_type */
const TIER_STYLES: Record<string, {
  border: string;
  bg: string;
  icon: React.ElementType;
  iconColor: string;
  titleColor: string;
  textColor: string;
  labelColor: string;
  title: string;
  inputBorder: string;
  inputBg: string;
  inputText: string;
  requireTypedConfirm?: boolean;
}> = {
  irreversible: {
    border: 'border-red-500/40',
    bg: 'bg-red-50 dark:bg-red-950/20',
    icon: ShieldAlert,
    iconColor: 'text-red-600 dark:text-red-400',
    titleColor: 'text-red-900 dark:text-red-200',
    textColor: 'text-red-800 dark:text-red-300',
    labelColor: 'text-red-700 dark:text-red-400',
    title: '危险操作确认',
    inputBorder: 'border-red-300 dark:border-red-700',
    inputBg: 'bg-red-50 dark:bg-red-900/40',
    inputText: 'text-red-900 dark:text-red-200',
    requireTypedConfirm: true,
  },
  high_value: {
    border: 'border-orange-500/40',
    bg: 'bg-orange-50 dark:bg-orange-950/20',
    icon: DollarSign,
    iconColor: 'text-orange-600 dark:text-orange-400',
    titleColor: 'text-orange-900 dark:text-orange-200',
    textColor: 'text-orange-800 dark:text-orange-300',
    labelColor: 'text-orange-700 dark:text-orange-400',
    title: '大额操作确认',
    inputBorder: 'border-orange-300 dark:border-orange-700',
    inputBg: 'bg-orange-50 dark:bg-orange-900/40',
    inputText: 'text-orange-900 dark:text-orange-200',
  },
  bulk: {
    border: 'border-blue-500/40',
    bg: 'bg-blue-50 dark:bg-blue-950/20',
    icon: ListChecks,
    iconColor: 'text-blue-600 dark:text-blue-400',
    titleColor: 'text-blue-900 dark:text-blue-200',
    textColor: 'text-blue-800 dark:text-blue-300',
    labelColor: 'text-blue-700 dark:text-blue-400',
    title: '批量操作确认',
    inputBorder: 'border-blue-300 dark:border-blue-700',
    inputBg: 'bg-blue-50 dark:bg-blue-900/40',
    inputText: 'text-blue-900 dark:text-blue-200',
  },
  external: {
    border: 'border-purple-500/40',
    bg: 'bg-purple-50 dark:bg-purple-950/20',
    icon: ExternalLink,
    iconColor: 'text-purple-600 dark:text-purple-400',
    titleColor: 'text-purple-900 dark:text-purple-200',
    textColor: 'text-purple-800 dark:text-purple-300',
    labelColor: 'text-purple-700 dark:text-purple-400',
    title: '外部操作确认',
    inputBorder: 'border-purple-300 dark:border-purple-700',
    inputBg: 'bg-purple-50 dark:bg-purple-900/40',
    inputText: 'text-purple-900 dark:text-purple-200',
  },
  escalation: {
    border: 'border-yellow-500/40',
    bg: 'bg-yellow-50 dark:bg-yellow-950/20',
    icon: ShieldCheck,
    iconColor: 'text-yellow-600 dark:text-yellow-500',
    titleColor: 'text-yellow-900 dark:text-yellow-200',
    textColor: 'text-yellow-800 dark:text-yellow-300',
    labelColor: 'text-yellow-700 dark:text-yellow-400',
    title: '权限提升确认',
    inputBorder: 'border-yellow-300 dark:border-yellow-700',
    inputBg: 'bg-yellow-50 dark:bg-yellow-900/40',
    inputText: 'text-yellow-900 dark:text-yellow-200',
  },
};

/** Default amber style (backward compatible) */
const DEFAULT_STYLE = {
  border: 'border-amber-500/30',
  bg: 'bg-amber-50 dark:bg-amber-950/20',
  icon: AlertTriangle,
  iconColor: 'text-amber-600 dark:text-amber-400',
  titleColor: 'text-amber-900 dark:text-amber-200',
  textColor: 'text-amber-800 dark:text-amber-300',
  labelColor: 'text-amber-700 dark:text-amber-400',
  title: '操作确认',
  inputBorder: 'border-amber-300 dark:border-amber-700',
  inputBg: 'bg-amber-50 dark:bg-amber-900/40',
  inputText: 'text-amber-900 dark:text-amber-200',
};

export const ConfirmationCard: React.FC<ConfirmationCardProps> = ({
  confirmation,
  onConfirm,
  onDismiss,
}) => {
  const [editedArgs, setEditedArgs] = useState<Record<string, unknown>>({});
  const [typedConfirm, setTypedConfirm] = useState('');

  useEffect(() => {
    if (confirmation.args) {
      setEditedArgs({ ...confirmation.args });
    }
    setTypedConfirm('');
  }, [confirmation]);

  const style = TIER_STYLES[confirmation.confirmation_type || ''] || DEFAULT_STYLE;
  const Icon = style.icon;
  const isDestructive = confirmation.tool_name.includes('delete') || confirmation.tool_name.includes('remove');
  const confirmPlaceholder = '确认';
  const needsTypedConfirm = 'requireTypedConfirm' in style && style.requireTypedConfirm;
  const canConfirm = !needsTypedConfirm || typedConfirm === confirmPlaceholder;

  return (
    <div className={`mx-4 mb-2 rounded-xl border ${style.border} ${style.bg} p-4 animate-in fade-in slide-in-from-bottom-2 duration-300`}>
      <div className="flex items-start gap-3">
        <Icon className={`w-5 h-5 ${style.iconColor} mt-0.5 shrink-0`} />
        <div className="flex-1 space-y-2">
          <p className={`text-sm font-medium ${style.titleColor}`}>
            {style.title}
          </p>
          <p className={`text-sm ${style.textColor}`}>
            {confirmation.message}
          </p>

          {/* Editable / viewable args */}
          {confirmation.args && Object.keys(confirmation.args).length > 0 && (
            <details className="pt-1" open={!!confirmation.modifiable}>
              <summary className={`text-xs ${style.labelColor} cursor-pointer hover:underline`}>
                {confirmation.modifiable ? '编辑参数' : '查看参数'}
              </summary>
              {confirmation.modifiable ? (
                <div className="mt-1 space-y-2">
                  {Object.entries(editedArgs).map(([key, value]) => {
                    const valType = typeof value;
                    return (
                      <div key={key} className="flex items-center gap-2">
                        <label className={`text-xs ${style.textColor} min-w-[80px] font-medium shrink-0`}>
                          {localizeArgKey(key)}
                        </label>
                        {valType === 'boolean' ? (
                          <select
                            className={`flex-1 h-7 px-2 rounded border ${style.inputBorder} ${style.inputBg} text-xs ${style.inputText}`}
                            value={String(value)}
                            onChange={(e) => setEditedArgs(prev => ({ ...prev, [key]: e.target.value === 'true' }))}
                          >
                            <option value="true">是</option>
                            <option value="false">否</option>
                          </select>
                        ) : valType === 'number' ? (
                          <input
                            type="number"
                            className={`flex-1 h-7 px-2 rounded border ${style.inputBorder} ${style.inputBg} text-xs ${style.inputText}`}
                            value={value as number}
                            onChange={(e) => setEditedArgs(prev => ({ ...prev, [key]: Number(e.target.value) }))}
                          />
                        ) : valType === 'string' ? (
                          <input
                            type="text"
                            className={`flex-1 h-7 px-2 rounded border ${style.inputBorder} ${style.inputBg} text-xs ${style.inputText}`}
                            value={value as string}
                            onChange={(e) => setEditedArgs(prev => ({ ...prev, [key]: e.target.value }))}
                          />
                        ) : (
                          <textarea
                            className={`flex-1 min-h-[56px] px-2 py-1 rounded border ${style.inputBorder} ${style.inputBg} text-xs ${style.inputText} font-mono`}
                            value={typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value ?? '')}
                            onChange={(e) => {
                              try {
                                setEditedArgs(prev => ({ ...prev, [key]: JSON.parse(e.target.value) }));
                              } catch {
                                setEditedArgs(prev => ({ ...prev, [key]: e.target.value }));
                              }
                            }}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <pre className={`mt-1 p-2 rounded ${style.inputBg} text-xs ${style.inputText} overflow-x-auto max-h-32`}>
                  {JSON.stringify(confirmation.args, null, 2)}
                </pre>
              )}
            </details>
          )}

          {/* Typed confirmation for irreversible ops */}
          {needsTypedConfirm && (
            <div className="pt-1">
              <p className={`text-xs ${style.labelColor} mb-1`}>
                请输入 <span className="font-bold">{confirmPlaceholder}</span> 以继续
              </p>
              <input
                type="text"
                className={`w-48 h-7 px-2 rounded border ${style.inputBorder} ${style.inputBg} text-xs ${style.inputText} focus:outline-none focus:ring-1 focus:ring-red-500`}
                placeholder={confirmPlaceholder}
                value={typedConfirm}
                onChange={(e) => setTypedConfirm(e.target.value)}
              />
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <Button
              size="sm"
              className="h-7 px-3 text-xs"
              disabled={!canConfirm}
              onClick={() => onConfirm(confirmation.modifiable ? editedArgs : undefined)}
            >
              <Zap className="w-3 h-3 mr-1" />
              确认执行
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-3 text-xs"
              onClick={onDismiss}
            >
              取消
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
