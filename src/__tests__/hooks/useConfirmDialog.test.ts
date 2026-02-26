import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';

describe('useConfirmDialog', () => {
  it('should initialize with closed state', () => {
    const { result } = renderHook(() => useConfirmDialog());
    expect(result.current.ConfirmDialogProps.isOpen).toBe(false);
  });

  it('should open dialog on confirm call', async () => {
    const { result } = renderHook(() => useConfirmDialog());

    let confirmPromise: Promise<boolean>;
    act(() => {
      confirmPromise = result.current.confirm({
        title: '测试标题',
        description: '测试描述',
        variant: 'destructive',
      });
    });

    expect(result.current.ConfirmDialogProps.isOpen).toBe(true);
    expect(result.current.ConfirmDialogProps.title).toBe('测试标题');
    expect(result.current.ConfirmDialogProps.description).toBe('测试描述');
    expect(result.current.ConfirmDialogProps.variant).toBe('destructive');
  });

  it('should resolve true on confirm', async () => {
    const { result } = renderHook(() => useConfirmDialog());

    let confirmResult: boolean | undefined;
    act(() => {
      result.current.confirm({
        title: '确认操作',
        description: '确定要继续吗？',
      }).then((v) => { confirmResult = v; });
    });

    act(() => {
      result.current.ConfirmDialogProps.onConfirm();
    });

    // Wait for promise to resolve
    await vi.waitFor(() => {
      expect(confirmResult).toBe(true);
    });
    expect(result.current.ConfirmDialogProps.isOpen).toBe(false);
  });

  it('should resolve false on cancel', async () => {
    const { result } = renderHook(() => useConfirmDialog());

    let confirmResult: boolean | undefined;
    act(() => {
      result.current.confirm({
        title: '确认操作',
        description: '确定要继续吗？',
      }).then((v) => { confirmResult = v; });
    });

    act(() => {
      result.current.ConfirmDialogProps.onCancel();
    });

    await vi.waitFor(() => {
      expect(confirmResult).toBe(false);
    });
    expect(result.current.ConfirmDialogProps.isOpen).toBe(false);
  });

  it('should use default text values', () => {
    const { result } = renderHook(() => useConfirmDialog());

    act(() => {
      result.current.confirm({
        title: '测试',
        description: '描述',
      });
    });

    expect(result.current.ConfirmDialogProps.confirmText).toBe('确认');
    expect(result.current.ConfirmDialogProps.cancelText).toBe('取消');
    expect(result.current.ConfirmDialogProps.variant).toBe('default');
  });

  it('should use custom text values', () => {
    const { result } = renderHook(() => useConfirmDialog());

    act(() => {
      result.current.confirm({
        title: '删除',
        description: '不可恢复',
        confirmText: '删除',
        cancelText: '返回',
        variant: 'destructive',
      });
    });

    expect(result.current.ConfirmDialogProps.confirmText).toBe('删除');
    expect(result.current.ConfirmDialogProps.cancelText).toBe('返回');
  });
});
