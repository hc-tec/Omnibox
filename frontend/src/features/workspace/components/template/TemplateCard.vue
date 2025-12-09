<script setup lang="ts">
/**
 * 模板卡片组件
 *
 * Phase 4: 在模板市场中展示单个模板
 */

import { computed } from 'vue'
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FileText, Play, Eye } from 'lucide-vue-next'
import type { TemplateResponse } from '../../types/template'
import { TEMPLATE_CATEGORIES } from '../../types/template'

const props = defineProps<{
  template: TemplateResponse
}>()

const emit = defineEmits<{
  use: [template: TemplateResponse]
  view: [template: TemplateResponse]
}>()

const categoryLabel = computed(() => {
  const cat = props.template.category
  if (!cat) return '自定义'
  return TEMPLATE_CATEGORIES[cat as keyof typeof TEMPLATE_CATEGORIES] || cat
})

const stepTypesText = computed(() => {
  const typeMap: Record<string, string> = {
    fetch: '采集',
    process: '处理',
    analyze: '分析',
    output: '输出',
  }
  return props.template.step_types.map(t => typeMap[t] || t).join(' → ')
})

function handleUse(e: Event) {
  e.stopPropagation()
  emit('use', props.template)
}

function handleView() {
  emit('view', props.template)
}
</script>

<template>
  <Card
    class="template-card cursor-pointer transition-all hover:shadow-md hover:border-primary/30"
    @click="handleView"
  >
    <!-- 预览图 -->
    <div class="card-preview h-32 bg-muted/30 flex items-center justify-center overflow-hidden rounded-t-lg">
      <img
        v-if="template.preview_image"
        :src="template.preview_image"
        :alt="template.name"
        class="w-full h-full object-cover"
      />
      <div v-else class="flex flex-col items-center gap-2 text-muted-foreground">
        <FileText class="w-8 h-8" />
        <span class="text-xs">{{ stepTypesText }}</span>
      </div>
    </div>

    <!-- 内容 -->
    <CardHeader class="p-3 pb-2">
      <div class="flex items-start justify-between gap-2">
        <CardTitle class="text-sm font-medium line-clamp-1">
          {{ template.name }}
        </CardTitle>
        <Badge variant="outline" class="shrink-0 text-xs">
          {{ categoryLabel }}
        </Badge>
      </div>
      <CardDescription class="text-xs line-clamp-2 mt-1">
        {{ template.description || '暂无描述' }}
      </CardDescription>
    </CardHeader>

    <!-- 标签 -->
    <div v-if="template.tags.length" class="px-3 pb-2 flex flex-wrap gap-1">
      <Badge
        v-for="tag in template.tags.slice(0, 3)"
        :key="tag"
        variant="secondary"
        class="text-xs"
      >
        {{ tag }}
      </Badge>
      <span v-if="template.tags.length > 3" class="text-xs text-muted-foreground">
        +{{ template.tags.length - 3 }}
      </span>
    </div>

    <!-- 底部信息 -->
    <CardFooter class="p-3 pt-0 flex justify-between items-center">
      <div class="text-xs text-muted-foreground space-x-2">
        <span>{{ template.step_count }} 步骤</span>
        <span>·</span>
        <span>{{ template.usage_count }} 次使用</span>
      </div>
      <div class="flex gap-1">
        <Button
          variant="ghost"
          size="sm"
          class="h-7 px-2"
          @click.stop="handleView"
        >
          <Eye class="w-3.5 h-3.5" />
        </Button>
        <Button
          size="sm"
          class="h-7 px-3"
          @click="handleUse"
        >
          <Play class="w-3.5 h-3.5 mr-1" />
          使用
        </Button>
      </div>
    </CardFooter>
  </Card>
</template>

<style scoped>
.template-card {
  display: flex;
  flex-direction: column;
}
</style>
