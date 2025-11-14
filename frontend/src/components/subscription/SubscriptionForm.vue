<script setup lang="ts">
/**
 * 订阅表单组件
 *
 * 用于创建和编辑订阅
 * 使用 shadcn-vue 组件：Dialog, Input, Select, Label, Button
 */
import { ref, reactive, watch, computed } from 'vue'
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
import { Textarea } from '@/components/ui/textarea'
import type {
  Subscription,
  SubscriptionCreateRequest,
  SubscriptionUpdateRequest,
} from '@/types/subscription'

interface Props {
  open: boolean
  mode: 'create' | 'edit'
  subscription?: Subscription | null
}

const props = defineProps<Props>()

interface Emits {
  (e: 'update:open', value: boolean): void
  (e: 'submit', data: SubscriptionCreateRequest | SubscriptionUpdateRequest): void
}

const emit = defineEmits<Emits>()

// 表单数据
const formData = reactive({
  display_name: '',
  platform: 'bilibili',
  entity_type: 'user',
  identifiers: {} as Record<string, string>,
  description: '',
  avatar_url: '',
  aliases: [] as string[],
  tags: [] as string[],
})

// 标识符字段（JSON输入）
const identifiersText = ref('')
const aliasesText = ref('')
const tagsText = ref('')

// 提交加载状态
const loading = ref(false)

// 监听props变化，初始化表单
watch(
  () => props.subscription,
  (newVal) => {
    if (newVal && props.mode === 'edit') {
      formData.display_name = newVal.display_name
      formData.platform = newVal.platform
      formData.entity_type = newVal.entity_type
      formData.identifiers = newVal.identifiers
      formData.description = newVal.description || ''
      formData.avatar_url = newVal.avatar_url || ''
      formData.aliases = [...newVal.aliases]
      formData.tags = [...newVal.tags]

      // 更新文本字段
      identifiersText.value = JSON.stringify(newVal.identifiers, null, 2)
      aliasesText.value = newVal.aliases.join(', ')
      tagsText.value = newVal.tags.join(', ')
    }
  },
  { immediate: true }
)

// 监听open变化，重置表单和loading状态
watch(
  () => props.open,
  (newVal) => {
    if (newVal && props.mode === 'create') {
      // 重置表单
      formData.display_name = ''
      formData.platform = 'bilibili'
      formData.entity_type = 'user'
      formData.identifiers = {}
      formData.description = ''
      formData.avatar_url = ''
      formData.aliases = []
      formData.tags = []

      identifiersText.value = '{}'
      aliasesText.value = ''
      tagsText.value = ''
    }

    // 对话框关闭时重置loading状态
    if (!newVal) {
      loading.value = false
    }
  }
)

// 对话框标题
const dialogTitle = computed(() => {
  return props.mode === 'create' ? '添加订阅' : '编辑订阅'
})

// 解析标识符
function parseIdentifiers(): Record<string, any> | null {
  try {
    return JSON.parse(identifiersText.value || '{}')
  } catch (err) {
    return null
  }
}

// 解析别名
function parseAliases(): string[] {
  return aliasesText.value
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
}

// 解析标签
function parseTags(): string[] {
  return tagsText.value
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
}

// 提交表单
function handleSubmit() {
  // 验证必填字段
  if (!formData.display_name) {
    alert('请输入显示名称')
    return
  }

  // 解析标识符
  const identifiers = parseIdentifiers()
  if (!identifiers || Object.keys(identifiers).length === 0) {
    alert('请输入有效的标识符（JSON格式）')
    return
  }

  loading.value = true

  const data: SubscriptionCreateRequest | SubscriptionUpdateRequest = {
    display_name: formData.display_name,
    platform: formData.platform,
    entity_type: formData.entity_type,
    identifiers,
    description: formData.description || undefined,
    avatar_url: formData.avatar_url || undefined,
    aliases: parseAliases(),
    tags: parseTags(),
  }

  // 触发提交事件，由父组件处理成功/失败逻辑
  emit('submit', data)
}

// 关闭对话框
function handleClose() {
  emit('update:open', false)
}
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="subscription-form max-w-2xl max-h-[90vh] overflow-y-auto rounded-[28px] border-2 border-border/30 bg-gradient-to-b from-card/98 to-card/95 shadow-2xl shadow-black/10 backdrop-blur-xl">
      <!-- 顶部装饰渐变 -->
      <div class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 via-blue-500 to-indigo-500 rounded-t-[28px]" />

      <DialogHeader class="relative">
        <DialogTitle class="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-blue-600 bg-clip-text text-transparent">
          {{ dialogTitle }}
        </DialogTitle>
        <DialogDescription class="text-sm text-muted-foreground/80 mt-1">
          填写订阅信息。标识符请使用JSON格式（如：{"uid": "12345"}）
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-5 py-6">
        <!-- 基本信息分组 -->
        <div class="space-y-4 rounded-2xl border border-border/20 bg-background/30 p-4">
          <p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">基本信息</p>

          <!-- 显示名称 -->
          <div class="space-y-2">
            <Label for="display_name" class="text-sm font-medium">显示名称 *</Label>
            <Input
              id="display_name"
              v-model="formData.display_name"
              placeholder="如：科技美学"
              class="rounded-xl border-border/40 bg-background/50 transition-all duration-200 focus:border-indigo-500/50 focus:bg-background/80 focus:shadow-sm focus:shadow-indigo-500/10"
            />
          </div>

          <!-- 平台和实体类型 - 两列布局 -->
          <div class="grid grid-cols-2 gap-3">
            <!-- 平台 -->
            <div class="space-y-2">
              <Label for="platform" class="text-sm font-medium">平台 *</Label>
              <Select v-model="formData.platform">
                <SelectTrigger id="platform" class="rounded-xl border-border/40 bg-background/50 transition-all duration-200 focus:border-indigo-500/50 focus:shadow-sm focus:shadow-indigo-500/10">
                  <SelectValue placeholder="选择平台" />
                </SelectTrigger>
                <SelectContent class="rounded-xl">
                  <SelectItem value="bilibili">B站</SelectItem>
                  <SelectItem value="zhihu">知乎</SelectItem>
                  <SelectItem value="weibo">微博</SelectItem>
                  <SelectItem value="github">GitHub</SelectItem>
                  <SelectItem value="gitee">Gitee</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <!-- 实体类型 -->
            <div class="space-y-2">
              <Label for="entity_type" class="text-sm font-medium">实体类型 *</Label>
              <Select v-model="formData.entity_type">
                <SelectTrigger id="entity_type" class="rounded-xl border-border/40 bg-background/50 transition-all duration-200 focus:border-indigo-500/50 focus:shadow-sm focus:shadow-indigo-500/10">
                  <SelectValue placeholder="选择实体类型" />
                </SelectTrigger>
                <SelectContent class="rounded-xl">
                  <SelectItem value="user">用户</SelectItem>
                  <SelectItem value="column">专栏</SelectItem>
                  <SelectItem value="repo">仓库</SelectItem>
                  <SelectItem value="topic">话题</SelectItem>
                  <SelectItem value="channel">频道</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <!-- 标识符分组 -->
        <div class="space-y-4 rounded-2xl border border-indigo-500/20 bg-indigo-500/5 p-4">
          <p class="text-xs font-semibold uppercase tracking-wider text-indigo-600">标识符配置</p>

          <div class="space-y-2">
            <Label for="identifiers" class="text-sm font-medium">标识符（JSON格式）*</Label>
            <Textarea
              id="identifiers"
              v-model="identifiersText"
              placeholder='{"uid": "12345"}'
              rows="3"
              class="font-mono text-sm rounded-xl border-border/40 bg-background/50 transition-all duration-200 focus:border-indigo-500/50 focus:bg-background/80 focus:shadow-sm focus:shadow-indigo-500/10"
            />
            <p class="text-xs text-muted-foreground">
              示例：B站UP主 {"uid": "12345"}，GitHub {"owner": "xxx", "repo": "yyy"}
            </p>
          </div>
        </div>

        <!-- 补充信息分组 -->
        <div class="space-y-4 rounded-2xl border border-border/20 bg-background/30 p-4">
          <p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">补充信息</p>

          <!-- 描述 -->
          <div class="space-y-2">
            <Label for="description" class="text-sm font-medium">描述</Label>
            <Textarea
              id="description"
              v-model="formData.description"
              placeholder="简要描述"
              rows="2"
              class="rounded-xl border-border/40 bg-background/50 transition-all duration-200 focus:border-indigo-500/50 focus:bg-background/80 focus:shadow-sm focus:shadow-indigo-500/10"
            />
          </div>

          <!-- 头像URL -->
          <div class="space-y-2">
            <Label for="avatar_url" class="text-sm font-medium">头像URL</Label>
            <Input
              id="avatar_url"
              v-model="formData.avatar_url"
              placeholder="https://..."
              class="rounded-xl border-border/40 bg-background/50 transition-all duration-200 focus:border-indigo-500/50 focus:bg-background/80 focus:shadow-sm focus:shadow-indigo-500/10"
            />
          </div>

          <!-- 别名 -->
          <div class="space-y-2">
            <Label for="aliases" class="text-sm font-medium">别名（逗号分隔）</Label>
            <Input
              id="aliases"
              v-model="aliasesText"
              placeholder="科技美学, 科技美学Official, 那岩"
              class="rounded-xl border-border/40 bg-background/50 transition-all duration-200 focus:border-indigo-500/50 focus:bg-background/80 focus:shadow-sm focus:shadow-indigo-500/10"
            />
          </div>

          <!-- 标签 -->
          <div class="space-y-2">
            <Label for="tags" class="text-sm font-medium">标签（逗号分隔）</Label>
            <Input
              id="tags"
              v-model="tagsText"
              placeholder="数码, 科技, 测评"
              class="rounded-xl border-border/40 bg-background/50 transition-all duration-200 focus:border-indigo-500/50 focus:bg-background/80 focus:shadow-sm focus:shadow-indigo-500/10"
            />
          </div>
        </div>
      </div>

      <DialogFooter class="gap-3 pt-2">
        <Button
          variant="outline"
          @click="handleClose"
          :disabled="loading"
          class="rounded-xl border-border/40 transition-all duration-200 hover:scale-105 hover:shadow-sm"
        >
          取消
        </Button>
        <Button
          @click="handleSubmit"
          :disabled="loading"
          class="group relative overflow-hidden rounded-xl bg-gradient-to-br from-indigo-500 via-blue-500 to-indigo-600 shadow-lg shadow-indigo-500/25 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-indigo-500/40 disabled:opacity-50 disabled:hover:scale-100"
        >
          <!-- 提交按钮发光效果 -->
          <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
          <span class="relative flex items-center gap-2">
            <span v-if="loading" class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            {{ loading ? '提交中...' : '提交' }}
          </span>
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
