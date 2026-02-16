import { useState } from 'react';
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
  type LucideIcon,
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { usePendingApprovalsCount } from '@/hooks/useApprovals';
import { cn } from '@/lib/utils';

// ── 类型定义 ──────────────────────────────────────────────

type Role = 'boss' | 'manager' | 'employee' | 'ai_assistant';

interface WorkbenchItem {
  label: string;
  path: string;
  icon: LucideIcon;
  badge?: number | null;
  /** 可见的角色列表，不指定则所有角色可见 */
  visibleTo?: Role[];
}

interface WorkbenchGroup {
  title: string;
  items: WorkbenchItem[];
}

// ── 组件 ──────────────────────────────────────────────────

export default function MobileWorkbenchPage() {
  const { role } = useAuth();
  const navigate = useNavigate();
  const { data: pendingCount } = usePendingApprovalsCount();
  const [searchFocused, setSearchFocused] = useState(false);

  const currentRole: Role = (role as Role) ?? 'employee';

  // ── 功能分组定义 ────────────────────────────────────────

  const groups: WorkbenchGroup[] = [
    {
      title: '待处理',
      items: [
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
          badge: 3,
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
        { label: '目标看板', path: '/target-dashboard', icon: Target },
        {
          label: '合同管理',
          path: '/contracts',
          icon: FileSignature,
          visibleTo: ['boss', 'manager'],
        },
        { label: '数据报表', path: '/reports', icon: BarChart3 },
      ],
    },
    {
      title: '办公协同',
      items: [
        { label: 'OA 办公', path: '/oa', icon: Calendar },
        {
          label: '人事中心',
          path: '/hr',
          icon: Clock,
          visibleTo: ['boss', 'manager'],
        },
        { label: '财务中心', path: '/finance', icon: DollarSign },
      ],
    },
  ];

  // ── 角色过滤 ────────────────────────────────────────────

  function isVisible(item: WorkbenchItem): boolean {
    if (!item.visibleTo) return true;
    return item.visibleTo.includes(currentRole);
  }

  // ── 渲染 ────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-5 px-4 pb-24 pt-4">
      {/* 搜索栏 */}
      <div
        role="button"
        tabIndex={0}
        className={cn(
          'flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2.5 transition-colors',
          searchFocused && 'border-primary/50 ring-2 ring-primary/20',
        )}
        onClick={() => setSearchFocused((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') setSearchFocused((v) => !v);
        }}
      >
        <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">搜索功能、客户、审批…</span>
      </div>

      {/* 功能分组 */}
      {groups.map((group) => {
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
                    onClick={() => navigate(item.path)}
                  >
                    {/* Badge */}
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

                    {/* Icon */}
                    <Icon className="h-6 w-6 text-foreground/80" />

                    {/* Label */}
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
    </div>
  );
}
