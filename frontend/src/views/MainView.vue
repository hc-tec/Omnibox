<template>
  <div class="app-shell relative min-h-screen overflow-hidden bg-background text-foreground">
    <div class="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-background/40 to-background" />
    <div class="pointer-events-none absolute -top-40 right-1/4 h-[520px] w-[520px] rounded-full bg-[#5b8cff]/30 blur-[180px]" />
    <div class="pointer-events-none absolute -bottom-52 left-1/5 h-[620px] w-[620px] rounded-full bg-emerald-400/25 blur-[200px]" />

    <div class="relative z-10 flex min-h-screen flex-col gap-4 px-6 py-6 md:px-12 md:py-8">
      <header class="app-chrome drag-region flex items-center justify-between rounded-[24px] border border-border/30 bg-[var(--shell-surface)]/75 px-5 py-2 backdrop-blur">
        <div class="no-drag flex items-center gap-3">
          <button
            type="button"
            class="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-blue-500 text-sm font-semibold text-white shadow-lg shadow-indigo-500/35 transition hover:scale-95"
            @click="focusCommandBar"
            aria-label="Focus command input"
          >
            CMD
          </button>
          <div>
            <p class="text-[10px] uppercase tracking-[0.5em] text-muted-foreground">Omnibox</p>
            <p class="text-lg font-semibold leading-tight">Desktop Intelligence Studio</p>
          </div>
        </div>

        <div class="chrome-controls no-drag flex items-center gap-1.5 text-xs">
          <div class="flex items-center gap-1 rounded-2xl border border-border/40 bg-[var(--shell-surface)]/60 px-2 py-1">
            <button
              v-for="option in sizeOptions"
              :key="option.value"
              class="rounded-xl px-2 py-1 text-[11px] font-medium transition"
              :class="sizePreset === option.value ? 'bg-primary/10 text-foreground' : 'text-muted-foreground hover:text-foreground'"
              @click="setSizePreset(option.value)"
            >
              {{ option.label }}
            </button>
          </div>
          <button class="rounded-xl px-3 py-2 text-muted-foreground transition hover:text-foreground" @click="navigateToSubscriptions">
            订阅管理
          </button>
          <button
            class="rounded-xl px-3 py-2 transition"
            :class="devModeEnabled ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'"
            @click="devModeStore.toggle()"
            title="开发者模式：点击组件查看调试信息"
          >
            {{ devModeEnabled ? "🔧 开发模式" : "开发模式" }}
          </button>
          <button class="rounded-xl px-3 py-2 text-muted-foreground transition hover:text-foreground" @click="toggleTheme">
            {{ isLight ? "Dark" : "Light" }}
          </button>
          <WindowControls />
        </div>
      </header>

      <main class="desktop-stage relative flex-1 rounded-[32px] border border-border/20 bg-[var(--canvas-gradient)]/95">
        <div
          class="canvas-flow mx-auto w-full px-4 py-12 pb-28 sm:px-6 md:px-10 md:py-8 2xl:px-8"
          style="max-width: clamp(320px, calc(100vw - 4rem), 2400px);"
        >
          <!-- Unified Workspace Cards -->
          <div v-if="workspaceStore.activeCards.length > 0" class="workspace-cards-grid mb-6">
            <QueryCard
              v-for="card in workspaceStore.activeCards"
              :key="card.id"
              :card="card"
              :research-task="card.mode === 'research' ? researchStore.getTask(card.id) : undefined"
              @delete="handleDeleteCard"
              @open="handleOpenCard"
              @refresh="handleRefreshCard"
            />
          </div>

          <PanelWorkspace
            class="min-h-[70vh]"
            :auto-initialize="false"
            @inspect-component="handleInspectComponent"
          />
          <div class="hud mt-10 flex flex-wrap items-center justify-center gap-4 text-[11px] uppercase tracking-[0.35em] text-muted-foreground/80">
            <span class="rounded-full border border-border/60 px-4 py-1">{{ version ? `Desktop v${version}` : "Waiting for Desktop..." }}</span>
            <span>Ctrl/Cmd + Space → Focus</span>
            <span>Ctrl/Cmd + K → Spotlight</span>
          </div>
        </div>

      </main>
    </div>

    <CommandPalette
      ref="commandPaletteRef"
      :loading="false"
      :default-query="query"
      :has-layout="hasBlocks"
      @submit="handleCommandSubmit"
      @reset-panels="handleReset"
    />

    <!-- Component Inspector (for component debugging in dev mode) -->
    <ComponentInspector
      :open="componentInspectorOpen"
      :block="inspectedComponent?.block"
      :data-block="inspectedComponent?.dataBlock"
      @close="componentInspectorOpen = false"
    />

    <!-- Action Inbox for Research Tasks -->
    <ActionInbox />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import PanelWorkspace from "@/features/panel/PanelWorkspace.vue";
import CommandPalette from "@/features/panel/components/CommandPalette.vue";
import ComponentInspector from "@/features/panel/components/ComponentInspector.vue";
import WindowControls from "@/components/system/WindowControls.vue";
import ActionInbox from "@/features/research/components/ActionInbox.vue";
import QueryCard from "@/components/workspace/QueryCard.vue";
import { usePanelActions } from "@/features/panel/usePanelActions";
import { usePanelStore } from "@/store/panelStore";
import { useResearchStore } from "@/features/research/stores/researchStore";
import { useResearchViewStore } from "@/store/researchViewStore";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { useDevModeStore } from "@/store/devModeStore";
import { persistResearchTaskQuery } from "@/features/research/utils/taskStorage";
import { useResearchWebSocketManager } from "@/composables/useResearchWebSocketManager";
import { generateUUID } from "@/utils/uuid";
import type { PanelSizePreset } from "@/shared/panelSizePresets";
import type { QueryMode } from "@/features/research/types/researchTypes";
import type { QueryCard as QueryCardType } from "@/types/queryCard";
import type { UIBlock, DataBlock } from "@/shared/types/panel";

const router = useRouter();

const version = ref<string | null>(null);
const componentInspectorOpen = ref(false);
const inspectedComponent = ref<{ block: UIBlock; dataBlock: DataBlock | null } | null>(null);
const appearance = ref<"dark" | "light">("light"); // 默认浅色主题
const isLight = computed(() => appearance.value === "light");
const commandPaletteRef = ref<InstanceType<typeof CommandPalette> | null>(null);

const { state: panelState, query, submit, reset } = usePanelActions();
const panelStore = usePanelStore();
const researchStore = useResearchStore();
const workspaceStore = useWorkspaceStore();
const devModeStore = useDevModeStore();
const { enabled: devModeEnabled } = storeToRefs(devModeStore);
const sizePreset = computed(() => panelStore.state.sizePreset);
const sizeOptions: { label: string; value: PanelSizePreset }[] = [
  { label: "紧凑", value: "compact" },
  { label: "适中", value: "balanced" },
  { label: "宽松", value: "spacious" },
];
const hasBlocks = computed(() => ((panelState.blocks?.length ?? 0) > 0));


const applyTheme = () => {
  const root = document.documentElement;
  root.classList.remove("theme-dark", "theme-light");
  root.classList.add(isLight.value ? "theme-light" : "theme-dark");
  root.classList.toggle("dark", !isLight.value);
  root.classList.toggle("light", isLight.value);
  document.body.classList.toggle("dark", !isLight.value);
  document.body.classList.toggle("light", isLight.value);
};

const toggleTheme = () => {
  appearance.value = isLight.value ? "dark" : "light";
  applyTheme();
};

const focusCommandBar = () => {
  commandPaletteRef.value?.open();
};

const navigateToSubscriptions = async () => {
  await router.push({ path: '/subscriptions' });
};

const handleReset = () => {
  reset();
};

function connectResearchWebSocket(taskId: string, query: string) {
  console.log('[MainView] connectResearchWebSocket:', { taskId, query });

  // 先初始化 researchViewStore，确保 task_id 被设置
  // 这样当 WebSocket 消息到达时，store 中就有正确的 task_id 了
  const viewStore = useResearchViewStore();
  if (viewStore.state.task_id !== taskId) {
    console.log('[MainView] 初始化 researchViewStore, taskId:', taskId);
    viewStore.initializeTask(taskId, query);
  }

  // 使用全局 WebSocket 管理器（自动处理连接复用）
  const wsManager = useResearchWebSocketManager({
    taskId,
    autoReconnect: true,
  });

  console.log('[MainView] 调用 wsManager.connect()');
  wsManager.connect();

  // 等待连接建立后发送查询（使用 watch 监听连接状态）
  const unwatch = watch(
    () => wsManager.isConnected.value,
    (connected) => {
      console.log('[MainView] WebSocket 连接状态变化:', connected);
      if (connected) {
        console.log('[MainView] 发送研究请求（带去重保护）');
        // 使用 sendResearchRequestOnce 确保不会重复发送
        wsManager.sendResearchRequestOnce({
          query,
          use_cache: true,
        });
        unwatch(); // 只执行一次
      }
    },
    { immediate: true }
  );
}

const handleCommandSubmit = async (payload: { query: string; mode: QueryMode }) => {
  console.log('[MainView] handleCommandSubmit:', payload);

  // Step 1: 立即生成卡片（< 100ms）
  const taskId = generateUUID();
  const card = workspaceStore.createCard({
    id: taskId,
    query: payload.query,
    mode: payload.mode === 'research' ? 'research' : 'simple',
    trigger_source: 'manual_input',
  });
  console.log('[MainView] 已创建卡片, taskId:', taskId);

  // Step 2: 异步提交到后端
  try {
    // 更新卡片状态为 processing
    workspaceStore.updateCardStatus(taskId, 'processing', {
      current_step: '正在提交查询...',
      progress: 10,
    });

    // 用户主动选择"研究"模式：创建任务卡片 + 启动 WebSocket
    if (payload.mode === "research") {
      // 使用相同的 taskId 创建研究任务，确保 workspace 卡片和研究任务关联
      const researchTaskId = researchStore.createTask(payload.query, payload.mode, taskId);
      persistResearchTaskQuery(researchTaskId, payload.query);
      console.log('[MainView] 用户选择研究模式，创建研究任务, researchTaskId === taskId:', researchTaskId, taskId);
      connectResearchWebSocket(researchTaskId, payload.query);

      // 研究模式：卡片状态由 WebSocket 更新，这里不做处理
      return;
    }

    // 普通查询：提交到后端（传递 taskId 避免重复创建）
    const result = await submit({
      ...payload,
      client_task_id: taskId,  // 传递已创建的 taskId
    });
    console.log('[MainView] submit result:', result);

    // 后端自动检测为研究模式
    if (result.requiresStreaming && result.taskId) {
      console.log('[MainView] 后端识别为研究模式，启动 WebSocket 连接, taskId:', result.taskId);

      // 更新 workspace 卡片的 mode 为 'research'（从 'simple' 升级）
      const workspaceCard = workspaceStore.getCard(taskId);
      if (workspaceCard && workspaceCard.mode === 'simple') {
        console.log('[MainView] 更新卡片 mode: simple -> research');
        workspaceCard.mode = 'research';
        workspaceCard.updated_at = new Date().toISOString();
      }

      // 使用返回的 taskId 连接 WebSocket（应该与我们创建的 taskId 相同）
      connectResearchWebSocket(result.taskId, payload.query);
      return;
    }

    // 普通查询成功完成
    if (panelState.blocks && panelState.blocks.length > 0) {
      // 注意：普通查询没有 streamLog（只有流式查询才有）
      // 只保存 metadata 和 message
      console.log('[MainView] 保存 Inspector 数据:');
      console.log('[MainView] - response:', result.response);
      console.log('[MainView] - response.metadata:', result.response.metadata);
      console.log('[MainView] - response.message:', result.response.message);
      console.log('[MainView] - panelState.metadata:', panelState.metadata);
      console.log('[MainView] - panelState.message:', panelState.message);

      workspaceStore.updateCardResult(
        taskId,
        panelState.blocks,
        panelState.metadata?.refresh_metadata,
        {
          metadata: result.response.metadata,  // 使用 response 的 metadata
          message: result.response.message,    // 使用 response 的 message
          streamLog: [],  // 普通查询无流式日志
          fetchSnapshot: null,  // 普通查询无 fetch 快照
        }
      );
      console.log('[MainView] 普通查询完成，卡片已更新');
    } else {
      // 无结果数据
      workspaceStore.updateCardStatus(taskId, 'completed', {
        current_step: '查询完成',
        progress: 100,
      });
    }
  } catch (error) {
    console.error('[MainView] 查询失败:', error);
    workspaceStore.updateCardStatus(taskId, 'error', {
      error_message: error instanceof Error ? error.message : '查询失败',
    });
  }
};

const handleDeleteCard = (cardId: string) => {
  console.log('[MainView] 删除卡片:', cardId);
  workspaceStore.deleteCard(cardId);
};

/**
 * 处理组件检查事件（开发者模式）
 */
const handleInspectComponent = (payload: { block: UIBlock; dataBlock: DataBlock | null }) => {
  console.log('[MainView] 打开组件调试信息:', payload);
  inspectedComponent.value = payload;
  componentInspectorOpen.value = true;
};

const handleOpenCard = async (cardId: string) => {
  const card = workspaceStore.getCard(cardId);
  if (!card) {
    console.warn('[MainView] 卡片不存在:', cardId);
    return;
  }

  console.log('[MainView] 打开卡片（进入研究页面）:', cardId, 'mode:', card.mode);

  try {
    // processing 状态的卡片，跳转到研究详情页面查看实时进度
    await router.push({
      path: `/research/${cardId}`,
      query: { query: card.query },
    });
  } catch (error) {
    console.error('[MainView] 打开卡片失败:', error);
  }
};

const handleRefreshCard = async (cardId: string) => {
  const card = workspaceStore.getCard(cardId);
  if (!card) {
    console.warn('[MainView] 卡片不存在:', cardId);
    return;
  }

  if (!card.refresh_metadata) {
    console.warn('[MainView] 卡片缺少 refresh_metadata，无法快速刷新:', cardId);
    return;
  }

  console.log('[MainView] 快速刷新卡片:', cardId, card.refresh_metadata);

  // Phase 3: 快速刷新流程
  try {
    // 1. 标记为 processing 状态
    workspaceStore.updateCardStatus(cardId, 'processing', {
      current_step: '正在刷新数据...',
      progress: 30,
    });

    // 2. 调用后端快速刷新 API
    const response = await fetch('/api/v1/refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        refresh_metadata: card.refresh_metadata,
        layout_snapshot: panelStore.getLayoutSnapshot(),
      }),
    });

    if (!response.ok) {
      throw new Error(`刷新失败：HTTP ${response.status}`);
    }

    const result = await response.json();

    // 3. 更新卡片结果
    if (result.data && result.data.blocks && result.data.blocks.length > 0) {
      workspaceStore.updateCardResult(
        cardId,
        result.data.blocks,
        result.metadata?.refresh_metadata,
        {
          metadata: result.metadata,
          message: result.message || '快速刷新完成',
          // 快速刷新没有 streamLog，保留原有的或空数组
          streamLog: card.streamLog || [],
          fetchSnapshot: null,
        }
      );
      console.log('[MainView] 卡片刷新完成（保留 Inspector 数据）:', cardId);
    } else {
      workspaceStore.updateCardStatus(cardId, 'completed', {
        current_step: '刷新完成',
        progress: 100,
      });
    }
  } catch (error) {
    console.error('[MainView] 卡片刷新失败:', error);
    workspaceStore.updateCardStatus(cardId, 'error', {
      error_message: error instanceof Error ? error.message : '刷新失败',
    });
  }
};

const setSizePreset = (preset: PanelSizePreset) => {
  panelStore.setSizePreset(preset);
};

const handleShortcut = (event: KeyboardEvent) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    focusCommandBar();
  }
  if ((event.metaKey || event.ctrlKey) && event.code === "Space") {
    event.preventDefault();
    focusCommandBar();
  }
};

onMounted(async () => {
  applyTheme();
  window.addEventListener("keydown", handleShortcut);
  if (window.desktop?.getVersion) {
    version.value = await window.desktop.getVersion();
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleShortcut);
  // 注意：不在这里清理 WebSocket 连接！
  // 因为导航到 ResearchView 时 MainView 会被卸载，但我们需要保留连接和请求状态
  // 连接会在以下情况清理：
  // 1. 用户主动删除任务时调用 disconnectAndCleanup()
  // 2. 页面刷新/关闭时浏览器自动清理
});
</script>

<style scoped>
.workspace-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
}

@media (min-width: 768px) {
  .workspace-cards-grid {
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  }
}

@media (min-width: 1536px) {
  .workspace-cards-grid {
    grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  }
}

.research-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
}

@media (min-width: 768px) {
  .research-cards-grid {
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  }
}

@media (min-width: 1536px) {
  .research-cards-grid {
    grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  }
}
</style>
