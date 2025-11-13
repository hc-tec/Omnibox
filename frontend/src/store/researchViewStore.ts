/**
 * 研究视图 Store
 *
 * 管理专属研究视图的状态：
 * - 研究任务信息
 * - 研究步骤进度
 * - 数据面板列表
 * - 分析结果列表
 * - WebSocket 连接状态
 */

import { defineStore } from "pinia";
import { ref, computed } from "vue";
import type { PanelPayload, DataBlock } from "@/shared/types/panel";

/**
 * 研究步骤状态
 */
export type ResearchStepStatus = "pending" | "processing" | "success" | "error";

/**
 * 研究步骤类型
 */
export type ResearchStepType = "planning" | "data_fetch" | "analysis";

/**
 * 研究步骤
 */
export interface ResearchStep {
  step_id: string;
  step_type: ResearchStepType;
  action: string;
  status: ResearchStepStatus;
  details?: Record<string, any>;
  timestamp: string;
}

/**
 * 研究面板数据
 */
export interface ResearchPanel {
  step_id: string;
  step_index?: number;
  source_query: string;
  panel_payload: PanelPayload;
  data_blocks: Record<string, DataBlock>;
  timestamp: string;
}

/**
 * 研究分析结果
 */
export interface ResearchAnalysis {
  step_id: string;
  step_index?: number;
  analysis_text: string;
  is_complete: boolean;
  timestamp: string;
}

/**
 * 研究任务状态
 */
export type ResearchTaskStatus = "pending" | "planning" | "running" | "completed" | "error";

/**
 * 研究视图状态
 */
export interface ResearchViewState {
  // 任务信息
  task_id: string | null;
  query: string | null;
  status: ResearchTaskStatus;
  error_message: string | null;

  // 执行计划
  plan: {
    reasoning: string;
    sub_queries: Array<{
      query: string;
      task_type: string;
      datasource: string | null;
    }>;
    estimated_time: number | null;
  } | null;

  // 研究步骤
  steps: ResearchStep[];

  // 数据面板
  panels: ResearchPanel[];

  // 分析结果
  analyses: ResearchAnalysis[];

  // WebSocket 连接状态
  ws_connected: boolean;
  ws_connecting: boolean;

  // 时间统计
  start_time: string | null;
  end_time: string | null;
  total_time: number | null;
}

export const useResearchViewStore = defineStore("researchView", () => {
  const state = ref<ResearchViewState>({
    task_id: null,
    query: null,
    status: "pending",
    error_message: null,
    plan: null,
    steps: [],
    panels: [],
    analyses: [],
    ws_connected: false,
    ws_connecting: false,
    start_time: null,
    end_time: null,
    total_time: null,
  });

  // ========== 计算属性 ==========

  const isActive = computed(() => {
    return state.value.status === "planning" || state.value.status === "running";
  });

  const isCompleted = computed(() => {
    return state.value.status === "completed" || state.value.status === "error";
  });

  const hasError = computed(() => {
    return state.value.status === "error";
  });

  const successStepsCount = computed(() => {
    return state.value.steps.filter((s) => s.status === "success").length;
  });

  const errorStepsCount = computed(() => {
    return state.value.steps.filter((s) => s.status === "error").length;
  });

  const progressPercentage = computed(() => {
    if (state.value.steps.length === 0) return 0;
    const completedSteps = state.value.steps.filter(
      (s) => s.status === "success" || s.status === "error"
    ).length;
    return Math.round((completedSteps / state.value.steps.length) * 100);
  });

  // ========== Actions ==========

  /**
   * 初始化研究任务
   */
  function initializeTask(taskId: string, query: string) {
    state.value.task_id = taskId;
    state.value.query = query;
    state.value.status = "pending";
    state.value.error_message = null;
    state.value.plan = null;
    state.value.steps = [];
    state.value.panels = [];
    state.value.analyses = [];
    state.value.start_time = new Date().toISOString();
    state.value.end_time = null;
    state.value.total_time = null;
  }

  /**
   * 设置 WebSocket 连接状态
   */
  function setWebSocketConnecting(connecting: boolean) {
    state.value.ws_connecting = connecting;
  }

  /**
   * 设置 WebSocket 已连接
   */
  function setWebSocketConnected(connected: boolean) {
    state.value.ws_connected = connected;
    if (connected) {
      state.value.ws_connecting = false;
    }
  }

  /**
   * 处理研究开始消息
   */
  function handleResearchStart(message: {
    plan: ResearchViewState["plan"];
  }) {
    state.value.status = "planning";
    state.value.plan = message.plan;
  }

  /**
   * 处理研究步骤消息
   */
  function handleResearchStep(step: ResearchStep) {
    const existingIndex = state.value.steps.findIndex(
      (s) => s.step_id === step.step_id
    );

    if (existingIndex >= 0) {
      // 更新现有步骤
      state.value.steps[existingIndex] = step;
    } else {
      // 添加新步骤
      state.value.steps.push(step);
    }

    // 更新任务状态
    if (state.value.status === "planning" && step.step_type !== "planning") {
      state.value.status = "running";
    }
  }

  /**
   * 处理研究面板消息
   */
  function handleResearchPanel(panel: ResearchPanel) {
    state.value.panels.push({
      ...panel,
      data_blocks: panel.data_blocks ?? {},
    });
  }

  /**
   * 处理研究分析消息
   */
  function handleResearchAnalysis(analysis: ResearchAnalysis) {
    // 如果是增量更新（is_complete = false），更新现有分析
    // 如果是完整分析（is_complete = true），添加新分析或替换现有分析
    const existingIndex = state.value.analyses.findIndex(
      (a) => a.step_id === analysis.step_id
    );

    if (existingIndex >= 0) {
      if (analysis.is_complete) {
        // 完整分析，替换
        state.value.analyses[existingIndex] = analysis;
      } else {
        // 增量更新，追加文本
        state.value.analyses[existingIndex].analysis_text += analysis.analysis_text;
        state.value.analyses[existingIndex].timestamp = analysis.timestamp;
      }
    } else {
      // 新分析
      state.value.analyses.push(analysis);
    }
  }

  /**
   * 处理研究完成消息
   */
  function handleResearchComplete(message: {
    success: boolean;
    total_time: number;
    message: string;
    summary?: string;
  }) {
    state.value.status = message.success ? "completed" : "error";
    state.value.end_time = new Date().toISOString();
    state.value.total_time = message.total_time;

    if (!message.success) {
      state.value.error_message = message.message;
    }
  }

  /**
   * 处理研究错误消息
   */
  function handleResearchError(message: {
    error_code: string;
    error_message: string;
  }) {
    state.value.status = "error";
    state.value.error_message = `[${message.error_code}] ${message.error_message}`;
    state.value.end_time = new Date().toISOString();
  }

  /**
   * 重置研究视图
   */
  function reset() {
    state.value.task_id = null;
    state.value.query = null;
    state.value.status = "pending";
    state.value.error_message = null;
    state.value.plan = null;
    state.value.steps = [];
    state.value.panels = [];
    state.value.analyses = [];
    state.value.ws_connected = false;
    state.value.ws_connecting = false;
    state.value.start_time = null;
    state.value.end_time = null;
    state.value.total_time = null;
  }

  return {
    state,
    isActive,
    isCompleted,
    hasError,
    successStepsCount,
    errorStepsCount,
    progressPercentage,
    initializeTask,
    setWebSocketConnecting,
    setWebSocketConnected,
    handleResearchStart,
    handleResearchStep,
    handleResearchPanel,
    handleResearchAnalysis,
    handleResearchComplete,
    handleResearchError,
    reset,
  };
});
