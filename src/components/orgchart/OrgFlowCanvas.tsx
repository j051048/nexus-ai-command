import { useCallback, useMemo, useEffect, useState, useRef } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  BackgroundVariant,
  type Node,
  type Edge,
  type NodeTypes,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { DepartmentNode, type DepartmentNodeData } from './DepartmentNode';
import { MemberNode } from './MemberNode';
import { OrgFlowToolbar } from './OrgFlowToolbar';
import { AddDepartmentDialog } from './AddDepartmentDialog';
import { TransferConfirmDialog } from './TransferConfirmDialog';
import { EditDepartmentDialog } from './EditDepartmentDialog';
import { OrgTemplatesDialog } from './OrgTemplatesDialog';
import {
  useOrgMembers,
  useDepartments,
  useTransferEmployee,
  useUpdateDepartmentParent,
  useUpdateDepartment,
  type OrgDepartment,
  type OrgMember,
} from '@/hooks/useOrgChart';
import { addEdge, type Connection, type OnConnect } from '@xyflow/react';
import { Loader2 } from 'lucide-react';

// 内联错误边界，用于精确定位 ReactFlow 内部的 #301 错误
import React from 'react';
class FlowErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null; errorInfo: React.ErrorInfo | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[FlowErrorBoundary] ReactFlow render error:', error.message);
    console.error('[FlowErrorBoundary] Component stack:', errorInfo.componentStack);
    this.setState({ errorInfo });
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4 border border-destructive/20 bg-destructive/5 rounded-lg text-sm">
          <p className="font-medium text-destructive">ReactFlow 渲染异常</p>
          <p className="text-xs text-muted-foreground mt-1 break-all">{this.state.error?.message}</p>
          {this.state.errorInfo?.componentStack && (
            <pre className="mt-2 text-[10px] text-muted-foreground bg-muted/50 rounded p-2 overflow-auto max-h-60 whitespace-pre-wrap break-all">
              {this.state.errorInfo.componentStack}
            </pre>
          )}
          <button
            onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
            className="mt-2 rounded bg-primary px-3 py-1 text-xs text-primary-foreground"
          >
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// 安全提取字符串值（防止字段是对象时 React #301 崩溃）
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

// ─── Node Types ──────────────────────────────────────────────

const nodeTypes: NodeTypes = {
  department: DepartmentNode,
  member: MemberNode,
};

// ─── Tree Layout Algorithm ───────────────────────────────────

const NODE_W = 200;
const NODE_H_DEPT = 90;
const NODE_H_MEMBER = 56;
const GAP_X = 32;
const GAP_Y = 80;

interface TreeNode {
  id: string;
  children: TreeNode[];
  width: number; // computed subtree width
  nodeHeight: number;
}

function buildTree(departments: OrgDepartment[], members: OrgMember[]): TreeNode[] {
  // Build department tree
  const deptMap = new Map<string, TreeNode>();
  const roots: TreeNode[] = [];

  for (const d of departments) {
    deptMap.set(d.id, { id: `dept-${d.id}`, children: [], width: 0, nodeHeight: NODE_H_DEPT });
  }

  // Attach member nodes under departments (EXCLUDE managers to avoid duplicates)
  const membersByDept = new Map<string, OrgMember[]>();
  for (const m of members) {
    if (!m.department) continue;
    const deptName = safeStr(m.department).trim();
    const dept = departments.find((d) => safeStr(d.name).trim() === deptName);
    
    // Check if this member is the manager of this department
    if (dept && dept.manager_id === m.id) {
      continue; // Skip, they are already shown in the Department box
    }

    if (dept) {
      const list = membersByDept.get(dept.id) || [];
      list.push(m);
      membersByDept.set(dept.id, list);
    }
  }

  for (const d of departments) {
    const node = deptMap.get(d.id)!;
    // Add member children
    const deptMembers = membersByDept.get(d.id) || [];
    for (const m of deptMembers) {
      node.children.push({
        id: `member-${m.id}`,
        children: [],
        width: 0,
        nodeHeight: NODE_H_MEMBER,
      });
    }
    // Build parent-child for departments
    if (d.parent_id && deptMap.has(d.parent_id)) {
      deptMap.get(d.parent_id)!.children.unshift(node); // departments first
    } else {
      roots.push(node);
    }
  }

  // Compute subtree widths bottom-up
  function computeWidth(node: TreeNode): number {
    if (node.children.length === 0) {
      node.width = NODE_W;
      return NODE_W;
    }
    let total = 0;
    for (const child of node.children) {
      total += computeWidth(child);
    }
    total += (node.children.length - 1) * GAP_X;
    node.width = Math.max(NODE_W, total);
    return node.width;
  }

  for (const r of roots) computeWidth(r);
  return roots;
}

function layoutTree(
  roots: TreeNode[],
  departments: OrgDepartment[],
  members: OrgMember[],
  onAddMember: (deptId: string) => void,
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Members grouped by dept for counting
  const memberCountByDept = new Map<string, number>();
  for (const m of members) {
    if (!m.department) continue;
    const deptName = safeStr(m.department).trim();
    const dept = departments.find((d) => safeStr(d.name).trim() === deptName);
    if (dept) memberCountByDept.set(dept.id, (memberCountByDept.get(dept.id) || 0) + 1);
  }

  // Total canvas width
  let totalRootsWidth = 0;
  for (const r of roots) totalRootsWidth += r.width;
  totalRootsWidth += (roots.length - 1) * GAP_X;

  let startX = -totalRootsWidth / 2;

  // Add a Virtual Root for the whole Organization if there's no single parent
  if (roots.length > 1 || (roots.length === 1 && roots[0].id.startsWith('dept-'))) {
    const orgId = 'org-root';
    nodes.push({
      id: orgId,
      type: 'department',
      position: { x: -NODE_W / 2, y: -GAP_Y - NODE_H_DEPT },
      data: {
        label: '企业总部',
        deptId: '0',
        memberCount: members.length,
        managerName: members.find(m => m.role === 'boss' || m.role === 'founder')?.full_name || '总管',
        onAddMember,
      } as DepartmentNodeData,
    });
    
    // Connect original roots to this virtual head
    for (const r of roots) {
      edges.push({
        id: `e-org-${r.id}`,
        source: orgId,
        target: r.id,
        type: 'smoothstep',
        style: { strokeWidth: 2.5, stroke: 'hsl(var(--primary))' },
      });
    }
  }

  function place(node: TreeNode, x: number, y: number, parentId?: string) {
    const cx = x + node.width / 2 - NODE_W / 2;

    if (node.id.startsWith('dept-')) {
      const deptId = node.id.replace('dept-', '');
      const dept = departments.find((d) => d.id === deptId);
      const manager = members.find((m) => m.id === dept?.manager_id);
      nodes.push({
        id: node.id,
        type: 'department',
        position: { x: cx, y },
        data: {
          label: safeStr(dept?.name) || '未命名',
          deptId,
          memberCount: memberCountByDept.get(deptId) || 0,
          managerName: safeStr(manager?.full_name),
          onAddMember,
        } satisfies DepartmentNodeData,
      });
    } else {
      const memberId = node.id.replace('member-', '');
      const m = members.find((mem) => mem.id === memberId);
      nodes.push({
        id: node.id,
        type: 'member',
        position: { x: cx, y },
        draggable: true,
        data: {
          memberId,
          name: safeStr(m?.full_name) || '未知',
          role: safeStr(m?.role) || 'employee',
          avatarUrl: m?.avatar_url,
        },
      });
    }

    if (parentId) {
      edges.push({
        id: `e-${parentId}-${node.id}`,
        source: parentId,
        target: node.id,
        type: 'smoothstep',
        animated: false,
        style: node.id.startsWith('member-')
          ? { strokeWidth: 1.5, strokeDasharray: '4 3', stroke: 'hsl(var(--primary) / 0.5)' }
          : { strokeWidth: 2, stroke: 'hsl(var(--primary))' },
      });
    }

    // Place children
    let childX = x + (node.width - childrenWidth(node)) / 2;
    for (const child of node.children) {
      place(child, childX, y + node.nodeHeight + GAP_Y, node.id);
      childX += child.width + GAP_X;
    }
  }

  function childrenWidth(node: TreeNode): number {
    if (node.children.length === 0) return 0;
    let w = 0;
    for (const c of node.children) w += c.width;
    w += (node.children.length - 1) * GAP_X;
    return w;
  }

  for (const root of roots) {
    place(root, startX, 0);
    startX += root.width + GAP_X;
  }

  return { nodes, edges };
}

// ─── Canvas Component ────────────────────────────────────────

export function OrgFlowCanvas() {
  const { data: members = [], isLoading: membersLoading } = useOrgMembers();
  const { data: departments = [], isLoading: deptsLoading } = useDepartments();
  const transferEmployee = useTransferEmployee();
  const updateDeptParent = useUpdateDepartmentParent();

  const [showAddDept, setShowAddDept] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [editDeptId, setEditDeptId] = useState<string | null>(null);

  const handleEditDepartment = useCallback((deptId: string) => {
    setEditDeptId(deptId);
  }, []);

  // Track original positions for snap-back
  const origPositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());

  const [transfer, setTransfer] = useState<{
    nodeId: string;
    name: string;
    targetDeptId: string;
    targetDeptName: string;
  } | null>(null);

  // Manual Wiring mode
  const [autoEdgeMode, setAutoEdgeMode] = useState(false);

  // Build flow data
  const { flowNodes, flowEdges } = useMemo(() => {
    if (!departments.length) return { flowNodes: [], flowEdges: [] };
    const roots = buildTree(departments, members);
    const { nodes, edges } = layoutTree(roots, departments, members, handleEditDepartment);
    
    // In manual mode, we might want to skip auto-edges 
    // BUT! Keeping them initially ensures the user sees the existing DB structure.
    // However, the user said "不应该自动生成", so I'll follow that.
    const finalEdges = autoEdgeMode ? edges : [];
    // Cache positions
    const posMap = new Map<string, { x: number; y: number }>();
    for (const n of nodes) posMap.set(n.id, { ...n.position });
    origPositionsRef.current = posMap;
    return { flowNodes: nodes, flowEdges: edges };
  }, [departments, members, handleEditDepartment, autoEdgeMode]);

  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  // Sync when data changes (useEffect, not useMemo — setState during render causes #301)
  useEffect(() => {
    setNodes(flowNodes);
    setEdges(prev => autoEdgeMode ? flowEdges : prev);
  }, [flowNodes, flowEdges, setNodes, setEdges, autoEdgeMode]);

  const onConnect: OnConnect = useCallback(
    async (params: Connection) => {
      // Create relationship in DB when a line is drawn
      if (params.source?.startsWith('dept-') && params.target?.startsWith('dept-')) {
        const sourceId = params.source.replace('dept-', '');
        const targetId = params.target.replace('dept-', '');
        await updateDeptParent.mutateAsync({ deptId: targetId, parentId: sourceId });
        setEdges((eds) => addEdge({ ...params, type: 'smoothstep', style: { strokeWidth: 2, stroke: 'hsl(var(--primary))' } }, eds));
      } else if (params.source?.startsWith('dept-') && params.target?.startsWith('member-')) {
        // Assign member to dept
        const deptId = params.source.replace('dept-', '');
        const memberId = params.target.replace('member-', '');
        await transferEmployee.mutateAsync({ employeeId: memberId, departmentId: deptId });
        setEdges((eds) => addEdge({ ...params, type: 'smoothstep', animated: true, style: { strokeWidth: 1.5, strokeDasharray: '4 3', stroke: 'hsl(var(--primary) / 0.5)' } }, eds));
      }
    },
    [setEdges, updateDeptParent, transferEmployee]
  );

  const snapBack = useCallback((nodeId: string) => {
    const orig = origPositionsRef.current.get(nodeId);
    if (orig) {
      setNodes((nds) => nds.map((n) => (n.id === nodeId ? { ...n, position: { ...orig } } : n)));
    }
  }, [setNodes]);

  // Drag-drop: detect if member node dropped on a department
  const onNodeDragStop = useCallback(
    (_event: React.MouseEvent | React.TouchEvent, draggedNode: Node) => {
      // Find possible target department
      const deptNodes = nodes.filter((n) => n.id.startsWith('dept-') && n.id !== draggedNode.id);
      const target = deptNodes.find((dn) => isOverlapping(draggedNode, dn));

      if (target) {
        const targetDeptId = target.id.replace('dept-', '');
        const targetDept = departments.find((d) => d.id === targetDeptId);

        if (draggedNode.id.startsWith('member-')) {
          const memberId = draggedNode.id.replace('member-', '');
          const member = members.find((m) => m.id === memberId);
          
          // Check if already in this dept
          const currentDept = departments.find((d) => d.name === safeStr(member?.department).trim());
          if (currentDept?.id === targetDeptId) {
            snapBack(draggedNode.id);
            return;
          }

          if (member && targetDept) {
            setTransfer({
              nodeId: draggedNode.id,
              name: safeStr(member.full_name),
              targetDeptId,
              targetDeptName: safeStr(targetDept.name),
            });
            return;
          }
        } else if (draggedNode.id.startsWith('dept-')) {
          const deptId = draggedNode.id.replace('dept-', '');
          const dept = departments.find((d) => d.id === deptId);
          if (dept && targetDept) {
            setTransfer({
              nodeId: draggedNode.id,
              name: `部门「${safeStr(dept.name)}」`,
              targetDeptId,
              targetDeptName: safeStr(targetDept.name),
            });
            return;
          }
        }
      }
      
      // If not dropping on a department to change relation, just let it stay at the new position
      // Nodes state is updated by React Flow's onNodesChange
    },
    [nodes, members, departments, snapBack],
  );

  function isOverlapping(a: Node, b: Node): boolean {
    const ax = a.position.x;
    const ay = a.position.y;
    const bx = b.position.x;
    const by = b.position.y;
    const bw = 220;
    const bh = 90;
    return ax > bx - 40 && ax < bx + bw + 40 && ay > by - 20 && ay < by + bh + 20;
  }

  const handleTransferConfirm = useCallback(async () => {
    if (!transfer) return;

    if (transfer.nodeId.startsWith('dept-')) {
      const deptId = transfer.nodeId.replace('dept-', '');
      await updateDeptParent.mutateAsync({ deptId, parentId: transfer.targetDeptId });
    } else {
      const memberId = transfer.nodeId.replace('member-', '');
      await transferEmployee.mutateAsync({
        employeeId: memberId,
        departmentId: transfer.targetDeptId,
      });
    }
    setTransfer(null);
  }, [transfer, transferEmployee, updateDeptParent]);

  const handleTransferCancel = useCallback(() => {
    if (transfer) snapBack(transfer.nodeId);
    setTransfer(null);
  }, [transfer, snapBack]);

  const isLoading = membersLoading || deptsLoading;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">正在加载组织架构...</p>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-14rem)] w-full rounded-xl border border-border bg-card overflow-hidden relative">
      <OrgFlowToolbar 
        onAddDepartment={() => setShowAddDept(true)} 
        onShowTemplates={() => setShowTemplates(true)}
      />

      <div className="absolute top-14 left-4 z-10 flex items-center gap-2 bg-background/50 backdrop-blur p-1 rounded-md border border-border">
         <span className="text-[10px] font-medium px-2">自动连线</span>
         <input 
            type="checkbox" 
            checked={autoEdgeMode} 
            onChange={e => setAutoEdgeMode(e.target.checked)}
            className="w-4 h-4 accent-primary"
         />
      </div>

      <FlowErrorBoundary>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeDragStop={onNodeDragStop}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          onNodeClick={(_e, node) => node.type === 'department' && setEditDeptId(node.id.replace('dept-', ''))}
          onlyRenderVisibleElements
          fitView
          fitViewOptions={{ padding: 0.3 }}
          minZoom={0.2}
          maxZoom={4}
          proOptions={{ hideAttribution: true }}
        >
          <Controls className="!bg-card !border-border !shadow-sm" />
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="hsl(var(--border))" />
          <MiniMap
            className="!bg-card !border-border"
            nodeColor={(node) => (node.type === 'department' ? 'hsl(var(--primary))' : 'hsl(var(--muted-foreground))')}
            maskColor="hsl(var(--background) / 0.8)"
          />
        </ReactFlow>
      </FlowErrorBoundary>

      <AddDepartmentDialog
        open={showAddDept}
        onOpenChange={setShowAddDept}
        departments={departments}
      />

      <EditDepartmentDialog
        deptId={editDeptId}
        onOpenChange={(open) => !open && setEditDeptId(null)}
        departments={departments}
      />

      <OrgTemplatesDialog
        open={showTemplates}
        onOpenChange={setShowTemplates}
      />

      <TransferConfirmDialog
        open={!!transfer}
        name={transfer?.name || ''}
        targetDeptName={transfer?.targetDeptName || ''}
        isPending={transferEmployee.isPending || updateDeptParent.isPending}
        onConfirm={handleTransferConfirm}
        onCancel={handleTransferCancel}
      />
    </div>
  );
}
