<script setup lang="ts">
/**
 * 卡片设置对话框
 *
 * Phase 5: Dashboard - 编辑卡片设置
 */
import { ref, watch, computed } from 'vue'
import { Settings, Bell, Trash2, Plus } from 'lucide-vue-next'
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
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useDashboardStore } from '../stores/dashboardStore'
import type { RefreshIntervalValue, Trigger, TriggerTypeValue, TriggerActionValue } from '../types/dashboard'

const store = useDashboardStore()

// 表单状态
const name = ref('')
const description = ref('')
const refreshInterval = ref<RefreshIntervalValue>('manual')
const enabled = ref(true)
const triggers = ref<Trigger[]>([])
const activeTab = ref('basic')

// 刷新选项
const refreshOptions = [
  { value: 'manual', label: '手动刷新' },
  { value: 'hourly', label: '每小时' },
  { value: 'daily', label: '每天' },
  { value: 'weekly', label: '每周' },
]

// 触发器类型选项
const triggerTypeOptions = [
  { value: 'value_change', label: '值变化' },
  { value: 'threshold', label: '阈值触发' },
  { value: 'pattern', label: '模式匹配' },
]

// 触发器动作选项
const actionOptions = [
  { value: 'notify', label: '发送通知' },
  { value: 'refresh', label: '刷新卡片' },
  { value: 'run_workflow', label: '执行工作流' },
]

// 监听选中的卡片变化
watch(() => store.selectedCard, (card) => {
  if (card) {
    name.value = card.name
    description.value = card.description || ''
    refreshInterval.value = card.refresh_interval
    enabled.value = card.enabled
    triggers.value = [...(card.triggers || [])]
  }
}, { immediate: true })

// 添加触发器
function addTrigger() {
  const newTrigger: Trigger = {
    trigger_id: `trg-${Date.now()}`,
    name: '新触发器',
    enabled: true,
    trigger_type: 'threshold',
    condition: { field: '', operator: 'gt', value: 0 },
    action: 'notify',
    action_config: { message: '数据发生变化' },
  }
  triggers.value.push(newTrigger)
}

// 删除触发器
function removeTrigger(index: number) {
  triggers.value.splice(index, 1)
}

// 保存设置
async function handleSave() {
  if (!store.selectedCard) return

  const success = await store.updateCard(store.selectedCard.card_id, {
    name: name.value,
    description: description.value,
    refresh_interval: refreshInterval.value,
    enabled: enabled.value,
  })

  if (success && triggers.value.length > 0) {
    await store.updateTriggers(store.selectedCard.card_id, triggers.value)
  }

  if (success) {
    handleClose()
  }
}

// 关闭对话框
function handleClose() {
  store.closeSettingsDialog()
  activeTab.value = 'basic'
}

// 卡片类型显示
const cardTypeLabel = computed(() => {
  const card = store.selectedCard
  if (!card) return ''
  const types: Record<string, string> = {
    artifact: '数据产物',
    workflow: '工作流',
    custom: '自定义查询',
  }
  return types[card.card_type] || card.card_type
})
</script>

<template>
  <Dialog :open="store.showSettingsDialog" @update:open="handleClose">
    <DialogContent class="sm:max-w-[600px]">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2">
          <Settings class="w-5 h-5" />
          卡片设置
        </DialogTitle>
        <DialogDescription>
          编辑卡片的基本信息、刷新策略和触发器
        </DialogDescription>
      </DialogHeader>

      <Tabs v-model="activeTab" class="w-full">
        <TabsList class="grid w-full grid-cols-2">
          <TabsTrigger value="basic">基本设置</TabsTrigger>
          <TabsTrigger value="triggers">
            触发器
            <span v-if="triggers.length" class="ml-1 text-xs bg-primary/20 px-1.5 rounded">
              {{ triggers.length }}
            </span>
          </TabsTrigger>
        </TabsList>

        <!-- 基本设置 -->
        <TabsContent value="basic" class="space-y-4 mt-4">
          <!-- 卡片名称 -->
          <div class="space-y-2">
            <Label for="edit-name">卡片名称</Label>
            <Input id="edit-name" v-model="name" />
          </div>

          <!-- 描述 -->
          <div class="space-y-2">
            <Label for="edit-desc">描述</Label>
            <Input id="edit-desc" v-model="description" placeholder="可选的描述信息" />
          </div>

          <!-- 卡片类型（只读） -->
          <div class="space-y-2">
            <Label>卡片类型</Label>
            <div class="text-sm text-muted-foreground bg-muted px-3 py-2 rounded-md">
              {{ cardTypeLabel }}
            </div>
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

          <!-- 启用状态 -->
          <div class="flex items-center justify-between">
            <div>
              <Label>启用卡片</Label>
              <p class="text-xs text-muted-foreground">禁用后卡片将不会自动刷新</p>
            </div>
            <Switch v-model:checked="enabled" />
          </div>
        </TabsContent>

        <!-- 触发器设置 -->
        <TabsContent value="triggers" class="space-y-4 mt-4">
          <div class="text-sm text-muted-foreground mb-4">
            当数据满足条件时，自动执行指定的动作
          </div>

          <!-- 触发器列表 -->
          <div class="space-y-3">
            <div
              v-for="(trigger, index) in triggers"
              :key="trigger.trigger_id"
              class="border rounded-lg p-4 space-y-3"
            >
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <Switch v-model:checked="trigger.enabled" />
                  <Input
                    v-model="trigger.name"
                    class="w-40 h-8"
                    placeholder="触发器名称"
                  />
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  class="text-destructive"
                  @click="removeTrigger(index)"
                >
                  <Trash2 class="w-4 h-4" />
                </Button>
              </div>

              <div class="grid grid-cols-2 gap-3">
                <!-- 触发类型 -->
                <div class="space-y-1">
                  <Label class="text-xs">触发类型</Label>
                  <Select v-model="trigger.trigger_type">
                    <SelectTrigger class="h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem
                        v-for="opt in triggerTypeOptions"
                        :key="opt.value"
                        :value="opt.value"
                      >
                        {{ opt.label }}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <!-- 触发动作 -->
                <div class="space-y-1">
                  <Label class="text-xs">触发动作</Label>
                  <Select v-model="trigger.action">
                    <SelectTrigger class="h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem
                        v-for="opt in actionOptions"
                        :key="opt.value"
                        :value="opt.value"
                      >
                        {{ opt.label }}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <!-- 阈值条件（当类型为 threshold 时） -->
              <div v-if="trigger.trigger_type === 'threshold'" class="grid grid-cols-3 gap-2">
                <Input
                  :model-value="String(trigger.condition.field || '')"
                  placeholder="字段名"
                  class="h-8"
                  @update:model-value="(v) => trigger.condition.field = v"
                />
                <Select
                  :model-value="String(trigger.condition.operator || 'gt')"
                  @update:model-value="(v) => trigger.condition.operator = v"
                >
                  <SelectTrigger class="h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="gt">大于</SelectItem>
                    <SelectItem value="lt">小于</SelectItem>
                    <SelectItem value="eq">等于</SelectItem>
                    <SelectItem value="gte">大于等于</SelectItem>
                    <SelectItem value="lte">小于等于</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  :model-value="String(trigger.condition.value || 0)"
                  type="number"
                  placeholder="阈值"
                  class="h-8"
                  @update:model-value="(v) => trigger.condition.value = Number(v)"
                />
              </div>

              <!-- 通知消息（当动作为 notify 时） -->
              <div v-if="trigger.action === 'notify'">
                <Input
                  :model-value="String(trigger.action_config.message || '')"
                  placeholder="通知消息内容"
                  class="h-8"
                  @update:model-value="(v) => trigger.action_config.message = v"
                />
              </div>
            </div>
          </div>

          <!-- 添加触发器按钮 -->
          <Button variant="outline" class="w-full" @click="addTrigger">
            <Plus class="w-4 h-4 mr-2" />
            添加触发器
          </Button>
        </TabsContent>
      </Tabs>

      <DialogFooter>
        <Button variant="outline" @click="handleClose">取消</Button>
        <Button @click="handleSave">保存</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
