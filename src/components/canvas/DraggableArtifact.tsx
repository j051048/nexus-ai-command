/**
 * DraggableArtifact — AI 生成内容的可拖拽容器
 * 使用 HTML5 Drag and Drop API，不引入额外依赖
 */

import React, { useCallback, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { GripVertical } from 'lucide-react';

export interface ArtifactData {
  id: string;
  type: 'chart' | 'card' | 'table' | 'text' | 'image';
  title: string;
  content: unknown;
  source: string;
}

interface DraggableArtifactProps {
  artifact: ArtifactData;
  children: React.ReactNode;
  className?: string;
  disabled?: boolean;
}

/** MIME type 用于 drag/drop 数据传递 */
export const ARTIFACT_MIME = 'application/x-nexus-artifact';

export function DraggableArtifact({
  artifact,
  children,
  className,
  disabled = false,
}: DraggableArtifactProps) {
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<HTMLDivElement>(null);

  const handleDragStart = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      if (disabled) {
        e.preventDefault();
        return;
      }

      // 设置拖拽数据
      e.dataTransfer.setData(ARTIFACT_MIME, JSON.stringify(artifact));
      e.dataTransfer.setData('text/plain', artifact.title);
      e.dataTransfer.effectAllowed = 'move';

      // 创建拖拽预览图像
      if (dragRef.current) {
        const rect = dragRef.current.getBoundingClientRect();
        e.dataTransfer.setDragImage(
          dragRef.current,
          rect.width / 2,
          20,
        );
      }

      setIsDragging(true);
    },
    [artifact, disabled],
  );

  const handleDragEnd = useCallback(() => {
    setIsDragging(false);
  }, []);

  return (
    <div
      ref={dragRef}
      draggable={!disabled}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      className={cn(
        'relative group rounded-lg transition-all duration-200',
        !disabled && 'cursor-grab active:cursor-grabbing',
        isDragging && 'opacity-50 scale-[0.98] ring-2 ring-primary/30',
        className,
      )}
    >
      {/* 拖拽手柄 */}
      {!disabled && (
        <div
          className={cn(
            'absolute top-2 left-2 z-10 p-1 rounded bg-background/80 backdrop-blur-sm',
            'opacity-0 group-hover:opacity-100 transition-opacity duration-150',
            'flex items-center gap-0.5 text-muted-foreground',
          )}
        >
          <GripVertical className="w-3.5 h-3.5" />
          <span className="text-[10px] font-medium">拖拽</span>
        </div>
      )}

      {children}
    </div>
  );
}

export default DraggableArtifact;
