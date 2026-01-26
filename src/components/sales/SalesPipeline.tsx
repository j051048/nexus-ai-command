import React, { useState, useMemo } from 'react';
import { Loader2, Zap } from 'lucide-react';
import { useSalesLeads } from '@/hooks/useSalesLeads';
import { SalesLead } from '@/types/nexus';
import { PriorityLeads } from './sections/PriorityLeads';
import { KanbanBoard } from './sections/KanbanBoard';
import { LeadDetailModal } from './components/LeadDetailModal';

export function SalesPipeline() {
  const [selectedLead, setSelectedLead] = useState<SalesLead | null>(null);
  const { leads, isLoading } = useSalesLeads();

  // Optimization: Memoize transformed leads
  const priorityLeads = useMemo(() => {
    return leads
      .slice()
      .sort((a, b) => b.score - a.score)
      .slice(0, 3)
      .map((l, i) => ({
        id: l.id,
        name: l.name,
        company: l.company,
        priority: i + 1,
        reason: l.aiSuggestion || 'AI 实时测算显示该客户意向度极高，建议立即切入。'
      }));
  }, [leads]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-[500px] gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground animate-pulse font-medium tracking-widest uppercase">
          AI 正在全量同步商机数据...
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-[1600px] mx-auto space-y-8 pb-20 animate-in fade-in slide-in-from-bottom-4 duration-700">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-black text-foreground tracking-tighter">销售 AI 战绩中心</h1>
          <p className="text-muted-foreground mt-2 text-lg">AI 实时推演，为您锁定高净值成交机会</p>
        </div>
        <div className="flex items-center gap-3 bg-success/10 px-4 py-2 rounded-2xl border border-success/20">
          <Zap className="w-5 h-5 text-success fill-success/20" />
          <span className="text-sm font-bold text-success uppercase tracking-wider">算力资源：优先调度已启动</span>
        </div>
      </div>

      <main className="space-y-10">
        {/* Priority Section (Part of User's Task C) */}
        <section>
          <PriorityLeads leads={priorityLeads} />
        </section>

        {/* Pipeline Section (Part of User's Task B - Refactoring) */}
        <section>
          <KanbanBoard leads={leads} onLeadClick={setSelectedLead} />
        </section>
      </main>

      {/* Detail Modal (Extracted) */}
      {selectedLead && (
        <LeadDetailModal
          lead={selectedLead}
          onClose={() => setSelectedLead(null)}
        />
      )}
    </div>
  );
}
