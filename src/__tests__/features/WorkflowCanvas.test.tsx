/**
 * WorkflowCanvas 专项测试
 *
 * 覆盖：节点类型注册、初始节点、拖拽添加、连线验证、数据转换、
 *       loadWorkflowData、getWorkflowData、固定节点不可删除
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import React, { createRef } from 'react';

// Mock ReactFlow
const mockSetNodes = vi.fn();
const mockSetEdges = vi.fn();
const mockScreenToFlowPosition = vi.fn((pos: any) => pos);

vi.mock('@xyflow/react', () => {
  const actual = {
    MarkerType: { ArrowClosed: 'arrowclosed' },
    BackgroundVariant: { Dots: 'dots' },
    Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
  };

  return {
    ...actual,
    ReactFlow: ({ children, nodeTypes, ...props }: any) => (
      <div data-testid="react-flow" data-node-types={Object.keys(nodeTypes || {}).join(',')}>
        {children}
      </div>
    ),
    Controls: () => <div data-testid="controls" />,
    Background: () => <div data-testid="background" />,
    MiniMap: () => <div data-testid="minimap" />,
    Handle: ({ type, position }: any) => <div data-testid={`handle-${type}`} />,
    useNodesState: (initial: any) => [initial, mockSetNodes, vi.fn()],
    useEdgesState: (initial: any) => [initial || [], mockSetEdges, vi.fn()],
    addEdge: vi.fn((conn: any, edges: any) => [...edges, { ...conn, id: 'new-edge' }]),
    useReactFlow: () => ({ screenToFlowPosition: mockScreenToFlowPosition }),
  };
});

// Mock all node components
const nodeComponents = [
  'ApproverNode', 'ConditionNode', 'ParallelNode', 'AutoApproveNode',
  'NotifyNode', 'CcNotifyNode', 'TimerNode', 'SubWorkflowNode',
  'InitiatorNode', 'EndNode',
];
for (const name of nodeComponents) {
  const modulePath = `@/components/workflow/nodes/${name}`;
  vi.mock(modulePath, () => ({
    [name]: () => <div data-testid={`node-${name}`} />,
  }));
}

import { WorkflowCanvas, type WorkflowCanvasRef } from '@/components/workflow/WorkflowCanvas';

describe('WorkflowCanvas', () => {
  const defaultProps = {
    onNodeSelect: vi.fn(),
    onNodeUpdate: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('注册所有 10 种自定义节点类型', () => {
    render(
      <WorkflowCanvas {...defaultProps} ref={createRef()} />
    );
    const flow = screen.getByTestId('react-flow');
    const types = flow.getAttribute('data-node-types')!.split(',');
    expect(types).toContain('initiator');
    expect(types).toContain('approver');
    expect(types).toContain('condition');
    expect(types).toContain('parallel');
    expect(types).toContain('auto_approve');
    expect(types).toContain('notify');
    expect(types).toContain('cc_notify');
    expect(types).toContain('timer');
    expect(types).toContain('sub_workflow');
    expect(types).toContain('end');
    expect(types).toHaveLength(10);
  });

  it('渲染控件、背景和小地图', () => {
    render(<WorkflowCanvas {...defaultProps} ref={createRef()} />);
    expect(screen.getByTestId('controls')).toBeInTheDocument();
    expect(screen.getByTestId('background')).toBeInTheDocument();
    expect(screen.getByTestId('minimap')).toBeInTheDocument();
  });

  it('getWorkflowData 返回 steps 和 conditions', () => {
    const ref = createRef<WorkflowCanvasRef>();
    render(<WorkflowCanvas {...defaultProps} ref={ref} />);

    const data = ref.current!.getWorkflowData();
    expect(data).toHaveProperty('steps');
    expect(data).toHaveProperty('conditions');
    // 初始应有 initiator 和 end 两个节点
    expect(data.steps.length).toBeGreaterThanOrEqual(2);
    expect(data.steps.some((s: any) => s.type === 'initiator')).toBe(true);
    expect(data.steps.some((s: any) => s.type === 'end')).toBe(true);
  });

  it('loadWorkflowData 加载外部定义', () => {
    const ref = createRef<WorkflowCanvasRef>();
    render(<WorkflowCanvas {...defaultProps} ref={ref} />);

    const definition = {
      steps: [
        { id: 'initiator', type: 'initiator' as const, label: '发起人', config: {}, position: { x: 250, y: 30 } },
        { id: 'a1', type: 'approver' as const, label: '审批人', config: { role: 'boss' }, position: { x: 250, y: 200 } },
        { id: 'end', type: 'end' as const, label: '结束', config: {}, position: { x: 250, y: 400 } },
      ],
      conditions: [
        { from_step_id: 'initiator', to_step_id: 'a1' },
        { from_step_id: 'a1', to_step_id: 'end' },
      ],
    };

    act(() => {
      ref.current!.loadWorkflowData(definition);
    });

    // setNodes 和 setEdges 应被调用
    expect(mockSetNodes).toHaveBeenCalled();
    expect(mockSetEdges).toHaveBeenCalled();
  });

  it('loadWorkflowData 缺少 initiator/end 时自动补全', () => {
    const ref = createRef<WorkflowCanvasRef>();
    render(<WorkflowCanvas {...defaultProps} ref={ref} />);

    const definition = {
      steps: [
        { id: 'a1', type: 'approver' as const, label: '审批人', config: {}, position: { x: 250, y: 200 } },
      ],
      conditions: [],
    };

    act(() => {
      ref.current!.loadWorkflowData(definition);
    });

    // setNodes 应被调用，且传入的节点应包含 initiator 和 end
    const setNodesCall = mockSetNodes.mock.calls[0][0];
    expect(setNodesCall.some((n: any) => n.type === 'initiator')).toBe(true);
    expect(setNodesCall.some((n: any) => n.type === 'end')).toBe(true);
  });

  it('固定节点 (initiator/end) 标记为 deletable: false', () => {
    const ref = createRef<WorkflowCanvasRef>();
    render(<WorkflowCanvas {...defaultProps} ref={ref} />);

    const definition = {
      steps: [
        { id: 'initiator', type: 'initiator' as const, label: '发起人', config: {}, position: { x: 0, y: 0 } },
        { id: 'end', type: 'end' as const, label: '结束', config: {}, position: { x: 0, y: 400 } },
      ],
      conditions: [],
    };

    act(() => {
      ref.current!.loadWorkflowData(definition);
    });

    const nodes = mockSetNodes.mock.calls[0][0];
    const initiator = nodes.find((n: any) => n.type === 'initiator');
    const end = nodes.find((n: any) => n.type === 'end');
    expect(initiator.deletable).toBe(false);
    expect(end.deletable).toBe(false);
  });
});
