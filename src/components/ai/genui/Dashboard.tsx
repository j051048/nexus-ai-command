import React from 'react';
import { DataChart } from './DataChart';

interface ChartConfig {
  type?: 'bar' | 'line' | 'pie' | 'area';
  title?: string;
  data: Record<string, unknown>[];
  dataKeys: string[];
  xKey?: string;
  span?: number;
}

interface DashboardProps {
  title?: string;
  charts: ChartConfig[];
  onSendMessage?: (prompt: string) => void;
}

export function Dashboard({ title, charts, onSendMessage }: DashboardProps) {
  if (!charts || charts.length === 0) {
    return (
      <div className="p-6 text-center text-muted-foreground text-sm">
        暂无仪表板数据
      </div>
    );
  }

  const handleDataClick = (chartTitle: string, label: string, value: number, dataKey: string) => {
    if (!onSendMessage) return;
    const prompt = `请详细分析"${chartTitle || '图表'}"中"${label}"的${dataKey}数据（当前值: ${value}），包括趋势、原因和建议。`;
    onSendMessage(prompt);
  };

  return (
    <div className="p-4">
      {title && <h3 className="text-base font-semibold mb-4">{title}</h3>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {charts.map((chart, i) => (
          <div
            key={i}
            className={`border border-border rounded-lg overflow-hidden ${chart.span === 2 ? 'md:col-span-2' : ''}`}
          >
            <DataChart
              type={chart.type}
              title={chart.title}
              data={chart.data}
              dataKeys={chart.dataKeys}
              xKey={chart.xKey}
              height={250}
              onDataClick={(label, value, dataKey) =>
                handleDataClick(chart.title || '', label, value, dataKey)
              }
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export default Dashboard;
