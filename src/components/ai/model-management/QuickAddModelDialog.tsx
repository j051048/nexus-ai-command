import { Info, Loader2, Sparkles, Wrench, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { AvailableModel } from "@/hooks/useVMD";

import { formatContextWindow } from "./modelManagementConfig";

interface QuickAddModelDialogProps {
  model: AvailableModel | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isPending: boolean;
}

export function QuickAddModelDialog({ model, onOpenChange, onConfirm, isPending }: QuickAddModelDialogProps) {
  return (
    <Dialog open={Boolean(model)} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            一键添加模型
          </DialogTitle>
          <DialogDescription>以下参数已从知识库自动预填充，确认后即可添加到您的模型列表</DialogDescription>
        </DialogHeader>
        {model && (
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Summary label="模型名称" value={model.name} />
              <Summary label="模型 ID" value={model.model_id} mono />
              <Summary label="厂商" value={model.provider_label} />
              <Summary label="类型" value={model.type === "chat" ? "对话模型" : "向量模型"} />
              <Summary label="上下文窗口" value={formatContextWindow(model.context_window)} />
              <Summary label="最大输出" value={formatContextWindow(model.max_tokens)} />
              <Summary label="输入价格" value={`$${model.input_price_per_1m}/M tokens`} />
              <Summary label="输出价格" value={`$${model.output_price_per_1m}/M tokens`} />
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              {model.supports_tools && <span className="flex items-center gap-1"><Wrench className="h-3 w-3 text-emerald-500" /> 工具调用</span>}
              {model.supports_streaming && <span className="flex items-center gap-1"><Zap className="h-3 w-3 text-blue-500" /> 流式输出</span>}
            </div>
            {!model.has_metadata && (
              <div className="flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-xs text-amber-600 dark:bg-amber-950/30 dark:text-amber-400">
                <Info className="mt-0.5 h-4 w-4 shrink-0" />
                <span>该模型不在知识库中，部分参数为默认值，添加后可能需要手动调整。</span>
              </div>
            )}
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={onConfirm} disabled={isPending}>
            {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            确认添加
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Summary({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <span className="block text-xs text-muted-foreground">{label}</span>
      <span className={mono ? "font-mono text-xs" : "font-medium"}>{value}</span>
    </div>
  );
}
