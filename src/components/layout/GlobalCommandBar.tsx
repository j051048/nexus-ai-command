import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
} from 'lucide-react';

interface CommandItem {
  label: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  keywords?: string[];
  group: string;
}

const COMMAND_ITEMS: CommandItem[] = [
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

export function GlobalCommandBar() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

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

  const handleSelect = useCallback(
    (path: string) => {
      setOpen(false);
      navigate(path);
    },
    [navigate],
  );

  // Group items
  const groups = COMMAND_ITEMS.reduce<Record<string, CommandItem[]>>((acc, item) => {
    if (!acc[item.group]) acc[item.group] = [];
    acc[item.group].push(item);
    return acc;
  }, {});

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="搜索功能、页面... (Ctrl+K)" />
      <CommandList>
        <CommandEmpty>未找到匹配的功能</CommandEmpty>
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
                  {item.path === '/dashboard' && (
                    <CommandShortcut>Ctrl+K</CommandShortcut>
                  )}
                </CommandItem>
              ))}
            </CommandGroup>
          </React.Fragment>
        ))}
      </CommandList>
    </CommandDialog>
  );
}
