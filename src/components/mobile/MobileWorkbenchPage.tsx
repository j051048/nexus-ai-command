import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  FileCheck,
  AlertTriangle,
  TrendingUp,
  Contact,
  FileSearch,
  Swords,
  Briefcase,
  Target,
  FileSignature,
  BarChart3,
  Calendar,
  Clock,
  DollarSign,
  Users,
  Building2,
  BookOpen,
  Workflow,
  Import,
  FileEdit,
  LayoutTemplate,
  Megaphone,
  ListTodo,
  Bot,
  ShieldCheck,
  BarChart2,
  Cpu,
  Inbox,
  ClipboardList,
  Package,
  Award,
  Warehouse,
  Fingerprint,
  type LucideIcon,
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { usePendingApprovalsCount } from '@/hooks/useApprovals';
import { useExceptions } from '@/hooks/useExceptions';
import { useUnreadCount } from '@/hooks/useNotificationCenter';
import { cn } from '@/lib/utils';

// ── Types ──
type Role = 'boss' | 'manager' | 'employee' | 'ai_assistant';

interface WorkbenchItem {
  label: string;
  path: string;
  icon: LucideIcon;
  badge?: number | null;
  visibleTo?: Role[];
}

interface WorkbenchGroup {
  title: string;
  items: WorkbenchItem[];
}

// ── Recent usage tracking ──
const RECENT_KEY = 'nexus:mobile-recent-apps';
const MAX_RECENT = 6;

function getRecentApps(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function trackAppUsage(path: string) {
  const recent = getRecentApps().filter((p) => p !== path);
  recent.unshift(path);
  localStorage.setItem(RECENT_KEY, JSON.stringify(recent.slice(0, MAX_RECENT * 2)));
}

// ── Component ──
export default function MobileWorkbenchPage() {
  const { role } = useAuth();
  const navigate = useNavigate();
  const { data: pendingCount } = usePendingApprovalsCount();
  const { data: exceptions = [] } = useExceptions();
  const unreadCountQuery = useUnreadCount();
  const unreadCount = unreadCountQuery.data ?? 0;
  const [searchQuery, setSearchQuery] = useState('');
  const [recentPaths] = useState(getRecentApps);

  const currentRole: Role = (role as Role) ?? 'employee';

  const inboxBadge = (pendingCount ?? 0) + exceptions.length + unreadCount;

  // ── Groups ──
  const groups: WorkbenchGroup[] = [
    {
      title: '待处理',
      items: [
        {
          label: '待办中心',
          path: '/inbox',
          icon: Inbox,
          badge: inboxBadge || null,
        },
        {
          label: '智能审批',
          path: '/approval',
          icon: FileCheck,
          badge: pendingCount ?? null,
        },
        {
          label: '异常待办',
          path: '/exceptions',
          icon: AlertTriangle,
          badge: exceptions.length || null,
          visibleTo: ['boss'],
        },
      ],
    },
    {
      title: '销售工具',
      items: [
        { label: '销售管道', path: '/sales', icon: TrendingUp },
        { label: 'CRM 客户', path: '/crm', icon: Contact },
        { label: '标书审阅', path: '/tender-analysis', icon: FileSearch },
        { label: '竞品库', path: '/battlecards', icon: Swords },
      ],
    },
    {
      title: '管理中心',
      items: [
        { label: '项目管理', path: '/projects', icon: Briefcase },
        { label: '目标管理', path: '/targets', icon: Target },
        { label: '目标看板', path: '/target-dashboard', icon: BarChart3 },
        {
          label: '合同管理',
          path: '/contracts',
          icon: FileSignature,
          visibleTo: ['boss', 'manager'],
        },
        { label: '数据报表', path: '/reports', icon: BarChart3 },
        {
          label: '员工管理',
          path: '/employees',
          icon: Users,
          visibleTo: ['boss', 'manager'],
        },
        {
          label: '部门管理',
          path: '/departments',
          icon: Building2,
          visibleTo: ['boss', 'manager'],
        },
      ],
    },
    {
      title: '办公协同',
      items: [
        { label: 'OA 办公', path: '/oa', icon: Calendar },
        { label: '考勤打卡', path: '/oa?tab=attendance', icon: Fingerprint },
        {
          label: '人事中心',
          path: '/hr',
          icon: Clock,
          visibleTo: ['boss', 'manager'],
        },
        { label: '财务中心', path: '/finance', icon: DollarSign },
        { label: '工单管理', path: '/work-orders', icon: ClipboardList },
        {
          label: '资产管理',
          path: '/assets',
          icon: Package,
          visibleTo: ['boss', 'manager'],
        },
        { label: '知识库', path: '/knowledge', icon: BookOpen },
        {
          label: '企业证照',
          path: '/certificates',
          icon: Award,
          visibleTo: ['boss', 'manager'],
        },
        {
          label: '库存管理',
          path: '/inventory',
          icon: Warehouse,
          visibleTo: ['boss', 'manager'],
        },
        { label: '工作流', path: '/workflows', icon: Workflow },
      ],
    },
    {
      title: '智能营销 (VMD)',
      items: [
        { label: 'VMD 中心', path: '/vmd', icon: Megaphone },
        { label: '任务中心', path: '/vmd/tasks', icon: ListTodo },
        { label: '线索管理', path: '/vmd/clues', icon: Contact },
        { label: '合规校验', path: '/vmd/compliance', icon: ShieldCheck },
        { label: 'VMD 看板', path: '/vmd/dashboard', icon: BarChart2 },
        {
          label: 'Agent 配置',
          path: '/vmd/agents',
          icon: Bot,
          visibleTo: ['boss', 'manager'],
        },
        {
          label: 'LLM 模型',
          path: '/llm/models',
          icon: Cpu,
          visibleTo: ['boss'],
        },
      ],
    },
    {
      title: '更多工具',
      items: [
        {
          label: '数据导入',
          path: '/import',
          icon: Import,
          visibleTo: ['boss', 'manager'],
        },
        { label: '表单设计', path: '/form-designer', icon: FileEdit, visibleTo: ['boss', 'founder'] },
        { label: '流程模板', path: '/workflow-templates', icon: LayoutTemplate, visibleTo: ['boss', 'founder'] },
      ],
    },
  ];

  // ── Flatten all items for search & recent ──
  const allItems = groups.flatMap((g) => g.items);

  // ── Role filter ──
  function isVisible(item: WorkbenchItem): boolean {
    if (!item.visibleTo) return true;
    return item.visibleTo.includes(currentRole);
  }

  // ── Search filter ──
  const filteredGroups = searchQuery.trim()
    ? [
        {
          title: '搜索结果',
          items: allItems.filter(
            (item) =>
              isVisible(item) &&
              item.label.toLowerCase().includes(searchQuery.toLowerCase()),
          ),
        },
      ]
    : groups;

  // ── Recent apps section ──
  const recentItems = recentPaths
    .map((path) => allItems.find((item) => item.path === path))
    .filter((item): item is WorkbenchItem => !!item && isVisible(item))
    .slice(0, MAX_RECENT);

  const handleNavigate = (path: string) => {
    trackAppUsage(path);
    navigate(path);
  };

  // ── Render ──
  return (
    <div className="flex flex-col gap-5 px-4 pb-24 pt-4">
      {/* Search bar - real filtering */}
      <div
        className={cn(
          'flex items-center gap-2 rounded-full bg-muted/50 px-3 py-2.5 transition-colors',
          searchQuery && 'ring-2 ring-primary/20',
        )}
      >
        <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索功能..."
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            清除
          </button>
        )}
      </div>

      {/* Recent apps (only show when not searching) */}
      {!searchQuery && recentItems.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">
            最近使用
          </h3>
          <div className="grid grid-cols-4 gap-3">
            {recentItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={`recent-${item.path}`}
                  type="button"
                  className={cn(
                    'relative flex flex-col items-center justify-center gap-1.5',
                    'rounded-xl border border-primary/20 bg-primary/5 p-3',
                    'transition-all active:scale-95 active:bg-accent',
                  )}
                  onClick={() => handleNavigate(item.path)}
                >
                  <Icon className="h-6 w-6 text-primary/80" />
                  <span className="text-xs leading-tight text-foreground/70">
                    {item.label}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* Feature groups */}
      {filteredGroups.map((group) => {
        const visibleItems = group.items.filter(isVisible);
        if (visibleItems.length === 0) return null;

        return (
          <section key={group.title}>
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">
              {group.title}
            </h3>
            <div className="grid grid-cols-4 gap-3">
              {visibleItems.map((item) => {
                const Icon = item.icon;
                const showBadge =
                  item.badge !== undefined && item.badge !== null && item.badge > 0;

                return (
                  <button
                    key={item.path}
                    type="button"
                    className={cn(
                      'relative flex flex-col items-center justify-center gap-1.5',
                      'rounded-xl border border-border bg-card p-3',
                      'transition-all active:scale-95 active:bg-accent',
                    )}
                    onClick={() => handleNavigate(item.path)}
                  >
                    {showBadge && (
                      <span
                        className={cn(
                          'absolute -right-1 -top-1 flex items-center justify-center',
                          'min-w-[18px] rounded-full bg-destructive px-1 py-0.5',
                          'text-[10px] font-semibold leading-none text-destructive-foreground',
                        )}
                      >
                        {item.badge! > 99 ? '99+' : item.badge}
                      </span>
                    )}
                    <Icon className="h-6 w-6 text-foreground/80" />
                    <span className="text-xs leading-tight text-foreground/70">
                      {item.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </section>
        );
      })}

      {/* Search empty state */}
      {searchQuery && filteredGroups[0]?.items.filter(isVisible).length === 0 && (
        <div className="text-center py-8">
          <p className="text-sm text-muted-foreground">
            未找到"{searchQuery}"相关功能
          </p>
        </div>
      )}
    </div>
  );
}
