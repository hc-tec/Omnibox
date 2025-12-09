<script setup lang="ts">
/**
 * 创建工作流对话框
 *
 * Phase 4: Workspace - 创建新工作流
 */
import { ref, computed } from 'vue'
import { Workflow } from 'lucide-vue-next'
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
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import * as workspaceApi from '../../services/workspaceApi'

const store = useWorkspaceStore()

// 表单状态
const name = ref('')
const description = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)

// 是否可以提交
const canSubmit = computed(() => {
  return name.value.trim().length > 0 && !submitting.value
})

// 提交表单
async function handleSubmit() {
  if (!canSubmit.value) return

  submitting.value = true
  error.value = null

  try {
    const workflow = await workspaceApi.createWorkflow({
      name: name.value.trim(),
      description: description.value.trim(),
      steps: [],
    })

    // 添加到工作流列表并选中
    store.workflows.push(workflow)
    store.selectWorkflow(workflow.workflow_id)

    // 关闭对话框
    handleClose()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '创建失败'
  } finally {
    submitting.value = false
  }
}

// 关闭对话框
function handleClose() {
  store.closeCreateWorkflowDialog()
  resetForm()
}

// 重置表单
function resetForm() {
  name.value = ''
  description.value = ''
  error.value = null
}
</script>

<template>
  <Dialog :open="store.showCreateWorkflowDialog" @update:open="handleClose">
    <DialogContent class="sm:max-w-[450px]">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2">
          <Workflow class="w-5 h-5" />
          创建工作流
        </DialogTitle>
        <DialogDescription>
          创建新的工作流来自动化数据处理任务
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4 py-4">
        <!-- 工作流名称 -->
        <div class="space-y-2">
          <Label for="workflow-name">名称 *</Label>
          <Input
            id="workflow-name"
            v-model="name"
            placeholder="输入工作流名称"
            @keyup.enter="handleSubmit"
          />
        </div>

        <!-- 描述 -->
        <div class="space-y-2">
          <Label for="workflow-desc">描述</Label>
          <Textarea
            id="workflow-desc"
            v-model="description"
            placeholder="可选的描述信息"
            rows="3"
          />
        </div>

        <!-- 错误提示 -->
        <div v-if="error" class="text-sm text-destructive">
          {{ error }}
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="handleClose">取消</Button>
        <Button :disabled="!canSubmit" @click="handleSubmit">
          {{ submitting ? '创建中...' : '创建' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
