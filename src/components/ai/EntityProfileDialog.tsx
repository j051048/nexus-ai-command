import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { useEntityProfile } from '@/hooks/useEntityProfile';

interface EntityProfileDialogProps {
  entity: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const typeColors: Record<string, string> = {
  person: 'bg-blue-500/20 text-blue-400',
  company: 'bg-green-500/20 text-green-400',
  concept: 'bg-purple-500/20 text-purple-400',
  product: 'bg-orange-500/20 text-orange-400',
};

export function EntityProfileDialog({ entity, open, onOpenChange }: EntityProfileDialogProps) {
  const { data, isLoading } = useEntityProfile(open ? entity : null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>实体画像</span>
            {entity && <Badge variant="outline">{entity}</Badge>}
          </DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-3 py-4">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ) : !data || data.triple_count === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            暂无该实体的知识图谱数据
          </p>
        ) : (
          <ScrollArea className="max-h-[400px] pr-2">
            {/* Aliases */}
            {data.aliases.length > 0 && (
              <div className="mb-3">
                <p className="mb-1 text-xs text-muted-foreground">别名</p>
                <div className="flex flex-wrap gap-1">
                  {data.aliases.map((a, i) => (
                    <Badge key={i} variant="secondary" className="text-xs">
                      {a.alias === entity ? a.canonical_name : a.alias}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Triples */}
            <p className="mb-2 text-xs text-muted-foreground">
              共 {data.triple_count} 条关系
            </p>
            <div className="space-y-2">
              {data.triples.map((t) => {
                const isSource = t.source_entity.toLowerCase() === entity?.toLowerCase();
                return (
                  <div
                    key={t.id}
                    className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm"
                  >
                    <Badge className={`text-xs ${typeColors[t.source_type] || typeColors.concept}`}>
                      {t.source_entity}
                    </Badge>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      —{t.relationship}→
                    </span>
                    <Badge className={`text-xs ${typeColors[t.destination_type] || typeColors.concept}`}>
                      {t.destination_entity}
                    </Badge>
                    {t.occurrences > 1 && (
                      <span className="ml-auto text-xs text-muted-foreground">
                        ×{t.occurrences}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  );
}
