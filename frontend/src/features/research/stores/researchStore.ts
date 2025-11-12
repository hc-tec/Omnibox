import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { ResearchTask, QueryMode, ResearchResponse } from '../types/researchTypes';

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
  function createTask(query: string, mode: QueryMode): string {
    const taskId = `task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const task: ResearchTask = {
      task_id: taskId,
      query,
      mode,
      status: 'processing',
      execution_steps: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    tasks.value.set(taskId, task);
    activeTaskId.value = taskId;
    return taskId;
  }

  function updateTaskStep(taskId: string, step: any) {
    const task = tasks.value.get(taskId);
    if (task) {
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
    createTask,
    updateTaskStep,
    setTaskHumanRequest,
    completeTask,
    setTaskError,
    deleteTask,
    clearCompletedTasks,
  };
});
