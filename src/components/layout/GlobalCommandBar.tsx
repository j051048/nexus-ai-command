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
  LayoutDashboard,
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
} from 'lucide-react';
import { aiClient } from '@/api/aiClient';

interface NavCommandItem {
  label: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  keywords?: string[];
  group: string;
}

interface CustomerResult {
  id: string;
  name: string;
  company?: string;
}

// Custom event for Command Bar → Chat Panel bridge
export const COMMAND_BAR_CHAT_EVENT = 'nexus:command-bar-chat';

export function dispatchAIChatMessage(message: string) {
  window.dispatchEvent(new CustomEvent(COMMAND_BAR_CHAT_EVENT, { detail: { message } }));
}

const COMMAND_ITEMS: NavCommandItem[] = [
  // 核心功能
  { label: '仪表板', path: '/dashboard', icon: LayoutDashboard, keywords: ['首页', 'home', 'dashboard'], group: '核心功能' },
  { label: '领导驾驶舱', path: '/boss-dashboard', icon: Crown, keywords: ['boss', '管理', '概览'], group: '核心功能' },
  { label: '审批中心', path: '/approval', icon: FileCheck, keywords: ['审批', 'approval', '请假', '报销'], group: '核心功能' },
  { label: '销售管理', path: '/sales', icon: TrendingUp, keywords: ['销售', 'sales', '商机', '客户'], group: '核心功能' },
  { label: '项目管理', path: '/projects', icon: Target, keywords: ['项目', 'project', '任务'], group: '核心功能' },

  // 办公协同
  { label: 'OA 办公', path: '/oa', icon: Calendar, keywords: ['办公', '请假', '会议', 'oa'], group: '办公协同' },
  { label: '人事中心', path: '/hr', icon: Users, keywords: ['人事', 'hr', '考勤', '绩效'], group: '办公协同' },
  { label: '财务中心', path: '/finance', icon: DollarSign, keywords: ['财务', 'finance', '报销', '发票'], group: '办公协同' },
  { label: 'CRM 客户管理', path: '/crm', icon: Users, keywords: ['crm', '客户', '线索'], group: '办公协同' },
  { label: '合同管理', path: '/contracts', icon: FileText, keywords: ['合同', 'contract'], group: '办公协同' },

  // 招投标
  { label: '标书分析', path: '/tender-analysis', icon: FileSearch, keywords: ['标书', 'tender', '招标', '投标'], group: '招投标' },
  { label: '竞标作战卡', path: '/battlecards', icon: Swords, keywords: ['竞标', 'battlecard', '竞品'], group: '招投标' },

  // 知识与文档
  { label: '知识库', path: '/knowledge', icon: BookOpen, keywords: ['知识', 'knowledge', '文档', 'rag'], group: '知识与文档' },
  { label: '数据导入', path: '/import', icon: Upload, keywords: ['导入', 'import', 'csv', 'excel'], group: '知识与文档' },

  // 流程与表单
  { label: '工作流列表', path: '/workflows', icon: Workflow, keywords: ['工作流', 'workflow', '流程'], group: '流程与表单' },
  { label: '新建工作流', path: '/workflows/new', icon: Workflow, keywords: ['新建流程', '创建工作流'], group: '流程与表单' },
  { label: '表单设计器', path: '/form-designer', icon: FileText, keywords: ['表单', 'form', '设计'], group: '流程与表单' },
  { label: '流程模板市场', path: '/workflow-templates', icon: Workflow, keywords: ['模板', 'template'], group: '流程与表单' },

  // 数据与报表
  { label: '自定义仪表板', path: '/custom-dashboard', icon: BarChart3, keywords: ['自定义', 'custom', '图表'], group: '数据与报表' },
  { label: '报表中心', path: '/reports', icon: BarChart3, keywords: ['报表', 'report', '统计'], group: '数据与报表' },
  { label: '目标看板', path: '/target-dashboard', icon: Target, keywords: ['目标', 'target', 'kpi'], group: '数据与报表' },

  // 管理
  { label: '员工管理', path: '/employees', icon: UserCog, keywords: ['员工', 'employee', '人员'], group: '系统管理' },
  { label: '角色管理', path: '/roles', icon: Shield, keywords: ['角色', 'role', '权限'], group: '系统管理' },
  { label: '部门管理', path: '/departments', icon: Building2, keywords: ['部门', 'department'], group: '系统管理' },
  { label: '审计日志', path: '/audit', icon: Shield, keywords: ['审计', 'audit', '日志', '安全'], group: '系统管理' },
  { label: 'AI 设置', path: '/settings', icon: Settings, keywords: ['设置', 'settings', 'ai', '配置'], group: '系统管理' },
  { label: 'API 密钥', path: '/api-keys', icon: Key, keywords: ['api', 'key', '密钥'], group: '系统管理' },

  // 其他
  { label: '消息中心', path: '/notification-center', icon: Bell, keywords: ['消息', 'notification', '通知'], group: '其他' },
  { label: '激励钱包', path: '/rewards', icon: Gift, keywords: ['激励', 'reward', '积分', '奖励'], group: '其他' },
  { label: '异常看板', path: '/exceptions', icon: Clock, keywords: ['异常', 'exception', '预警'], group: '其他' },
  { label: '个人中心', path: '/profile', icon: Users, keywords: ['个人', 'profile', '我的'], group: '其他' },
  { label: '支付管理', path: '/payments', icon: CreditCard, keywords: ['支付', 'payment', '订阅'], group: '其他' },
  { label: '培训中心', path: '/training', icon: GraduationCap, keywords: ['培训', 'training', '学习'], group: '其他' },
  { label: '插件市场', path: '/plugins', icon: Plug, keywords: ['插件', 'plugin', '扩展'], group: '其他' },
];

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
  { label: '生成今日日报', prompt: '帮我生成今天的工作日报', icon: FileText },
  { label: '查看待审批事项', prompt: '有哪些待审批的事项？', icon: FileCheck },
  { label: '本周业绩总结', prompt: '帮我总结本周的业绩情况', icon: BarChart3 },
];

export function GlobalCommandBar() {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [customerResults, setCustomerResults] = useState<CustomerResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
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
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
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

  const handleThemeToggle = useCallback(() => {
    setOpen(false);
    document.documentElement.classList.toggle('dark');
  }, []);

  // Group items
  const groups = COMMAND_ITEMS.reduce<Record<string, NavCommandItem[]>>((acc, item) => {
    if (!acc[item.group]) acc[item.group] = [];
    acc[item.group].push(item);
    return acc;
  }, {});

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
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
                  value={`${item.label} ${item.keywords?.join(' ') || ''}`}
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
