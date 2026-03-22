import React, { useCallback, useRef, useState } from 'react';
import { Download, Maximize2, Minimize2, X } from 'lucide-react';

// Table-like component names that support CSV export
const TABLE_COMPONENTS = new Set([
  'DataTable', 'ComparisonTable', 'DataChart',
]);

// Components that support PNG export (charts + visual components)
const CHART_COMPONENTS = new Set([
  'DataChart', 'PieChart', 'FunnelChart', 'StatCards',
  'MetricComparison', 'ProgressTracker', 'OrgChart',
  'ApprovalFlow', 'CalendarView', 'KanbanMini',
  'StatusTimeline', 'Timeline', 'AlertList',
  'UserProfileCard', 'QuoteCard', 'BadgePanel',
  'TodoList', 'FormBuilder', 'FileList',
]);

interface GenUIToolbarProps {
  componentName: string;
  props: Record<string, unknown>;
  children: React.ReactNode;
}

function exportTableCSV(componentName: string, props: Record<string, unknown>) {
  let csvContent = '';

  if (componentName === 'DataTable') {
    const columns = (props.columns as Array<{ key: string; label: string }>) || [];
    const rows = (props.rows as Array<Record<string, unknown>>) || [];
    // Header
    csvContent += columns.map(c => `"${c.label}"`).join(',') + '\n';
    // Rows
    for (const row of rows) {
      csvContent += columns.map(c => {
        const val = row[c.key] ?? '';
        return `"${String(val).replace(/"/g, '""')}"`;
      }).join(',') + '\n';
    }
  } else if (componentName === 'ComparisonTable') {
    const columns = (props.columns as Array<{ name: string }>) || [];
    const rows = (props.rows as Array<{ label: string; values: string[] }>) || [];
    // Header
    csvContent += ['', ...columns.map(c => `"${c.name}"`)].join(',') + '\n';
    // Rows
    for (const row of rows) {
      csvContent += [`"${row.label}"`, ...(row.values || []).map(v => `"${v}"`)].join(',') + '\n';
    }
  } else if (componentName === 'DataChart') {
    const data = (props.data as Array<Record<string, unknown>>) || [];
    const dataKeys = (props.dataKeys as string[]) || [];
    const xKey = (props.xKey as string) || 'name';
    if (data.length > 0) {
      // Header
      csvContent += [xKey, ...dataKeys].map(k => `"${k}"`).join(',') + '\n';
      // Rows
      for (const row of data) {
        csvContent += [row[xKey], ...dataKeys.map(k => row[k])].map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',') + '\n';
      }
    }
  }

  if (!csvContent) return;

  const title = (props.title as string) || componentName;
  const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${title}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

async function exportPNG(element: HTMLElement, title: string) {
  const html2canvas = (await import('html2canvas')).default;
  const canvas = await html2canvas(element, {
    backgroundColor: null,
    scale: 2,
    useCORS: true,
    logging: false,
  });
  const url = canvas.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = url;
  a.download = `${title}.png`;
  a.click();
}

export function GenUIToolbar({ componentName, props, children }: GenUIToolbarProps) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const canExportCSV = TABLE_COMPONENTS.has(componentName);
  const canExportPNG = CHART_COMPONENTS.has(componentName) || TABLE_COMPONENTS.has(componentName);
  const title = (props.title as string) || componentName;

  const handleExport = useCallback(async () => {
    if (canExportCSV) {
      exportTableCSV(componentName, props);
    } else if (canExportPNG && contentRef.current) {
      await exportPNG(contentRef.current, title);
    }
  }, [componentName, props, canExportCSV, canExportPNG, title]);

  const toggleFullscreen = useCallback(() => {
    setIsFullscreen(prev => !prev);
  }, []);

  // Fullscreen overlay
  if (isFullscreen) {
    return (
      <div className="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex flex-col animate-in fade-in duration-200">
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card">
          <span className="text-sm font-medium text-foreground">{title}</span>
          <div className="flex items-center gap-1">
            {(canExportCSV || canExportPNG) && (
              <button
                onClick={handleExport}
                className="p-2 sm:p-1.5 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                title={canExportCSV ? '导出 CSV' : '导出 PNG'}
              >
                <Download className="h-4 w-4" />
              </button>
            )}
            <button
              onClick={toggleFullscreen}
              className="p-2 sm:p-1.5 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
              title="退出全屏"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div ref={contentRef} className="flex-1 overflow-auto p-4">
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className="group relative">
      {/* Hover toolbar */}
      <div className="absolute top-2 right-2 z-10 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity bg-card/90 backdrop-blur-sm rounded-md border border-border shadow-sm">
        {(canExportCSV || canExportPNG) && (
          <button
            onClick={handleExport}
            className="p-2 sm:p-1.5 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
            title={canExportCSV ? '导出 CSV' : '导出 PNG'}
          >
            <Download className="h-3.5 w-3.5" />
          </button>
        )}
        <button
          onClick={toggleFullscreen}
          className="p-2 sm:p-1.5 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
          title="全屏查看"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
      </div>
      <div ref={contentRef}>
        {children}
      </div>
    </div>
  );
}
