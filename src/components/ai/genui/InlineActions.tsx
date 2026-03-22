import React from 'react';
import { Button } from '@/components/ui/button';
import { Zap } from 'lucide-react';
import { useToolMetadata } from '@/hooks/useToolMetadata';

/** Map tool names to short Chinese action labels */
const TOOL_LABELS: Record<string, string> = {
  // CRM
  create_followup: '添加跟进',
  update_customer: '更新客户',
  list_customers: '查看客户',
  get_customer_detail: '客户详情',
  search_customers: '搜索客户',
  // Contracts
  create_contract: '创建合同',
  list_contracts: '查看合同',
  get_contract_detail: '合同详情',
  // Approvals
  list_approvals: '查看审批',
  approve_item: '审批通过',
  // Finance
  list_invoices: '查看发票',
  create_invoice: '创建发票',
  // OA
  list_announcements: '查看公告',
  create_announcement: '发布公告',
  // General
  web_search: '网页搜索',
  data_analysis: '数据分析',
};

interface InlineActionsProps {
  toolName: string;
  entityData?: Record<string, unknown>;
  onAction: (prompt: string) => void;
}

/** Build a natural language prompt from related tool + entity context */
function buildPrompt(relatedToolName: string, entityData?: Record<string, unknown>): string {
  const name = entityData?.name || entityData?.title || entityData?.customer_name || '';
  const id = entityData?.id || entityData?.customer_id || entityData?.contract_id || '';

  // Simple prompt templates based on tool name patterns
  if (relatedToolName.includes('followup') || relatedToolName.includes('follow_up')) {
    return name ? `为${name}添加跟进记录` : '添加跟进记录';
  }
  if (relatedToolName.includes('detail')) {
    return id ? `查看 ${name || id} 的详细信息` : `查看详情`;
  }
  if (relatedToolName.includes('update')) {
    return name ? `更新${name}的信息` : '更新信息';
  }
  if (relatedToolName.includes('create')) {
    return `创建新记录`;
  }
  if (relatedToolName.includes('list')) {
    return `查看相关列表`;
  }
  if (relatedToolName.includes('delete')) {
    return name ? `删除${name}` : '删除记录';
  }
  if (relatedToolName.includes('approve')) {
    return name ? `审批${name}` : '执行审批';
  }

  // Fallback: use the label or tool name
  const label = TOOL_LABELS[relatedToolName] || relatedToolName;
  return name ? `${label} - ${name}` : label;
}

export const InlineActions: React.FC<InlineActionsProps> = ({ toolName, entityData, onAction }) => {
  const { getRelatedTools } = useToolMetadata();
  const relatedTools = getRelatedTools(toolName);

  if (relatedTools.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-border/30">
      {relatedTools.slice(0, 4).map((tool) => (
        <Button
          key={tool.name}
          variant="outline"
          size="sm"
          className="h-6 px-2 text-xs gap-1 text-muted-foreground hover:text-foreground"
          onClick={() => onAction(buildPrompt(tool.name, entityData))}
        >
          <Zap className="w-3 h-3" />
          {TOOL_LABELS[tool.name] || tool.description.slice(0, 8)}
        </Button>
      ))}
    </div>
  );
};
