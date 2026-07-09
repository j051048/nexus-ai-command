/* eslint-disable react-refresh/only-export-components */
import React, { useCallback, useEffect, useState, useRef, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from '@/components/ui/command';
import {
  Users,
  FileCheck,
  BookOpen,
  Gift,
  Settings,
  TrendingUp,
  FileSearch,
  Swords,
  Target,
  Calendar,
  DollarSign,
  Clock,
  Workflow,
  Upload,
  FileText,
  BarChart3,
  Shield,
  Bell,
  CreditCard,
  GraduationCap,
  Plug,
  Crown,
  Key,
  UserCog,
  Building2,
  Loader2,
  MessageSquare,
  Sparkles,
  SunMoon,
  ClipboardList,
  Package,
  Award,
  Warehouse,
  Fingerprint,
  PlusCircle,
  ListTodo,
  Activity,
  Server,
  Brain,
} from 'lucide-react';
import { aiClient } from '@/api/aiClient';
import { pinyin } from 'pinyin-pro';
import { isModuleEnabled, type ModuleFlag } from '@/config/featureFlags';
import { usePageContext } from '@/hooks/usePageContext';

/**
 * 拼音处理辅助函数：生成全拼和首字母
 * 例如 "待办" -> "daiban db"
 */
function getPinyinValues(text: string): string {
  try {
    const full = pinyin(text, { toneType: 'none', type: 'array' }).join('');
    const first = pinyin(text, { pattern: 'initial', toneType: 'none', type: 'array' }).join('');
    return `${full} ${first}`;
  } catch {
    return '';
  }
}

interface NavCommandItem {
  label: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  keywords?: string[];
  group: string;
}

function moduleForPath(path: string): ModuleFlag | null {
  const normalized = path.split('?')[0].replace(/^\/+/, '');
  if (normalized === 'crm') return 'crm';
  if (normalized === 'contracts' || normalized === 'documents') return 'documents';
  if (normalized === 'knowledge') return 'knowledge';
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
  if (normalized === 'battlecards') return 'battlecards';
  if (normalized === 'training') return 'training';
  if (normalized === 'vmd' || normalized.startsWith('vmd/')) return 'vmd';
  if (normalized === 'plugins') return 'plugins';
  if (normalized === 'soul-document') return 'soul_document';
  if (normalized === 'agent-debug' || normalized === 'dev/animations') return 'dev_tools';
  return null;
}

function isCommandFeatureEnabled(item: NavCommandItem): boolean {
  const moduleFlag = moduleForPath(item.path);
  return moduleFlag ? isModuleEnabled(moduleFlag) : true;
}

interface CustomerResult {
  id: string;
  name: string;
  company?: string;
}

// Custom event for Command Bar → Chat Panel bridge
export const COMMAND_BAR_CHAT_EVENT = 'nexus:command-bar-chat';
export const COMMAND_BAR_NEW_CHAT_EVENT = 'nexus:command-bar-new-chat';

export function dispatchAIChatMessage(message: string) {
  window.dispatchEvent(new CustomEvent(COMMAND_BAR_CHAT_EVENT, { detail: { message } }));
}

export function dispatchNewChat() {
  window.dispatchEvent(new CustomEvent(COMMAND_BAR_NEW_CHAT_EVENT));
}

const COMMAND_ITEMS: NavCommandItem[] = [
  // 核心功能
  { label: '收件箱', path: '/dashboard', icon: Bell, keywords: ['首页', 'home', 'dashboard', '待办', '收件箱', '行动'], group: '核心空间' },
  { label: 'CRM', path: '/crm', icon: Users, keywords: ['crm', '客户', '线索', '商机', '销售'], group: '核心空间' },
  { label: '工作台', path: '/workbench', icon: Workflow, keywords: ['项目', '审批', '合同', 'oa', 'hr', '流程'], group: '核心空间' },
  { label: '数据', path: '/data', icon: BarChart3, keywords: ['报表', '数据', '目标', 'dashboard', '经营'], group: '核心空间' },
  { label: '助手', path: '/ai-center', icon: Sparkles, keywords: ['ai', 'agent', '知识库', '模型', '插件', 'ai中心', '助手中心'], group: '核心空间' },
  { label: '助手工作台', path: '/ai-operating-system', icon: Sparkles, keywords: ['助手工作台', 'agent sandbox', 'sop', 'aop', '知识图谱', 'demo', '角色化', '业务流程'], group: '核心空间' },
  { label: '助手优化', path: '/agent-improvement-center', icon: Brain, keywords: ['agent', '进化中心', 'prompt registry', 'context quality', 'harness', 'hermes', '自我进化', 'memory hygiene'], group: '核心空间' },
  { label: '领导驾驶舱', path: '/boss-dashboard', icon: Crown, keywords: ['boss', '管理', '概览'], group: '核心功能' },
  { label: '待办中心', path: '/inbox', icon: Bell, keywords: ['待办', 'inbox', '收件箱', '审批', '通知', '异常'], group: '核心功能' },
  { label: '审批中心', path: '/approval', icon: FileCheck, keywords: ['审批', 'approval', '请假', '报销'], group: '核心功能' },
  { label: '销售管理', path: '/sales', icon: TrendingUp, keywords: ['销售', 'sales', '商机', '客户'], group: '核心功能' },
  { label: '项目管理', path: '/projects', icon: Target, keywords: ['项目', 'project', '任务'], group: '核心功能' },

  // 办公协同
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

  // 招投标
  { label: '标书分析', path: '/tender-analysis', icon: FileSearch, keywords: ['标书', 'tender', '招标', '投标'], group: '招投标' },
  { label: '竞品对比卡', path: '/battlecards', icon: Swords, keywords: ['竞标', 'battlecard', '竞品', '作战卡'], group: '招投标' },

  // 知识与培训
  { label: '知识库', path: '/knowledge', icon: BookOpen, keywords: ['知识', 'knowledge', '文档', 'rag'], group: '知识与培训' },
  { label: '培训中心', path: '/training', icon: GraduationCap, keywords: ['培训', 'training', '学习'], group: '知识与培训' },
  { label: '激励钱包', path: '/rewards', icon: Gift, keywords: ['激励', 'reward', '积分', '奖励'], group: '知识与培训' },

  // 虚拟市场部
  { label: '虚拟市场部', path: '/vmd', icon: Crown, keywords: ['vmd', '市场', '营销', '推广'], group: '虚拟市场部' },
  { label: 'VMD 任务中心', path: '/vmd/tasks', icon: Target, keywords: ['vmd任务', '营销任务'], group: '虚拟市场部' },
  { label: 'VMD Agent配置', path: '/vmd/agents', icon: Settings, keywords: ['vmd agent', '营销agent'], group: '虚拟市场部' },
  { label: 'VMD 线索管理', path: '/vmd/clues', icon: Users, keywords: ['vmd线索', '营销线索'], group: '虚拟市场部' },
  { label: 'VMD 合规校验', path: '/vmd/compliance', icon: Shield, keywords: ['vmd合规', '内容合规'], group: '虚拟市场部' },
  { label: 'VMD 看板', path: '/vmd/dashboard', icon: BarChart3, keywords: ['vmd看板', '营销数据'], group: '虚拟市场部' },

  // 流程与表单
  { label: '工作流列表', path: '/workflows', icon: Workflow, keywords: ['工作流', 'workflow', '流程'], group: '流程与表单' },
  { label: '新建工作流', path: '/workflows/new', icon: Workflow, keywords: ['新建流程', '创建工作流'], group: '流程与表单' },
  { label: '表单设计器', path: '/form-designer', icon: FileText, keywords: ['表单', 'form', '设计'], group: '流程与表单' },
  { label: '流程模板市场', path: '/workflow-templates', icon: Workflow, keywords: ['模板', 'template'], group: '流程与表单' },

  // 数据与报表
  { label: '自定义仪表板', path: '/custom-dashboard', icon: BarChart3, keywords: ['自定义', 'custom', '图表'], group: '数据与报表' },
  { label: '报表中心', path: '/reports', icon: BarChart3, keywords: ['报表', 'report', '统计'], group: '数据与报表' },
  { label: '目标看板', path: '/target-dashboard', icon: Target, keywords: ['目标', 'target', 'kpi'], group: '数据与报表' },

  // 组织管理
  { label: '员工管理', path: '/employees', icon: UserCog, keywords: ['员工', 'employee', '人员'], group: '组织管理' },
  { label: '部门管理', path: '/departments', icon: Building2, keywords: ['部门', 'department'], group: '组织管理' },
  { label: '组织架构', path: '/org-chart', icon: Building2, keywords: ['组织', '架构', 'org'], group: '组织管理' },
  { label: '企业设置', path: '/company-settings', icon: Building2, keywords: ['企业', 'company', '公司设置'], group: '组织管理' },

  // 系统管理
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

  // 其他
  { label: '消息中心', path: '/notification-center', icon: Bell, keywords: ['消息', 'notification', '通知'], group: '其他' },
  { label: '异常看板', path: '/exceptions', icon: Clock, keywords: ['异常', 'exception', '预警'], group: '其他' },
  { label: '个人中心', path: '/profile', icon: Users, keywords: ['个人', 'profile', '我的'], group: '其他' },
  { label: '支付管理', path: '/payments', icon: CreditCard, keywords: ['支付', 'payment', '订阅'], group: '其他' },
];

// Pre-compute pinyin search values at module level (COMMAND_ITEMS is static)
const COMMAND_ITEM_VALUES = new Map<string, string>(
  COMMAND_ITEMS.map((item) => [
    item.path,
    `${item.label} ${item.keywords?.join(' ') || ''} ${getPinyinValues(item.label)}`,
  ])
);

// P2: Intent detection — ACTION_KEYWORDS trigger AI routing
const ACTION_KEYWORDS = [
  '帮我', '帮忙', '查一下', '查询', '分析', '生成', '总结',
  '对比', '计算', '预测', '统计', '列出', '搜索', '找',
  '创建', '修改', '删除', '发送', '提交', '导出',
];

// P2: Page-context-aware suggestions
const PAGE_SUGGESTIONS: Record<string, Array<{ label: string; prompt: string }>> = {
  '/crm': [
    { label: '分析客户画像', prompt: '分析当前客户的画像和价值评估' },
    { label: '推荐跟进策略', prompt: '根据客户状态推荐最佳跟进策略' },
  ],
  '/approval': [
    { label: '查看待审批', prompt: '有哪些待我审批的事项？' },
    { label: '审批趋势分析', prompt: '分析最近的审批通过率和趋势' },
  ],
  '/workbench': [
    { label: '今日推进顺序', prompt: '请根据审批、合同和项目状态，生成今天工作台的推进顺序。' },
    { label: '查找堵点', prompt: '请帮我找出当前工作台里最可能阻塞成交或交付的事项。' },
  ],
  '/contracts': [
    { label: '合同风险清单', prompt: '请基于当前合同台账，按金额、到期日、审核状态生成合同风险清单。' },
    { label: '续签提醒', prompt: '请找出 30 天内到期或需要续签的合同，并生成跟进话术。' },
  ],
  '/tender-analysis': [
    { label: '标书审阅清单', prompt: '请给我一份投标文件审阅清单，优先检查否决项、技术偏离和评分风险。' },
    { label: '生成投标策略', prompt: '请根据招标文件评分标准，生成投标响应策略和材料准备清单。' },
  ],
  '/sales': [
    { label: '本周业绩', prompt: '总结本周的销售业绩情况' },
    { label: '商机预测', prompt: '预测本月的商机转化情况' },
  ],
  '/dashboard': [
    { label: '今日概览', prompt: '帮我总结今天的工作要点' },
    { label: '异常预警', prompt: '有哪些需要关注的异常指标？' },
  ],
  '/knowledge': [
    { label: '搜索知识库', prompt: '在知识库中搜索' },
    { label: '文档推荐', prompt: '推荐与当前工作相关的文档' },
  ],
  '/finance': [
    { label: '费用统计', prompt: '统计本月的费用支出情况' },
    { label: '报销进度', prompt: '查看我的报销审批进度' },
  ],
  '/hr': [
    { label: '考勤统计', prompt: '查看本月考勤统计' },
    { label: '请假审批', prompt: '有待审批的请假申请吗？' },
  ],
  '/oa': [
    { label: '今日打卡', prompt: '帮我打上班卡' },
    { label: '我的审批', prompt: '我有哪些待处理的审批？' },
  ],
  '/inbox': [
    { label: '待审批', prompt: '列出所有待审批事项' },
    { label: '异常预警', prompt: '当前有哪些异常需要处理？' },
  ],
  '/vmd': [
    { label: '营销任务', prompt: '查看当前营销任务进度' },
    { label: '线索分析', prompt: '分析最近的营销线索质量' },
  ],
};

type IntentType = 'navigation' | 'ai_action' | 'search';

function detectIntent(query: string): IntentType {
  if (!query || query.length < 2) return 'navigation';
  const lower = query.toLowerCase();
  if (ACTION_KEYWORDS.some(kw => lower.includes(kw))) return 'ai_action';
  if (lower.endsWith('?') || lower.endsWith('？')) return 'ai_action';
  return 'search';
}

// AI quick actions shown at the top of the command list
const AI_QUICK_ACTIONS = [
  { label: '生成今日计划', prompt: '请根据收件箱、客户风险、审批、合同和项目，生成今天可以照着执行的工作计划。', icon: ListTodo },
  { label: '生成今日日报', prompt: '帮我生成今天的工作日报', icon: FileText },
  { label: '查看待审批事项', prompt: '有哪些待审批的事项？', icon: FileCheck },
  { label: '本周业绩总结', prompt: '帮我总结本周的业绩情况', icon: BarChart3 },
];

const EXECUTION_COMMANDS = [
  {
    label: '创建客户',
    path: '/crm',
    prompt: '请打开创建客户流程，并提示我补齐客户名称、联系人、需求、预算和下一步动作。',
    icon: Users,
  },
  {
    label: '写跟进邮件',
    path: '/crm',
    prompt: '请根据当前客户上下文，写一封专业的销售跟进邮件，并列出需要人工确认的信息。',
    icon: MessageSquare,
  },
  {
    label: '合同风险清单',
    path: '/contracts',
    prompt: '请基于当前合同台账，输出到期、金额、付款条款和客户主体的风险清单。',
    icon: FileText,
  },
  {
    label: '创建合同',
    path: '/contracts',
    prompt: '请帮我创建合同草稿，并先询问合同标题、客户、金额、起止日期、付款条款和负责人。',
    icon: FileText,
  },
  {
    label: '发起投标分析',
    path: '/tender-analysis',
    prompt: '请打开投标分析流程，并提示我上传招标文件，然后优先检查否决项、技术偏离和评分风险。',
    icon: FileSearch,
  },
  {
    label: '发起审批',
    path: '/approval',
    prompt: '请帮我发起审批，并先询问审批类型、金额、事由、附件和审批人。',
    icon: FileCheck,
  },
];

export function GlobalCommandBar() {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [customerResults, setCustomerResults] = useState<CustomerResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { pageContext } = usePageContext();
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // P2: Detect intent from current input
  const intent = useMemo(() => detectIntent(searchQuery), [searchQuery]);

  // P2: Get page-context-aware suggestions
  const pageSuggestions = useMemo(() => {
    const path = location.pathname;
    for (const [prefix, suggestions] of Object.entries(PAGE_SUGGESTIONS)) {
      if (path.startsWith(prefix)) return suggestions;
    }
    return [];
  }, [location.pathname]);

  // Listen for Ctrl+K / Cmd+K
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  // Reset search state when dialog closes
  useEffect(() => {
    if (!open) {
      setSearchQuery('');
      setCustomerResults([]);
      setIsSearching(false);
    }
  }, [open]);

  // Debounced business data search
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    if (searchQuery.length < 2) {
      setCustomerResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    debounceTimerRef.current = setTimeout(async () => {
      try {
        const data = await aiClient.fetch<CustomerResult[]>(
          `api/crm/customers?search=${encodeURIComponent(searchQuery)}`
        );
        setCustomerResults(Array.isArray(data) ? data : []);
      } catch {
        setCustomerResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [searchQuery]);

  const handleSelect = useCallback(
    (path: string) => {
      setOpen(false);
      navigate(path);
    },
    [navigate],
  );

  const handleAIChat = useCallback((message: string) => {
    setOpen(false);
    dispatchAIChatMessage(message);
  }, []);

  const handleNewChat = useCallback(() => {
    setOpen(false);
    dispatchNewChat();
  }, []);

  const handleThemeToggle = useCallback(() => {
    setOpen(false);
    document.documentElement.classList.toggle('dark');
  }, []);

  // Group items
  const groups = COMMAND_ITEMS.filter(isCommandFeatureEnabled).reduce<Record<string, NavCommandItem[]>>((acc, item) => {
    if (!acc[item.group]) acc[item.group] = [];
    acc[item.group].push(item);
    return acc;
  }, {});

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        data-testid="global-command-input"
        placeholder={intent === 'ai_action' ? '💡 AI 将处理你的请求...' : '搜索功能、页面，或直接提问 AI... (Ctrl+K)'}
        value={searchQuery}
        onValueChange={setSearchQuery}
      />
      <CommandList>
        <CommandEmpty>
          <div className="py-2 text-center">
            <p className="text-sm text-muted-foreground">
              {intent === 'ai_action' ? '按回车让 AI 处理' : '未找到匹配的功能'}
            </p>
            {searchQuery.trim() && (
              <button
                className="mt-2 inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                onClick={() => handleAIChat(searchQuery)}
              >
                <Sparkles className="w-3.5 h-3.5" />
                {intent === 'ai_action' ? '发送给 AI' : '问问 AI'}: &ldquo;{searchQuery}&rdquo;
              </button>
            )}
          </div>
        </CommandEmpty>

        {/* P2: Page context suggestions */}
        {pageSuggestions.length > 0 && !searchQuery && (
          <>
            <CommandGroup heading="当前页面建议">
              {pageSuggestions.map((s) => (
                <CommandItem
                  key={s.prompt}
                  value={`建议 ${s.label} ${s.prompt}`}
                  onSelect={() => handleAIChat(s.prompt)}
                >
                  <Sparkles className="mr-2 h-4 w-4 text-amber-500" />
                  <span>{s.label}</span>
                  <MessageSquare className="ml-auto h-3.5 w-3.5 text-muted-foreground" />
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}

        {/* AI 智能助手 — promoted when intent is ai_action */}
        {(intent === 'ai_action' && searchQuery.trim()) && (
          <>
            <CommandGroup heading="AI 智能处理">
              <CommandItem
                value={`AI 执行 ${searchQuery}`}
                onSelect={() => handleAIChat(searchQuery)}
              >
                <Sparkles className="mr-2 h-4 w-4 text-primary" />
                <span>让 AI 处理: &ldquo;{searchQuery}&rdquo;</span>
              </CommandItem>
            </CommandGroup>
            <CommandSeparator />
          </>
        )}

        {/* AI 智能助手 */}
        <CommandGroup heading="AI 智能助手">
          <CommandItem
            value="新建对话 new chat 清空"
            onSelect={handleNewChat}
          >
            <PlusCircle className="mr-2 h-4 w-4" />
            <span>新建对话</span>
            <CommandShortcut>/new</CommandShortcut>
          </CommandItem>
          {AI_QUICK_ACTIONS.map((action) => (
            <CommandItem
              key={action.prompt}
              value={`AI ${action.label} ${action.prompt}`}
              onSelect={() => handleAIChat(action.prompt)}
            >
              <action.icon className="mr-2 h-4 w-4" />
              <span>{action.label}</span>
              <MessageSquare className="ml-auto h-3.5 w-3.5 text-muted-foreground" />
            </CommandItem>
          ))}
          {searchQuery.trim() && (
            <CommandItem
              value={`AI 提问 ${searchQuery}`}
              onSelect={() => handleAIChat(searchQuery)}
            >
              <Sparkles className="mr-2 h-4 w-4" />
              <span>问 AI: &ldquo;{searchQuery}&rdquo;</span>
            </CommandItem>
          )}
        </CommandGroup>

        <CommandSeparator />

        {/* Executable business actions */}
        <CommandGroup heading="常用动作">
          {EXECUTION_COMMANDS.map((action) => (
            <CommandItem
              key={action.label}
              value={`动作 ${action.label} ${action.prompt}`}
              onSelect={() => handleAIChat(action.prompt)}
            >
              <action.icon className="mr-2 h-4 w-4" />
              <span>{action.label}</span>
              <CommandShortcut>{action.path}</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>

        {pageContext && (
          <>
            <CommandSeparator />
            <CommandGroup heading="AI 当前上下文">
              <CommandItem value={`当前上下文 ${pageContext.type} ${pageContext.name ?? ''}`} disabled>
                <Sparkles className="mr-2 h-4 w-4 text-primary" />
                <span>
                  {pageContext.type}
                  {pageContext.name ? ` / ${pageContext.name}` : ''}
                  {pageContext.id ? ` / ${pageContext.id.slice(0, 8)}` : ''}
                </span>
              </CommandItem>
            </CommandGroup>
          </>
        )}

        <CommandSeparator />

        {/* 业务数据搜索结果 */}
        {(isSearching || customerResults.length > 0) && (
          <>
            <CommandGroup heading="搜索结果">
              {isSearching && (
                <CommandItem value="__searching__" disabled>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  <span className="text-muted-foreground">正在搜索...</span>
                </CommandItem>
              )}
              {customerResults.map((customer) => (
                <CommandItem
                  key={`customer-${customer.id}`}
                  value={`客户 ${customer.name} ${customer.company || ''}`}
                  onSelect={() => handleSelect('/crm')}
                >
                  <Users className="mr-2 h-4 w-4" />
                  <span>{customer.name}</span>
                  {customer.company && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      {customer.company}
                    </span>
                  )}
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}

        {/* 页面导航 */}
        {Object.entries(groups).map(([group, items], idx) => (
          <React.Fragment key={group}>
            {idx > 0 && <CommandSeparator />}
            <CommandGroup heading={group}>
              {items.map((item) => (
                <CommandItem
                  key={item.path}
                  value={COMMAND_ITEM_VALUES.get(item.path) || item.label}
                  onSelect={() => handleSelect(item.path)}
                >
                  <item.icon className="mr-2 h-4 w-4" />
                  <span>{item.label}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </React.Fragment>
        ))}

        <CommandSeparator />

        {/* 通用操作 */}
        <CommandGroup heading="通用">
          <CommandItem
            value="切换主题 theme dark light 深色 浅色"
            onSelect={handleThemeToggle}
          >
            <SunMoon className="mr-2 h-4 w-4" />
            <span>切换主题</span>
            <CommandShortcut>Ctrl+J</CommandShortcut>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
