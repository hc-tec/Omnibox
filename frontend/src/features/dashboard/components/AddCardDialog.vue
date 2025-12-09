<script setup lang="ts">
/**
 * 添加卡片对话框
 *
 * Phase 5: Dashboard - 添加卡片功能
 */
import { ref, computed } from 'vue'
import { Package, Workflow, FileText } from 'lucide-vue-next'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useDashboardStore } from '../stores/dashboardStore'
import type { CardTypeValue, RefreshIntervalValue } from '../types/dashboard'

const store = useDashboardStore()

// 表单状态
const cardType = ref<CardTypeValue>('artifact')
const name = ref('')
const artifactId = ref('')
const workflowId = ref('')
const refreshInterval = ref<RefreshIntervalValue>('manual')

// 刷新选项
const refreshOptions = [
  { value: 'manual', label: '手动刷新' },
  { value: 'hourly', label: '每小时' },
  { value: 'daily', label: '每天' },
  { value: 'weekly', label: '每周' },
]

// 卡片类型选项
const cardTypeOptions = [
  { value: 'artifact', label: '数据产物', icon: Package, description: '从已有的数据产物创建卡片' },
  { value: 'workflow', label: '工作流', icon: Workflow, description: '绑定工作流，定时执行并展示结果' },
]

// 是否可以提交
const canSubmit = computed(() => {
  if (!name.value.trim()) return false
  if (cardType.value === 'artifact' && !artifactId.value.trim()) return false
  if (cardType.value === 'workflow' && !workflowId.value.trim()) return false
  return true
})

// 提交表单
async function handleSubmit() {
  if (!canSubmit.value) return

  if (cardType.value === 'artifact') {
    await store.pinArtifact({
      artifact_id: artifactId.value,
      name: name.value,
      refresh_interval: refreshInterval.value,
    })
  } else if (cardType.value === 'workflow') {
    await store.pinWorkflow({
      workflow_id: workflowId.value,
      name: name.value,
      variable_values: {},
      refresh_interval: refreshInterval.value,
    })
  }

  // 关闭对话框并重置表单
  handleClose()
}

// 关闭对话框
function handleClose() {
  store.closeAddCardDialog()
  resetForm()
}

// 重置表单
function resetForm() {
  cardType.value = 'artifact'
  name.value = ''
  artifactId.value = ''
  workflowId.value = ''
  refreshInterval.value = 'manual'
}
</script>

<template>
  <Dialog :open="store.showAddCardDialog" @update:open="handleClose">
    <DialogContent class="sm:max-w-[500px]">
      <DialogHeader>
        <DialogTitle>添加仪表盘卡片</DialogTitle>
        <DialogDescription>
          选择数据源类型，创建新的监控卡片
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-6 py-4">
        <!-- 卡片类型选择 -->
        <div class="space-y-3">
          <Label>卡片类型</Label>
          <div class="grid grid-cols-2 gap-3">
            <button
              v-for="option in cardTypeOptions"
              :key="option.value"
              type="button"
              class="flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-colors"
              :class="[
                cardType === option.value
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:border-primary/50'
              ]"
              @click="cardType = option.value as CardTypeValue"
            >
              <component :is="option.icon" class="w-6 h-6" />
              <span class="font-medium">{{ option.label }}</span>
              <span class="text-xs text-muted-foreground text-center">
                {{ option.description }}
              </span>
            </button>
          </div>
        </div>

        <!-- 卡片名称 -->
        <div class="space-y-2">
          <Label for="card-name">卡片名称</Label>
          <Input
            id="card-name"
            v-model="name"
            placeholder="输入卡片显示名称"
          />
        </div>

        <!-- 数据产物 ID（当选择 artifact 时） -->
        <div v-if="cardType === 'artifact'" class="space-y-2">
          <Label for="artifact-id">数据产物 ID</Label>
          <Input
            id="artifact-id"
            v-model="artifactId"
            placeholder="输入要监控的数据产物 ID"
          />
          <p class="text-xs text-muted-foreground">
            可以在工作台的数据产物列表中复制 ID
          </p>
        </div>

        <!-- 工作流 ID（当选择 workflow 时） -->
        <div v-if="cardType === 'workflow'" class="space-y-2">
          <Label for="workflow-id">工作流 ID</Label>
          <Input
            id="workflow-id"
            v-model="workflowId"
            placeholder="输入要绑定的工作流 ID"
          />
          <p class="text-xs text-muted-foreground">
            工作流将按设定的刷新频率自动执行
          </p>
        </div>

        <!-- 刷新频率 -->
        <div class="space-y-2">
          <Label>刷新频率</Label>
          <Select v-model="refreshInterval">
            <SelectTrigger>
              <SelectValue placeholder="选择刷新频率" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="option in refreshOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="handleClose">取消</Button>
        <Button :disabled="!canSubmit || store.loading" @click="handleSubmit">
          {{ store.loading ? '创建中...' : '创建卡片' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
