import type { Dispatch, SetStateAction } from "react";
import { CheckCircle2, Loader2, TestTube, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import type { LLMModel } from "@/hooks/useVMD";
import { cn } from "@/lib/utils";

import { MODEL_PROVIDERS } from "./modelManagementConfig";

interface ModelEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isEditing: boolean;
  model: Partial<LLMModel>;
  setModel: Dispatch<SetStateAction<Partial<LLMModel>>>;
  onSave: () => void;
  onTest: (modelId: string) => void;
  testingId: string | null;
  testResult: { success: boolean; latency_ms: number } | null;
  isSaving: boolean;
}

export function ModelEditorDialog({
  open,
  onOpenChange,
  isEditing,
  model,
  setModel,
  onSave,
  onTest,
  testingId,
  testResult,
  isSaving,
}: ModelEditorDialogProps) {
  const update = (values: Partial<LLMModel>) => setModel((current) => ({ ...current, ...values }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "编辑模型" : "新增模型"}</DialogTitle>
          <DialogDescription>配置 LLM 模型的接入参数和能力选项</DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[60vh] pr-4">
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>模型厂商</Label>
                <Select value={model.provider_type || "openai"} onValueChange={(value) => update({ provider_type: value })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {MODEL_PROVIDERS.map((provider) => (
                      <SelectItem key={provider.value} value={provider.value}>{provider.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>模型类型</Label>
                <Select
                  value={model.model_type || "chat"}
                  onValueChange={(value) => update({ model_type: value as "chat" | "embedding" })}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="chat">对话模型</SelectItem>
                    <SelectItem value="embedding">向量模型</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <TextField label="模型编码" placeholder="例如: gpt-4o" value={model.model_code} onChange={(value) => update({ model_code: value })} />
              <TextField label="模型名称" placeholder="例如: GPT-4o" value={model.model_name} onChange={(value) => update({ model_name: value })} />
            </div>
            <TextField label="API Base URL" placeholder="https://api.openai.com/v1" value={model.api_base_url} onChange={(value) => update({ api_base_url: value })} />
            <div className="grid grid-cols-2 gap-4">
              <TextField label="API Key" type="password" placeholder="sk-..." value={model.api_key} onChange={(value) => update({ api_key: value })} />
              <TextField label="Secret Key（可选）" type="password" placeholder="百度等平台需要" value={model.secret_key} onChange={(value) => update({ secret_key: value })} />
            </div>
            <TextField label="Model ID" placeholder="模型标识符" value={model.model_id} onChange={(value) => update({ model_id: value })} />

            <Separator />
            <div className="grid grid-cols-3 gap-4">
              <NumberField label="超时时间 (ms)" value={model.timeout_ms || 30000} onChange={(value) => update({ timeout_ms: value })} />
              <NumberField label="最大Token" value={model.max_tokens || 4096} onChange={(value) => update({ max_tokens: value })} />
              <NumberField label="上下文窗口" value={model.context_window || 8192} onChange={(value) => update({ context_window: value })} />
            </div>

            <div className="flex items-center gap-6">
              <CapabilityCheckbox id="supports_tools" label="支持工具调用" checked={model.supports_tools ?? true} onChange={(checked) => update({ supports_tools: checked })} />
              <CapabilityCheckbox id="supports_streaming" label="支持流式输出" checked={model.supports_streaming ?? true} onChange={(checked) => update({ supports_streaming: checked })} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <NumberField label="输入价格 (元/千Token)" value={model.input_price || 0} step="0.001" onChange={(value) => update({ input_price: value })} />
              <NumberField label="输出价格 (元/千Token)" value={model.output_price || 0} step="0.001" onChange={(value) => update({ output_price: value })} />
            </div>

            {isEditing && model.id && (
              <div className="flex items-center gap-3">
                <Button variant="outline" size="sm" onClick={() => model.id && onTest(model.id)} disabled={testingId === model.id}>
                  {testingId === model.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <TestTube className="mr-2 h-4 w-4" />}
                  测试连通性
                </Button>
                {testResult && (
                  <span className={cn("flex items-center gap-1 text-sm", testResult.success ? "text-green-600" : "text-red-600")}>
                    {testResult.success ? <><CheckCircle2 className="h-4 w-4" /> 连通成功 ({testResult.latency_ms}ms)</> : <><XCircle className="h-4 w-4" /> 连通失败</>}
                  </span>
                )}
              </div>
            )}
          </div>
        </ScrollArea>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={onSave} disabled={isSaving}>
            {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function TextField({ label, value, onChange, ...inputProps }: { label: string; value?: string | null; onChange: (value: string) => void } & Omit<React.ComponentProps<typeof Input>, "value" | "onChange">) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Input {...inputProps} value={value || ""} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

function NumberField({ label, value, onChange, step }: { label: string; value: number; onChange: (value: number) => void; step?: string }) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Input type="number" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </div>
  );
}

function CapabilityCheckbox({ id, label, checked, onChange }: { id: string; label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <div className="flex items-center gap-2">
      <Checkbox id={id} checked={checked} onCheckedChange={(value) => onChange(Boolean(value))} />
      <Label htmlFor={id} className="text-sm">{label}</Label>
    </div>
  );
}
