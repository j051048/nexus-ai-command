import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  BarChart3,
  Bot,
  BrainCircuit,
  ClipboardCheck,
  FileText,
  FlaskConical,
  Gauge,
  GitBranch,
  Library,
  MessageSquareText,
  Network,
  PlayCircle,
  Radar,
  Rocket,
  ShieldCheck,
  Target,
  UserRoundCog,
  Users,
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
    proof: 'VMD / 行业知识 / CRM 360 已串联',
    aiPrompt: '请以科学仪器销售总监视角，生成今天 VMD 最应该推进的 5 个客户动作。',
  },
  {
    priority: 'P0',
    title: 'Agent 仿真沙盒',
    description: '用历史消息对比新旧 Agent，检查工具调用、越权风险、证据引用和完成率。',
    owner: 'AI 运营',
    status: 'ready',
    icon: PlayCircle,
    href: '/agent-runs',
    proof: 'Agent Runs + 质量守卫 + 评测入口',
    aiPrompt: '请设计一组用于测试销售跟进 Agent 的 12 条仿真对话，并给出评分标准。',
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
    aiPrompt: '请把这份科学仪器投标 SOP 转成 Agent Operating Procedure：触发条件、步骤、工具、护栏、测试样例。',
  },
  {
    priority: 'P1',
    title: '轻量业务知识图谱',
    description: '连接客户、联系人、销售、项目、合同、审批、文档和行动事件，成为 Agent 的业务上下文层。',
    owner: '数据负责人',
    status: 'ready',
    icon: Network,
    href: '/knowledge',
    proof: 'Context Graph 设计进入产品面板',
    aiPrompt: '请基于客户、项目、合同、审批、文档和行动事件，生成一个最小业务知识图谱 schema。',
  },
  {
    priority: 'P2',
    title: 'AI 价值量化仪表盘',
    description: '面向 Boss 展示节省时间、自动化跟进、风险避免、商机推进和 ROI。',
    owner: '客户成功',
    status: 'live',
    icon: BarChart3,
    href: '/customer-success',
    proof: '客户成功看板 + 行动分析 + LLM 成本',
    aiPrompt: '请把本月 AI 自动化效果转成老板能看懂的 ROI 叙事：节省时间、推进商机、避免风险。',
  },
  {
    priority: 'P2',
    title: '纯 AI-Native 场景',
    description: '线索跟进、投标支持、竞品分析不再只是 CRUD 页面加按钮，而是对话 + GenUI 的作战流。',
    owner: '产品负责人',
    status: 'ready',
    icon: MessageSquareText,
    href: '/dashboard#ai-chat',
    proof: '聊天面板 + GenUI + 页面内嵌 AI',
    aiPrompt: '请以对话 + GenUI 的形式跑一遍“线索发现 → 客户 360 → 竞品战卡 → 投标评分 → 跟进邮件”。',
  },
  {
    priority: 'P3',
    title: '自主行动与事件触发',
    description: '低风险动作可自动执行，高风险动作进入人工确认；触发条件从 cron 升级为业务事件。',
    owner: 'AI 运营',
    status: 'ready',
    icon: Zap,
    href: '/scheduled-tasks',
    proof: 'Proactive Copilot + 行动事件审计',
    aiPrompt: '请为 30 天未联系客户、合同到期前 60 天、投标截止前 3 天设计事件触发 Agent 策略。',
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
    aiPrompt: '请根据我的角色生成一个今天的作战台：客户、项目风险、AI 自动推进、待确认动作。',
  },
  {
    priority: 'P4',
    title: '行业模板库',
    description: '把高校客户跟进、招投标评分、竞品战卡、复购提醒、销售周报沉淀成一键安装模板。',
    owner: '行业运营',
    status: 'ready',
    icon: Library,
    href: '/industry-knowledge',
    proof: '科学仪器资产 + 模板安装蓝图',
    aiPrompt: '请推荐 5 个最适合科学仪器销售团队的一键安装 Agent 模板。',
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
    aiPrompt: '请为一个 20 人科学仪器销售团队生成 Nexus 上线首周成功计划。',
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
    aiPrompt: '请生成一个科学仪器销售 Demo 剧本：线索发现、客户 360、竞品战卡、投标分析、ROI 报告。',
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
    aiPrompt: '请分别为 Boss、销售、售前、运营、管理员生成 Nexus 默认首页和 AI 副驾策略。',
  },
];

export const AI_NATIVE_SCENES = [
  {
    title: '线索跟进作战流',
    flow: '客户风险 → AI 拜访提纲 → 跟进邮件 → 行动事件',
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
    installs: ['CRM 风险规则', '跟进邮件模板', '拜访提纲', '行动台提醒'],
    outcomeMetric: '高价值客户无触达率下降',
    aiPrompt: '请安装高校客户跟进 Agent，并列出触发条件、动作、权限和测试样例。',
  },
  {
    id: 'tender-scoring-agent',
    title: '招投标评分 Agent',
    scenario: '拆解标书评分标准，对技术方案、商务条款和竞品风险给出分数。',
    installs: ['标书解析', '评分矩阵', '风险清单', '方案草稿'],
    outcomeMetric: '投标准备周期缩短',
    aiPrompt: '请安装招投标评分 Agent，生成评分矩阵和投标风险检查清单。',
  },
  {
    id: 'battlecard-agent',
    title: '竞品战卡 Agent',
    scenario: '围绕 Thermo Fisher、Agilent、Shimadzu 生成参数对比和销售话术。',
    installs: ['竞品知识资产', '话术模板', '现场问答', '证据引用'],
    outcomeMetric: '售前答复速度提升',
    aiPrompt: '请安装竞品战卡 Agent，并针对 Thermo Fisher LC/MS 生成一张销售战卡。',
  },
  {
    id: 'renewal-agent',
    title: '老客户复购提醒 Agent',
    scenario: '结合合同、项目和耗材周期，提前触发复购或续签动作。',
    installs: ['合同到期事件', '复购预测', '客户邮件', 'Boss 汇总'],
    outcomeMetric: '续签遗漏率下降',
    aiPrompt: '请安装老客户复购提醒 Agent，按合同到期前 60 天触发续签流程。',
  },
];

export const ROLE_WORKBENCH_PROFILES: RoleWorkbenchProfile[] = [
  {
    role: 'Boss',
    focus: '风险、ROI、团队执行力、预测缺口',
    firstScreen: ['AI 价值仪表盘', '高风险未闭环', '团队动作榜', '本月预测缺口'],
    aiDefault: '生成本周经营复盘和下周管理动作。',
  },
  {
    role: '销售',
    focus: '客户、下一步、话术、拜访纪要',
    firstScreen: ['今日客户', '30 天未跟进', '拜访提纲', '跟进邮件草稿'],
    aiDefault: '帮我准备今天最重要客户的拜访材料。',
  },
  {
    role: '售前',
    focus: '技术方案、竞品参数、投标评分',
    firstScreen: ['待处理标书', '竞品战卡', '技术方案草稿', '知识缺口'],
    aiDefault: '请根据标书评分标准生成技术响应建议。',
  },
  {
    role: '运营/市场',
    focus: '线索、内容、行业知识缺口',
    firstScreen: ['行业线索', '内容任务', '知识缺口', 'VMD 任务'],
    aiDefault: '找出本周最该补齐的行业知识资产。',
  },
  {
    role: '管理员',
    focus: '权限、成本、Agent 质量、安全边界',
    firstScreen: ['Agent 质量', '工具权限', 'LLM 成本', '安全审计'],
    aiDefault: '检查本周 Agent 风险和工具权限异常。',
  },
];

export const SEVEN_DAY_SUCCESS_PATH = [
  '第 1 天：导入客户和联系人，生成第一版客户 360。',
  '第 2 天：上传竞品资料和销售 SOP，建立行业知识资产。',
  '第 3 天：安装高校客户跟进 Agent，并跑 10 条仿真测试。',
  '第 4 天：上传一个真实标书，生成评分矩阵和风险清单。',
  '第 5 天：启用行动台运营分析，检查采纳率和未闭环事项。',
  '第 6 天：查看 AI 价值仪表盘，输出老板版 ROI 叙事。',
  '第 7 天：邀请团队成员，按角色分配首页和 Agent 权限。',
];

export const DEMO_WORKSPACE_ARTIFACTS: DemoWorkspaceArtifact[] = [
  { title: '客户', count: '20 个', example: '中科院物理所、清华材料学院、华东检测中心' },
  { title: '投标项目', count: '3 个', example: 'LC/MS 平台采购、质谱实验室升级、样品前处理系统' },
  { title: '竞品', count: '5 个', example: 'Thermo Fisher、Agilent、Shimadzu、Waters、Bruker' },
  { title: '业务记录', count: '60 条', example: '拜访纪要、审批、合同、邮件、行动事件' },
];

export const AUTONOMOUS_ACTION_POLICIES = [
  {
    level: '自动执行',
    scope: '低风险动作：生成周报、更新客户标签、归档拜访纪要',
    guardrail: '保留审计日志，可撤销，不触发财务或外部发送',
  },
  {
    level: '人工确认',
    scope: '中风险动作：发送客户邮件、创建审批、调整商机阶段',
    guardrail: '显示置信度、证据链、影响范围，用户确认后执行',
  },
  {
    level: '禁止自动化',
    scope: '高风险动作：付款、删除数据、合同承诺、价格承诺',
    guardrail: '必须走权限、审批和人工签核',
  },
];

export const OPERATING_SYSTEM_METRICS = [
  { label: '首周激活目标', value: '7 天', icon: Activity },
  { label: '核心超级场景', value: '1 个', icon: Rocket },
  { label: '行业模板', value: `${AGENT_TEMPLATES.length} 个`, icon: Library },
  { label: '角色工作台', value: `${ROLE_WORKBENCH_PROFILES.length} 类`, icon: Users },
  { label: 'Agent 生命周期', value: 'Define-Test-Deploy-Measure', icon: Bot },
  { label: '业务上下文层', value: 'Context Graph', icon: BrainCircuit },
];

export const EVENT_TRIGGER_BLUEPRINTS = [
  '客户进入 30 天未联系：触发跟进 Agent，生成邮件和拜访提纲。',
  '合同到期前 60 天：触发续签 Agent，汇总历史服务和复购建议。',
  '投标截止前 3 天：触发投标风险 Agent，列出未完成材料和评分缺口。',
  'AI 建议连续 3 次被忽略：触发质量监控，要求运营复盘建议是否有误。',
];

export const CONTEXT_GRAPH_EDGES = [
  '客户 ↔ 联系人 ↔ 销售',
  '客户 ↔ 项目 ↔ 合同',
  '合同 ↔ 审批 ↔ 回款',
  '客户 ↔ 文档 ↔ 行业知识资产',
  '行动事件 ↔ Agent 版本 ↔ 用户反馈',
];
