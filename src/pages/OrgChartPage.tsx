/**
 * OrgChartPage - 组织架构管理页面
 * 管理员可查看和编辑员工的汇报关系（manager_id）
 */

import React, { useState, useMemo } from 'react';
import {
  Users,
  Edit2,
  Loader2,
  Search,
  UserCheck,
  X,
  Building2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useOrgMembers, useUpdateManager, type OrgMember } from '@/hooks/useOrgChart';

// ─── Role Display ───────────────────────────────────────────

const ROLE_LABELS: Record<string, string> = {
  boss: '管理员',
  founder: '创始人',
  manager: '经理',
  admin: '系统管理员',
  employee: '员工',
};

function getRoleLabel(role: string) {
  return ROLE_LABELS[role] || role;
}

function getRoleBadgeColor(role: string) {
  switch (role) {
    case 'boss':
    case 'founder':
      return 'bg-amber-500/10 text-amber-600 border-amber-500/20';
    case 'manager':
      return 'bg-blue-500/10 text-blue-600 border-blue-500/20';
    case 'admin':
      return 'bg-purple-500/10 text-purple-600 border-purple-500/20';
    default:
      return 'bg-muted text-muted-foreground border-border';
  }
}

// ─── Edit Manager Modal ─────────────────────────────────────

interface EditManagerModalProps {
  member: OrgMember;
  allMembers: OrgMember[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (userId: string, managerId: string | null) => void;
  isSaving: boolean;
}

function EditManagerModal({
  member,
  allMembers,
  open,
  onOpenChange,
  onSave,
  isSaving,
}: EditManagerModalProps) {
  const [selectedManagerId, setSelectedManagerId] = useState<string>(
    member.manager_id || '__none__'
  );

  // Exclude the member themselves from the manager dropdown
  const managerOptions = allMembers.filter((m) => m.id !== member.id);

  const handleSave = () => {
    const managerId = selectedManagerId === '__none__' ? null : selectedManagerId;
    onSave(member.id, managerId);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>编辑汇报关系</DialogTitle>
          <DialogDescription>
            设置 <span className="font-medium text-foreground">{member.full_name}</span> 的直属上级
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          {/* Current info */}
          <div className="p-3 rounded-lg bg-secondary/30 border border-border/50">
            <div className="text-sm">
              <span className="text-muted-foreground">员工：</span>
              <span className="font-medium">{member.full_name}</span>
            </div>
            <div className="text-sm mt-1">
              <span className="text-muted-foreground">部门：</span>
              <span>{member.department || '未分配'}</span>
            </div>
            <div className="text-sm mt-1">
              <span className="text-muted-foreground">当前上级：</span>
              <span>{member.manager_name || '无'}</span>
            </div>
          </div>

          {/* Manager select */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">选择新上级</label>
            <Select
              value={selectedManagerId}
              onValueChange={setSelectedManagerId}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择上级" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">
                  <span className="text-muted-foreground">无上级</span>
                </SelectItem>
                {managerOptions.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    <div className="flex items-center gap-2">
                      <span>{m.full_name}</span>
                      {m.department && (
                        <span className="text-xs text-muted-foreground">({m.department})</span>
                      )}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <UserCheck className="w-4 h-4 mr-2" />
              )}
              保存
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ─── Main Page ──────────────────────────────────────────────

export function OrgChartPage() {
  const { data: members = [], isLoading } = useOrgMembers();
  const updateManager = useUpdateManager();
  const [search, setSearch] = useState('');
  const [editingMember, setEditingMember] = useState<OrgMember | null>(null);

  // Filter members by search
  const filteredMembers = useMemo(() => {
    if (!search.trim()) return members;
    const lower = search.toLowerCase();
    return members.filter(
      (m) =>
        m.full_name.toLowerCase().includes(lower) ||
        (m.department && m.department.toLowerCase().includes(lower)) ||
        (m.manager_name && m.manager_name.toLowerCase().includes(lower))
    );
  }, [members, search]);

  const handleSave = async (userId: string, managerId: string | null) => {
    await updateManager.mutateAsync({ userId, managerId });
    setEditingMember(null);
  };

  return (
    <div className="max-w-[1200px] mx-auto space-y-6 pb-20 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-foreground tracking-tight flex items-center gap-3">
            <Building2 className="w-8 h-8 text-primary" />
            组织架构管理
          </h1>
          <p className="text-muted-foreground mt-2">
            管理员工的汇报关系，维护组织架构层级
          </p>
        </div>
        <Badge variant="outline" className="text-sm px-3 py-1">
          <Users className="w-4 h-4 mr-1.5" />
          共 {members.length} 人
        </Badge>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          placeholder="搜索姓名、部门..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
        />
        {search && (
          <button
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => setSearch('')}
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-card rounded-2xl border border-border shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <Loader2 className="w-10 h-10 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">正在加载组织成员...</p>
          </div>
        ) : filteredMembers.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <Users className="w-16 h-16 mb-4 opacity-20" />
            <h3 className="text-lg font-medium text-foreground">
              {search ? '未找到匹配的成员' : '暂无成员数据'}
            </h3>
            <p className="text-sm mt-1">
              {search ? '请尝试其他搜索关键词' : '组织中还没有任何成员'}
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[200px]">姓名</TableHead>
                <TableHead>部门</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>直属上级</TableHead>
                <TableHead className="w-[80px] text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredMembers.map((member) => (
                <TableRow key={member.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary text-sm font-medium">
                        {member.full_name.charAt(0)}
                      </div>
                      <span className="font-medium text-foreground">{member.full_name}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className="text-muted-foreground">{member.department || '未分配'}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={cn('text-xs', getRoleBadgeColor(member.role))}>
                      {getRoleLabel(member.role)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {member.manager_name ? (
                      <span className="text-foreground">{member.manager_name}</span>
                    ) : (
                      <span className="text-muted-foreground/50">无</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => setEditingMember(member)}
                    >
                      <Edit2 className="w-4 h-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {/* Edit Modal */}
      {editingMember && (
        <EditManagerModal
          member={editingMember}
          allMembers={members}
          open={!!editingMember}
          onOpenChange={(open) => !open && setEditingMember(null)}
          onSave={handleSave}
          isSaving={updateManager.isPending}
        />
      )}
    </div>
  );
}

export default OrgChartPage;
