import type { LucideIcon } from 'lucide-react';
import {
  BarChart3,
  Bot,
  ClipboardCheck,
  FileText,
  FlaskConical,
  Gauge,
  Library,
  MessageSquareText,
  Network,
  PlayCircle,
  Radar,
  Rocket,
  ShieldCheck,
  Target,
  UserRoundCog,
  Zap,
} from 'lucide-react';

export type OperatingPriority = 'P0' | 'P1' | 'P2' | 'P3' | 'P4' | 'P5' | 'P6';

export interface OperatingCapability {
  priority: OperatingPriority;
  title: string;
  description: string;
  owner: string;
  status: 'live' | 'ready' | 'next';
  icon: LucideIcon;
  href: string;
  proof: string;
  aiPrompt: string;
}

export interface AgentTemplate {
  id: string;
  title: string;
  scenario: string;
  installs: string[];
  outcomeMetric: string;
  aiPrompt: string;
}

export interface RoleWorkbenchProfile {
  role: string;
  focus: string;
  firstScreen: string[];
  aiDefault: string;
}

export interface DemoWorkspaceArtifact {
  title: string;
  count: string;
  example: string;
}

export const AI_OPERATING_CAPABILITIES: OperatingCapability[] = [
  {
    priority: 'P0',
    title: 'VMD + 科学仪器超级场景',
    description: '把线索发现、客户 360、竞品战卡、招投标评分和跟进动作收进一个行业作战闭环。',
    owner: '增长负责人',
    status: 'live',
    icon: Rocket,
    href: '/vmd',
    proof: 'VMD、行业知识、CRM 360 已串联',
    aiPrompt: '以科学仪器销售总监视角，生成今天 VMD 最应该推进的 5 个客户动作。',
  },
  {
    priority: 'P0',
    title: 'Agent 仿真沙盒',
    description: '用历史消息对比新旧 Agent，检查工具调用、越权风险、证据引用和完成率。',
    owner: 'AI 运营',
    status: 'live',
    icon: PlayCircle,
    href: '/ai-operating-system',
    proof: 'AI 作战系统已接入 /simulate 仿真接口',
    aiPrompt: '设计 12 条用于测试销售跟进 Agent 的仿真对话，并给出评分标准。',
  },
  {
    priority: 'P1',
    title: 'SOP → AOP 自然语言定义器',
    description: '业务人员上传销售 SOP、投标流程、话术文档后，生成 Agent 规则、工具链和测试用例。',
    owner: '业务运营',
    status: 'ready',
    icon: FileText,
    href: '/ai-center',
    proof: 'Agent Studio 入口 + 行业资产 hook',
    aiPrompt: '把科学仪器投标 SOP 转成 Agent Operating Procedure：触发条件、步骤、工具、护栏、测试样例。',
  },
  {
    priority: 'P1',
    title: '轻量业务知识图谱',
    description: '连接客户、联系人、销售、项目、合同、审批、文档和行动事件，成为 Agent 的业务上下文层。',
    owner: '数据负责人',
    status: 'live',
    icon: Network,
    href: '/ai-operating-system',
    proof: 'business_context_graph 已注入 ContextEngine',
    aiPrompt: '基于客户、项目、合同、审批、文档和行动事件，生成最小业务知识图谱 schema。',
  },
  {
    priority: 'P2',
    title: 'AI 价值量化仪表盘',
    description: '面向 Boss 展示节省时间、自动化跟进、风险避免、商机推进和 ROI。',
    owner: '客户成功',
    status: 'live',
    icon: BarChart3,
    href: '/customer-success',
    proof: '客户成功看板、行动分析、LLM 成本已具备',
    aiPrompt: '把本月 AI 自动化效果转成老板能看懂的 ROI 叙事：节省时间、推进商机、避免风险。',
  },
  {
    priority: 'P2',
    title: '纯 AI-Native 场景',
    description: '线索跟进、投标支持、竞品分析不再只是 CRUD 页面加按钮，而是对话 + GenUI 的作战流。',
    owner: '产品负责人',
    status: 'ready',
    icon: MessageSquareText,
    href: '/dashboard#ai-chat',
    proof: '聊天面板、GenUI、页面内嵌 AI 已落地',
    aiPrompt: '用对话 + GenUI 跑一遍“线索发现 → 客户 360 → 竞品战卡 → 投标评分 → 跟进邮件”。',
  },
  {
    priority: 'P3',
    title: '自主行动与事件触发',
    description: '低风险动作可自动执行，高风险动作进入人工确认；触发条件从 cron 升级为业务事件。',
    owner: 'AI 运营',
    status: 'ready',
    icon: Zap,
    href: '/scheduled-tasks',
    proof: 'Proactive Copilot + action_events 审计',
    aiPrompt: '为 30 天未联系客户、合同到期前 60 天、投标截止前 3 天设计事件触发 Agent 策略。',
  },
  {
    priority: 'P4',
    title: '首屏作战台与角色首页',
    description: '首页回答“今天推进谁、哪个项目有风险、AI 已经做了什么、我下一步点哪里”。',
    owner: '产品设计',
    status: 'live',
    icon: Radar,
    href: '/dashboard',
    proof: '行动台取代传统 Dashboard',
    aiPrompt: '根据我的角色生成今天的作战台：客户、项目风险、AI 自动推进、待确认动作。',
  },
  {
    priority: 'P4',
    title: '行业模板库',
    description: '把高校客户跟进、招投标评分、竞品战卡、复购提醒、销售周报沉淀成一键安装模板。',
    owner: '行业运营',
    status: 'ready',
    icon: Library,
    href: '/industry-knowledge',
    proof: '科学仪器资产与模板安装蓝图',
    aiPrompt: '推荐 5 个最适合科学仪器销售团队的一键安装 Agent 模板。',
  },
  {
    priority: 'P5',
    title: '7 天成功路径',
    description: '从导入客户到配置 Agent、上传 SOP、跑投标分析、看 ROI、邀请团队，形成首周激活闭环。',
    owner: '客户成功',
    status: 'ready',
    icon: ClipboardCheck,
    href: '/customer-success',
    proof: 'LaunchChecklist + 客户成功页',
    aiPrompt: '为一个 20 人科学仪器销售团队生成 Nexus 上线首周成功计划。',
  },
  {
    priority: 'P5',
    title: '科学仪器 Demo 空间',
    description: '预置客户、投标项目、竞品、审批、合同、拜访记录，一键演示完整销售闭环。',
    owner: '售前',
    status: 'ready',
    icon: FlaskConical,
    href: '/ai-operating-system#demo-space',
    proof: 'Demo 数据空间产品化',
    aiPrompt: '生成科学仪器销售 Demo 剧本：线索发现、客户 360、竞品战卡、投标分析、ROI 报告。',
  },
  {
    priority: 'P6',
    title: '角色化体验',
    description: 'Boss、销售、售前、运营、管理员看到不同作战台、不同默认 AI、不同价值指标。',
    owner: '增长产品',
    status: 'ready',
    icon: UserRoundCog,
    href: '/ai-operating-system#role-workbench',
    proof: 'Role Workbench 产品模型',
    aiPrompt: '分别为 Boss、销售、售前、运营、管理员生成默认首页和 AI 副驾策略。',
  },
];

export const AI_NATIVE_SCENES = [
  {
    title: '线索跟进作战流',
    flow: '客户风险 → AI 拜访提醒 → 跟进邮件 → 行动事件',
    metric: '30 天未跟进客户下降 60%',
    icon: Target,
  },
  {
    title: '投标支持作战流',
    flow: '标书上传 → 评分拆解 → 风险项 → 技术方案草稿',
    metric: '投标准备周期缩短 40%',
    icon: Gauge,
  },
  {
    title: '竞品战卡作战流',
    flow: '客户型号 → 竞品参数 → 差异话术 → 现场问答',
    metric: '售前响应时间缩短 50%',
    icon: ShieldCheck,
  },
];

export const AGENT_TEMPLATES: AgentTemplate[] = [
  {
    id: 'university-followup-agent',
    title: '高校客户跟进 Agent',
    scenario: '科研院所、高校实验室 30 天无触达自动识别并生成跟进建议。',
    installs: ['CRM 风险规则', '跟进邮件模板', '拜访提醒', '行动台提醒'],
    outcomeMetric: '高价值客户无触达率下降',
    aiPrompt: '安装高校客户跟进 Agent，并列出触发条件、动作、权限和测试样例。',
  },
  {
    id: 'tender-scoring-agent',
    title: '招投标评分 Agent',
    scenario: '拆解标书评分标准，对技术方案、商务条款和竞品风险给出分数。',
    installs: ['标书解析', '评分矩阵', '风险清单', '方案草稿'],
    outcomeMetric: '投标准备周期缩短',
    aiPrompt: '安装招投标评分 Agent，生成评分矩阵和投标风险检查清单。',
  },
  {
    id: 'battlecard-agent',
    title: '竞品战卡 Agent',
    scenario: '围绕 Thermo Fisher、Agilent、Shimadzu 生成参数对比和销售话术。',
    installs: ['竞品知识资产', '话术模板', '现场问答', '证据引用'],
    outcomeMetric: '售前答复速度提升',
    aiPrompt: '安装竞品战卡 Agent，并针对 Thermo Fisher LC/MS 生成一张销售战卡。',
  },
  {
    id: 'renewal-agent',
    title: '老客户复购提醒 Agent',
    scenario: '结合合同、项目和耗材周期，提前触发复购或续签动作。',
    installs: ['合同到期事件', '复购预测', '客户邮件', 'Boss 汇总'],
    outcomeMetric: '续签遗漏率下降',
    aiPrompt: '安装老客户复购提醒 Agent，按合同到期前 60 天触发续签流程。',
  },
];

export const ROLE_WORKBENCH_PROFILES: RoleWorkbenchProfile[] = [
  {
    role: 'Boss',
    focus: '风险、ROI、团队执行力、预测缺口',
    firstScreen: ['AI 价值仪表盘', '高风险未闭环', '团队动作漏斗', '本月预测缺口'],
    aiDefault: '生成本周经营复盘和下周管理动作。',
  },
  {
    role: '销售',
    focus: '今日客户、跟进动作、拜访记录、邮件草稿',
    firstScreen: ['今日跟进', '客户健康分', '拜访速记', '邮件草稿'],
    aiDefault: '列出我今天最应该跟进的客户，并写好第一封跟进邮件。',
  },
  {
    role: '售前',
    focus: '标书、竞品、技术参数、方案草稿',
    firstScreen: ['投标评分', '竞品战卡', '参数差异', '方案草稿'],
    aiDefault: '帮我准备明天客户技术交流的竞品差异和问答材料。',
  },
  {
    role: 'AI 运营',
    focus: 'Agent 仿真、失败回放、规则优化、自动化率',
    firstScreen: ['仿真沙盒', '失败对话', '规则变更', '自动化率'],
    aiDefault: '找出本周 Agent 失败最多的 3 类场景并给出修复建议。',
  },
];

export const SEVEN_DAY_SUCCESS_PATH = [
  'Day 1：导入客户、线索、项目和历史拜访记录',
  'Day 2：安装高校客户跟进、投标评分、竞品战卡三个 Agent 模板',
  'Day 3：上传销售 SOP 和投标流程，让系统生成 AOP 草案',
  'Day 4：跑 20 条历史消息仿真，确认自动执行和人工确认边界',
  'Day 5：上线行动台，要求团队每天处理高优先级动作',
  'Day 6：查看 AI 价值仪表盘，复盘节省时间和推进商机',
  'Day 7：邀请管理层看 Demo 空间和本组织真实作战数据',
];

export const DEMO_WORKSPACE_ARTIFACTS: DemoWorkspaceArtifact[] = [
  { title: '行业客户', count: '36', example: '高校实验室、科研院所、药企研发中心、第三方检测机构' },
  { title: '投标项目', count: '8', example: '液相色谱质谱联用仪、离子色谱、样品前处理系统' },
  { title: '竞品战卡', count: '12', example: 'Thermo Fisher、Agilent、Shimadzu、Waters 参数对比' },
  { title: '行动事件', count: '120+', example: '采纳、完成、忽略、延后、人工确认、自动执行' },
];

export const AUTONOMOUS_ACTION_POLICIES = [
  {
    level: '自动执行',
    scope: '低风险：生成草稿、更新标签、创建待办、整理拜访纪要。',
    guardrail: '写入 action_events，允许用户撤销或标记误判。',
  },
  {
    level: '人工确认',
    scope: '中高风险：审批、合同、付款、客户外发、批量变更。',
    guardrail: '必须展示证据、置信度、影响范围和回滚路径。',
  },
  {
    level: '禁止执行',
    scope: '越权、删除核心数据、绕过审批链、无证据财务动作。',
    guardrail: '直接阻断并进入审计日志。',
  },
];

export const EVENT_TRIGGER_BLUEPRINTS = [
  '客户 30 天无跟进 → 生成拜访提醒、邮件草稿和行动台任务',
  '合同到期前 60 天 → 触发续签机会、客户健康检查和 Boss 摘要',
  '投标截止前 3 天 → 检查评分矩阵缺口、技术响应草稿和风险条款',
  'Agent 连续失败 3 次 → 进入仿真沙盒并推荐 SOP 或工具链修复',
  '高价值客户阶段停滞 14 天 → 触发竞品战卡和下一步跟进建议',
];

export const CONTEXT_GRAPH_EDGES = [
  '客户 ↔ 销售 ↔ 项目 ↔ 合同',
  '客户 ↔ 拜访记录 ↔ 行动事件',
  '投标项目 ↔ 标书文档 ↔ 评分矩阵',
  '审批 ↔ 合同 ↔ 风险证据',
  '用户角色 ↔ 可见范围 ↔ Agent 默认策略',
];

export const OPERATING_SYSTEM_METRICS = [
  { label: '超级场景', value: '1 个', icon: Rocket },
  { label: 'Agent 模板', value: '4 个', icon: Bot },
  { label: '知识图谱实体', value: '7 类', icon: Network },
  { label: 'AI-Native 场景', value: '3 条', icon: MessageSquareText },
  { label: '成功路径', value: '7 天', icon: ClipboardCheck },
  { label: '自主行动层级', value: '3 档', icon: Zap },
];
