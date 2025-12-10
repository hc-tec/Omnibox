<!--
  用户查询条目组件 - Manus 风格
-->
<script setup lang="ts">
import type { TimelineEntry } from '../../../types/workspace'

const { entry, isActive = false } = defineProps<{
  entry: TimelineEntry
  /** 是否当前活跃步骤，用于运行态提示 */
  isActive?: boolean
}>()
</script>

<template>
  <div class="flex justify-start">
    <div
      class="bg-primary text-primary-foreground px-3.5 py-2 rounded-xl rounded-tl text-sm leading-relaxed max-w-[90%] break-words"
      :class="isActive ? 'shimmer-text' : ''"
    >
      {{ entry.userQuery?.query }}
    </div>
  </div>
</template>

<style scoped>
.shimmer-text {
  position: relative;
  color: var(--foreground);
}

.shimmer-text::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(
    120deg,
    transparent 0%,
    rgba(255, 255, 255, 0.4) 45%,
    rgba(255, 255, 255, 0.75) 50%,
    rgba(255, 255, 255, 0.4) 55%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.3s linear infinite;
  mix-blend-mode: screen;
  pointer-events: none;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
