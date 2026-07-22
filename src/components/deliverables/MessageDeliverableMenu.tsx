import { useState } from 'react';
import { FileImage, FileText, Loader2, MoreHorizontal, Sheet, Sparkles } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { ArtifactReviewDialog } from '@/components/deliverables/ArtifactReviewDialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { announceDeliverable } from '@/features/deliverables/deliverableStore';
import {
  assessDeliverableEligibility,
  inferArtifactType,
} from '@/features/deliverables/deliverableEligibility';
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

interface MessageDeliverableMenuProps {
  content: string;
  originalRequest?: string;
  sessionId?: string;
}

export function MessageDeliverableMenu({
  content,
  originalRequest = '',
  sessionId,
}: MessageDeliverableMenuProps) {
  const [exporting, setExporting] = useState<DeliverableFormat | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const eligibility = assessDeliverableEligibility(content, originalRequest);
  const defaultType = inferArtifactType(originalRequest, content);

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

  if (!eligibility.canCreateArtifact) return null;

  return (
    <div className="mt-2 flex items-center gap-1.5">
      <Button
        variant="outline"
        size="sm"
        className="h-7 gap-1.5 px-2.5 text-xs"
        onClick={() => setReviewOpen(true)}
        disabled={Boolean(exporting)}
        data-testid="message-deliverable-menu"
      >
        <Sparkles className="h-3.5 w-3.5 text-primary" />
        制作精品成果
      </Button>

      {eligibility.canQuickExport && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground"
              disabled={Boolean(exporting)}
              aria-label="快速导出当前回答"
              title="快速导出当前回答"
            >
              {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MoreHorizontal className="h-3.5 w-3.5" />}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-64">
            <div className="px-2 py-1.5 text-xs font-medium">快速导出当前回答</div>
            <div className="px-2 pb-2 text-[11px] leading-4 text-muted-foreground">不重新检索或改写，适合内部留档。</div>
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
      )}

      <ArtifactReviewDialog
        open={reviewOpen}
        onOpenChange={setReviewOpen}
        content={content}
        originalRequest={originalRequest}
        defaultType={defaultType}
        sessionId={sessionId}
      />
    </div>
  );
}
