<script setup lang="ts">
/**
 * 导入模板对话框
 *
 * Phase 4: 从 JSON 文件导入模板
 */

import { ref } from 'vue'
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
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Upload, FileJson, Loader2, AlertCircle, CheckCircle } from 'lucide-vue-next'
import { useTemplateStore } from '../../stores/templateStore'

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  imported: []
}>()

const store = useTemplateStore()

// 状态
const author = ref('')
const selectedFile = ref<File | null>(null)
const fileContent = ref<Record<string, unknown> | null>(null)
const error = ref('')
const loading = ref(false)
const success = ref(false)

// 文件选择
function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  if (!file) return

  // 验证文件类型
  if (!file.name.endsWith('.json')) {
    error.value = '请选择 JSON 文件'
    return
  }

  selectedFile.value = file
  error.value = ''
  success.value = false

  // 读取文件内容预览
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const content = JSON.parse(e.target?.result as string)
      fileContent.value = content
    } catch {
      error.value = 'JSON 文件格式错误'
      fileContent.value = null
    }
  }
  reader.readAsText(file)
}

// 导入
async function handleImport() {
  if (!selectedFile.value) {
    error.value = '请选择文件'
    return
  }

  loading.value = true
  error.value = ''

  try {
    const template = await store.importTemplateFromFile(
      selectedFile.value,
      author.value || 'imported'
    )

    if (template) {
      success.value = true
      setTimeout(() => {
        emit('imported')
        resetForm()
      }, 1000)
    } else {
      error.value = store.error || '导入失败'
    }
  } finally {
    loading.value = false
  }
}

// 重置表单
function resetForm() {
  selectedFile.value = null
  fileContent.value = null
  author.value = ''
  error.value = ''
  success.value = false
}

// 关闭时重置
function handleClose() {
  resetForm()
  open.value = false
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="max-w-md">
      <DialogHeader>
        <DialogTitle>导入模板</DialogTitle>
        <DialogDescription>
          从 JSON 文件导入工作流模板
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4 py-4">
        <!-- 文件选择 -->
        <div class="space-y-2">
          <Label>选择文件</Label>
          <div
            class="border-2 border-dashed rounded-lg p-6 text-center hover:border-primary/50 transition-colors cursor-pointer"
            @click="($refs.fileInput as HTMLInputElement)?.click()"
          >
            <input
              ref="fileInput"
              type="file"
              accept=".json"
              class="hidden"
              @change="handleFileSelect"
            />

            <div v-if="selectedFile" class="flex flex-col items-center gap-2">
              <FileJson class="w-10 h-10 text-primary" />
              <span class="text-sm font-medium">{{ selectedFile.name }}</span>
              <span class="text-xs text-muted-foreground">
                {{ (selectedFile.size / 1024).toFixed(1) }} KB
              </span>
            </div>

            <div v-else class="flex flex-col items-center gap-2 text-muted-foreground">
              <Upload class="w-10 h-10" />
              <span class="text-sm">点击或拖拽 JSON 文件到此处</span>
            </div>
          </div>
        </div>

        <!-- 文件预览 -->
        <div v-if="fileContent" class="space-y-2">
          <Label>模板信息</Label>
          <div class="bg-muted/30 rounded-md p-3 text-sm space-y-1">
            <div v-if="(fileContent.template as Record<string, unknown>)?.name">
              <span class="text-muted-foreground">名称: </span>
              {{ (fileContent.template as Record<string, unknown>).name }}
            </div>
            <div v-if="(fileContent.template as Record<string, unknown>)?.description">
              <span class="text-muted-foreground">描述: </span>
              {{ (fileContent.template as Record<string, unknown>).description }}
            </div>
            <div v-if="(fileContent.template as Record<string, unknown>)?.category">
              <span class="text-muted-foreground">分类: </span>
              {{ (fileContent.template as Record<string, unknown>).category }}
            </div>
          </div>
        </div>

        <!-- 作者 -->
        <div class="space-y-2">
          <Label for="author">导入者标记</Label>
          <Input
            id="author"
            v-model="author"
            placeholder="你的名字（可选）"
          />
        </div>

        <!-- 错误提示 -->
        <Alert v-if="error" variant="destructive">
          <AlertCircle class="h-4 w-4" />
          <AlertDescription>{{ error }}</AlertDescription>
        </Alert>

        <!-- 成功提示 -->
        <Alert v-if="success" class="border-green-500 text-green-700">
          <CheckCircle class="h-4 w-4" />
          <AlertDescription>导入成功！</AlertDescription>
        </Alert>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="handleClose">
          取消
        </Button>
        <Button
          @click="handleImport"
          :disabled="!selectedFile || loading || success"
        >
          <Loader2 v-if="loading" class="w-4 h-4 mr-1 animate-spin" />
          <Upload v-else class="w-4 h-4 mr-1" />
          导入
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
