import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';
import { cn } from '@/lib/utils';

// Mapping URL paths to Chinese labels
const PATH_MAP: Record<string, string> = {
  'boss-dashboard': '总控中心',
  'dashboard': '战绩中心',
  'inbox': '待办中心',
  'sales': '销售AI管理',
  'crm': 'CRM管理',
  'tender-analysis': '标书审阅',
  'battlecards': '竞品库',
  'contracts': '合同管理',
  'inventory': '库存管理',
  'projects': '项目管理',
  'target-dashboard': '目标看板',
  'targets': '目标管理',
  'reports': '数据报表',
  'oa': 'OA办公',
  'hr': '人事中心',
  'finance': '财务中心',
  'approval': '审批中心',
  'workflows': '流程设计',
  'workflow-templates': '流程模板',
  'form-designer': '表单设计',
  'work-orders': '工单管理',
  'assets': '资产管理',
  'knowledge': '知识库',
  'training': '培训中心',
  'rewards': '激励钱包',
  'certificates': '企业证照',
  'vmd': '虚拟市场部',
  'tasks': '任务中心',
  'agents': 'Agent配置',
  'clues': '线索管理',
  'compliance': '合规校验',
  'employees': '员工管理',
  'departments': '部门管理',
  'org-chart': '组织架构',
  'company-settings': '企业设置',
  'settings': '系统设置',
  'llm': '模型管理',
  'models': '可用模型',
  'costs': '成本消耗',
  'import': '数据导入',
  'audit': '审计日志',
  'plugins': '插件市场',
  'api-keys': 'API密钥',
  'payments': '订阅支付',
  'agent-debug': 'Agent调试',
  'scheduled-tasks': '定时任务',
};

export function Breadcrumbs() {
  const location = useLocation();
  const pathnames = location.pathname.split('/').filter((x) => x);

  if (pathnames.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="flex items-center space-x-2 text-xs font-medium text-muted-foreground mb-4 animate-fade-in">
      <Link
        to="/"
        className="flex items-center hover:text-foreground transition-colors"
      >
        <Home className="w-3.5 h-3.5" />
      </Link>

      {pathnames.map((value, index) => {
        const last = index === pathnames.length - 1;
        const to = `/${pathnames.slice(0, index + 1).join('/')}`;
        const label = PATH_MAP[value] || value;

        return (
          <React.Fragment key={to}>
            <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/40" />
            {last ? (
              <span className="text-foreground font-semibold truncate max-w-[150px]">
                {label}
              </span>
            ) : (
              <Link
                to={to}
                className="hover:text-foreground transition-colors truncate max-w-[150px]"
              >
                {label}
              </Link>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
