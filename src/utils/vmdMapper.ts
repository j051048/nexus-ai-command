/**
 * VMD Task Data Mapper
 * 统一规范化后端 API 返回的 VMD 任务数据，消除字段命名差异和类型不一致
 */

import type { VMDTask } from '@/hooks/useVMD';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyData = Record<string, any>;

// ─── Status 映射 ────────────────────────────────────────────

const STATUS_MAP: Record<string, VMDTask['status']> = {
  pending: 'pending',
  planning: 'planning',
  executing: 'executing',
  reviewing: 'reviewing',
  done: 'done',
  failed: 'failed',
  // 兼容后端可能使用的别名
  running: 'executing',
  completed: 'done',
  success: 'done',
  error: 'failed',
  cancelled: 'failed',
};

function normalizeStatus(raw: string | undefined | null): VMDTask['status'] {
  if (!raw) return 'pending';
  return STATUS_MAP[raw.toLowerCase()] || 'pending';
}

// ─── Progress 规范化 ────────────────────────────────────────

/**
 * 将后端返回的 progress 值规范化为 0-100 的数字
 * 后端可能返回：
 *  - number: 直接使用
 *  - object: { percentage: number } 或 { completed: number, total: number }
 *  - string: "75" 或 "75%"
 *  - undefined/null: 默认 0
 */
function normalizeProgress(raw: unknown): number {
  if (raw === null || raw === undefined) return 0;

  if (typeof raw === 'number') {
    return Math.min(100, Math.max(0, raw));
  }

  if (typeof raw === 'string') {
    const num = parseFloat(raw.replace('%', ''));
    return isNaN(num) ? 0 : Math.min(100, Math.max(0, num));
  }

  if (typeof raw === 'object' && raw !== null) {
    const obj = raw as AnyData;
    // { percentage: 75 }
    if (obj.percentage != null) {
      return normalizeProgress(obj.percentage);
    }
    // { completed: 3, total: 4 }
    if (obj.completed != null && obj.total != null && obj.total > 0) {
      return Math.round((obj.completed / obj.total) * 100);
    }
    // { total_sub_tasks: 4, completed: 3 }
    if (obj.total_sub_tasks != null && obj.completed != null && obj.total_sub_tasks > 0) {
      return Math.round((obj.completed / obj.total_sub_tasks) * 100);
    }
  }

  return 0;
}

// ─── 时间字段规范化 ──────────────────────────────────────────

/**
 * 规范化时间字段，兼容 created_at / create_time 等命名差异
 */
function normalizeTimestamp(...candidates: (string | undefined | null)[]): string {
  for (const candidate of candidates) {
    if (candidate && candidate.trim()) return candidate;
  }
  return '';
}

// ─── 主映射函数 ──────────────────────────────────────────────

/**
 * 将单个后端 API 原始数据映射为前端 VMDTask 类型
 */
export function mapVMDTaskFromAPI(raw: AnyData): VMDTask {
  return {
    id: raw.id || '',
    task_code: raw.task_code || '',
    title: raw.title || '',
    description: raw.description || '',
    scene_code: raw.scene_code || '',
    status: normalizeStatus(raw.status),
    priority: raw.priority || 'normal',
    progress: normalizeProgress(raw.progress),
    deadline: raw.deadline || null,
    created_at: normalizeTimestamp(raw.created_at, raw.create_time),
    updated_at: normalizeTimestamp(raw.updated_at, raw.update_time),
    sub_tasks: raw.sub_tasks,
  };
}

/**
 * 将后端 API 返回的任务列表批量映射
 */
export function mapVMDTaskListFromAPI(data: AnyData[]): VMDTask[] {
  if (!Array.isArray(data)) return [];
  return data.map(mapVMDTaskFromAPI);
}

/**
 * 将任务详情（含 progress 对象）映射为 VMDTask
 * 后端详情接口返回格式: { task: {...}, sub_tasks: [...], progress: { percentage, ... } }
 */
export function mapVMDTaskDetailFromAPI(raw: AnyData): VMDTask {
  const task = raw.task || raw;
  const progressObj = raw.progress;

  return {
    ...mapVMDTaskFromAPI(task),
    progress: progressObj ? normalizeProgress(progressObj) : normalizeProgress(task.progress),
    sub_tasks: raw.sub_tasks || task.sub_tasks || [],
  };
}
