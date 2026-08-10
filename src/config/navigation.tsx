import type { ReactNode } from 'react';
import {
  Activity,
  BarChart3,
  BookOpen,
  Bot,
  Brain,
  Building2,
  Calendar,
  Clock,
  Contact,
  Cpu,
  Crosshair,
  Crown,
  DollarSign,
  FileSearch,
  FileSignature,
  GraduationCap,
  Network,
  Package,
  PanelsTopLeft,
  Puzzle,
  Radar,
  Rocket,
  Server,
  Settings,
  Shield,
  ShieldCheck,
  Swords,
  Target,
  TrendingUp,
  Warehouse,
  Workflow,
  Wrench,
} from 'lucide-react';

import { isModuleEnabled, type ModuleFlag } from '@/config/featureFlags';

export type AppRole = 'boss' | 'manager' | 'ai_assistant' | 'employee' | 'founder';

export interface NavItem {
  icon: ReactNode;
  label: string;
  href: string;
  badge?: string;
  badgeType?: 'primary' | 'success' | 'warning';
  roles?: AppRole[];
  group: string;
}

function moduleForHref(href: string): ModuleFlag | null {
  const path = href.split('?')[0].replace(/^\/+/, '');
  if (path === 'crm') return 'crm';
  if (path === 'contracts' || path === 'documents') return 'documents';
  if (path === 'knowledge' || path.startsWith('knowledge/')) return 'knowledge';
  if (path === 'approval') return 'approval';
  if (path === 'sales') return 'sales';
  if (path === 'projects') return 'projects';
  if (path === 'oa') return 'oa';
  if (path === 'hr') return 'hr';
  if (path === 'finance') return 'finance';
  if (path === 'work-orders') return 'work_orders';
  if (path === 'reports') return 'reports';
  if (path === 'report-builder') return 'report_builder';
  if (path === 'inventory') return 'inventory';
  if (path === 'assets') return 'assets';
  if (path === 'certificates') return 'certificates';
  if (path === 'workflows' || path.startsWith('workflows/') || path === 'workflow-templates') {
    return 'workflow_designer';
  }
  if (path === 'form-designer' || path.startsWith('form-designer/')) return 'form_designer';
  if (path === 'custom-dashboard') return 'custom_dashboard';
  if (path === 'tender-analysis' || path === 'growth/tenders') return 'tender';
  if (path === 'battlecards') return 'battlecards';
  if (path === 'training') return 'training';
  if (path === 'vmd' || path.startsWith('vmd/')) return 'vmd';
  if (path === 'dashboard' || path.startsWith('growth/')) return 'vmd';
  if (path === 'plugins') return 'plugins';
  if (path === 'soul-document') return 'soul_document';
  if (path === 'dev/animations' || path === 'agent-debug') return 'dev_tools';
  return null;
}

export function isNavFeatureEnabled(item: NavItem): boolean {
  const moduleFlag = moduleForHref(item.href);
  return moduleFlag ? isModuleEnabled(moduleFlag) : true;
}

// 一级入口围绕科学仪器销售交付闭环，其余能力按需从“更多应用”开启。
export const NAV_CONFIG: NavItem[] = [
  { icon: <Crosshair size={18} />, label: '今日作战', href: 'dashboard', group: 'primary' },
  { icon: <Contact size={18} />, label: '客户与项目', href: 'growth/accounts', group: 'primary' },
  { icon: <PanelsTopLeft size={18} />, label: '方案作战', href: 'growth/solutions', group: 'primary' },
  { icon: <FileSearch size={18} />, label: '投标作战', href: 'growth/tenders', group: 'primary' },
  { icon: <BookOpen size={18} />, label: '企业资料', href: 'knowledge', group: 'primary' },

  { icon: <Radar size={18} />, label: '线索雷达', href: 'growth/radar', group: '客户增长' },
  { icon: <TrendingUp size={18} />, label: '销售管道', href: 'sales', group: '客户增长' },
  { icon: <FileSignature size={18} />, label: '合同', href: 'contracts', roles: ['manager', 'boss', 'founder'], group: '客户增长' },
  { icon: <Swords size={18} />, label: '竞品库', href: 'battlecards', group: '客户增长' },

  { icon: <Calendar size={18} />, label: 'OA 办公', href: 'oa', group: '协作' },
  { icon: <Clock size={18} />, label: '人事', href: 'hr', roles: ['manager', 'boss', 'founder'], group: '协作' },
  { icon: <DollarSign size={18} />, label: '财务', href: 'finance', group: '协作' },
  { icon: <Wrench size={18} />, label: '工单', href: 'work-orders', group: '协作' },
  { icon: <Workflow size={18} />, label: '流程', href: 'workflows', roles: ['boss', 'founder'], group: '协作' },

  { icon: <BarChart3 size={18} />, label: '经营复盘', href: 'growth/review', group: '经营数据' },
  { icon: <BarChart3 size={18} />, label: '数据报表', href: 'reports', group: '经营数据' },
  { icon: <Target size={18} />, label: '目标看板', href: 'target-dashboard', group: '经营数据' },
  { icon: <BarChart3 size={18} />, label: 'AI 报表引擎', href: 'report-builder', roles: ['boss', 'founder', 'manager'], group: '经营数据' },
  { icon: <Crown size={18} />, label: '老板看板', href: 'boss-dashboard', roles: ['boss', 'founder'], group: '经营数据' },
  { icon: <BarChart3 size={18} />, label: '客户成功', href: 'customer-success', roles: ['boss', 'founder', 'manager'], group: '经营数据' },

  { icon: <Warehouse size={18} />, label: '库存', href: 'inventory', group: '资产' },
  { icon: <Package size={18} />, label: '资产', href: 'assets', group: '资产' },

  { icon: <Bot size={18} />, label: '助手工作台', href: 'ai-operating-system', group: '智能助手' },
  { icon: <Brain size={18} />, label: 'Agent 进化中心', href: 'agent-improvement-center', roles: ['boss', 'founder'], group: '智能助手' },
  { icon: <Rocket size={18} />, label: '增长作战配置', href: 'vmd', group: '智能助手' },
  { icon: <Puzzle size={18} />, label: '插件', href: 'plugins', group: '智能助手' },
  { icon: <Cpu size={18} />, label: '模型', href: 'llm/models', roles: ['boss', 'founder'], group: '智能助手' },
  { icon: <ShieldCheck size={18} />, label: '工具治理', href: 'tools/governance', roles: ['boss', 'founder'], group: '智能助手' },
  { icon: <Activity size={18} />, label: '运行记录', href: 'agent-runs', roles: ['boss', 'founder'], group: '智能助手' },
  { icon: <BarChart3 size={18} />, label: '成果质量', href: 'artifact-quality', roles: ['boss', 'founder'], group: '智能助手' },

  { icon: <GraduationCap size={18} />, label: '培训', href: 'training', group: '管理' },
  { icon: <Network size={18} />, label: '组织', href: 'org-chart', roles: ['boss', 'founder'], group: '管理' },
  { icon: <Building2 size={18} />, label: '公司设置', href: 'company-settings', roles: ['boss', 'founder'], group: '管理' },
  { icon: <Server size={18} />, label: '上线交付', href: 'deployment-readiness', roles: ['boss', 'founder'], group: '管理' },
  { icon: <Shield size={18} />, label: '权限矩阵', href: 'permissions-matrix', roles: ['boss', 'founder'], group: '管理' },
  { icon: <Brain size={18} />, label: '意图规则', href: 'admin/intent-rules', roles: ['boss', 'founder'], group: '管理' },
  { icon: <Settings size={18} />, label: '系统设置', href: 'settings', roles: ['boss', 'founder'], group: '管理' },
];

export const NAV_GROUPS = ['primary', '客户增长', '协作', '经营数据', '资产', '智能助手', '管理'];

export const SPACE_MATCH_PREFIXES: Record<string, string[]> = {
  workbench: ['projects', 'approval', 'contracts', 'oa', 'hr', 'finance', 'work-orders', 'workflows', 'workflow-templates', 'form-designer', 'org-chart'],
  data: ['reports', 'report-builder', 'target-dashboard', 'performance-dashboard', 'boss-dashboard', 'custom-dashboard', 'customer-success'],
  'ai-center': ['knowledge', 'ai-operating-system', 'agent-improvement-center', 'vmd', 'plugins', 'llm', 'tools', 'agent-runs', 'artifact-quality', 'agent-debug', 'scheduled-tasks', 'admin'],
};
