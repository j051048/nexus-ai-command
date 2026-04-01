import { AlertTriangle } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';

interface ErrorDialogProps {
  error: { message: string; details?: any } | null;
  onRetry?: () => void;
  onClose: () => void;
}

export function ErrorDialog({ error, onRetry, onClose }: ErrorDialogProps) {
  return (
    <Dialog open={!!error} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="w-5 h-5" />
            操作失败
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <p className="text-sm">{error?.message}</p>
          {error?.details && (
            <Collapsible>
              <CollapsibleTrigger className="text-xs text-muted-foreground hover:text-foreground">
                查看详情 ↓
              </CollapsibleTrigger>
              <CollapsibleContent>
                <pre className="mt-2 p-3 bg-muted rounded text-xs overflow-auto max-h-40">
                  {JSON.stringify(error.details, null, 2)}
                </pre>
              </CollapsibleContent>
            </Collapsible>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          {onRetry && <Button onClick={onRetry}>重试</Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
