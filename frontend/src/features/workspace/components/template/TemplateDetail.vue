<script setup lang="ts">
/**
 * 模板详情弹窗
 *
 * Phase 4: 展示模板详细信息
 */

import { computed } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  User,
  Calendar,
  Download,
  Play,
  FileText,
  Settings,
  Tag,
} from 'lucide-vue-next'
import type { TemplateResponse } from '../../types/template'
import { TEMPLATE_CATEGORIES } from '../../types/template'
import { useTemplateStore } from '../../stores/templateStore'

const props = defineProps<{
  template: TemplateResponse | null
}>()

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  use: [template: TemplateResponse]
}>()

const store = useTemplateStore()

const categoryLabel = computed(() => {
  const cat = props.template?.category
  if (!cat) return '自定义'
  return TEMPLATE_CATEGORIES[cat as keyof typeof TEMPLATE_CATEGORIES] || cat
})

const stepTypesText = computed(() => {
  if (!props.template) return ''
  const typeMap: Record<string, string> = {
    fetch: '数据采集',
    process: '数据处理',
    analyze: '数据分析',
    output: '结果输出',
  }
  return props.template.step_types.map(t => typeMap[t] || t).join(' → ')
})

const variableList = computed(() => {
  if (!props.template) return []
  return Object.entries(props.template.variables).map(([name, schema]) => ({
    name,
    ...schema,
  }))
})

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function handleUse() {
  if (props.template) {
    emit('use', props.template)
    open.value = false
  }
}

async function handleExport() {
  if (props.template) {
    await store.exportTemplate(props.template.template_id, `${props.template.name}.json`)
  }
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
      <DialogHeader>
        <div class="flex items-start justify-between">
          <div>
            <DialogTitle class="text-xl">{{ template?.name }}</DialogTitle>
            <DialogDescription class="mt-1">
              {{ template?.description || '暂无描述' }}
            </DialogDescription>
          </div>
          <Badge variant="outline">{{ categoryLabel }}</Badge>
        </div>
      </DialogHeader>

      <div class="flex-1 overflow-auto space-y-6 py-4">
        <!-- 基本信息 -->
        <div class="grid grid-cols-2 gap-4 text-sm">
          <div class="flex items-center gap-2 text-muted-foreground">
            <User class="w-4 h-4" />
            <span>作者: {{ template?.author || '匿名' }}</span>
          </div>
          <div class="flex items-center gap-2 text-muted-foreground">
            <Calendar class="w-4 h-4" />
            <span>创建于: {{ template ? formatDate(template.created_at) : '' }}</span>
          </div>
          <div class="flex items-center gap-2 text-muted-foreground">
            <FileText class="w-4 h-4" />
            <span>{{ template?.step_count }} 个步骤</span>
          </div>
          <div class="flex items-center gap-2 text-muted-foreground">
            <Play class="w-4 h-4" />
            <span>已使用 {{ template?.usage_count }} 次</span>
          </div>
        </div>

        <Separator />

        <!-- 工作流概要 -->
        <div>
          <h4 class="text-sm font-medium mb-2 flex items-center gap-2">
            <Settings class="w-4 h-4" />
            工作流程
          </h4>
          <div class="text-sm text-muted-foreground bg-muted/30 rounded-md px-3 py-2">
            {{ stepTypesText }}
          </div>
        </div>

        <!-- 变量定义 -->
        <div v-if="variableList.length">
          <h4 class="text-sm font-medium mb-2 flex items-center gap-2">
            <Tag class="w-4 h-4" />
            变量定义 ({{ variableList.length }})
          </h4>
          <div class="space-y-2">
            <div
              v-for="variable in variableList"
              :key="variable.name"
              class="flex items-start justify-between bg-muted/30 rounded-md px-3 py-2"
            >
              <div>
                <div class="flex items-center gap-2">
                  <span class="font-mono text-sm">{{ variable.name }}</span>
                  <Badge variant="outline" class="text-xs">
                    {{ variable.var_type }}
                  </Badge>
                  <Badge v-if="variable.required" variant="destructive" class="text-xs">
                    必填
                  </Badge>
                </div>
                <p class="text-xs text-muted-foreground mt-1">
                  {{ variable.description || '无描述' }}
                </p>
              </div>
              <div v-if="variable.default !== undefined" class="text-xs text-muted-foreground">
                默认: {{ variable.default }}
              </div>
            </div>
          </div>
        </div>

        <!-- 标签 -->
        <div v-if="template?.tags.length">
          <h4 class="text-sm font-medium mb-2">标签</h4>
          <div class="flex flex-wrap gap-2">
            <Badge
              v-for="tag in template.tags"
              :key="tag"
              variant="secondary"
            >
              {{ tag }}
            </Badge>
          </div>
        </div>
      </div>

      <DialogFooter class="flex gap-2">
        <Button variant="outline" @click="handleExport">
          <Download class="w-4 h-4 mr-1" />
          导出
        </Button>
        <Button @click="handleUse">
          <Play class="w-4 h-4 mr-1" />
          使用此模板
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
