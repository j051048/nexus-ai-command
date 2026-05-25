import { useRef } from 'react';
import { Camera, FileUp, Mic, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

function triggerAI(message: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message } }));
}

export default function MobileNativeCapturePanel() {
  const cardInputRef = useRef<HTMLInputElement>(null);
  const attachmentInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelected = (kind: 'card' | 'attachment', files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    if (kind === 'card') {
      toast.success('已读取名片图片', { description: 'AI 将按 OCR 名片建档流程提取联系人。' });
      triggerAI(`我刚拍了一张名片：${file.name}。请按 OCR 名片流程提取姓名、公司、职位、电话、邮箱，并生成创建联系人草稿。`);
      return;
    }
    toast.success('已选择项目附件', { description: 'AI 将整理成客户/项目附件说明。' });
    triggerAI(`我刚上传了一份移动端附件：${file.name}。请帮我判断应归档到哪个客户或项目，并生成附件说明。`);
  };

  return (
    <section className="rounded-2xl border bg-card p-4 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="h-4 w-4 text-primary" />
            移动速记
          </div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            拜访结束后直接语音、拍名片或上传现场资料，让 AI 生成客户记录和下一步动作。
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Button
          variant="outline"
          className="h-auto flex-col gap-1 py-3 text-xs"
          onClick={() =>
            triggerAI('启动语音拜访速记：请提示我口述客户名称、参会人、需求、异议、预算、下一步动作和跟进日期。')
          }
        >
          <Mic className="h-5 w-5" />
          语音速记
        </Button>
        <Button
          variant="outline"
          className="h-auto flex-col gap-1 py-3 text-xs"
          onClick={() => cardInputRef.current?.click()}
        >
          <Camera className="h-5 w-5" />
          拍名片
        </Button>
        <Button
          variant="outline"
          className="h-auto flex-col gap-1 py-3 text-xs"
          onClick={() => attachmentInputRef.current?.click()}
        >
          <FileUp className="h-5 w-5" />
          附件归档
        </Button>
      </div>

      <input
        ref={cardInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(event) => handleFileSelected('card', event.target.files)}
      />
      <input
        ref={attachmentInputRef}
        type="file"
        accept="image/*,application/pdf,.doc,.docx,.xls,.xlsx"
        capture="environment"
        className="hidden"
        onChange={(event) => handleFileSelected('attachment', event.target.files)}
      />
    </section>
  );
}
