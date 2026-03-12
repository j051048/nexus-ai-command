import React, { useState } from 'react';
import { TableProperties, Download, Save, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export interface DataGridProps {
  title: string;
  columns: { key: string; label: string; editable?: boolean }[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  rows: any[];
}

export default function DataGrid({ title, columns = [], rows = [] }: DataGridProps) {
  const [data, setData] = useState(rows);
  const [isSaving, setIsSaving] = useState(false);

  const handleCellChange = (rowIndex: number, key: string, value: string) => {
    const newData = [...data];
    newData[rowIndex] = { ...newData[rowIndex], [key]: value };
    setData(newData);
  };

  const handleSave = () => {
    setIsSaving(true);
    setTimeout(() => {
      setIsSaving(false);
      toast.success('数据已成功保存至系统');
    }, 600);
  };

  const handleExport = () => {
    if (!columns.length || !data.length) return;
    const headers = columns.map(c => c.label).join(',');
    const csvRows = data.map(row => columns.map(c => `"${row[c.key] || ''}"`).join(','));
    const csvContent = [headers, ...csvRows].join('\n');
    
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${title || 'export'}.csv`;
    link.click();
    toast.success('已开始下载 CSV');
  };

  return (
    <div className="flex flex-col w-full bg-card rounded-xl border border-border shadow-sm overflow-hidden">
      <div className="bg-muted/10 px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-primary/10 rounded-md text-primary">
            <TableProperties className="w-4 h-4" />
          </div>
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleExport} className="h-7 text-xs px-2.5">
            <Download className="w-3.5 h-3.5 mr-1" />
            导出
          </Button>
          <Button size="sm" onClick={handleSave} disabled={isSaving} className="h-7 text-xs px-2.5">
            {isSaving ? <Check className="w-3.5 h-3.5 mr-1 animate-pulse" /> : <Save className="w-3.5 h-3.5 mr-1" />}
            {isSaving ? '保存中' : '保存修改'}
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left border-collapse">
          <thead className="bg-muted/30">
            <tr>
              {columns.map((col, i) => (
                <th key={i} className="px-4 py-2 font-medium text-xs text-muted-foreground border-b border-border border-r border-border/50 last:border-r-0 whitespace-nowrap">
                  {col.label}
                  {col.editable && <span className="ml-1 opacity-50 text-[10px]">(可编辑)</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-b border-border/50 hover:bg-muted/10 transition-colors last:border-b-0">
                {columns.map((col, colIndex) => (
                  <td key={colIndex} className="px-3 py-1.5 border-r border-border/50 last:border-r-0">
                    {col.editable ? (
                      <input
                        type="text"
                        value={row[col.key] || ''}
                        onChange={(e) => handleCellChange(rowIndex, col.key, e.target.value)}
                        className="w-full bg-transparent border-none focus:outline-none focus:ring-1 focus:ring-primary/50 px-1 py-1 -ml-1 rounded text-sm text-foreground transition-all hover:bg-muted/50"
                      />
                    ) : (
                      <span className="px-1 py-1 block text-muted-foreground">{row[col.key] || '-'}</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
            {data.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-muted-foreground text-sm flex items-center justify-center gap-2">
                  <TableProperties className="w-4 h-4 opacity-50" />
                  暂无数据记录
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
