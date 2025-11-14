import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type {
  ResearchTask,
  QueryMode,
  ResearchResponse,
  ExecutionStep,
  ResearchPreview,
  ResearchTaskStatus,
} from '../types/researchTypes';

// 常量定义
const MAX_PREVIEW_CARDS = 5; // 最多保留的预览卡片数量

interface CreateTaskOptions {
  status?: ResearchTaskStatus;
  metadata?: ResearchTask["metadata"];
  autoDetected?: boolean;
}

export const useResearchStore = defineStore('research', () => {
  // 状态
  const tasks = ref<Map<string, ResearchTask>>(new Map());
  const activeTaskId = ref<string | null>(null);
  const queryMode = ref<QueryMode>('auto');

  // 计算属性
  /**
   * 需要在主界面显示的任务
   * 包括：idle（待启动的建议任务）、processing（处理中）、human_in_loop（等待人工输入）、completed（已完成）
   */
  const activeTasks = computed(() =>
    Array.from(tasks.value.values()).filter(
      t =>
        t.status === 'processing' ||
        t.status === 'human_in_loop' ||
        t.status === 'idle' ||
        t.status === 'completed'
    ).sort((a, b) => {
      // 按状态优先级排序：processing > human_in_loop > idle > completed
      const statusPriority: Record<string, number> = {
        'processing': 1,
        'human_in_loop': 2,
        'idle': 3,
        'completed': 4,
      };
      const priorityDiff = (statusPriority[a.status] || 99) - (statusPriority[b.status] || 99);
      if (priorityDiff !== 0) return priorityDiff;

      // 相同状态按更新时间倒序（最新的在前）
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    })
  );

  /**
   * 正在运行的任务（不包括 idle）
   */
  const runningTasks = computed(() =>
    Array.from(tasks.value.values()).filter(
      t =>
        t.status === 'processing' ||
        t.status === 'human_in_loop'
    )
  );

  const completedTasks = computed(() =>
    Array.from(tasks.value.values()).filter(
      t => t.status === 'completed'
    )
  );

  const pendingHumanTasks = computed(() =>
    Array.from(tasks.value.values()).filter(
      t => t.status === 'human_in_loop'
    )
  );

  const pendingCount = computed(() => pendingHumanTasks.value.length);

  // Actions
  function createTask(query: string, mode: QueryMode, presetTaskId?: string, options?: CreateTaskOptions): string {
    const taskId = presetTaskId ?? `task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const task: ResearchTask = {
      task_id: taskId,
      query,
      mode,
      status: options?.status ?? 'processing',
      execution_steps: [],
      previews: [],
      metadata: options?.metadata,
      auto_detected: options?.autoDetected ?? false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    tasks.value.set(taskId, task);
    activeTaskId.value = taskId;
    return taskId;
  }

  function ensureTask(taskId: string, query: string, mode: QueryMode = 'research', options?: CreateTaskOptions): string {
    if (tasks.value.has(taskId)) {
      return taskId;
    }
    return createTask(query, mode, taskId, options);
  }

  function updateTaskStep(taskId: string, stepData: any) {
    const task = tasks.value.get(taskId);
    if (task) {
      const step: ExecutionStep = {
        step_id: stepData?.step_id ?? stepData?.stepId ?? task.execution_steps.length + 1,
        node: stepData?.node ?? stepData?.node_name ?? 'unknown',
        action: stepData?.action ?? '',
        status: stepData?.status ?? 'success',
        timestamp: stepData?.timestamp ?? new Date().toISOString(),
      };
      task.execution_steps.push(step);
      task.updated_at = new Date().toISOString();
    }
  }

  function setTaskHumanRequest(taskId: string, message: string) {
    const task = tasks.value.get(taskId);
    if (task) {
      task.status = 'human_in_loop';
      task.human_request = {
        message,
        timestamp: new Date().toISOString(),
      };
      task.updated_at = new Date().toISOString();
    }
  }

  function completeTask(taskId: string, report: string, metadata?: ResearchResponse["metadata"]) {
    const task = tasks.value.get(taskId);
    if (task) {
      if (metadata) {
        task.metadata = metadata;
        if (metadata.execution_steps) {
          task.execution_steps = metadata.execution_steps;
        }
      }
      task.status = 'completed';
      task.final_report = report;
      task.updated_at = new Date().toISOString();
    }
  }

  function setTaskError(taskId: string, error: string) {
    const task = tasks.value.get(taskId);
    if (task) {
      task.status = 'error';
      task.error = error;
      task.updated_at = new Date().toISOString();
    }
  }

  function deleteTask(taskId: string) {
    tasks.value.delete(taskId);
    if (activeTaskId.value === taskId) {
      activeTaskId.value = null;
    }
  }

  function clearCompletedTasks() {
    completedTasks.value.forEach(task => {
      tasks.value.delete(task.task_id);
    });
  }

  function markTaskProcessing(taskId: string) {
    const task = tasks.value.get(taskId);
    if (task) {
      task.status = 'processing';
      task.human_request = undefined;
      // auto_detected 是任务创建来源的历史事实，不应该因为状态转换而改变
      task.updated_at = new Date().toISOString();
    }
  }

  function getTask(taskId: string): ResearchTask | undefined {
    return tasks.value.get(taskId);
  }

  /**
   * 更新任务的 metadata（不会修改任务状态）
   */
  function updateTaskMetadata(taskId: string, metadata: ResearchTask["metadata"]) {
    const task = tasks.value.get(taskId);
    if (!task) return;

    task.metadata = metadata;
    task.updated_at = new Date().toISOString();
  }

  function appendPreview(taskId: string, payload: any) {
    const task = tasks.value.get(taskId);
    if (!task) return;
    const list = task.previews ?? (task.previews = []);
    const incoming = Array.isArray(payload?.previews) ? payload.previews : (payload ? [payload] : []);
    incoming.forEach((entry: any, index: number) => {
      const normalized: ResearchPreview = {
        preview_id: entry?.preview_id || `${taskId}-${Date.now()}-${index}`,
        title: entry?.title || task.query,
        items: Array.isArray(entry?.items) ? entry.items : [],
        generated_path: entry?.generated_path,
        source: entry?.source ?? null,
        created_at: new Date().toISOString(),
      };
      list.unshift(normalized);
    });
    if (list.length > MAX_PREVIEW_CARDS) {
      list.splice(MAX_PREVIEW_CARDS);
    }
    task.updated_at = new Date().toISOString();
  }

  return {
    // State
    tasks,
    activeTaskId,
    queryMode,
    // Computed
    activeTasks,
    runningTasks,
    completedTasks,
    pendingHumanTasks,
    pendingCount,
    // Actions
    ensureTask,
    createTask,
    updateTaskStep,
    setTaskHumanRequest,
    completeTask,
    setTaskError,
    deleteTask,
    clearCompletedTasks,
    markTaskProcessing,
    getTask,
    updateTaskMetadata,
    appendPreview,
  };
});
