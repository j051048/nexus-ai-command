import type { Dispatch, SetStateAction } from "react";
import { Loader2 } from "lucide-react";

import { SCENES } from "@/components/vmd/SceneSelector";
import { VMDTaskDomainFields } from "@/components/vmd/VMDTaskDomainFields";
import { Button } from "@/components/ui/button";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { InstrumentLineCode } from "@/config/growthOperatingModel";

import { VMD_TASK_PRIORITY_CONFIG } from "./vmdTaskConfig";

interface VMDCreateTaskDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  setTitle: Dispatch<SetStateAction<string>>;
  description: string;
  setDescription: Dispatch<SetStateAction<string>>;
  scene: string;
  setScene: Dispatch<SetStateAction<string>>;
  priority: string;
  setPriority: Dispatch<SetStateAction<string>>;
  deadline: string;
  setDeadline: Dispatch<SetStateAction<string>>;
  instrumentLine: InstrumentLineCode | "unclassified";
  setInstrumentLine: Dispatch<SetStateAction<InstrumentLineCode | "unclassified">>;
  applicationField: string;
  setApplicationField: Dispatch<SetStateAction<string>>;
  productModels: string;
  setProductModels: Dispatch<SetStateAction<string>>;
  onCreate: () => void;
  isPending: boolean;
}

export function VMDCreateTaskDialog({
  open,
  onOpenChange,
  title,
  setTitle,
  description,
  setDescription,
  scene,
  setScene,
  priority,
  setPriority,
  deadline,
  setDeadline,
  instrumentLine,
  setInstrumentLine,
  applicationField,
  setApplicationField,
  productModels,
  setProductModels,
  onCreate,
  isPending,
}: VMDCreateTaskDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>创建新任务</DialogTitle>
          <DialogDescription>描述您的营销需求，AI Agent 将自动规划执行方案</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="task-title">任务标题</Label>
            <Input id="task-title" placeholder="例如：Q2新品上市全案策划" value={title} onChange={(event) => setTitle(event.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="task-desc">任务描述</Label>
            <Textarea id="task-desc" placeholder="用自然语言描述您的需求，AI 将自动拆解为可执行子任务..." rows={4} value={description} onChange={(event) => setDescription(event.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>场景类型</Label>
              <Select value={scene} onValueChange={setScene}>
                <SelectTrigger><SelectValue placeholder="选择场景" /></SelectTrigger>
                <SelectContent>
                  {SCENES.map((item) => <SelectItem key={item.code} value={item.code}>{item.icon} {item.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>优先级</Label>
              <Select value={priority} onValueChange={setPriority}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(VMD_TASK_PRIORITY_CONFIG).map(([value, config]) => <SelectItem key={value} value={value}>{config.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <VMDTaskDomainFields
            instrumentLine={instrumentLine}
            applicationField={applicationField}
            productModels={productModels}
            onInstrumentLineChange={setInstrumentLine}
            onApplicationFieldChange={setApplicationField}
            onProductModelsChange={setProductModels}
          />
          <div className="space-y-2">
            <Label htmlFor="task-deadline">截止日期（可选）</Label>
            <Input id="task-deadline" type="date" value={deadline} onChange={(event) => setDeadline(event.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={onCreate} disabled={isPending}>
            {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            创建任务
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
