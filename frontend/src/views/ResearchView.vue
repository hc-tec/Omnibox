<template>
  <div class="research-view min-h-screen bg-background text-foreground">
    <!-- 顶部工具栏 -->
    <header class="research-header border-b border-border/20 bg-[var(--shell-surface)]/95 px-6 py-3 backdrop-blur">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-4">
          <button
            class="inline-flex h-9 items-center gap-2 rounded-xl border border-border/40 bg-background/50 px-3 text-sm font-medium text-foreground transition hover:bg-background hover:text-foreground"
            @click="handleBackToMain"
          >
            <ArrowLeft class="h-4 w-4" />
            返回主界面
          </button>

          <div class="h-6 w-px bg-border/40" />

          <div>
            <p class="text-xs text-muted-foreground">研究任务</p>
            <p class="text-sm font-semibold">{{ store.state.query || "加载中..." }}</p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <!-- WebSocket 连接状态 -->
          <div class="flex items-center gap-2 rounded-xl border border-border/40 bg-background/50 px-3 py-1.5 text-xs">
            <div
              class="h-2 w-2 rounded-full"
              :class="{
                'bg-green-500': wsConnected,
                'bg-yellow-500 animate-pulse': wsConnecting,
                'bg-red-500': !wsConnecting && !wsConnected,
              }"
            />
            <span class="text-muted-foreground">
              {{ wsConnected ? "已连接" : wsConnecting ? "连接中..." : "未连接" }}
            </span>
          </div>

          <!-- 研究状态 -->
          <div
            class="rounded-xl border px-3 py-1.5 text-xs font-medium"
            :class="{
              'border-blue-500/40 bg-blue-500/10 text-blue-500': store.state.status === 'running',
              'border-green-500/40 bg-green-500/10 text-green-500': store.state.status === 'completed',
              'border-red-500/40 bg-red-500/10 text-red-500': store.state.status === 'error',
              'border-yellow-500/40 bg-yellow-500/10 text-yellow-500': store.state.status === 'planning',
              'border-border/40 bg-background/50 text-muted-foreground': store.state.status === 'pending',
            }"
          >
            {{ statusText }}
          </div>
        </div>
      </div>
    </header>

    <!-- 主内容区域：两栏布局 -->
    <main class="research-main flex h-[calc(100vh-65px)]">
      <!-- 左侧：上下文面板 (30%) -->
      <aside class="research-context-panel w-[30%] border-r border-border/20 bg-background/50">
        <ResearchContextPanel />
      </aside>

      <!-- 右侧：数据面板 (70%) -->
      <section class="research-data-panel flex-1 overflow-auto bg-background">
        <ResearchDataPanel />
      </section>
    </main>

    <!-- 错误提示 -->
    <div
      v-if="wsError"
      class="fixed bottom-4 right-4 z-50 max-w-md rounded-xl border border-red-500/40 bg-red-500/10 p-4 shadow-2xl backdrop-blur"
    >
      <div class="flex items-start gap-3">
        <AlertCircle class="h-5 w-5 flex-shrink-0 text-red-500" />
        <div class="flex-1">
          <p class="text-sm font-semibold text-red-500">WebSocket 错误</p>
          <p class="mt-1 text-xs text-red-400">{{ wsError }}</p>
        </div>
        <button
          class="text-red-400 transition hover:text-red-300"
          @click="wsError = null"
        >
          <X class="h-4 w-4" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ArrowLeft, AlertCircle, X } from "lucide-vue-next";
import { useResearchViewStore } from "@/store/researchViewStore";
import { useResearchStore } from "@/features/research/stores/researchStore";
import { useResearchWebSocketManager } from "@/composables/useResearchWebSocketManager";
import { loadResearchTaskQuery, persistResearchTaskQuery } from "@/features/research/utils/taskStorage";
import ResearchContextPanel from "@/features/research/components/ResearchContextPanel.vue";
import ResearchDataPanel from "@/features/research/components/ResearchDataPanel.vue";

// ========== Props ==========
const props = defineProps<{
  taskId: string;
}>();

// ========== Composables ==========
const router = useRouter();
const store = useResearchViewStore();
const researchTaskStore = useResearchStore();

// 使用全局 WebSocket 管理器（自动复用主页面的连接）
const wsManager = useResearchWebSocketManager({
  taskId: props.taskId,
  autoReconnect: true,
  reconnectDelay: 3000,
  maxReconnectAttempts: 5,
});

const {
  isConnecting: wsConnecting,
  isConnected: wsConnected,
  error: wsError,
  connect,
  sendResearchRequestOnce,
  hasRequestSent,
} = wsManager;

// ========== 计算属性 ==========
const statusText = computed(() => {
  switch (store.state.status) {
    case "pending":
      return "等待中";
    case "planning":
      return "规划中";
    case "running":
      return "执行中";
    case "completed":
      return "已完成";
    case "error":
      return "错误";
    default:
      return "未知";
  }
});

// ========== 方法 ==========

/**
 * 返回主界面
 * 注意：不断开 WebSocket 连接，因为主页面可能还在使用
 */
async function handleBackToMain() {
  try {
    await router.push({ name: "Main" });
    // 不调用 store.reset()，保留研究数据供后续查看
  } catch (err) {
    console.error("[ResearchView] Failed to navigate back to main view", err);
  }
}

/**
 * 初始化研究任务
 */
async function initializeResearch() {
  const queryParam = new URLSearchParams(window.location.search).get("query");
  let resolvedQuery = (queryParam ?? "").trim();

  if (resolvedQuery) {
    persistResearchTaskQuery(props.taskId, resolvedQuery);
  } else {
    const stored = loadResearchTaskQuery(props.taskId);
    if (stored) {
      resolvedQuery = stored;
    }
  }

  if (!resolvedQuery) {
    console.error("[ResearchView] Missing query parameter");
    wsError.value = "缂哄皯鐮旂┒鏌ヨ鍙傛暟";
    return;
  }

  // 检查 researchViewStore 是否已有当前任务的数据
  // 注意：WebSocket 消息会同时更新 researchViewStore 和 researchStore
  // researchViewStore 包含完整数据（steps、panels、analyses）
  // researchStore 只包含预览数据（execution_steps、previews）
  // 所以应该直接使用 researchViewStore 中的数据，不要从 researchStore 同步！
  console.log("[ResearchView] 检查 researchViewStore 状态:");
  console.log(`  - store.state.task_id: ${store.state.task_id}`);
  console.log(`  - props.taskId: ${props.taskId}`);
  console.log(`  - store.state.steps.length: ${store.state.steps.length}`);
  console.log(`  - store.state.panels.length: ${store.state.panels.length}`);
  console.log(`  - store.state.analyses.length: ${store.state.analyses.length}`);

  const hasDataInViewStore = store.state.task_id === props.taskId && store.state.steps.length > 0;

  if (hasDataInViewStore) {
    console.log("[ResearchView] researchViewStore 已有数据，复用现有数据");
    // WebSocket 消息会持续更新 researchViewStore，无需手动同步
  } else {
    console.log("[ResearchView] 初始化新任务或任务 ID 不匹配，重新初始化");
    console.log(`  原因: task_id匹配=${store.state.task_id === props.taskId}, 有步骤=${store.state.steps.length > 0}`);
    // 初始化新任务
    // WebSocket 连接会自动接收消息并更新 researchViewStore
    store.initializeTask(props.taskId, resolvedQuery);
  }

  researchTaskStore.ensureTask(props.taskId, resolvedQuery);

  // 连接 WebSocket（如果已连接会复用，如果未连接会创建）
  connect();
}


// ========== 生命周期 ==========

onMounted(() => {
  console.log(`[ResearchView] Mounted with taskId: ${props.taskId}`);
  initializeResearch();
});

// 监听 WebSocket 连接状态，连接成功后发送研究请求（带去重保护）
watch(() => wsConnected.value, (connected) => {
  if (connected && store.state.query) {
    // 检查是否已经发送过研究请求
    if (hasRequestSent()) {
      console.log("[ResearchView] 研究请求已发送（可能在主页面），复用现有连接");
      return;
    }

    // 首次连接且未发送请求，发送研究请求
    console.log("[ResearchView] WebSocket 已连接，发送研究请求");
    sendResearchRequestOnce({
      query: store.state.query,
      use_cache: true,
    });
  }
});
</script>

<style scoped>
.research-view {
  /* 自定义滚动条样式 */
  --scrollbar-width: 8px;
  --scrollbar-track: rgba(0, 0, 0, 0.1);
  --scrollbar-thumb: rgba(100, 100, 100, 0.3);
  --scrollbar-thumb-hover: rgba(100, 100, 100, 0.5);
}

.research-data-panel {
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track);
}

.research-data-panel::-webkit-scrollbar {
  width: var(--scrollbar-width);
}

.research-data-panel::-webkit-scrollbar-track {
  background: var(--scrollbar-track);
}

.research-data-panel::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 4px;
}

.research-data-panel::-webkit-scrollbar-thumb:hover {
  background: var(--scrollbar-thumb-hover);
}
</style>
