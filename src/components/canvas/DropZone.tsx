/**
 * DropZone — 接收拖拽 artifact 的放置区域
 */

import React, { useCallback, useState } from 'react';
import { cn } from '@/lib/utils';
import { Plus } from 'lucide-react';
import { ARTIFACT_MIME, type ArtifactData } from './DraggableArtifact';

interface DropZoneProps {
  onDrop: (artifact: ArtifactData) => void;
  children?: React.ReactNode;
  className?: string;
  label?: string;
  /** 是否接受特定类型的 artifact */
  acceptTypes?: ArtifactData['type'][];
}

export function DropZone({
  onDrop,
  children,
  className,
  label = '拖拽 AI 组件到此处',
  acceptTypes,
}: DropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [isInvalid, setIsInvalid] = useState(false);

  const handleDragOver = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();

      // 检查是否携带 artifact 数据
      if (!e.dataTransfer.types.includes(ARTIFACT_MIME)) {
        return;
      }

      e.dataTransfer.dropEffect = 'move';
      setIsDragOver(true);
    },
    [],
  );

  const handleDragEnter = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      if (e.dataTransfer.types.includes(ARTIFACT_MIME)) {
        setIsDragOver(true);
      }
    },
    [],
  );

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    // 只有离开 DropZone 本身时才取消高亮（不是子元素）
    const relatedTarget = e.relatedTarget as Node | null;
    if (e.currentTarget.contains(relatedTarget)) return;

    setIsDragOver(false);
    setIsInvalid(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragOver(false);
      setIsInvalid(false);

      const raw = e.dataTransfer.getData(ARTIFACT_MIME);
      if (!raw) return;

      try {
        const artifact: ArtifactData = JSON.parse(raw);

        // 类型检查
        if (acceptTypes && !acceptTypes.includes(artifact.type)) {
          setIsInvalid(true);
          setTimeout(() => setIsInvalid(false), 1000);
          return;
        }

        onDrop(artifact);
      } catch {
        console.error('Failed to parse dropped artifact data');
      }
    },
    [onDrop, acceptTypes],
  );

  const isEmpty = !children || (Array.isArray(children) && children.length === 0);

  return (
    <div
      onDragOver={handleDragOver}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        'relative rounded-xl border-2 border-dashed transition-all duration-200 min-h-[120px]',
        isDragOver && !isInvalid && 'border-primary bg-primary/5 scale-[1.01] shadow-lg',
        isInvalid && 'border-destructive bg-destructive/5',
        !isDragOver && !isInvalid && 'border-border/50 hover:border-border',
        className,
      )}
    >
      {isEmpty && !isDragOver && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground gap-2">
          <Plus className="w-8 h-8 opacity-30" />
          <span className="text-sm opacity-50">{label}</span>
        </div>
      )}

      {isDragOver && !isInvalid && (
        <div className="absolute inset-0 flex flex-col items-center justify-center z-10 pointer-events-none">
          <div className="px-4 py-2 rounded-lg bg-primary/10 backdrop-blur-sm">
            <span className="text-sm font-medium text-primary">释放以添加</span>
          </div>
        </div>
      )}

      {isInvalid && (
        <div className="absolute inset-0 flex flex-col items-center justify-center z-10 pointer-events-none">
          <div className="px-4 py-2 rounded-lg bg-destructive/10 backdrop-blur-sm">
            <span className="text-sm font-medium text-destructive">不支持该类型</span>
          </div>
        </div>
      )}

      {children && <div className="relative z-0">{children}</div>}
    </div>
  );
}

export default DropZone;
