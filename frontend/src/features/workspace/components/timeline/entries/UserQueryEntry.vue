<!--
  用户查询条目组件 - Manus 风格
-->
<script setup lang="ts">
import type { TimelineEntry } from '../../../types/workspace'

defineProps<{
  entry: TimelineEntry
}>()
</script>

<template>
  <div class="flex justify-start">
    <div class="bg-primary text-primary-foreground px-3.5 py-2 rounded-xl rounded-tl text-sm leading-relaxed max-w-[90%] break-words">
      {{ entry.userQuery?.query }}
    </div>
  </div>
</template>
