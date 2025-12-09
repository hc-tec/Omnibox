<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-[425px]">
      <DialogHeader>
        <DialogTitle>保存为工作流模板</DialogTitle>
        <DialogDescription>
          将当前 Session 的 {{ stepsCount }} 个执行步骤保存为可复用的工作流模板
        </DialogDescription>
      </DialogHeader>

      <form @submit.prevent="handleSubmit" class="space-y-4">
        <!-- 模板名称 -->
        <div class="space-y-2">
          <Label for="name">模板名称</Label>
          <Input
            id="name"
            v-model="formData.name"
            placeholder="输入模板名称"
            :disabled="saving"
          />
        </div>

        <!-- 模板描述 -->
        <div class="space-y-2">
          <Label for="description">描述（可选）</Label>
          <Textarea
            id="description"
            v-model="formData.description"
            placeholder="描述这个工作流的用途..."
            :disabled="saving"
            rows="3"
          />
        </div>

        <!-- 模板分类 -->
        <div class="space-y-2">
          <Label for="category">分类</Label>
          <Select v-model="formData.category" :disabled="saving">
            <SelectTrigger>
              <SelectValue placeholder="选择分类" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="data_analysis">数据分析</SelectItem>
              <SelectItem value="content_research">内容研究</SelectItem>
              <SelectItem value="competitive">竞品分析</SelectItem>
              <SelectItem value="social_monitoring">社交监控</SelectItem>
              <SelectItem value="report_generation">报告生成</SelectItem>
              <SelectItem value="custom">自定义</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <!-- 错误提示 -->
        <div v-if="error" class="text-sm text-destructive">
          {{ error }}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            :disabled="saving"
            @click="$emit('update:open', false)"
          >
            取消
          </Button>
          <Button type="submit" :disabled="!canSubmit || saving">
            <Loader2 v-if="saving" class="mr-2 h-4 w-4 animate-spin" />
            保存模板
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useSessionStore } from '../../stores/sessionStore'

// ========== Props ==========
const props = defineProps<{
  open: boolean
  sessionId: string | null
  stepsCount: number
}>()

// ========== Emits ==========
const emit = defineEmits<{
  'update:open': [value: boolean]
  saved: [result: { workflowId: string; workflowName: string }]
}>()

// ========== Store ==========
const sessionStore = useSessionStore()

// ========== State ==========
const formData = ref({
  name: '',
  description: '',
  category: 'custom',
})
const saving = ref(false)
const error = ref<string | null>(null)

// ========== Computed ==========
const canSubmit = computed(() => {
  return formData.value.name.trim().length > 0 && props.sessionId
})

// ========== Watch ==========
watch(
  () => props.open,
  (newOpen) => {
    if (newOpen) {
      // 重置表单
      formData.value = {
        name: '',
        description: '',
        category: 'custom',
      }
      error.value = null
    }
  }
)

// ========== Methods ==========
async function handleSubmit() {
  if (!canSubmit.value) return

  saving.value = true
  error.value = null

  try {
    const result = await sessionStore.saveAsTemplate(
      formData.value.name,
      formData.value.description,
      formData.value.category
    )

    if (result.workflowId && result.workflowName) {
      emit('saved', {
        workflowId: result.workflowId,
        workflowName: result.workflowName,
      })
      emit('update:open', false)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}
</script>
