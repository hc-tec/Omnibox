<template>
  <div class="command-palette fixed inset-x-0 bottom-4 z-30 flex justify-center px-6">
    <div class="w-full max-w-4xl">
      <div ref="paletteRoot" class="palette-container relative transition-all duration-300" :class="{ 'is-expanded': open }">
        <CommandBar
          ref="commandBarRef"
          :loading="loading"
          :default-query="defaultQuery"
          :has-layout="hasLayout"
          :condensed="!open"
          @submit="handleSubmit"
          @reset-panels="handleReset"
          @focus-change="handleFocusChange"
        />
        <button
          v-if="!open"
          type="button"
          class="palette-overlay absolute inset-0 rounded-[32px] focus:outline-none"
          aria-label="唤醒命令面板"
          @click="openPalette"
        />
        <button
          v-if="open"
          type="button"
          class="palette-close absolute -top-3 -right-3 flex h-8 w-8 items-center justify-center rounded-full border border-border/40 bg-[var(--shell-surface)]/85 text-muted-foreground shadow hover:text-foreground"
          aria-label="收起命令面板"
          @click="closePalette"
        >
          ✕
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import CommandBar from "./CommandBar.vue";
import type { QueryMode } from "@/features/research/types/researchTypes";

const props = defineProps<{
  loading: boolean;
  defaultQuery: string;
  hasLayout: boolean;
}>();

const emit = defineEmits<{
  (event: "submit", payload: { query: string; mode: QueryMode }): void;
  (event: "reset-panels"): void;
}>();

const open = ref(false);
const commandBarRef = ref<InstanceType<typeof CommandBar> | null>(null);
const paletteRoot = ref<HTMLElement | null>(null);

const focusInput = () => {
  commandBarRef.value?.focusInput();
};

const openPalette = () => {
  if (open.value) {
    focusInput();
    return;
  }
  open.value = true;
  nextTick(focusInput);
};

const closePalette = () => {
  open.value = false;
};

const handleSubmit = (payload: { query: string; mode: QueryMode }) => {
  emit("submit", payload);
  closePalette();
};

const handleReset = () => {
  emit("reset-panels");
};

const handleFocusChange = (value: boolean) => {
  if (value) {
    openPalette();
  }
};

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === "Escape" && open.value) {
    event.preventDefault();
    closePalette();
  }
};

const handleClickOutside = (event: MouseEvent) => {
  if (!open.value) return;
  const target = event.target as Node;
  if (paletteRoot.value && !paletteRoot.value.contains(target)) {
    closePalette();
  }
};

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
  window.addEventListener("mousedown", handleClickOutside);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeydown);
  window.removeEventListener("mousedown", handleClickOutside);
});

defineExpose({
  open: openPalette,
  close: closePalette,
});
</script>

<style scoped>
.palette-container {
  border-radius: 32px;
  background: color-mix(in srgb, var(--shell-surface) 65%, transparent);
  border: 1px solid color-mix(in srgb, var(--border) 90%, transparent);
  padding: 2px;
  backdrop-filter: blur(20px);
}

.palette-container:not(.is-expanded) {
  max-width: 480px;
  margin: 0 auto;
  background: color-mix(in srgb, var(--shell-surface) 45%, transparent);
}

.palette-container.is-expanded {
  max-width: 100%;
}

.palette-overlay {
  background: transparent;
}
</style>
