import React from 'react';
import { Receipt, Building2, Calendar, FileDigit, BadgeCheck, FileWarning } from 'lucide-react';

interface InvoiceItem {
  name: string;
  quantity?: number;
  price?: number;
  amount: number;
}

export interface InvoiceCardProps {
  invoiceNumber: string;
  vendor: string;
  date: string;
  amount: number;
  tax?: number;
  status?: 'paid' | 'unpaid' | 'void' | 'verified';
  items?: InvoiceItem[];
}

export default function InvoiceCard({ invoiceNumber, vendor, date, amount, tax, status = 'verified', items = [] }: InvoiceCardProps) {
  const isPaid = status === 'paid';
  const isVerified = status === 'verified';
  const isVoid = status === 'void';

  return (
    <div className="flex flex-col w-full bg-card rounded-xl border border-border overflow-hidden shadow-sm relative">
      {/* Visual Watermark for status */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-[0.03] pointer-events-none rotate-[-15deg]">
        <span className="text-8xl font-black uppercase whitespace-nowrap">
          {isPaid ? 'PAID' : isVerified ? 'VERIFIED' : isVoid ? 'VOID' : 'INVOICE'}
        </span>
      </div>

      <div className="bg-primary/5 px-5 py-4 flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-border/50 gap-2 relative z-10">
        <div className="flex gap-3">
          <div className="p-2 bg-background border border-border shadow-sm rounded-lg text-primary self-start">
            <Receipt className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground uppercase tracking-widest text-muted-foreground">发票 / 凭证</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <FileDigit className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-base font-bold font-mono tracking-tight">{invoiceNumber}</span>
            </div>
          </div>
        </div>
        {status && (
          <div className={`
            inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider
            ${isPaid ? 'bg-green-500/10 text-green-500 border border-green-500/20' : 
              isVoid ? 'bg-red-500/10 text-red-500 border border-red-500/20' : 
              isVerified ? 'bg-blue-500/10 text-blue-500 border border-blue-500/20' : 
              'bg-orange-500/10 text-orange-500 border border-orange-500/20'}
          `}>
             {isVerified && <BadgeCheck className="w-3.5 h-3.5" />}
             {isVoid && <FileWarning className="w-3.5 h-3.5" />}
             {isPaid ? '已付款' : isVerified ? '验真通过' : isVoid ? '已作废' : '未付款'}
          </div>
        )}
      </div>

      <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-y-4 gap-x-8 bg-background relative z-10 border-b border-border border-dashed">
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground flex items-center gap-1"><Building2 className="w-3 h-3" /> 开票方 / 收款方</span>
          <span className="text-sm font-medium text-foreground">{vendor}</span>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground flex items-center gap-1"><Calendar className="w-3 h-3" /> 开票日期</span>
          <span className="text-sm font-medium text-foreground">{date}</span>
        </div>
      </div>

      {items.length > 0 && (
        <div className="bg-background px-5 py-4 relative z-10 border-b border-border/30">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50 text-muted-foreground">
                <th className="font-normal text-left pb-2 text-xs">项目名称</th>
                <th className="font-normal text-right pb-2 text-xs">单价/数量</th>
                <th className="font-normal text-right pb-2 text-xs">金额</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {items.map((item, i) => (
                <tr key={i}>
                  <td className="py-2.5 text-foreground font-medium">{item.name}</td>
                  <td className="py-2.5 text-right text-muted-foreground">
                    {item.quantity ? `${item.price || ''} × ${item.quantity}` : '-'}
                  </td>
                  <td className="py-2.5 text-right font-mono">¥{item.amount.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="bg-muted/10 px-5 py-4 flex flex-col sm:flex-row justify-end items-end sm:items-center gap-4 sm:gap-8 relative z-10">
        {tax !== undefined && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">税额:</span>
            <span className="text-sm font-mono text-foreground tracking-tight">¥{tax.toLocaleString()}</span>
          </div>
        )}
        <div className="flex items-center gap-3 bg-background border border-border px-4 py-2 rounded-lg shadow-sm">
          <span className="text-sm font-bold text-muted-foreground uppercase">合计金额</span>
          <span className="text-2xl font-bold font-mono text-primary">¥{amount.toLocaleString()}</span>
        </div>
      </div>
    </div>
  );
}
