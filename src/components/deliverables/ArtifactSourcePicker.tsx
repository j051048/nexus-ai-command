import { useEffect, useMemo, useState } from 'react';
import { BookOpen, CheckCircle2, Loader2 } from 'lucide-react';

import { Checkbox } from '@/components/ui/checkbox';
import {
  listArtifactSourceDocuments,
  type ArtifactSourceDocument,
} from '@/features/deliverables/artifactApi';

interface ArtifactSourcePickerProps {
  selected: string[];
  onChange: (selected: string[]) => void;
}

function isUsable(document: ArtifactSourceDocument) {
  return ['ready', 'completed'].includes(document.status || '')
    && document.review_status !== 'expired';
}

export function ArtifactSourcePicker({ selected, onChange }: ArtifactSourcePickerProps) {
  const [documents, setDocuments] = useState<ArtifactSourceDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    void listArtifactSourceDocuments()
      .then((rows) => {
        if (active) setDocuments(rows.filter(isUsable).slice(0, 30));
      })
      .catch(() => {
        if (active) setFailed(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const selectedNames = useMemo(
    () => documents.filter((document) => selected.includes(document.id)).map((document) => document.name),
    [documents, selected],
  );

  const toggle = (documentId: string, checked: boolean) => {
    onChange(checked
      ? [...new Set([...selected, documentId])]
      : selected.filter((item) => item !== documentId));
  };

  return (
    <details className="group border-b px-6 py-4">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-xs font-medium">
        <span className="flex items-center gap-2">
          <BookOpen className="h-3.5 w-3.5 text-primary" />
          指定企业资料
          <span className="font-normal text-muted-foreground">可选，AI 仍会自动检索</span>
        </span>
        <span className="text-muted-foreground">
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : selected.length ? `已选 ${selected.length} 份` : '展开选择'}
        </span>
      </summary>

      <div className="mt-4 max-h-44 space-y-1 overflow-y-auto pr-1">
        {failed ? (
          <p className="text-xs text-muted-foreground">资料列表暂时不可用，系统仍会按需求自动检索。</p>
        ) : documents.length ? documents.map((document) => (
          <label key={document.id} className="flex cursor-pointer items-center gap-3 rounded px-2 py-2 text-xs hover:bg-muted/50">
            <Checkbox
              checked={selected.includes(document.id)}
              onCheckedChange={(value) => toggle(document.id, value === true)}
              aria-label={`选择资料 ${document.name}`}
            />
            <span className="min-w-0 flex-1 truncate">{document.name}</span>
            {document.review_status === 'verified' && (
              <span className="flex items-center gap-1 text-[11px] text-emerald-700">
                <CheckCircle2 className="h-3 w-3" />可信
              </span>
            )}
          </label>
        )) : !loading ? (
          <p className="text-xs text-muted-foreground">暂无已完成索引的企业资料。</p>
        ) : null}
      </div>

      {selectedNames.length > 0 && (
        <p className="mt-3 truncate text-[11px] text-muted-foreground" title={selectedNames.join('、')}>
          本次优先引用：{selectedNames.join('、')}
        </p>
      )}
    </details>
  );
}
