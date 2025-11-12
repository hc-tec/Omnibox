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
          <button class="rounded-xl px-3 py-2 text-muted-foreground transition hover:text-foreground" @click="toggleTheme">
            {{ isLight ? "Dark" : "Light" }}
          </button>
          <button class="rounded-xl px-3 py-2 text-muted-foreground transition hover:text-foreground" @click="inspectorOpen = true">
            Inspector
          </button>
          <WindowControls />
        </div>
      </header>

      <main class="desktop-stage relative flex-1 rounded-[32px] border border-border/20 bg-[var(--canvas-gradient)]/95">
        <div
          class="canvas-flow mx-auto w-full px-4 py-12 pb-28 sm:px-6 md:px-10 md:py-8 2xl:px-8"
          style="max-width: clamp(320px, calc(100vw - 4rem), 2400px);"
        >
          <!-- Research Live Cards -->
          <div v-if="activeTasks.length > 0" class="research-cards-grid mb-6">
            <ResearchLiveCard
              v-for="task in activeTasks"
              :key="task.task_id"
              :task="task"
              @delete="handleDeleteTask"
            />
          </div>

          <PanelWorkspace class="min-h-[70vh]" :auto-initialize="false" />
          <div class="hud mt-10 flex flex-wrap items-center justify-center gap-4 text-[11px] uppercase tracking-[0.35em] text-muted-foreground/80">
            <span class="rounded-full border border-border/60 px-4 py-1">{{ version ? `Desktop v${version}` : "Waiting for Desktop..." }}</span>
            <span>Ctrl/Cmd + Space → Focus</span>
            <span>Ctrl/Cmd + K → Spotlight</span>
          </div>
        </div>

      </main>
    </div>

    <button
      class="no-drag fixed bottom-28 right-6 z-30 inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-border/40 bg-[var(--shell-surface)]/85 text-muted-foreground shadow-2xl shadow-black/40 backdrop-blur transition hover:text-foreground"
      @click="inspectorOpen = true"
      aria-label="Open Inspector"
    >
      <Sparkles class="h-4 w-4" />
    </button>

    <CommandPalette
      ref="commandPaletteRef"
      :loading="panelState.loading"
      :default-query="query"
      :has-layout="hasBlocks"
      @submit="handleCommandSubmit"
      @reset-panels="handleReset"
    />

    <InspectorDrawer
      :open="inspectorOpen"
      :metadata="panelState.metadata"
      :message="panelState.message"
      :log="panelState.streamLog"
      :fetch-snapshot="panelState.fetchSnapshot"
      @close="inspectorOpen = false"
    />

    <!-- Action Inbox for Research Tasks -->
    <ActionInbox />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { Sparkles } from "lucide-vue-next";
import PanelWorkspace from "@/features/panel/PanelWorkspace.vue";
import CommandPalette from "@/features/panel/components/CommandPalette.vue";
import InspectorDrawer from "@/features/panel/components/InspectorDrawer.vue";
import WindowControls from "@/components/system/WindowControls.vue";
import ResearchLiveCard from "@/features/research/components/ResearchLiveCard.vue";
import ActionInbox from "@/features/research/components/ActionInbox.vue";
import { usePanelActions } from "@/features/panel/usePanelActions";
import { usePanelStore } from "@/store/panelStore";
import { useResearchStore } from "@/features/research/stores/researchStore";
import type { PanelSizePreset } from "@/shared/panelSizePresets";
import type { QueryMode, ResearchResponse } from "@/features/research/types/researchTypes";

const version = ref<string | null>(null);
const inspectorOpen = ref(false);
const appearance = ref<"dark" | "light">("dark");
const isLight = computed(() => appearance.value === "light");
const commandPaletteRef = ref<InstanceType<typeof CommandPalette> | null>(null);

const { state: panelState, query, submit, reset } = usePanelActions();
const panelStore = usePanelStore();
const researchStore = useResearchStore();
const sizePreset = computed(() => panelStore.state.sizePreset);
const sizeOptions: { label: string; value: PanelSizePreset }[] = [
  { label: "紧凑", value: "compact" },
  { label: "适中", value: "balanced" },
  { label: "宽松", value: "spacious" },
];
const hasBlocks = computed(() => ((panelState.blocks?.length ?? 0) > 0));
const activeTasks = computed(() => researchStore.activeTasks);

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

const handleReset = () => {
  reset();
};

const handleCommandSubmit = async (payload: { query: string; mode: QueryMode }) => {
  let taskId: string | null = null;
  if (payload.mode === "research") {
    taskId = researchStore.createTask(payload.query, payload.mode);
  }

  try {
    const response = await submit(payload);
    if (taskId) {
      const metadata = response?.metadata as ResearchResponse["metadata"] | undefined;
      if (metadata?.mode === "research") {
        researchStore.completeTask(taskId, response.message, metadata);
      } else {
        researchStore.setTaskError(taskId, "服务器未返回研究元数据，无法更新研究卡片。");
      }
    }
  } catch (error) {
    if (taskId) {
      const message = error instanceof Error ? error.message : "研究请求失败";
      researchStore.setTaskError(taskId, message);
    }
    throw error;
  }
};

const handleDeleteTask = (taskId: string) => {
  researchStore.deleteTask(taskId);
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
});
</script>

<style scoped>
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
