/**
 * P1 UX Enhancement: Data Export Component
 * 数据导出组件，支持多种格式和自定义配置
 */

import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Download,
  FileSpreadsheet,
  FileJson,
  FileText,
  File,
  Loader2,
  Check,
  ChevronDown,
  Settings2,
  Calendar,
  Filter,
} from 'lucide-react';
import { toast } from 'sonner';

// ==================== 类型定义 ====================

export type ExportFormat = 'csv' | 'xlsx' | 'json' | 'pdf';

export interface ExportColumn {
  key: string;
  label: string;
  selected?: boolean;
  formatter?: (value: unknown) => string;
}

export interface ExportConfig {
  filename?: string;
  format?: ExportFormat;
  columns?: ExportColumn[];
  dateRange?: {
    start?: Date;
    end?: Date;
  };
  filters?: Record<string, unknown>;
}

interface DataExportProps<T> {
  data: T[];
  columns: ExportColumn[];
  filename?: string;
  title?: string;
  description?: string;
  formats?: ExportFormat[];
  onExport?: (config: ExportConfig, data: T[]) => Promise<void>;
  children?: React.ReactNode;
  className?: string;
  showQuickExport?: boolean;
  showAdvancedOptions?: boolean;
}

interface QuickExportButtonProps {
  format: ExportFormat;
  onClick: () => void;
  loading?: boolean;
}

// ==================== 工具函数 ====================

const formatIcons: Record<ExportFormat, React.ReactNode> = {
  csv: <FileText className="w-4 h-4" />,
  xlsx: <FileSpreadsheet className="w-4 h-4" />,
  json: <FileJson className="w-4 h-4" />,
  pdf: <File className="w-4 h-4" />,
};

const formatLabels: Record<ExportFormat, string> = {
  csv: 'CSV 表格',
  xlsx: 'Excel 表格',
  json: 'JSON 数据',
  pdf: 'PDF 文档',
};

const formatDescriptions: Record<ExportFormat, string> = {
  csv: '通用表格格式，可用Excel打开',
  xlsx: 'Microsoft Excel 格式',
  json: '适合开发者使用的数据格式',
  pdf: '适合打印和分享的文档格式',
};

/**
 * 将数据转换为 CSV 格式
 */
function convertToCSV<T>(
  data: T[],
  columns: ExportColumn[]
): string {
  const selectedColumns = columns.filter((col) => col.selected !== false);
  const headers = selectedColumns.map((col) => col.label).join(',');
  
  const rows = data.map((item) =>
    selectedColumns
      .map((col) => {
        const value = (item as Record<string, unknown>)[col.key];
        const formatted = col.formatter ? col.formatter(value) : String(value ?? '');
        // 处理包含逗号或引号的值
        if (formatted.includes(',') || formatted.includes('"') || formatted.includes('\n')) {
          return `"${formatted.replace(/"/g, '""')}"`;
        }
        return formatted;
      })
      .join(',')
  );

  return [headers, ...rows].join('\n');
}

/**
 * 将数据转换为 JSON 格式
 */
function convertToJSON<T>(
  data: T[],
  columns: ExportColumn[]
): string {
  const selectedColumns = columns.filter((col) => col.selected !== false);
  
  const exportData = data.map((item) => {
    const obj: Record<string, unknown> = {};
    selectedColumns.forEach((col) => {
      const value = (item as Record<string, unknown>)[col.key];
      obj[col.key] = col.formatter ? col.formatter(value) : value;
    });
    return obj;
  });

  return JSON.stringify(exportData, null, 2);
}

/**
 * 下载文件
 */
function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// ==================== 子组件 ====================

function QuickExportButton({ format, onClick, loading }: QuickExportButtonProps) {
  return (
    <DropdownMenuItem
      onClick={onClick}
      disabled={loading}
      className="cursor-pointer"
    >
      {loading ? (
        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
      ) : (
        formatIcons[format]
      )}
      <span className="ml-2">{formatLabels[format]}</span>
    </DropdownMenuItem>
  );
}

interface ColumnSelectorProps {
  columns: ExportColumn[];
  onChange: (columns: ExportColumn[]) => void;
}

function ColumnSelector({ columns, onChange }: ColumnSelectorProps) {
  const allSelected = columns.every((col) => col.selected !== false);
  const someSelected = columns.some((col) => col.selected !== false);

  const toggleAll = () => {
    const newValue = !allSelected;
    onChange(columns.map((col) => ({ ...col, selected: newValue })));
  };

  const toggleColumn = (key: string) => {
    onChange(
      columns.map((col) =>
        col.key === key ? { ...col, selected: col.selected === false } : col
      )
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium">选择导出列</Label>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs"
          onClick={toggleAll}
        >
          {allSelected ? '取消全选' : '全选'}
        </Button>
      </div>
      <ScrollArea className="h-[200px] rounded-md border p-3">
        <div className="space-y-2">
          {columns.map((col) => (
            <div key={col.key} className="flex items-center space-x-2">
              <Checkbox
                id={col.key}
                checked={col.selected !== false}
                onCheckedChange={() => toggleColumn(col.key)}
              />
              <Label
                htmlFor={col.key}
                className="text-sm font-normal cursor-pointer"
              >
                {col.label}
              </Label>
            </div>
          ))}
        </div>
      </ScrollArea>
      <p className="text-xs text-muted-foreground">
        已选择 {columns.filter((col) => col.selected !== false).length} / {columns.length} 列
      </p>
    </div>
  );
}

// ==================== 主组件 ====================

export function DataExport<T extends Record<string, unknown>>({
  data,
  columns: initialColumns,
  filename = 'export',
  title = '导出数据',
  description = '选择导出格式和配置',
  formats = ['csv', 'xlsx', 'json'],
  onExport,
  children,
  className,
  showQuickExport = true,
  showAdvancedOptions = true,
}: DataExportProps<T>) {
  const [isOpen, setIsOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('csv');
  const [columns, setColumns] = useState<ExportColumn[]>(
    initialColumns.map((col) => ({ ...col, selected: col.selected ?? true }))
  );

  const handleExport = useCallback(
    async (format: ExportFormat, showDialog = false) => {
      setIsExporting(true);
      setExportProgress(0);

      try {
        // 模拟进度
        const progressInterval = setInterval(() => {
          setExportProgress((prev) => Math.min(prev + 20, 90));
        }, 100);

        const selectedColumns = columns.filter((col) => col.selected !== false);
        const config: ExportConfig = {
          filename,
          format,
          columns: selectedColumns,
        };

        if (onExport) {
          await onExport(config, data);
        } else {
          // 默认导出逻辑
          let content: string;
          let mimeType: string;
          let extension: string;

          switch (format) {
            case 'csv':
              content = convertToCSV(data, columns);
              mimeType = 'text/csv;charset=utf-8';
              extension = 'csv';
              break;
            case 'json':
              content = convertToJSON(data, columns);
              mimeType = 'application/json';
              extension = 'json';
              break;
            case 'xlsx':
              // 对于 Excel，使用 CSV 作为后备
              content = convertToCSV(data, columns);
              mimeType = 'text/csv;charset=utf-8';
              extension = 'csv';
              toast.info('Excel 格式暂不支持，已导出为 CSV');
              break;
            case 'pdf':
              toast.info('PDF 导出功能即将上线');
              clearInterval(progressInterval);
              setIsExporting(false);
              return;
            default:
              throw new Error(`Unsupported format: ${format}`);
          }

          const timestamp = new Date().toISOString().slice(0, 10);
          downloadFile(content, `${filename}_${timestamp}.${extension}`, mimeType);
        }

        clearInterval(progressInterval);
        setExportProgress(100);
        
        toast.success(`成功导出 ${data.length} 条数据`);
        
        if (showDialog) {
          setTimeout(() => setIsOpen(false), 500);
        }
      } catch (error) {
        console.error('Export error:', error);
        toast.error('导出失败，请稍后重试');
      } finally {
        setTimeout(() => {
          setIsExporting(false);
          setExportProgress(0);
        }, 500);
      }
    },
    [data, columns, filename, onExport]
  );

  // 快速导出下拉菜单
  if (showQuickExport && !showAdvancedOptions) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          {children || (
            <Button variant="outline" className={className}>
              <Download className="w-4 h-4 mr-2" />
              导出
              <ChevronDown className="w-4 h-4 ml-2" />
            </Button>
          )}
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>选择格式</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {formats.map((format) => (
            <QuickExportButton
              key={format}
              format={format}
              onClick={() => handleExport(format)}
              loading={isExporting}
            />
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  // 高级导出对话框
  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        {children || (
          <Button variant="outline" className={className}>
            <Download className="w-4 h-4 mr-2" />
            导出
            {showAdvancedOptions && (
              <Settings2 className="w-4 h-4 ml-2" />
            )}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="w-5 h-5" />
            {title}
          </DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* 格式选择 */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">导出格式</Label>
            <RadioGroup
              value={selectedFormat}
              onValueChange={(value) => setSelectedFormat(value as ExportFormat)}
              className="grid grid-cols-1 sm:grid-cols-2 gap-3"
            >
              {formats.map((format) => (
                <div key={format}>
                  <RadioGroupItem
                    value={format}
                    id={format}
                    className="peer sr-only"
                  />
                  <Label
                    htmlFor={format}
                    className={cn(
                      'flex items-center gap-3 rounded-lg border-2 p-3 cursor-pointer transition-all',
                      'hover:bg-muted/50',
                      'peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/5'
                    )}
                  >
                    <div className="p-2 rounded-md bg-muted">
                      {formatIcons[format]}
                    </div>
                    <div>
                      <p className="text-sm font-medium">{formatLabels[format]}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatDescriptions[format]}
                      </p>
                    </div>
                  </Label>
                </div>
              ))}
            </RadioGroup>
          </div>

          {/* 列选择 */}
          {showAdvancedOptions && (
            <ColumnSelector columns={columns} onChange={setColumns} />
          )}

          {/* 数据统计 */}
          <div className="p-3 bg-muted/50 rounded-lg">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">将导出</span>
              <span className="font-medium">
                {data.length} 条记录，{columns.filter((c) => c.selected !== false).length} 列
              </span>
            </div>
          </div>

          {/* 导出进度 */}
          {isExporting && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">正在导出...</span>
                <span>{exportProgress}%</span>
              </div>
              <Progress value={exportProgress} className="h-2" />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setIsOpen(false)}>
            取消
          </Button>
          <Button
            onClick={() => handleExport(selectedFormat, true)}
            disabled={isExporting || columns.filter((c) => c.selected !== false).length === 0}
          >
            {isExporting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                导出中...
              </>
            ) : (
              <>
                <Download className="w-4 h-4 mr-2" />
                导出 {formatLabels[selectedFormat]}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ==================== 快捷导出按钮 ====================

interface QuickExportProps<T> {
  data: T[];
  columns: ExportColumn[];
  filename?: string;
  format?: ExportFormat;
  className?: string;
  children?: React.ReactNode;
}

export function QuickExport<T extends Record<string, unknown>>({
  data,
  columns,
  filename = 'export',
  format = 'csv',
  className,
  children,
}: QuickExportProps<T>) {
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const content = format === 'json'
        ? convertToJSON(data, columns)
        : convertToCSV(data, columns);
      
      const mimeType = format === 'json' ? 'application/json' : 'text/csv;charset=utf-8';
      const timestamp = new Date().toISOString().slice(0, 10);
      downloadFile(content, `${filename}_${timestamp}.${format}`, mimeType);
      
      toast.success(`成功导出 ${data.length} 条数据`);
    } catch (error) {
      toast.error('导出失败');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <Button
      variant="outline"
      onClick={handleExport}
      disabled={isExporting}
      className={className}
    >
      {isExporting ? (
        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
      ) : (
        formatIcons[format]
      )}
      <span className="ml-2">{children || `导出 ${formatLabels[format]}`}</span>
    </Button>
  );
}

export default DataExport;