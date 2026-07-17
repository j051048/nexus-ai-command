import { FlaskConical } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  SCIENTIFIC_INSTRUMENT_LINES,
  getInstrumentLine,
  type InstrumentLineCode,
} from "@/config/growthOperatingModel";

interface VMDTaskDomainFieldsProps {
  instrumentLine: InstrumentLineCode | "unclassified";
  applicationField: string;
  productModels: string;
  onInstrumentLineChange: (value: InstrumentLineCode | "unclassified") => void;
  onApplicationFieldChange: (value: string) => void;
  onProductModelsChange: (value: string) => void;
}

export function VMDTaskDomainFields({
  instrumentLine,
  applicationField,
  productModels,
  onInstrumentLineChange,
  onApplicationFieldChange,
  onProductModelsChange,
}: VMDTaskDomainFieldsProps) {
  const selected = getInstrumentLine(instrumentLine);

  return (
    <div className="space-y-3 border-y border-border/70 py-4">
      <div className="flex items-start gap-2">
        <FlaskConical className="mt-0.5 h-4 w-4 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium">行业上下文</p>
          <p className="text-xs text-muted-foreground">
            用于选择证据标准、决策角色和投标检查项，不会改变原有执行流程。
          </p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-2">
          <Label>产品线</Label>
          <Select
            value={instrumentLine}
            onValueChange={(value) =>
              onInstrumentLineChange(value as InstrumentLineCode | "unclassified")
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="选择产品线" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="unclassified">暂不分类</SelectItem>
              {SCIENTIFIC_INSTRUMENT_LINES.map((line) => (
                <SelectItem key={line.code} value={line.code}>
                  {line.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="task-application">应用场景</Label>
          <Input
            id="task-application"
            value={applicationField}
            onChange={(event) => onApplicationFieldChange(event.target.value)}
            placeholder={selected?.description || "如环境检测、半导体失效分析"}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="task-product-models">目标产品或型号</Label>
        <Input
          id="task-product-models"
          value={productModels}
          onChange={(event) => onProductModelsChange(event.target.value)}
          placeholder="多个型号用逗号分隔"
        />
        {selected && (
          <p className="text-xs text-muted-foreground">
            适用方向：{selected.families.slice(0, 4).join("、")}
          </p>
        )}
      </div>
    </div>
  );
}
