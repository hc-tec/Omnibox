<template>
  <div class="flex h-full items-center justify-center">
    <div class="text-center">
      <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-border/40 bg-background/50">
        <Database class="h-8 w-8 text-muted-foreground/50" />
      </div>
      <p class="mt-4 text-sm text-muted-foreground">
        {{ message }}
      </p>
      <p class="mt-1 text-xs text-muted-foreground/70">
        {{ hint }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Database } from 'lucide-vue-next'

// ========== Props ==========
withDefaults(defineProps<{
  message?: string
  hint?: string
}>(), {
  message: '选择一个步骤或产物查看数据',
  hint: '从左侧工作流面板选择步骤，或从右侧数据面板选择产物',
})
</script>
