import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Loader2 } from 'lucide-react';

interface TransferConfirmDialogProps {
  open: boolean;
  name: string;
  targetDeptName: string;
  isPending: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function TransferConfirmDialog({
  open,
  name,
  targetDeptName,
  isPending,
  onConfirm,
  onCancel,
}: TransferConfirmDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>确认调动</AlertDialogTitle>
          <AlertDialogDescription>
            确定将 <span className="font-medium text-foreground">{name}</span> 调动到{' '}
            <span className="font-medium text-foreground">{targetDeptName}</span> 吗？
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel}>取消</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm} disabled={isPending}>
            {isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
            确认调动
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
