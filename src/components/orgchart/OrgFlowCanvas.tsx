import { useCallback, useMemo, useState, useRef } from 'react';
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
  type NodeDragHandler,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { DepartmentNode, type DepartmentNodeData } from './DepartmentNode';
import { MemberNode } from './MemberNode';
import { OrgFlowToolbar } from './OrgFlowToolbar';
import { AddDepartmentDialog } from './AddDepartmentDialog';
import { TransferConfirmDialog } from './TransferConfirmDialog';
import {
  useOrgMembers,
  useDepartments,
  useTransferEmployee,
  useUpdateDepartmentParent,
  type OrgDepartment,
  type OrgMember,
} from '@/hooks/useOrgChart';
import { Loader2 } from 'lucide-react';

// 安全提取字符串值（防止字段是对象时 React #301 崩溃）
function safeStr(v: unknown): string {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'object' && v !== null) return (v as Record<string, unknown>).name as string || '';
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

  // Attach member nodes under departments
  const membersByDept = new Map<string, OrgMember[]>();
  for (const m of members) {
    if (!m.department) continue;
    const deptName = safeStr(m.department);
    const dept = departments.find((d) => d.name === deptName);
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
    const dept = departments.find((d) => d.name === safeStr(m.department));
    if (dept) memberCountByDept.set(dept.id, (memberCountByDept.get(dept.id) || 0) + 1);
  }

  // Total canvas width
  let totalRootsWidth = 0;
  for (const r of roots) totalRootsWidth += r.width;
  totalRootsWidth += (roots.length - 1) * GAP_X;

  let startX = -totalRootsWidth / 2;

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
        style: node.id.startsWith('member-')
          ? { strokeWidth: 1, strokeDasharray: '4 3', stroke: 'hsl(var(--border))' }
          : { strokeWidth: 2, stroke: 'hsl(var(--border))' },
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
  const [transfer, setTransfer] = useState<{
    nodeId: string;
    name: string;
    targetDeptId: string;
    targetDeptName: string;
  } | null>(null);

  // Track original positions for snap-back
  const origPositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());

  const handleAddMember = useCallback((deptId: string) => {
    // Navigate to employee management with dept context
    window.open(`/employees?dept=${deptId}`, '_self');
  }, []);

  // Build flow data
  const { flowNodes, flowEdges } = useMemo(() => {
    if (!departments.length) return { flowNodes: [], flowEdges: [] };
    const roots = buildTree(departments, members);
    const { nodes, edges } = layoutTree(roots, departments, members, handleAddMember);
    // Cache positions
    const posMap = new Map<string, { x: number; y: number }>();
    for (const n of nodes) posMap.set(n.id, { ...n.position });
    origPositionsRef.current = posMap;
    return { flowNodes: nodes, flowEdges: edges };
  }, [departments, members, handleAddMember]);

  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  // Sync when data changes
  useMemo(() => {
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [flowNodes, flowEdges, setNodes, setEdges]);

  // Drag-drop: detect if member node dropped on a department
  const onNodeDragStop: NodeDragHandler = useCallback(
    (_event, draggedNode) => {
      if (!draggedNode.id.startsWith('member-')) {
        // Dept drag: check if dropped on another dept
        if (draggedNode.id.startsWith('dept-')) {
          const deptNodes = nodes.filter((n) => n.id.startsWith('dept-') && n.id !== draggedNode.id);
          const target = deptNodes.find((dn) => isOverlapping(draggedNode, dn));
          if (target) {
            const deptId = draggedNode.id.replace('dept-', '');
            const targetDeptId = target.id.replace('dept-', '');
            const dept = departments.find((d) => d.id === deptId);
            const targetDept = departments.find((d) => d.id === targetDeptId);
            if (dept && targetDept) {
              setTransfer({
                nodeId: draggedNode.id,
                name: `部门「${dept.name}」`,
                targetDeptId,
                targetDeptName: targetDept.name,
              });
              return;
            }
          }
        }
        snapBack(draggedNode.id);
        return;
      }

      const deptNodes = nodes.filter((n) => n.id.startsWith('dept-'));
      const target = deptNodes.find((dn) => isOverlapping(draggedNode, dn));

      if (target) {
        const memberId = draggedNode.id.replace('member-', '');
        const member = members.find((m) => m.id === memberId);
        const targetDeptId = target.id.replace('dept-', '');
        const targetDept = departments.find((d) => d.id === targetDeptId);

        // Check if already in this dept
        const currentDept = departments.find((d) => d.name === safeStr(member?.department));
        if (currentDept?.id === targetDeptId) {
          snapBack(draggedNode.id);
          return;
        }

        if (member && targetDept) {
          setTransfer({
            nodeId: draggedNode.id,
            name: member.full_name,
            targetDeptId,
            targetDeptName: targetDept.name,
          });
          return;
        }
      }

      snapBack(draggedNode.id);
    },
    [nodes, members, departments],
  );

  function snapBack(nodeId: string) {
    const orig = origPositionsRef.current.get(nodeId);
    if (orig) {
      setNodes((nds) => nds.map((n) => (n.id === nodeId ? { ...n, position: { ...orig } } : n)));
    }
  }

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
  }, [transfer]);

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
    <div className="h-[calc(100vh-14rem)] w-full rounded-xl border border-border bg-card overflow-hidden">
      <OrgFlowToolbar onAddDepartment={() => setShowAddDept(true)} />

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={onNodeDragStop}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        minZoom={0.2}
        maxZoom={2}
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

      <AddDepartmentDialog
        open={showAddDept}
        onOpenChange={setShowAddDept}
        departments={departments}
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
