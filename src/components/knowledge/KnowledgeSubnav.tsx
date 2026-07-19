import { BookOpen, Library, Network } from 'lucide-react';
import { NavLink } from 'react-router-dom';

import { cn } from '@/lib/utils';

const KNOWLEDGE_VIEWS = [
  { to: '/knowledge', label: '企业资料', icon: Library, end: true },
  { to: '/knowledge/industry', label: '行业资产', icon: BookOpen, end: false },
  { to: '/knowledge/graph', label: '关系洞察', icon: Network, end: false },
] as const;

export function KnowledgeSubnav() {
  return (
    <nav aria-label="知识资产视图" className="flex items-center gap-1 border-b px-6">
      {KNOWLEDGE_VIEWS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            cn(
              'relative flex h-11 items-center gap-2 px-3 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground',
              isActive && 'text-foreground after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-primary',
            )
          }
        >
          <Icon className="h-4 w-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
