import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';

// ═══════════════════════════════════════════════════════════════════════════════
//  Mock dependencies used across GenUI components
// ═══════════════════════════════════════════════════════════════════════════════

// Mock LeadCard at top level to fix hoisting warning
vi.mock('@/components/sales/components/LeadCard', () => ({
  LeadCard: ({ lead }: { lead: { company_name: string } }) =>
    React.createElement('div', { 'data-testid': 'lead-card' }, lead.company_name),
}));

// Mock recharts (used by DataChart)
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
    React.createElement('div', { 'data-testid': 'responsive-container' }, children),
  BarChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement('div', { 'data-testid': 'bar-chart' }, children),
  Bar: () => React.createElement('div', { 'data-testid': 'bar' }),
  LineChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement('div', { 'data-testid': 'line-chart' }, children),
  Line: () => React.createElement('div', { 'data-testid': 'line' }),
  PieChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement('div', { 'data-testid': 'pie-chart' }, children),
  Pie: () => React.createElement('div', { 'data-testid': 'pie' }),
  AreaChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement('div', { 'data-testid': 'area-chart' }, children),
  Area: () => React.createElement('div', { 'data-testid': 'area' }),
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  Cell: () => null,
}));

vi.mock('lucide-react', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  const mocked: Record<string, unknown> = {};
  for (const key in actual) {
    if (typeof actual[key] === 'function' || typeof actual[key] === 'object') {
      mocked[key] = () => React.createElement('span', { 'data-testid': `icon-${key.toLowerCase()}` });
    }
  }
  return mocked;
});

// ═══════════════════════════════════════════════════════════════════════════════
//  1. DataChart
// ═══════════════════════════════════════════════════════════════════════════════

describe('DataChart', () => {
  it('renders bar chart with title and data', async () => {
    const { DataChart } = await import('@/components/ai/genui/DataChart');
    const mockData = [
      { month: '1月', sales: 4000 },
      { month: '2月', sales: 3000 },
      { month: '3月', sales: 5000 },
    ];

    render(
      <DataChart
        type="bar"
        title="月度销售额"
        data={mockData}
        dataKeys={['sales']}
        xKey="month"
      />
    );

    expect(screen.getByText('月度销售额')).toBeDefined();
  });

  it('renders with empty data without crashing', async () => {
    const { DataChart } = await import('@/components/ai/genui/DataChart');
    const { container } = render(
      <DataChart data={[]} dataKeys={['value']} />
    );
    expect(container).toBeDefined();
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
//  2. DataTable
// ═══════════════════════════════════════════════════════════════════════════════

describe('DataTable', () => {
  it('renders columns and rows correctly', async () => {
    const { DataTable } = await import('@/components/ai/genui/DataTable');
    const columns = [
      { key: 'name', label: '姓名' },
      { key: 'amount', label: '金额' },
    ];
    const rows = [
      { name: '张三', amount: 5000 },
      { name: '李四', amount: 3000 },
    ];

    render(<DataTable title="费用明细" columns={columns} rows={rows} />);

    expect(screen.getByText('费用明细')).toBeDefined();
    expect(screen.getByText('姓名')).toBeDefined();
    expect(screen.getByText('张三')).toBeDefined();
    expect(screen.getByText('李四')).toBeDefined();
  });

  it('handles empty rows gracefully', async () => {
    const { DataTable } = await import('@/components/ai/genui/DataTable');
    const { container } = render(
      <DataTable columns={[{ key: 'a', label: 'A' }]} rows={[]} />
    );
    expect(container).toBeDefined();
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
//  3. StatCards
// ═══════════════════════════════════════════════════════════════════════════════

describe('StatCards', () => {
  it('renders cards with values and trends', async () => {
    const { StatCards } = await import('@/components/ai/genui/StatCards');
    const cards = [
      { label: '总收入', value: '¥128,000', change: 12.5, trend: 'up' as const },
      { label: '新客户', value: 45, change: -5, trend: 'down' as const },
      { label: '成交率', value: '68%', trend: 'flat' as const },
    ];

    render(<StatCards title="本月概览" cards={cards} />);

    expect(screen.getByText('本月概览')).toBeDefined();
    expect(screen.getByText('总收入')).toBeDefined();
    expect(screen.getByText('新客户')).toBeDefined();
  });

  it('returns null for empty cards array', async () => {
    const { StatCards } = await import('@/components/ai/genui/StatCards');
    const { container } = render(<StatCards cards={[]} />);
    expect(container.innerHTML).toBe('');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
//  4. Timeline
// ═══════════════════════════════════════════════════════════════════════════════

describe('Timeline', () => {
  it('renders timeline items with status', async () => {
    const { Timeline } = await import('@/components/ai/genui/Timeline');
    const items = [
      { time: '09:00', title: '客户拜访', status: 'done' as const },
      { time: '14:00', title: '方案评审', description: '与技术团队', status: 'active' as const },
      { time: '16:00', title: '合同签署', status: 'pending' as const },
    ];

    render(<Timeline title="今日日程" items={items} />);

    expect(screen.getByText('今日日程')).toBeDefined();
    expect(screen.getByText('客户拜访')).toBeDefined();
    expect(screen.getByText('方案评审')).toBeDefined();
  });

  it('returns null for empty items', async () => {
    const { Timeline } = await import('@/components/ai/genui/Timeline');
    const { container } = render(<Timeline items={[]} />);
    expect(container.innerHTML).toBe('');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
//  5. TodoList
// ═══════════════════════════════════════════════════════════════════════════════

describe('TodoList', () => {
  it('renders todo items with priority', async () => {
    const { TodoList } = await import('@/components/ai/genui/TodoList');
    const items = [
      { label: '跟进客户A', done: false, priority: 'high' as const },
      { label: '准备周报', done: true, priority: 'medium' as const },
      { label: '整理文档', done: false, priority: 'low' as const },
    ];

    render(<TodoList title="待办事项" items={items} />);

    expect(screen.getByText('待办事项')).toBeDefined();
    expect(screen.getByText('跟进客户A')).toBeDefined();
  });

  it('returns null for empty items', async () => {
    const { TodoList } = await import('@/components/ai/genui/TodoList');
    const { container } = render(<TodoList items={[]} />);
    expect(container.innerHTML).toBe('');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
//  6. PieChart (custom SVG-based, not recharts)
// ═══════════════════════════════════════════════════════════════════════════════

describe('PieChart (GenUI)', () => {
  it('renders pie chart with data slices', async () => {
    const PieChartModule = await import('@/components/ai/genui/PieChart');
    const PieChart = PieChartModule.default;
    const data = [
      { label: '差旅', value: 45000 },
      { label: '招待', value: 25000 },
      { label: '办公', value: 15000 },
    ];

    render(<PieChart title="费用分布" data={data} />);

    expect(screen.getByText('费用分布')).toBeDefined();
    expect(screen.getByText('差旅')).toBeDefined();
    expect(screen.getByText('招待')).toBeDefined();
  });

  it('returns null for empty data', async () => {
    const PieChartModule = await import('@/components/ai/genui/PieChart');
    const PieChart = PieChartModule.default;
    const { container } = render(<PieChart data={[]} />);
    expect(container.innerHTML).toBe('');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
//  7. AlertList
// ═══════════════════════════════════════════════════════════════════════════════

describe('AlertList', () => {
  it('renders alerts with different levels', async () => {
    const AlertListModule = await import('@/components/ai/genui/AlertList');
    const AlertList = AlertListModule.default;
    const alerts = [
      { level: 'error' as const, title: '紧急: 大客户流失风险', message: '客户A已7天未响应' },
      { level: 'warning' as const, title: '注意: 预算超支', message: '销售部已用90%' },
      { level: 'info' as const, title: '提示: 新线索分配' },
      { level: 'success' as const, title: '完成: 合同已签署' },
    ];

    render(<AlertList title="告警中心" alerts={alerts} />);

    expect(screen.getByText('告警中心')).toBeDefined();
    expect(screen.getByText('紧急: 大客户流失风险')).toBeDefined();
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
//  8. KanbanBoard (business component with external deps)
// ═══════════════════════════════════════════════════════════════════════════════

describe('KanbanBoard', () => {
  it('renders stage columns', async () => {
    const { KanbanBoard } = await import('@/components/sales/sections/KanbanBoard');

    const leads = [
      {
        id: '1', company_name: 'ABC公司', contact_name: '张三', stage: 'new',
        amount: 50000, priority: 'high', created_at: '2026-03-01',
      },
      {
        id: '2', company_name: 'XYZ公司', contact_name: '李四', stage: 'qualified',
        amount: 80000, priority: 'medium', created_at: '2026-03-05',
      },
    ] as Record<string, unknown>[];

    // @ts-expect-error Testing with partial mock properties
    render(<KanbanBoard leads={leads} onLeadClick={vi.fn()} />);

    expect(screen.getByText('实时执行管道')).toBeDefined();
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
//  9. Error boundary behavior
// ═══════════════════════════════════════════════════════════════════════════════

describe('GenUI Error Boundary Behavior', () => {
  it('DataChart handles malformed data without crashing', async () => {
    const { DataChart } = await import('@/components/ai/genui/DataChart');

    // Pass completely wrong data shapes
    const { container } = render(
      <DataChart
        data={[{ wrong: 'shape' }]}
        dataKeys={['nonexistent']}
        type="bar"
      />
    );
    expect(container).toBeDefined();
  });

  it('StatCards handles undefined cards without crashing', async () => {
    const { StatCards } = await import('@/components/ai/genui/StatCards');
    // @ts-expect-error Testing undefined cards
    const { container } = render(<StatCards cards={undefined} />);
    expect(container.innerHTML).toBe('');
  });

  it('Timeline handles undefined items without crashing', async () => {
    const { Timeline } = await import('@/components/ai/genui/Timeline');
    // @ts-expect-error Testing undefined items
    const { container } = render(<Timeline items={undefined} />);
    expect(container.innerHTML).toBe('');
  });

  it('TodoList handles undefined items without crashing', async () => {
    const { TodoList } = await import('@/components/ai/genui/TodoList');
    // @ts-expect-error Testing undefined items
    const { container } = render(<TodoList items={undefined} />);
    expect(container.innerHTML).toBe('');
  });

  it('PieChart handles undefined data without crashing', async () => {
    const PieChartModule = await import('@/components/ai/genui/PieChart');
    const PieChart = PieChartModule.default;
    // @ts-expect-error Testing undefined data
    const { container } = render(<PieChart data={undefined} />);
    expect(container.innerHTML).toBe('');
  });

  it('DataTable renders with missing column keys in rows', async () => {
    const { DataTable } = await import('@/components/ai/genui/DataTable');
    const { container } = render(
      <DataTable
        columns={[{ key: 'name', label: 'Name' }, { key: 'value', label: 'Value' }]}
        rows={[{ name: 'test' }]}
      />
    );
    // Should not crash even though 'value' key is missing from rows
    expect(container).toBeDefined();
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
//  10. ApprovalCenter (complex component - shallow render test)
// ═══════════════════════════════════════════════════════════════════════════════

describe('ApprovalCenter', () => {
  it('module is importable without crashing', async () => {
    // ApprovalCenter has many hooks and context dependencies,
    // we only verify the module can be imported (no parse errors)
    const mod = await import('@/components/approval/ApprovalCenter');
    expect(mod.ApprovalCenter).toBeDefined();
    expect(typeof mod.ApprovalCenter).toBe('function');
  });
});
