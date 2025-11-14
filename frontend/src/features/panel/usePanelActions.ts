import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import { usePanelStore } from "../../store/panelStore";
import type { PanelResponse } from "@/shared/types/panel";
import { useResearchStore } from "@/features/research/stores/researchStore";
import { persistResearchTaskQuery } from "@/features/research/utils/taskStorage";

interface SubmitPayload {
  query: string;
  datasource?: string | null;
  mode?: string;
  client_task_id?: string | null;
}

export interface SubmitResult {
  response: PanelResponse;
  requiresStreaming: boolean;
  taskId?: string;
}

export function usePanelActions(initialQuery = "我想看看bilibili热点") {
  const panelStore = usePanelStore();
  const { state, hasPanel } = storeToRefs(panelStore);
  const researchStore = useResearchStore();
  const { tasks } = storeToRefs(researchStore);
  const query = ref(initialQuery);
  const datasource = ref<string | null>(null);

  const isBusy = computed(() => state.value.loading || state.value.streamLoading);

  const submit = async (payload: SubmitPayload): Promise<SubmitResult> => {
    query.value = payload.query;
    datasource.value = payload.datasource ?? null;
    const response = await panelStore.fetchPanel(
      query.value,
      datasource.value,
      panelStore.getLayoutSnapshot(),
      payload.mode,
      payload.client_task_id ?? null
    );

    // 检查是否需要启动流式研究
    const requiresStreaming = response.metadata?.requires_streaming === true;
    let taskId: string | undefined;

    if (requiresStreaming) {
      // 创建研究任务（processing 状态），不跳转
      taskId = researchStore.createTask(query.value, "research", undefined, {
        status: "processing",
        metadata: response.metadata,
        autoDetected: true,
      });
      persistResearchTaskQuery(taskId, query.value);
    } else {
      // 使用原有的建议逻辑（创建 idle 任务卡片）
      maybeSuggestResearchTask(response, payload);
    }

    return {
      response,
      requiresStreaming,
      taskId,
    };
  };

  const startStream = (payload: { query: string; datasource?: string | null; mode?: string }) => {
    query.value = payload.query;
    datasource.value = payload.datasource ?? null;
    panelStore.connectStream(query.value, datasource.value, panelStore.getLayoutSnapshot(), payload.mode);
  };

  const stopStream = () => {
    panelStore.disconnectStream();
  };

  const reset = () => {
    panelStore.resetPanel();
  };

  /**
   * 根据 Panel 响应判断是否需要建议用户启动研究模式
   *
   * 业务逻辑：
   * 1. 当用户使用 auto 或 simple 模式查询时，如果后端判断为 complex_research 意图
   * 2. 如果提供了 router，则 submit() 会自动跳转到研究页面（不会调用此函数）
   * 3. 如果没有提供 router（降级场景），则在主界面创建一个 idle 状态的研究任务建议卡片
   * 4. 用户可以点击卡片启动研究，或直接忽略
   *
   * 去重策略：
   * - 相同 query 且状态为 idle 的任务：更新 metadata
   * - 相同 query 且正在运行的任务：不做任何操作（避免干扰运行中任务）
   * - 不同 query：创建新任务
   */
  function maybeSuggestResearchTask(response: PanelResponse, payload: SubmitPayload) {
    const requestMode = payload.mode ?? "auto";
    // 如果用户明确使用研究模式，不需要建议
    if (requestMode === "research") return;

    const metadata = response.metadata;
    if (!metadata) return;

    // 检查是否为复杂研究意图
    const intent = metadata.intent_type ?? metadata.research_type;
    if (intent !== "complex_research") return;

    const normalizedQuery = payload.query.trim();
    if (!normalizedQuery) return;

    // 查找相同 query 的现有任务
    const existing = Array.from(tasks.value.values()).find(
      (task) => task.query === normalizedQuery && task.status !== "completed" && task.status !== "error"
    );

    if (existing) {
      // 只有在任务为 idle 状态时才更新 metadata
      // 正在运行的任务（processing/human_in_loop）不应该被更新，避免干扰
      if (existing.status === "idle") {
        researchStore.updateTaskMetadata(existing.task_id, metadata);
      }
      // 如果任务正在运行，直接返回，不做任何操作
      return;
    }

    // 创建新的研究任务建议
    const taskId = researchStore.createTask(normalizedQuery, "research", undefined, {
      status: "idle",
      metadata,
      autoDetected: true,
    });
    persistResearchTaskQuery(taskId, normalizedQuery);
  }

  return {
    state,
    hasPanel,
    query,
    datasource,
    isBusy,
    submit,
    startStream,
    stopStream,
    reset,
  };
}
