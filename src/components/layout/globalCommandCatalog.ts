import type { ComponentType } from 'react';
import {
  Activity,
  Award,
  BarChart3,
  Bell,
  BookOpen,
  Brain,
  Building2,
  Calendar,
  ClipboardList,
  Clock,
  CreditCard,
  Crown,
  DollarSign,
  FileCheck,
  FileSearch,
  FileText,
  Fingerprint,
  Gift,
  GraduationCap,
  Key,
  ListTodo,
  MessageSquare,
  Package,
  PanelsTopLeft,
  Plug,
  Search,
  Server,
  Settings,
  Shield,
  Sparkles,
  Swords,
  Target,
  TrendingUp,
  Upload,
  UserCog,
  Users,
  Warehouse,
  Workflow,
} from 'lucide-react';
import { pinyin } from 'pinyin-pro';

import { isModuleEnabled, type ModuleFlag } from '@/config/featureFlags';

export interface NavCommandItem {
  label: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
  keywords?: string[];
  group: string;
}

function getPinyinValues(text: string): string {
  try {
    const full = pinyin(text, { toneType: 'none', type: 'array' }).join('');
    const first = pinyin(text, { pattern: 'initial', toneType: 'none', type: 'array' }).join('');
    return `${full} ${first}`;
  } catch {
    return '';
  }
}

function moduleForPath(path: string): ModuleFlag | null {
  const normalized = path.split('?')[0].replace(/^\/+/, '');
  if (normalized === 'crm') return 'crm';
  if (normalized === 'contracts' || normalized === 'documents') return 'documents';
  if (normalized === 'knowledge' || normalized.startsWith('knowledge/')) return 'knowledge';
  if (normalized === 'approval') return 'approval';
  if (normalized === 'sales') return 'sales';
  if (normalized === 'projects') return 'projects';
  if (normalized === 'oa') return 'oa';
  if (normalized === 'hr') return 'hr';
  if (normalized === 'finance') return 'finance';
  if (normalized === 'work-orders') return 'work_orders';
  if (normalized === 'reports') return 'reports';
  if (normalized === 'report-builder') return 'report_builder';
  if (normalized === 'inventory') return 'inventory';
  if (normalized === 'assets') return 'assets';
  if (normalized === 'certificates') return 'certificates';
  if (normalized === 'workflows' || normalized.startsWith('workflows/') || normalized === 'workflow-templates') return 'workflow_designer';
  if (normalized === 'form-designer' || normalized.startsWith('form-designer/')) return 'form_designer';
  if (normalized === 'custom-dashboard') return 'custom_dashboard';
  if (normalized === 'tender-analysis') return 'tender';
  if (normalized.startsWith('growth/')) {
    return normalized === 'growth/tenders' ? 'tender' : 'vmd';
  }
  if (normalized === 'battlecards') return 'battlecards';
  if (normalized === 'training') return 'training';
  if (normalized === 'vmd' || normalized.startsWith('vmd/')) return 'vmd';
  if (normalized === 'plugins') return 'plugins';
  if (normalized === 'soul-document') return 'soul_document';
  if (normalized === 'agent-debug' || normalized === 'dev/animations') return 'dev_tools';
  return null;
}

export function isCommandFeatureEnabled(item: NavCommandItem): boolean {
  const moduleFlag = moduleForPath(item.path);
  return moduleFlag ? isModuleEnabled(moduleFlag) : true;
}

export const COMMAND_ITEMS: NavCommandItem[] = [
  { label: '今日工作', path: '/dashboard', icon: Target, keywords: ['首页', 'home', 'dashboard', '今日', '行动', '增长'], group: '业务增长' },
  { label: '线索雷达', path: '/growth/radar', icon: Search, keywords: ['线索', '商机', '雷达', '基金', '论文', '招标'], group: '业务增长' },
  { label: '客户与项目', path: '/growth/accounts', icon: Users, keywords: ['crm', '客户', '项目', '商机', '跟进'], group: '业务增长' },
  { label: '方案作战', path: '/growth/solutions', icon: PanelsTopLeft, keywords: ['方案', '解决方案', '售前', '配置', '选型', '预算', '客户方案'], group: '业务增长' },
  { label: '投标作战', path: '/growth/tenders', icon: FileSearch, keywords: ['标书', '审阅', '生成标书', '投标', '招标', '应答矩阵', '胜率', '合规'], group: '业务增长' },
  { label: '经营复盘', path: '/growth/review', icon: BarChart3, keywords: ['复盘', 'roi', '采纳率', '结果', '经营'], group: '业务增长' },
  { label: '助手工作台', path: '/ai-operating-system', icon: Sparkles, keywords: ['助手工作台', 'agent sandbox', 'sop', 'aop', '知识图谱', 'demo', '角色化', '业务流程'], group: '核心空间' },
  { label: '助手优化', path: '/agent-improvement-center', icon: Brain, keywords: ['agent', '进化中心', 'prompt registry', 'context quality', 'harness', 'hermes', '自我进化', 'memory hygiene'], group: '核心空间' },
  { label: 'AI 记忆', path: '/memory-center', icon: Brain, keywords: ['记忆', 'memory', '忘记', '偏好', '仪器记录'], group: '个人' },
  { label: '领导驾驶舱', path: '/boss-dashboard', icon: Crown, keywords: ['boss', '管理', '概览'], group: '核心功能' },
  { label: '待办中心', path: '/inbox', icon: Bell, keywords: ['待办', 'inbox', '收件箱', '审批', '通知', '异常'], group: '核心功能' },
  { label: '审批中心', path: '/approval', icon: FileCheck, keywords: ['审批', 'approval', '请假', '报销'], group: '核心功能' },
  { label: '销售管理', path: '/sales', icon: TrendingUp, keywords: ['销售', 'sales', '商机', '客户'], group: '核心功能' },
  { label: '项目管理', path: '/projects', icon: Target, keywords: ['项目', 'project', '任务'], group: '核心功能' },
  { label: 'OA 办公', path: '/oa', icon: Calendar, keywords: ['办公', '请假', '会议', 'oa'], group: '办公协同' },
  { label: '考勤打卡', path: '/oa?tab=attendance', icon: Fingerprint, keywords: ['考勤', '打卡', '签到', '签退', 'attendance'], group: '办公协同' },
  { label: '人事中心', path: '/hr', icon: Users, keywords: ['人事', 'hr', '绩效', '排班'], group: '办公协同' },
  { label: '财务中心', path: '/finance', icon: DollarSign, keywords: ['财务', 'finance', '报销', '发票', '预算'], group: '办公协同' },
  { label: 'CRM 客户管理', path: '/crm', icon: Users, keywords: ['crm', '客户', '线索', '商机'], group: '办公协同' },
  { label: '合同管理', path: '/contracts', icon: FileText, keywords: ['合同', 'contract'], group: '办公协同' },
  { label: '工单管理', path: '/work-orders', icon: ClipboardList, keywords: ['工单', '报修', '投诉', 'work order', '服务'], group: '办公协同' },
  { label: '资产管理', path: '/assets', icon: Package, keywords: ['资产', '设备', '领用', '归还', 'asset'], group: '办公协同' },
  { label: '库存管理', path: '/inventory', icon: Warehouse, keywords: ['库存', '进销存', '出入库', '盘点', 'inventory'], group: '办公协同' },
  { label: '企业证照', path: '/certificates', icon: Award, keywords: ['证照', '资质', '证书', '许可', 'certificate'], group: '办公协同' },
  { label: '竞品对比卡', path: '/battlecards', icon: Swords, keywords: ['竞标', 'battlecard', '竞品', '对比卡'], group: '招投标' },
  { label: '企业知识资产', path: '/knowledge', icon: BookOpen, keywords: ['知识', 'knowledge', '文档', 'rag', '产品资料', '手册', '竞品'], group: '知识与培训' },
  { label: '行业知识资产', path: '/knowledge/industry', icon: BookOpen, keywords: ['行业知识', '科学仪器', '竞品战卡', '销售打法'], group: '知识与培训' },
  { label: '知识关系洞察', path: '/knowledge/graph', icon: Brain, keywords: ['知识图谱', '关系', '实体', 'graph'], group: '知识与培训' },
  { label: '培训中心', path: '/training', icon: GraduationCap, keywords: ['培训', 'training', '学习'], group: '知识与培训' },
  { label: '激励钱包', path: '/rewards', icon: Gift, keywords: ['激励', 'reward', '积分', '奖励'], group: '知识与培训' },
  { label: 'AI 增长工作台', path: '/vmd', icon: Crown, keywords: ['vmd', '市场', '营销', '推广', '增长'], group: '业务增长' },
  { label: 'VMD 任务中心', path: '/vmd/tasks', icon: Target, keywords: ['vmd任务', '营销任务'], group: '虚拟市场部' },
  { label: 'VMD Agent配置', path: '/vmd/agents', icon: Settings, keywords: ['vmd agent', '营销agent'], group: '虚拟市场部' },
  { label: 'VMD 线索管理', path: '/vmd/clues', icon: Users, keywords: ['vmd线索', '营销线索'], group: '虚拟市场部' },
  { label: 'VMD 合规校验', path: '/vmd/compliance', icon: Shield, keywords: ['vmd合规', '内容合规'], group: '虚拟市场部' },
  { label: 'VMD 看板', path: '/vmd/dashboard', icon: BarChart3, keywords: ['vmd看板', '营销数据'], group: '虚拟市场部' },
  { label: '工作流列表', path: '/workflows', icon: Workflow, keywords: ['工作流', 'workflow', '流程'], group: '流程与表单' },
  { label: '新建工作流', path: '/workflows/new', icon: Workflow, keywords: ['新建流程', '创建工作流'], group: '流程与表单' },
  { label: '表单设计器', path: '/form-designer', icon: FileText, keywords: ['表单', 'form', '设计'], group: '流程与表单' },
  { label: '流程模板市场', path: '/workflow-templates', icon: Workflow, keywords: ['模板', 'template'], group: '流程与表单' },
  { label: '自定义仪表板', path: '/custom-dashboard', icon: BarChart3, keywords: ['自定义', 'custom', '图表'], group: '数据与报表' },
  { label: '报表中心', path: '/reports', icon: BarChart3, keywords: ['报表', 'report', '统计'], group: '数据与报表' },
  { label: '目标看板', path: '/target-dashboard', icon: Target, keywords: ['目标', 'target', 'kpi'], group: '数据与报表' },
  { label: '员工管理', path: '/employees', icon: UserCog, keywords: ['员工', 'employee', '人员'], group: '组织管理' },
  { label: '部门管理', path: '/departments', icon: Building2, keywords: ['部门', 'department'], group: '组织管理' },
  { label: '组织架构', path: '/org-chart', icon: Building2, keywords: ['组织', '架构', 'org'], group: '组织管理' },
  { label: '企业设置', path: '/company-settings', icon: Building2, keywords: ['企业', 'company', '公司设置'], group: '组织管理' },
  { label: '审计日志', path: '/audit', icon: Shield, keywords: ['审计', 'audit', '日志', '安全'], group: '系统管理' },
  { label: 'AI 设置', path: '/settings', icon: Settings, keywords: ['设置', 'settings', 'ai', '配置'], group: '系统管理' },
  { label: 'API 密钥', path: '/api-keys', icon: Key, keywords: ['api', 'key', '密钥'], group: '系统管理' },
  { label: '模型管理', path: '/llm/models', icon: Settings, keywords: ['模型', 'llm', 'model', 'ai模型'], group: '系统管理' },
  { label: 'LLM 成本', path: '/llm/costs', icon: DollarSign, keywords: ['llm成本', '模型费用', 'token'], group: '系统管理' },
  { label: 'Agent Run 管理台', path: '/agent-runs', icon: Activity, keywords: ['agent run', 'trace', '运行观测', '重放'], group: '系统管理' },
  { label: '上线交付中心', path: '/deployment-readiness', icon: Server, keywords: ['上线', '部署', '交付', 'health', 'readiness', 'handoff'], group: '系统管理' },
  { label: '客户成功看板', path: '/customer-success', icon: BarChart3, keywords: ['客户成功', '验收', 'roi', '活跃', '交付价值'], group: '系统管理' },
  { label: '权限与 AI 安全矩阵', path: '/permissions-matrix', icon: Shield, keywords: ['权限', '角色', 'rbac', '安全', 'ai边界'], group: '系统管理' },
  { label: 'Tool 治理清单', path: '/tools/governance', icon: Shield, keywords: ['tool治理', '工具治理', 'tool rag', '召回评估'], group: '系统管理' },
  { label: '数据导入', path: '/import', icon: Upload, keywords: ['导入', 'import', 'csv', 'excel'], group: '系统管理' },
  { label: '插件市场', path: '/plugins', icon: Plug, keywords: ['插件', 'plugin', '扩展'], group: '系统管理' },
  { label: 'Agent 调试', path: '/agent-debug', icon: Settings, keywords: ['agent', '调试', 'debug'], group: '系统管理' },
  { label: '定时任务', path: '/scheduled-tasks', icon: Clock, keywords: ['定时', 'scheduled', 'cron', '任务'], group: '系统管理' },
  { label: '消息中心', path: '/notification-center', icon: Bell, keywords: ['消息', 'notification', '通知'], group: '其他' },
  { label: '异常看板', path: '/exceptions', icon: Clock, keywords: ['异常', 'exception', '预警'], group: '其他' },
  { label: '个人中心', path: '/profile', icon: Users, keywords: ['个人', 'profile', '我的'], group: '其他' },
  { label: '支付管理', path: '/payments', icon: CreditCard, keywords: ['支付', 'payment', '订阅'], group: '其他' },
];

export const COMMAND_ITEM_VALUES = new Map<string, string>(
  COMMAND_ITEMS.map((item) => [
    item.path,
    `${item.label} ${item.keywords?.join(' ') || ''} ${getPinyinValues(item.label)}`,
  ])
);

const ACTION_KEYWORDS = [
  '帮我', '帮忙', '查一下', '查询', '分析', '生成', '总结',
  '对比', '计算', '预测', '统计', '列出', '搜索', '找',
  '创建', '修改', '删除', '发送', '提交', '导出',
];

export const PAGE_SUGGESTIONS: Record<string, Array<{ label: string; prompt: string }>> = {
  '/crm': [{ label: '分析客户画像', prompt: '分析当前客户的画像和价值评估' }, { label: '推荐跟进策略', prompt: '根据客户状态推荐最佳跟进策略' }],
  '/approval': [{ label: '查看待审批', prompt: '有哪些待我审批的事项？' }, { label: '审批趋势分析', prompt: '分析最近的审批通过率和趋势' }],
  '/workbench': [{ label: '今日推进顺序', prompt: '请根据审批、合同和项目状态，生成今天工作台的推进顺序。' }, { label: '查找堵点', prompt: '请帮我找出当前工作台里最可能阻塞成交或交付的事项。' }],
  '/contracts': [{ label: '合同风险清单', prompt: '请基于当前合同台账，按金额、到期日、审核状态生成合同风险清单。' }, { label: '续签提醒', prompt: '请找出 30 天内到期或需要续签的合同，并生成跟进话术。' }],
  '/growth/solutions': [{ label: '梳理方案需求', prompt: '请根据当前客户、行业、预算和应用场景，列出生成解决方案前必须核验的信息。' }, { label: '检查证据缺口', prompt: '请检查当前方案中的关键参数、预算与外部承诺，列出仍缺少企业资料依据的内容。' }],
  '/growth/tenders': [{ label: '标书审阅清单', prompt: '请给我一份投标文件审阅清单，优先检查否决项、技术偏离和评分风险。' }, { label: '生成应答矩阵', prompt: '请根据招标文件评分标准，生成带证据引用和责任人的应答矩阵草稿。' }],
  '/tender-analysis': [{ label: '标书审阅清单', prompt: '请给我一份投标文件审阅清单，优先检查否决项、技术偏离和评分风险。' }, { label: '生成应答矩阵', prompt: '请根据招标文件评分标准，生成带证据引用和责任人的应答矩阵草稿。' }],
  '/sales': [{ label: '本周业绩', prompt: '总结本周的销售业绩情况' }, { label: '商机预测', prompt: '预测本月的商机转化情况' }],
  '/dashboard': [{ label: '今日概览', prompt: '帮我总结今天的工作要点' }, { label: '异常预警', prompt: '有哪些需要关注的异常指标？' }],
  '/knowledge': [{ label: '检查资料缺口', prompt: '请按产品、手册、案例、竞品、法规和历史方案，检查企业资料库最值得补充的三项。' }, { label: '用资料生成方案', prompt: '请先询问客户行业、预算、地域、样品和检测目标，再基于企业资料生成客户方案。' }],
  '/finance': [{ label: '费用统计', prompt: '统计本月的费用支出情况' }, { label: '报销进度', prompt: '查看我的报销审批进度' }],
  '/hr': [{ label: '考勤统计', prompt: '查看本月考勤统计' }, { label: '请假审批', prompt: '有待审批的请假申请吗？' }],
  '/oa': [{ label: '今日打卡', prompt: '帮我打上班卡' }, { label: '我的审批', prompt: '我有哪些待处理的审批？' }],
  '/inbox': [{ label: '待审批', prompt: '列出所有待审批事项' }, { label: '异常预警', prompt: '当前有哪些异常需要处理？' }],
  '/vmd': [{ label: '营销任务', prompt: '查看当前营销任务进度' }, { label: '线索分析', prompt: '分析最近的营销线索质量' }],
};

export type IntentType = 'navigation' | 'ai_action' | 'search';

export function detectIntent(query: string): IntentType {
  if (!query || query.length < 2) return 'navigation';
  const lower = query.toLowerCase();
  if (ACTION_KEYWORDS.some((keyword) => lower.includes(keyword))) return 'ai_action';
  if (lower.endsWith('?') || lower.endsWith('？')) return 'ai_action';
  return 'search';
}

export const AI_QUICK_ACTIONS = [
  { label: '生成今日计划', prompt: '请根据收件箱、客户风险、审批、合同和项目，生成今天可以照着执行的工作计划。', icon: ListTodo },
  { label: '生成今日日报', prompt: '帮我生成今天的工作日报', icon: FileText },
  { label: '查看待审批事项', prompt: '有哪些待审批的事项？', icon: FileCheck },
  { label: '本周业绩总结', prompt: '帮我总结本周的业绩情况', icon: BarChart3 },
];

export const EXECUTION_COMMANDS = [
  { label: '创建客户', path: '/crm', prompt: '请打开创建客户流程，并提示我补齐客户名称、联系人、需求、预算和下一步动作。', icon: Users },
  { label: '写跟进邮件', path: '/crm', prompt: '请根据当前客户上下文，写一封专业的销售跟进邮件，并列出需要人工确认的信息。', icon: MessageSquare },
  { label: '合同风险清单', path: '/contracts', prompt: '请基于当前合同台账，输出到期、金额、付款条款和客户主体的风险清单。', icon: FileText },
  { label: '创建合同', path: '/contracts', prompt: '请帮我创建合同草稿，并先询问合同标题、客户、金额、起止日期、付款条款和负责人。', icon: FileText },
  { label: '生成客户方案', path: '/growth/solutions', prompt: '请打开方案作战流程，先关联客户并补齐应用场景、预算、仪器谱系和交付约束，再基于企业知识资产生成三档配置建议。', icon: PanelsTopLeft },
  { label: '发起投标作战', path: '/growth/tenders', prompt: '请打开投标作战流程，先建立项目并上传招标文件，然后检查否决项、技术偏离、评分风险和证据缺口。', icon: FileSearch },
  { label: '发起审批', path: '/approval', prompt: '请帮我发起审批，并先询问审批类型、金额、事由、附件和审批人。', icon: FileCheck },
];
