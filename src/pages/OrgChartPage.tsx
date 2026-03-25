/**
 * OrgChartPage - 组织架构管理页面
 * Tab 1: 可视化架构图（ReactFlow 树形图 + 拖拽编辑）
 * Tab 2: 部门管理（层级化树形列表 + CRUD）
 * Tab 3: 成员列表（原表格）
 */

import React, { useState, useMemo, lazy, Suspense } from 'react';
import {
  Users,
  Edit2,
  Loader2,
  Search,
  UserCheck,
  X,
  Building2,
  Network,
  List,
  Plus,
  Trash2,
  ChevronRight,
  FolderTree,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
import { useOrgMembers, useUpdateManager, useDepartments, useDeleteDepartment, type OrgMember, type OrgDepartment } from '@/hooks/useOrgChart';
import { ReactFlowProvider } from '@xyflow/react';
import { OrgFlowCanvas } from '@/components/orgchart/OrgFlowCanvas';
import { EditDepartmentDialog } from '@/components/orgchart/EditDepartmentDialog';
import { AddDepartmentDialog } from '@/components/orgchart/AddDepartmentDialog';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';

// ─── Role Display ───────────────────────────────────────────

const ROLE_LABELS: Record<string, string> = {
  boss: '管理员',
  founder: '创始人',
  manager: '经理',
  admin: '系统管理员',
  employee: '员工',
};

function getRoleLabel(role: unknown) {
  const r = safeStr(role);
  return ROLE_LABELS[r] || r;
}

// 安全提取字符串值（全局复用，防止字段是对象时崩溃）
function safeStr(v: unknown): string {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (typeof v === 'object') {
    const name = (v as Record<string, unknown>).name;
    if (typeof name === 'string') return name;
    return JSON.stringify(v);
  }
  return String(v);
}

function getRoleBadgeColor(role: unknown) {
  const r = safeStr(role);
  switch (r) {
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
           设置 <span className="font-medium text-foreground">{safeStr(member.full_name)}</span> 的直属上级
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="p-3 rounded-lg bg-secondary/30 border border-border/50">
            <div className="text-sm">
              <span className="text-muted-foreground">员工：</span>
              <span className="font-medium">{safeStr(member.full_name)}</span>
            </div>
            <div className="text-sm mt-1">
              <span className="text-muted-foreground">部门：</span>
              <span>{safeStr(member.department) || '未分配'}</span>
            </div>
            <div className="text-sm mt-1">
              <span className="text-muted-foreground">当前上级：</span>
              <span>{safeStr(member.manager_name) || '无'}</span>
            </div>
          </div>
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
                      <span>{safeStr(m.full_name)}</span>
                      {m.department && (
                        <span className="text-xs text-muted-foreground">({safeStr(m.department)})</span>
                      )}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
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

// ─── List View (original table) ──────────────────────────────

function OrgListView() {
  const { data: members = [], isLoading } = useOrgMembers();
  const updateManager = useUpdateManager();
  const [search, setSearch] = useState('');
  const [editingMember, setEditingMember] = useState<OrgMember | null>(null);

  const filteredMembers = useMemo(() => {
    if (!search.trim()) return members;
    const lower = search.toLowerCase();
    return members.filter(
      (m) =>
        safeStr(m.full_name).toLowerCase().includes(lower) ||
        safeStr(m.department).toLowerCase().includes(lower) ||
        safeStr(m.manager_name).toLowerCase().includes(lower)
    );
  }, [members, search]);

  const handleSave = async (userId: string, managerId: string | null) => {
    await updateManager.mutateAsync({ userId, managerId });
    setEditingMember(null);
  };

  return (
    <>
      {/* Search */}
      <div className="relative max-w-md mb-4">
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
                        {safeStr(member.full_name).charAt(0)}
                      </div>
                      <span className="font-medium text-foreground">{safeStr(member.full_name)}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className="text-muted-foreground">{safeStr(member.department) || '未分配'}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={cn('text-xs', getRoleBadgeColor(member.role))}>
                      {getRoleLabel(member.role)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {member.manager_name ? (
                      <span className="text-foreground">{safeStr(member.manager_name)}</span>
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
    </>
  );
}

// ─── Department Tree Helpers ──────────────────────────────────

interface FlatDept extends OrgDepartment {
  depth: number;
}

function flattenDeptTree(departments: OrgDepartment[]): FlatDept[] {
  const byParent = new Map<string | null, OrgDepartment[]>();
  for (const d of departments) {
    const key = d.parent_id || null;
    const list = byParent.get(key) || [];
    list.push(d);
    byParent.set(key, list);
  }
  const result: FlatDept[] = [];
  function walk(parentId: string | null, depth: number) {
    const children = (byParent.get(parentId) || []).sort((a, b) => a.sort_order - b.sort_order);
    for (const c of children) {
      result.push({ ...c, depth });
      walk(c.id, depth + 1);
    }
  }
  walk(null, 0);
  return result;
}

// ─── Department Management View ──────────────────────────────

function OrgDeptManageView() {
  const { data: departments = [], isLoading: deptsLoading } = useDepartments();
  const { data: members = [] } = useOrgMembers();
  const deleteDept = useDeleteDepartment();
  const { confirm, ConfirmDialogProps } = useConfirmDialog();
  const [search, setSearch] = useState('');
  const [editDeptId, setEditDeptId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  const flatDepts = useMemo(() => flattenDeptTree(departments), [departments]);

  const filtered = useMemo(() => {
    if (!search.trim()) return flatDepts;
    const lower = search.toLowerCase();
    return flatDepts.filter(d => safeStr(d.name).toLowerCase().includes(lower));
  }, [flatDepts, search]);

  // Count members per department (by name match)
  const memberCountMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const m of members) {
      const deptName = safeStr(m.department);
      if (deptName) {
        const dept = departments.find(d => safeStr(d.name) === deptName);
        if (dept) map.set(dept.id, (map.get(dept.id) || 0) + 1);
      }
    }
    return map;
  }, [members, departments]);

  const handleDelete = async (dept: FlatDept) => {
    const ok = await confirm({
      title: '确认删除部门',
      description: `确定要删除「${safeStr(dept.name)}」吗？该操作将解散此部门。`,
      variant: 'destructive',
    });
    if (ok) {
      await deleteDept.mutateAsync(dept.id);
    }
  };

  return (
    <>
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 mb-4">
        <div className="relative max-w-md flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="搜索部门名称..."
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
        <Button onClick={() => setAddOpen(true)} size="sm">
          <Plus className="w-4 h-4 mr-1.5" />
          新建部门
        </Button>
      </div>

      <div className="bg-card rounded-2xl border border-border shadow-sm overflow-hidden">
        {deptsLoading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <Loader2 className="w-10 h-10 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">正在加载部门数据...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <FolderTree className="w-16 h-16 mb-4 opacity-20" />
            <h3 className="text-lg font-medium text-foreground">
              {search ? '未找到匹配的部门' : '暂无部门数据'}
            </h3>
            <p className="text-sm mt-1">
              {search ? '请尝试其他搜索关键词' : '可以在架构图中使用模板快速创建组织结构'}
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[320px]">部门名称</TableHead>
                <TableHead>负责人</TableHead>
                <TableHead className="w-[100px] text-center">成员数</TableHead>
                <TableHead className="w-[100px] text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((dept) => {
                const manager = members.find(m => m.id === dept.manager_id);
                const count = memberCountMap.get(dept.id) || 0;
                return (
                  <TableRow key={dept.id}>
                    <TableCell>
                      <div className="flex items-center gap-2" style={{ paddingLeft: dept.depth * 24 }}>
                        {dept.depth > 0 && (
                          <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/50 shrink-0" />
                        )}
                        <Building2 className="w-4 h-4 text-primary shrink-0" />
                        <span className="font-medium text-foreground">{safeStr(dept.name)}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      {manager ? (
                        <span className="text-foreground">{safeStr(manager.full_name)}</span>
                      ) : (
                        <span className="text-muted-foreground/50">未指定</span>
                      )}
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline" className="text-xs">
                        {count}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => setEditDeptId(dept.id)}
                        >
                          <Edit2 className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:text-destructive"
                          onClick={() => handleDelete(dept)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>

      {/* Dialogs */}
      <EditDepartmentDialog
        deptId={editDeptId}
        onOpenChange={(open) => !open && setEditDeptId(null)}
        departments={departments}
      />
      <AddDepartmentDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        departments={departments}
      />
      <ConfirmDialog {...ConfirmDialogProps} />
    </>
  );
}

// ─── Main Page ──────────────────────────────────────────────

export function OrgChartPage() {
  const { data: members = [] } = useOrgMembers();

  // 版本标记：确认最新代码已加载 (v5 - 2026-03-25)
  React.useEffect(() => {
    console.log('[OrgChartPage] v5 loaded, members:', members.length);
  }, [members.length]);

  return (
    <div className="max-w-[1400px] mx-auto space-y-6 pb-20 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-3xl font-extrabold text-foreground tracking-tight flex items-center gap-3">
            <Building2 className="w-8 h-8 text-primary" />
            组织架构管理
          </h1>
          <p className="text-muted-foreground mt-2">
            可视化管理组织结构，拖拽调整部门层级和人员归属
          </p>
        </div>
        <Badge variant="outline" className="text-sm px-3 py-1">
          <Users className="w-4 h-4 mr-1.5" />
          共 {members.length} 人
        </Badge>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="chart" className="w-full">
        <TabsList>
          <TabsTrigger value="chart" className="gap-1.5">
            <Network className="w-4 h-4" />
            架构图
          </TabsTrigger>
          <TabsTrigger value="departments" className="gap-1.5">
            <FolderTree className="w-4 h-4" />
            部门管理
          </TabsTrigger>
          <TabsTrigger value="list" className="gap-1.5">
            <List className="w-4 h-4" />
            成员列表
          </TabsTrigger>
        </TabsList>

        <TabsContent value="chart" className="mt-4">
          <ReactFlowProvider>
            <OrgFlowCanvas />
          </ReactFlowProvider>
        </TabsContent>

        <TabsContent value="departments" className="mt-4">
          <OrgDeptManageView />
        </TabsContent>

        <TabsContent value="list" className="mt-4">
          <OrgListView />
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default OrgChartPage;
