import { useState, useCallback } from 'react';

interface ConfirmOptions {
  title: string;
  description: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'default' | 'destructive';
}

interface ConfirmState extends ConfirmOptions {
  isOpen: boolean;
  resolve: ((confirmed: boolean) => void) | null;
}

/**
 * Hook for imperative confirmation dialogs.
 *
 * Usage:
 *   const { confirm, ConfirmDialogProps } = useConfirmDialog();
 *
 *   const handleDelete = async () => {
 *     const ok = await confirm({
 *       title: '确认删除',
 *       description: '此操作不可撤销，确定要继续吗？',
 *       variant: 'destructive',
 *     });
 *     if (ok) { ... }
 *   };
 *
 *   return <><ConfirmDialog {...ConfirmDialogProps} />...</>;
 */
export function useConfirmDialog() {
  const [state, setState] = useState<ConfirmState>({
    isOpen: false,
    title: '',
    description: '',
    resolve: null,
  });

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      setState({
        isOpen: true,
        resolve,
        ...options,
      });
    });
  }, []);

  const handleConfirm = useCallback(() => {
    state.resolve?.(true);
    setState((prev) => ({ ...prev, isOpen: false, resolve: null }));
  }, [state.resolve]);

  const handleCancel = useCallback(() => {
    state.resolve?.(false);
    setState((prev) => ({ ...prev, isOpen: false, resolve: null }));
  }, [state.resolve]);

  return {
    confirm,
    ConfirmDialogProps: {
      isOpen: state.isOpen,
      title: state.title,
      description: state.description,
      confirmText: state.confirmText || '确认',
      cancelText: state.cancelText || '取消',
      variant: state.variant || 'default',
      onConfirm: handleConfirm,
      onCancel: handleCancel,
    },
  };
}
