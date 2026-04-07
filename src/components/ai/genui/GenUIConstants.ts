/**
 * CRUD components that have a corresponding traditional page for manual fallback
 */
export const CRUD_FALLBACK_ROUTES: Record<string, string> = {
  ApprovalCenter: '/approval',
  ApprovalFlow: '/approval',
  FormBuilder: '/form-designer',
  TodoList: '/scheduled-tasks',
  EmailDraft: '/oa',
  KanbanBoard: '/sales',
  PriorityLeads: '/crm',
  ContractPreview: '/contracts',
  InvoiceCard: '/finance',
  CalendarView: '/schedule',
};

/**
 * Table-like component names that support CSV export
 */
export const TABLE_COMPONENTS = new Set([
  'DataTable', 'ComparisonTable', 'DataChart',
]);

/**
 * Components that support PNG export (charts + visual components)
 */
export const CHART_COMPONENTS = new Set([
  'DataChart', 'PieChart', 'FunnelChart', 'StatCards',
  'MetricComparison', 'ProgressTracker', 'OrgChart',
  'ApprovalFlow', 'CalendarView', 'KanbanMini',
  'StatusTimeline', 'Timeline', 'AlertList',
  'UserProfileCard', 'QuoteCard', 'BadgePanel',
  'TodoList', 'FormBuilder', 'FileList',
]);
