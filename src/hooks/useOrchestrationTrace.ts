import { useState, useCallback } from 'react';

export interface OrchestrationTask {
  subTaskId: string;
  agentCode: string;
  title: string;
  layerIdx: number;
  status: 'pending' | 'running' | 'completed' | 'degraded' | 'failed';
  durationMs?: number;
}

export interface OrchestrationLayer {
  layerIdx: number;
  totalLayers: number;
  tasks: Array<{ sub_task_id: string; agent_code: string; title: string }>;
}

export interface OrchestrationTrace {
  isActive: boolean;
  layers: OrchestrationLayer[];
  tasks: Map<string, OrchestrationTask>;
  completedCount: number;
  failedCount: number;
  totalTasks: number;
}

export interface OrchestrationEvent {
  type: 'layer_start' | 'task_end' | 'complete';
  layer_idx?: number;
  total_layers?: number;
  tasks?: Array<{ sub_task_id: string; agent_code: string; title: string }>;
  sub_task_id?: string;
  agent_code?: string;
  title?: string;
  status?: string;
  duration_ms?: number;
  total_tasks?: number;
  completed?: number;
  failed?: number;
}

export function useOrchestrationTrace() {
  const [orchestration, setOrchestration] = useState<OrchestrationTrace>({
    isActive: false,
    layers: [],
    tasks: new Map(),
    completedCount: 0,
    failedCount: 0,
    totalTasks: 0,
  });

  const handleOrchestrationEvent = useCallback((event: OrchestrationEvent) => {
    setOrchestration(prev => {
      const next = { ...prev, tasks: new Map(prev.tasks) };

      switch (event.type) {
        case 'layer_start': {
          next.isActive = true;
          const layer: OrchestrationLayer = {
            layerIdx: event.layer_idx ?? 0,
            totalLayers: event.total_layers ?? 1,
            tasks: event.tasks ?? [],
          };
          next.layers = [...prev.layers, layer];
          // Mark all tasks in this layer as running
          for (const t of layer.tasks) {
            if (!next.tasks.has(t.sub_task_id)) {
              next.tasks.set(t.sub_task_id, {
                subTaskId: t.sub_task_id,
                agentCode: t.agent_code,
                title: t.title,
                layerIdx: layer.layerIdx,
                status: 'running',
              });
              next.totalTasks++;
            }
          }
          break;
        }
        case 'task_end': {
          const taskId = event.sub_task_id ?? '';
          const existing = next.tasks.get(taskId);
          const status = (event.status ?? 'completed') as OrchestrationTask['status'];
          if (existing) {
            next.tasks.set(taskId, { ...existing, status, durationMs: event.duration_ms });
          } else {
            next.tasks.set(taskId, {
              subTaskId: taskId,
              agentCode: event.agent_code ?? '',
              title: event.title ?? '',
              layerIdx: event.layer_idx ?? 0,
              status,
              durationMs: event.duration_ms,
            });
          }
          if (status === 'completed' || status === 'degraded') next.completedCount++;
          if (status === 'failed') next.failedCount++;
          break;
        }
        case 'complete': {
          next.isActive = false;
          break;
        }
      }

      return next;
    });
  }, []);

  const resetOrchestration = useCallback(() => {
    setOrchestration({
      isActive: false,
      layers: [],
      tasks: new Map(),
      completedCount: 0,
      failedCount: 0,
      totalTasks: 0,
    });
  }, []);

  return { orchestration, handleOrchestrationEvent, resetOrchestration };
}
