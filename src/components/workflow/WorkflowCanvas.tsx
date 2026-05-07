import {
  useCallback,
  useRef,
  forwardRef,
  useImperativeHandle,
  useEffect,
  DragEvent,
} from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Edge,
  type Node,
  type NodeTypes,
  BackgroundVariant,
  MarkerType,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { ApproverNode } from './nodes/ApproverNode';
import { ConditionNode } from './nodes/ConditionNode';
import { ParallelNode } from './nodes/ParallelNode';
import { AutoApproveNode } from './nodes/AutoApproveNode';
import { NotifyNode } from './nodes/NotifyNode';
import { CcNotifyNode } from './nodes/CcNotifyNode';
import { TimerNode } from './nodes/TimerNode';
import { SubWorkflowNode } from './nodes/SubWorkflowNode';
import { InitiatorNode } from './nodes/InitiatorNode';
import { EndNode } from './nodes/EndNode';

import type { WorkflowStep, WorkflowCondition, WorkflowDefinition } from '@/hooks/useWorkflows';

// ---- Custom node type mapping ----

const nodeTypes: NodeTypes = {
  initiator: InitiatorNode,
  approver: ApproverNode,
  condition: ConditionNode,
  parallel: ParallelNode,
  auto_approve: AutoApproveNode,
  notify: NotifyNode,
  cc_notify: CcNotifyNode,
  timer: TimerNode,
  sub_workflow: SubWorkflowNode,
  end: EndNode,
};

// Fixed node types that cannot be deleted or created via drag
const FIXED_NODE_TYPES = new Set(['initiator', 'end']);

// Default initial nodes for new workflows
const INITIAL_NODES: Node[] = [
  {
    id: 'initiator',
    type: 'initiator',
    position: { x: 250, y: 30 },
    data: { label: '发起人' },
    deletable: false,
  },
  {
    id: 'end',
    type: 'end',
    position: { x: 250, y: 500 },
    data: { label: '结束' },
    deletable: false,
  },
];

// ---- Default data for new nodes ----

const DEFAULT_NODE_DATA: Record<string, Record<string, unknown>> = {
  approver: {
    label: '审批人',
    role: 'manager',
    timeout_hours: 24,
    can_delegate: false,
  },
  condition: {
    label: '条件分支',
    field: 'amount',
    operator: 'gt',
    value: '5000',
  },
  parallel: {
    label: '并行审批',
    parallel_count: 2,
  },
  auto_approve: {
    label: '自动审批',
    max_amount: 1000,
  },
  notify: {
    label: '发送通知',
    channels: ['email'],
    template: 'default',
  },
  cc_notify: {
    label: '抄送通知',
    recipients: [],
    message: '',
  },
  timer: {
    label: '定时等待',
    wait_hours: 24,
    auto_advance: true,
  },
  sub_workflow: {
    label: '子流程',
    workflow_id: '',
    workflow_name: '',
  },
};

// ---- Public ref interface ----

export interface WorkflowCanvasRef {
  getWorkflowData: () => WorkflowDefinition;
  loadWorkflowData: (definition: WorkflowDefinition) => void;
  updateNodeData: (nodeId: string, data: Record<string, unknown>) => void;
}

interface WorkflowCanvasProps {
  onNodeSelect: (node: Node | null) => void;
  onNodeUpdate: (nodeId: string, data: Record<string, unknown>) => void;
}

// ---- Helpers to convert between ReactFlow and backend formats ----

function stepsToNodes(steps: WorkflowStep[]): Node[] {
  return steps.map((step) => ({
    id: step.id,
    type: step.type,
    position: step.position || { x: 250, y: 100 },
    data: {
      label: step.label,
      ...step.config,
    },
  }));
}

function conditionsToEdges(conditions: WorkflowCondition[]): Edge[] {
  return conditions.map((cond, idx) => ({
    id: `e-${cond.from_step_id}-${cond.to_step_id}-${idx}`,
    source: cond.from_step_id,
    target: cond.to_step_id,
    label: cond.label || '',
    sourceHandle: cond.sourceHandle || undefined,
    targetHandle: cond.targetHandle || undefined,
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
    style: { strokeWidth: 2 },
  }));
}

function nodesToSteps(nodes: Node[]): WorkflowStep[] {
  return nodes.map((node) => {
    const { label, ...config } = node.data as Record<string, unknown>;
    return {
      id: node.id,
      type: node.type as WorkflowStep['type'],
      label: (label as string) || '',
      config,
      position: node.position,
    };
  });
}

function edgesToConditions(edges: Edge[]): WorkflowCondition[] {
  return edges.map((edge) => ({
    from_step_id: edge.source,
    to_step_id: edge.target,
    label: (edge.label as string) || undefined,
    sourceHandle: edge.sourceHandle || undefined,
    targetHandle: edge.targetHandle || undefined,
  }));
}

// ---- Component ----

let nodeIdCounter = 0;
function getNodeId() {
  nodeIdCounter += 1;
  return `node_${Date.now()}_${nodeIdCounter}`;
}

export const WorkflowCanvas = forwardRef<WorkflowCanvasRef, WorkflowCanvasProps>(
  function WorkflowCanvas({ onNodeSelect, onNodeUpdate }, ref) {
    const reactFlowWrapper = useRef<HTMLDivElement>(null);
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>(INITIAL_NODES);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { screenToFlowPosition } = useReactFlow();

    // Expose methods to parent
    useImperativeHandle(ref, () => ({
      getWorkflowData: (): WorkflowDefinition => ({
        steps: nodesToSteps(nodes),
        conditions: edgesToConditions(edges),
      }),
      loadWorkflowData: (definition: WorkflowDefinition) => {
        if (definition?.steps) {
          const loaded = stepsToNodes(definition.steps);
          // Ensure initiator and end nodes exist (backward compat)
          const hasInitiator = loaded.some((n) => n.type === 'initiator');
          const hasEnd = loaded.some((n) => n.type === 'end');
          if (!hasInitiator) loaded.unshift({ ...INITIAL_NODES[0] });
          if (!hasEnd) loaded.push({ ...INITIAL_NODES[1] });
          // Mark fixed nodes as non-deletable
          for (const n of loaded) {
            if (FIXED_NODE_TYPES.has(n.type || '')) n.deletable = false;
          }
          setNodes(loaded);
        }
        if (definition?.conditions) {
          setEdges(conditionsToEdges(definition.conditions));
        }
      },
      updateNodeData: (nodeId: string, data: Record<string, unknown>) => {
        setNodes((nds) =>
          nds.map((node) =>
            node.id === nodeId ? { ...node, data: { ...node.data, ...data } } : node
          )
        );
      },
    }));

    // Handle node update from properties panel
    useEffect(() => {
      // We attach onNodeUpdate to the canvas so it can be called from parent
    }, [onNodeUpdate]);

    // Update node data when triggered by properties panel
    const handleNodeDataUpdate = useCallback(
      (nodeId: string, newData: Record<string, unknown>) => {
        setNodes((nds) =>
          nds.map((node) =>
            node.id === nodeId ? { ...node, data: { ...newData } } : node
          )
        );
      },
      [setNodes]
    );

    // Expose handleNodeDataUpdate via the onNodeUpdate callback pattern
    useEffect(() => {
      // This effect bridges external onNodeUpdate calls to internal setNodes
      // The parent will call the canvas ref's methods or use a callback
    }, []);

    // Connection validation
    const isValidConnection = useCallback(
      (connection: Connection | Edge) => {
        const sourceNode = nodes.find((n) => n.id === connection.source);
        const targetNode = nodes.find((n) => n.id === connection.target);
        if (!sourceNode || !targetNode) return false;

        // End node cannot be a source
        if (sourceNode.type === 'end') return false;
        // Initiator node cannot be a target
        if (targetNode.type === 'initiator') return false;

        // Count existing edges from source
        const sourceEdges = edges.filter((e) => e.source === connection.source);

        // Initiator: max 1 outgoing
        if (sourceNode.type === 'initiator' && sourceEdges.length >= 1) {
          return false;
        }

        // Condition nodes: max 2 outgoing (yes/no)
        if (sourceNode.type === 'condition' && sourceEdges.length >= 2) {
          return false;
        }

        // Approver, auto_approve, timer, cc_notify, sub_workflow nodes: max 1 outgoing
        if (
          (sourceNode.type === 'approver' || sourceNode.type === 'auto_approve' ||
           sourceNode.type === 'timer' || sourceNode.type === 'cc_notify' ||
           sourceNode.type === 'sub_workflow') &&
          sourceEdges.length >= 1
        ) {
          return false;
        }

        // Prevent self-connections
        if (connection.source === connection.target) {
          return false;
        }

        return true;
      },
      [nodes, edges]
    );

    // Handle new connections
    const onConnect = useCallback(
      (params: Connection) => {
        const sourceNode = nodes.find((n) => n.id === params.source);
        let label = '';

        // Auto-label for condition nodes based on handle id
        if (sourceNode?.type === 'condition') {
          label = params.sourceHandle === 'no' ? '否 / 驳回' : '是 / 通过';
        }

        const newEdge = {
          ...params,
          label,
          labelStyle: { fill: 'hsl(var(--foreground))', fontWeight: 600, fontSize: 12 },
          labelBgStyle: { fill: 'hsl(var(--background))', fillOpacity: 0.8 },
          labelBgPadding: [4, 2],
          labelBgBorderRadius: 4,
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
          style: { strokeWidth: 2, stroke: params.sourceHandle === 'no' ? 'hsl(var(--destructive))' : 'hsl(var(--primary))' },
        };
        setEdges((eds) => addEdge(newEdge, eds));
      },
      [setEdges, nodes]
    );

    // Handle node selection
    const onNodeClick = useCallback(
      (_: React.MouseEvent, node: Node) => {
        onNodeSelect(node);
      },
      [onNodeSelect]
    );

    // Deselect on pane click
    const onPaneClick = useCallback(() => {
      onNodeSelect(null);
    }, [onNodeSelect]);

    // Drag and drop from sidebar
    const onDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
    }, []);

    const onDrop = useCallback(
      (event: DragEvent<HTMLDivElement>) => {
        event.preventDefault();

        const nodeType = event.dataTransfer.getData('application/reactflow');
        if (!nodeType || !DEFAULT_NODE_DATA[nodeType] || FIXED_NODE_TYPES.has(nodeType)) return;

        // Use screenToFlowPosition for accurate placement regardless of zoom/pan
        const position = screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });

        // Center the node
        position.x -= 75;
        position.y -= 25;

        const newNode: Node = {
          id: getNodeId(),
          type: nodeType,
          position,
          data: { ...DEFAULT_NODE_DATA[nodeType] },
        };

        setNodes((nds) => [...nds, newNode]);
      },
      [setNodes, screenToFlowPosition]
    );

    // Bridge external node update calls
    // The parent calls onNodeUpdate -> we need to update the node
    // We expose handleNodeDataUpdate and also let the parent use it through props
    // But since the parent already has access to setNodes indirectly via this
    // component, we'll handle it by watching for external node update calls.

    // Whether canvas only has fixed nodes (empty state)
    const isEmptyCanvas = nodes.every((n) => FIXED_NODE_TYPES.has(n.type || ''));

    return (
      <div ref={reactFlowWrapper} className="flex-1 h-full relative">
        {isEmptyCanvas && (
          <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
            <div className="border-2 border-dashed border-muted-foreground/25 rounded-xl px-8 py-6 text-center bg-background/60 backdrop-blur-sm">
              <p className="text-sm font-medium text-muted-foreground mb-1">
                从左侧拖入节点，连线构建审批流程
              </p>
              <p className="text-xs text-muted-foreground/70">
                将发起人节点连接到审批节点，最后连接到结束节点
              </p>
            </div>
          </div>
        )}
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          onDragOver={onDragOver}
          onDrop={onDrop}
          isValidConnection={isValidConnection}
          nodeTypes={nodeTypes}
          onlyRenderVisibleElements
          fitView
          fitViewOptions={{ padding: 0.2 }}
          deleteKeyCode={['Backspace', 'Delete']}
          className="bg-muted/30"
          defaultEdgeOptions={{
            markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
            style: { strokeWidth: 2 },
          }}
        >
          <Controls className="!bg-background !border !shadow-sm" />
          <MiniMap
            className="!bg-background !border !shadow-sm"
            nodeStrokeWidth={3}
            zoomable
            pannable
          />
          <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
        </ReactFlow>
      </div>
    );
  }
);

// Re-export the handleNodeDataUpdate as a static helper for parent use
// eslint-disable-next-line react-refresh/only-export-components
export function updateNodeInCanvas(
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>,
  nodeId: string,
  newData: Record<string, unknown>
) {
  setNodes((nds) =>
    nds.map((node) =>
      node.id === nodeId ? { ...node, data: { ...newData } } : node
    )
  );
}
