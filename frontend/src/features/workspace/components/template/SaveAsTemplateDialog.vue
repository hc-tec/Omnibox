<script setup lang="ts">
/**
 * 保存为模板对话框
 *
 * Phase 4: 将工作流保存为可复用的模板
 */

import { ref, computed, watch } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, AlertCircle, CheckCircle, Save, Tag } from 'lucide-vue-next'
import { TEMPLATE_CATEGORIES } from '../../types/template'
import type { Workflow, Variable } from '../../types/workspace'
import { useTemplateStore } from '../../stores/templateStore'

const props = defineProps<{
  workflow: Workflow | null
  extractedVariables?: Record<string, Variable>
}>()

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  saved: [templateId: string]
}>()

const store = useTemplateStore()

// 表单状态
const category = ref('custom')
const author = ref('')
const tagsInput = ref('')
const error = ref('')
const loading = ref(false)
const success = ref(false)

// 解析后的标签列表
const tagsList = computed(() => {
  if (!tagsInput.value.trim()) return []
  return tagsInput.value.split(/[,，\s]+/).filter(Boolean)
})

// 变量预览
const variableList = computed(() => {
  if (props.extractedVariables) {
    return Object.entries(props.extractedVariables)
  }
  return []
})

// 初始化
watch(open, (isOpen) => {
  if (isOpen) {
    category.value = 'custom'
    author.value = ''
    tagsInput.value = ''
    error.value = ''
    success.value = false
  }
})

// 保存
async function handleSave() {
  if (!props.workflow) {
    error.value = '工作流不存在'
    return
  }

  loading.value = true
  error.value = ''

  try {
    const template = await store.createTemplate({
      workflow_id: props.workflow.workflow_id,
      category: category.value,
      author: author.value || 'anonymous',
      tags: tagsList.value.length > 0 ? tagsList.value : undefined,
    })

    if (template) {
      success.value = true
      setTimeout(() => {
        emit('saved', template.template_id)
        open.value = false
      }, 1000)
    } else {
      error.value = store.error || '保存失败'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="max-w-lg">
      <DialogHeader>
        <DialogTitle>保存为模板</DialogTitle>
        <DialogDescription>
          将当前工作流保存为可复用的模板
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4 py-4">
        <!-- 工作流信息 -->
        <div class="bg-muted/30 rounded-md p-3">
          <div class="font-medium">{{ workflow?.name }}</div>
          <div class="text-sm text-muted-foreground mt-1">
            {{ workflow?.description || '暂无描述' }}
          </div>
        </div>

        <!-- 分类 -->
        <div class="space-y-2">
          <Label>分类</Label>
          <Select v-model="category">
            <SelectTrigger>
              <SelectValue placeholder="选择分类" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="(label, key) in TEMPLATE_CATEGORIES"
                :key="key"
                :value="key"
              >
                {{ label }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <!-- 作者 -->
        <div class="space-y-2">
          <Label for="author">作者</Label>
          <Input
            id="author"
            v-model="author"
            placeholder="你的名字"
          />
        </div>

        <!-- 标签 -->
        <div class="space-y-2">
          <Label for="tags">
            标签
            <span class="text-muted-foreground text-xs ml-1">（逗号分隔）</span>
          </Label>
          <Textarea
            id="tags"
            v-model="tagsInput"
            placeholder="例如: 竞品分析, B站, 视频"
            :rows="2"
          />
          <div v-if="tagsList.length" class="flex flex-wrap gap-1 mt-2">
            <Badge
              v-for="tag in tagsList"
              :key="tag"
              variant="secondary"
            >
              <Tag class="w-3 h-3 mr-1" />
              {{ tag }}
            </Badge>
          </div>
        </div>

        <!-- 变量预览 -->
        <div v-if="variableList.length" class="space-y-2">
          <Label>识别到的变量</Label>
          <div class="text-xs text-muted-foreground">
            以下参数将作为模板变量，使用时需要填写：
          </div>
          <div class="space-y-1 mt-2">
            <div
              v-for="[name, variable] in variableList"
              :key="name"
              class="flex items-center gap-2 text-sm bg-muted/30 rounded px-2 py-1"
            >
              <Badge variant="outline" class="text-xs">
                {{ variable.var_type }}
              </Badge>
              <span class="font-mono">{{ name }}</span>
              <span class="text-muted-foreground text-xs">
                {{ variable.description }}
              </span>
            </div>
          </div>
        </div>

        <!-- 无变量提示 -->
        <div v-else class="text-sm text-muted-foreground text-center py-2 bg-muted/30 rounded">
          未检测到可模板化的变量
        </div>

        <!-- 错误提示 -->
        <Alert v-if="error" variant="destructive">
          <AlertCircle class="h-4 w-4" />
          <AlertDescription>{{ error }}</AlertDescription>
        </Alert>

        <!-- 成功提示 -->
        <Alert v-if="success" class="border-green-500 text-green-700">
          <CheckCircle class="h-4 w-4" />
          <AlertDescription>模板保存成功！</AlertDescription>
        </Alert>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="open = false">
          取消
        </Button>
        <Button @click="handleSave" :disabled="loading || success">
          <Loader2 v-if="loading" class="w-4 h-4 mr-1 animate-spin" />
          <Save v-else class="w-4 h-4 mr-1" />
          保存模板
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
