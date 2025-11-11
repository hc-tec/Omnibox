<template>
  <div class="inline-flex items-center gap-2 pl-4">
    <button
      type="button"
      class="flex h-7 w-10 items-center justify-center rounded-md border border-border/60 bg-background/80 text-foreground/70 transition hover:text-foreground"
      @click="minimize"
      aria-label="最小化"
    >
      <span class="block h-[1px] w-3 bg-current" />
    </button>
    <button
      type="button"
      class="flex h-7 w-10 items-center justify-center rounded-md border border-border/60 bg-background/80 text-foreground/70 transition hover:text-foreground"
      @click="toggleMaximize"
      aria-label="最大化"
    >
      <span
        class="block h-3 w-3 rounded-sm border border-current"
        :class="{ 'scale-95': isMaximized }"
      />
    </button>
    <button
      type="button"
      class="flex h-7 w-10 items-center justify-center rounded-md border border-border/60 bg-red-500/10 text-red-400 transition hover:bg-red-500/20 hover:text-red-200"
      @click="close"
      aria-label="关闭"
    >
      <span class="relative block h-[1px] w-3 bg-current before:absolute before:block before:h-[1px] before:w-full before:bg-current before:rotate-90" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

const isMaximized = ref(false);
let dispose: (() => void) | null = null;

const controls = () => window.desktop?.windowControls ?? null;

async function sync() {
  const bridge = controls();
  if (!bridge) return;
  isMaximized.value = await bridge.isMaximized();
}

async function minimize() {
  const bridge = controls();
  if (!bridge) return;
  await bridge.command("minimize");
}

async function toggleMaximize() {
  const bridge = controls();
  if (!bridge) return;
  await bridge.command("maximize");
  await sync();
}

async function close() {
  const bridge = controls();
  if (!bridge) return;
  await bridge.command("close");
}

onMounted(() => {
  sync();
  const bridge = controls();
  if (bridge) {
    dispose = bridge.onStateChange((state) => {
      isMaximized.value = state;
    });
  }
});

onBeforeUnmount(() => {
  dispose?.();
});
</script>
