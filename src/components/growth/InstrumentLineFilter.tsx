import { FlaskConical } from "lucide-react";
import type { ReactNode } from "react";

import {
  SCIENTIFIC_INSTRUMENT_LINES,
  getInstrumentLine,
  type InstrumentLineCode,
} from "@/config/growthOperatingModel";
import { cn } from "@/lib/utils";

export type InstrumentLineSelection = InstrumentLineCode | "all";

interface InstrumentLineFilterProps {
  value: InstrumentLineSelection;
  onChange: (value: InstrumentLineSelection) => void;
  counts?: Partial<Record<InstrumentLineCode, number>>;
  className?: string;
}

export function InstrumentLineFilter({
  value,
  onChange,
  counts,
  className,
}: InstrumentLineFilterProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-1 overflow-x-auto border-b border-border/70 pb-3",
        className,
      )}
      aria-label="科学仪器产品线"
    >
      <FlaskConical className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
      <LineButton active={value === "all"} onClick={() => onChange("all")}>
        全部产品线
      </LineButton>
      {SCIENTIFIC_INSTRUMENT_LINES.map((line) => (
        <LineButton
          key={line.code}
          active={value === line.code}
          onClick={() => onChange(line.code)}
          count={counts?.[line.code]}
          title={`${line.description}：${line.families.join("、")}`}
        >
          {line.name}
        </LineButton>
      ))}
    </div>
  );
}

function LineButton({
  active,
  children,
  count,
  onClick,
  title,
}: {
  active: boolean;
  children: ReactNode;
  count?: number;
  onClick: () => void;
  title?: string;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={cn(
        "flex h-8 shrink-0 items-center gap-1.5 border-b-2 px-3 text-sm transition-colors",
        active
          ? "border-foreground font-medium text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
      {typeof count === "number" && (
        <span className="text-xs tabular-nums text-muted-foreground">{count}</span>
      )}
    </button>
  );
}

export function InstrumentLineLabel({ code }: { code?: string | null }) {
  const line = getInstrumentLine(code);
  if (!line) return null;
  return (
    <span className="inline-flex items-center text-xs font-medium text-foreground/70">
      {line.name}
    </span>
  );
}
