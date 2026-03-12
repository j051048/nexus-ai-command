import React from 'react';
import { Calendar, AlertCircle, RefreshCcw, CheckCircle, ShieldAlert } from 'lucide-react';

interface Risk {
  clause: string;
  severity: 'high' | 'medium' | 'low';
  suggestion: string;
}

export interface ContractPreviewProps {
  title: string;
  partyA: string;
  partyB: string;
  amount?: string | number;
  date?: string;
  risks?: Risk[];
}

export default function ContractPreview({ title, partyA, partyB, amount, date, risks = [] }: ContractPreviewProps) {
  const getSeverityColors = (severity: string) => {
    switch (severity) {
      case 'high': return 'bg-red-500/10 border-red-500/20 text-red-500';
      case 'medium': return 'bg-orange-500/10 border-orange-500/20 text-orange-500';
      case 'low': return 'bg-yellow-500/10 border-yellow-500/20 text-yellow-500';
      default: return 'bg-muted border-border text-foreground';
    }
  };

  const highRisksCount = risks.filter(r => r.severity === 'high').length;

  return (
    <div className="flex flex-col w-full bg-card rounded-xl border border-border overflow-hidden shadow-sm">
      <div className="bg-primary/5 px-4 py-3 border-b border-border flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground tracking-tight">{title}</h3>
        </div>
        <div className="flex gap-2">
          {highRisksCount > 0 && (
            <span className="inline-flex items-center gap-1 bg-red-500/10 text-red-500 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider">
              <AlertCircle className="w-3 h-3" />
              {highRisksCount} 处高危
            </span>
          )}
          <span className="inline-flex items-center gap-1 bg-primary/10 text-primary px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider">
            法务预审
          </span>
        </div>
      </div>

      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4 border-b border-border">
        <div className="space-y-1 bg-muted/20 p-3 rounded-lg border border-border/50">
          <span className="text-xs text-muted-foreground uppercase font-medium">甲方 (买方)</span>
          <p className="text-sm font-bold text-foreground">{partyA}</p>
        </div>
        <div className="space-y-1 bg-muted/20 p-3 rounded-lg border border-border/50">
          <span className="text-xs text-muted-foreground uppercase font-medium">乙方 (卖方)</span>
          <p className="text-sm font-bold text-foreground">{partyB}</p>
        </div>
        {(amount !== undefined || date) && (
          <div className="col-span-1 md:col-span-2 flex items-center justify-between bg-primary/5 p-3 rounded-lg mt-2">
            {amount !== undefined && (
              <div>
                <span className="text-xs text-muted-foreground uppercase font-medium mr-2">标的金额</span>
                <span className="text-lg font-bold text-primary">¥ {Number(amount).toLocaleString()}</span>
              </div>
            )}
            {date && (
              <div className="flex items-center gap-1 text-sm text-foreground">
                <Calendar className="w-3.5 h-3.5 text-muted-foreground" />
                <span>{date}</span>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="p-4 bg-background">
        <h4 className="text-xs font-bold text-foreground mb-3 flex items-center gap-2 uppercase tracking-wide">
          <RefreshCcw className="w-3.5 h-3.5 text-muted-foreground" />
          智能审核意见 ({risks.length})
        </h4>
        <div className="space-y-3">
          {risks.length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-green-500 bg-green-500/10 p-3 rounded-lg border border-green-500/20">
              <CheckCircle className="w-4 h-4" />
              <span>未发现明显法务风险，合同条款标准。</span>
            </div>
          ) : (
            risks.map((risk, idx) => (
              <div key={idx} className={`p-3 rounded-lg border shadow-sm ${getSeverityColors(risk.severity)}`}>
                <div className="flex items-start gap-2">
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-sm bg-background/50 uppercase whitespace-nowrap mt-0.5">
                    {risk.severity === 'high' ? '高危' : risk.severity === 'medium' ? '中危' : '低风险'}
                  </span>
                  <p className="text-sm font-medium leading-relaxed">
                    {risk.clause}
                  </p>
                </div>
                {risk.suggestion && (
                  <div className="mt-2 text-xs opacity-80 pl-9 border-l-2 border-current/20 ml-3">
                    <span className="font-semibold block mb-0.5">建议修改：</span>
                    {risk.suggestion}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
