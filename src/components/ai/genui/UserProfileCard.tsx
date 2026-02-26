import React from 'react';
import { Badge } from '@/components/ui/badge';
import { User } from 'lucide-react';

interface UserProfileCardProps {
  name: string;
  role?: string;
  department?: string;
  avatar?: string;
  stats?: { label: string; value: string | number }[];
  badges?: string[];
}

export default function UserProfileCard({ name, role, department, avatar, stats = [], badges = [] }: UserProfileCardProps) {
  return (
    <div className="p-4 flex gap-4">
      <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center shrink-0 overflow-hidden">
        {avatar ? (
          <img src={avatar} alt={name} className="w-full h-full object-cover" />
        ) : (
          <User className="w-7 h-7 text-primary" />
        )}
      </div>
      <div className="space-y-2 flex-1">
        <div>
          <div className="text-base font-semibold text-foreground">{name}</div>
          <div className="text-xs text-muted-foreground">
            {[role, department].filter(Boolean).join(' · ')}
          </div>
        </div>
        {badges.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {badges.map((b, i) => <Badge key={i} variant="secondary" className="text-xs">{b}</Badge>)}
          </div>
        )}
        {stats.length > 0 && (
          <div className="flex gap-4 pt-1">
            {stats.map((s, i) => (
              <div key={i} className="text-center">
                <div className="text-sm font-bold text-foreground">{s.value}</div>
                <div className="text-xs text-muted-foreground">{s.label}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
