import React from 'react';
import {
  Plane, ShoppingCart, Receipt, Calendar, FileSignature,
  Clock, Briefcase, FileCheck,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { ApprovalTypeConfig } from '@/hooks/useApprovalTypeConfig';
import { cn } from '@/lib/utils';

// 图标名 → 组件映射表（避免 import * 影响 tree-shaking）
const ICON_MAP: Record<string, LucideIcon> = {
  Plane,
  ShoppingCart,
  Receipt,
  Calendar,
  FileSignature,
  Clock,
  Briefcase,
  FileCheck,
};

function DynamicIcon({ name, className }: { name: string; className?: string }) {
  const Icon = ICON_MAP[name] || FileCheck;
  return <Icon className={className} />;
}

const CATEGORY_COLORS: Record<string, string> = {
  finance: 'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800',
  oa: 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-800',
  general: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800',
};

interface ApprovalTypeGridProps {
  types: ApprovalTypeConfig[];
  selectedType: string | null;
  onSelect: (typeCode: string) => void;
}

export function ApprovalTypeGrid({ types, selectedType, onSelect }: ApprovalTypeGridProps) {
  if (!types || types.length === 0) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-3">
      {types.map((t) => {
        const isSelected = selectedType === t.type_code;
        const colorClass = CATEGORY_COLORS[t.category] || CATEGORY_COLORS.general;

        return (
          <button
            key={t.type_code}
            onClick={() => onSelect(t.type_code)}
            className={cn(
              'flex flex-col items-center gap-2 p-4 rounded-xl border transition-all duration-200',
              'hover:shadow-md hover:scale-[1.02] cursor-pointer',
              isSelected
                ? 'ring-2 ring-primary border-primary bg-primary/5'
                : colorClass,
            )}
          >
            <DynamicIcon name={t.icon} className="w-6 h-6" />
            <span className="text-sm font-medium">{t.type_name}</span>
          </button>
        );
      })}
    </div>
  );
}
