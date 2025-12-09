<!--
  错误条目组件 - Manus 风格（使用 shadcn UI）
-->
<script setup lang="ts">
import { ref } from 'vue'
import { AlertCircle, ChevronDown, ChevronRight } from 'lucide-vue-next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import type { TimelineEntry } from '../../../types/workspace'

defineProps<{
  entry: TimelineEntry
}>()

// 详情折叠状态
const showDetails = ref(false)
</script>

<template>
  <Alert variant="destructive" class="border-l-[3px]">
    <AlertCircle class="h-4 w-4" />
    <AlertTitle class="text-sm font-medium">执行错误</AlertTitle>
    <AlertDescription class="text-xs mt-1">
      {{ entry.error?.message }}
    </AlertDescription>

    <!-- 详细信息 -->
    <div v-if="entry.error?.details" class="mt-2">
      <Button
        variant="ghost"
        size="sm"
        class="h-6 px-2 text-xs"
        @click="showDetails = !showDetails"
      >
        <component :is="showDetails ? ChevronDown : ChevronRight" class="h-3 w-3 mr-1" />
        {{ showDetails ? '隐藏详情' : '显示详情' }}
      </Button>
      <pre
        v-if="showDetails"
        class="mt-2 p-2 bg-destructive/5 rounded text-xs overflow-x-auto max-h-32"
      >{{ entry.error.details }}</pre>
    </div>
  </Alert>
</template>
