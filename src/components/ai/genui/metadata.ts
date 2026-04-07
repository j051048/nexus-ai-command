import { LucideIcon, Briefcase, Users, LayoutDashboard, Search, FileText } from 'lucide-react';

export type GenUIDomain = 'CRM' | 'HR' | 'FINANCE' | 'GENERAL' | 'ADMIN';

export interface GenUIMetadata {
  name: string;
  domain: GenUIDomain;
  description: string;
  icon: string | LucideIcon;
  interactive: boolean;
  capabilities: string[];
}

export const GEN_UI_METADATA: Record<string, GenUIMetadata> = {
  ApprovalFlow: {
    name: '审批流',
    domain: 'HR',
    description: '展示多级业务审批进度并支持实时操作',
    icon: FileText,
    interactive: true,
    capabilities: ['approve', 'reject', 'comment'],
  },
  KanbanMini: {
    name: '迷你看板',
    domain: 'CRM',
    description: '展示商机或任务看板，支持阶段拖拽',
    icon: LayoutDashboard,
    interactive: true,
    capabilities: ['move_stage', 'edit_card'],
  },
  OrgChart: {
    name: '组织架构图',
    domain: 'HR',
    description: '可视化展示公司或部门汇报关系',
    icon: Users,
    interactive: false,
    capabilities: ['drill_down'],
  },
  DataGrid: {
    name: '数据表格',
    domain: 'GENERAL',
    description: '高性能可筛选、排序的数据网格',
    icon: Search,
    interactive: true,
    capabilities: ['filter', 'sort', 'export'],
  }
};
