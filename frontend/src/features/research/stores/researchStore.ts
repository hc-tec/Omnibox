import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { ResearchTask, QueryMode, ResearchResponse, ExecutionStep, ResearchPreview } from '../types/researchTypes';

// 常量定义
const MAX_PREVIEW_CARDS = 5; // 最多保留的预览卡片数量

export const useResearchStore = defineStore('research', () => {
  // 状态
  const tasks = ref<Map<string, ResearchTask>>(new Map());
  const activeTaskId = ref<string | null>(null);
  const queryMode = ref<QueryMode>('auto');

  // 计算属性
  const activeTasks = computed(() =>
    Array.from(tasks.value.values()).filter(
      t => t.status === 'processing' || t.status === 'human_in_loop'
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
  function createTask(query: string, mode: QueryMode, presetTaskId?: string): string {
    const taskId = presetTaskId ?? `task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const task: ResearchTask = {
      task_id: taskId,
      query,
      mode,
      status: 'processing',
      execution_steps: [],
      previews: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    tasks.value.set(taskId, task);
    activeTaskId.value = taskId;
    return taskId;
  }

  function ensureTask(taskId: string, query: string, mode: QueryMode = 'research'): string {
    if (tasks.value.has(taskId)) {
      return taskId;
    }
    return createTask(query, mode, taskId);
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
      task.updated_at = new Date().toISOString();
    }
  }

  function appendPreview(taskId: string, payload: any) {
    const task = tasks.value.get(taskId);
    if (!task) return;
    const list = task.previews ?? (task.previews = []);
    const incoming = Array.isArray(payload?.previews) ? payload.previews : (payload ? [payload] : []);
    incoming.forEach((entry: any, index) => {
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
    appendPreview,
  };
});
