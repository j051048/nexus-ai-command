import React, { useMemo, useState, useRef, useEffect } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Search, Wrench } from 'lucide-react';

interface ToolMeta {
  name: string;
  description: string;
  domain: string | null;
}

interface ToolPaletteProps {
  tools: ToolMeta[];
  isLoading: boolean;
  onSelectTool: (tool: ToolMeta) => void;
  onClose: () => void;
}

const DOMAIN_LABELS: Record<string, string> = {
  crm: 'CRM 客户',
  approval: '审批',
  finance: '财务',
  hr: '人事',
  oa: '办公',
  contract: '合同',
  knowledge: '知识库',
  asset: '资产',
  inventory: '库存',
  attendance: '考勤',
  expense: '报销',
  work_order: '工单',
  project: '项目',
  certificate: '证照',
  workflow: '流程',
  organization: '组织',
  operational: '运营',
  vmd: '任务管理',
  ai_insight: 'AI 洞察',
  boss: '管理决策',
};

export const ToolPalette = React.memo(function ToolPalette({
  tools,
  isLoading,
  onSelectTool,
  onClose,
}: ToolPaletteProps) {
  const [search, setSearch] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    searchRef.current?.focus();
  }, []);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const grouped = useMemo(() => {
    const q = search.toLowerCase();
    const filtered = q
      ? tools.filter(
          (t) =>
            t.name.toLowerCase().includes(q) ||
            t.description.toLowerCase().includes(q) ||
            (t.domain || '').toLowerCase().includes(q) ||
            (DOMAIN_LABELS[t.domain || ''] || '').includes(q)
        )
      : tools;

    const groups: Record<string, ToolMeta[]> = {};
    for (const t of filtered) {
      const key = t.domain || 'other';
      (groups[key] ||= []).push(t);
    }
    return groups;
  }, [tools, search]);

  if (isLoading) {
    return (
      <div className="mb-3 p-4 bg-secondary/50 rounded-lg animate-fade-slide-up text-center text-xs text-muted-foreground">
        加载工具列表...
      </div>
    );
  }

  return (
    <div className="mb-3 bg-secondary/50 rounded-lg animate-fade-slide-up overflow-hidden">
      <div className="p-2 border-b border-border/50">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            ref={searchRef}
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索工具..."
            className="w-full pl-7 pr-2 py-1.5 text-xs bg-background rounded border border-border/50 focus:outline-none focus:ring-1 focus:ring-primary/50"
          />
        </div>
      </div>
      <ScrollArea className="max-h-60">
        <div className="p-2 space-y-3">
          {Object.keys(grouped).length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">未找到匹配工具</p>
          )}
          {Object.entries(grouped).map(([domain, domainTools]) => (
            <div key={domain}>
              <p className="text-[10px] font-medium text-muted-foreground px-1 mb-1">
                {DOMAIN_LABELS[domain] || domain}
              </p>
              <div className="space-y-0.5">
                {domainTools.map((tool) => (
                  <button
                    key={tool.name}
                    onClick={() => {
                      onSelectTool(tool);
                      onClose();
                    }}
                    className="w-full flex items-start gap-2 px-2 py-1.5 rounded text-left hover:bg-secondary transition-colors"
                  >
                    <Wrench className="w-3 h-3 mt-0.5 text-muted-foreground shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">{tool.name}</p>
                      <p className="text-[10px] text-muted-foreground truncate">{tool.description}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
});
