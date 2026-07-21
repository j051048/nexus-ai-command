import { useState } from 'react';
import { FileDown, FileImage, FileText, Loader2, Sheet } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { announceDeliverable } from '@/features/deliverables/deliverableStore';
import { exportAIContent, titleFromContent } from '@/features/deliverables/exportContent';
import type { DeliverableFormat } from '@/features/deliverables/types';

const FORMATS: Array<{
  format: 'docx' | 'pdf' | 'xlsx' | 'png';
  label: string;
  description: string;
  icon: typeof FileText;
}> = [
  { format: 'docx', label: 'Word 文档', description: '继续编辑和套用企业模板', icon: FileText },
  { format: 'pdf', label: 'PDF 文件', description: '适合审阅与正式发送', icon: FileText },
  { format: 'xlsx', label: 'Excel 表格', description: '自动提取表格或结构化条目', icon: Sheet },
  { format: 'png', label: '成果图片', description: '适合微信、汇报和快速预览', icon: FileImage },
];

export function MessageDeliverableMenu({ content }: { content: string }) {
  const [exporting, setExporting] = useState<DeliverableFormat | null>(null);

  const handleExport = async (format: 'docx' | 'pdf' | 'xlsx' | 'png') => {
    const title = titleFromContent(content);
    setExporting(format);
    try {
      const result = await exportAIContent(content, format);
      announceDeliverable({
        title,
        filename: result.filename,
        format,
        source: 'assistant',
        sourceLabel: 'AI 对话',
        sourcePath: `${window.location.pathname}${window.location.search}`,
        sizeBytes: result.sizeBytes,
        download: () => exportAIContent(content, format).then(() => undefined),
      });
      toast.success(`${result.filename} 已生成`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '成果文件生成失败');
    } finally {
      setExporting(null);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="mt-2 h-7 gap-1.5 px-2.5 text-xs"
          disabled={Boolean(exporting)}
          data-testid="message-deliverable-menu"
        >
          {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
          生成文件
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        {FORMATS.map((item) => (
          <DropdownMenuItem
            key={item.format}
            className="items-start gap-3 py-2.5"
            onClick={() => void handleExport(item.format)}
          >
            <item.icon className="mt-0.5 h-4 w-4 text-primary" />
            <span>
              <span className="block text-sm font-medium">{item.label}</span>
              <span className="block text-xs text-muted-foreground">{item.description}</span>
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

