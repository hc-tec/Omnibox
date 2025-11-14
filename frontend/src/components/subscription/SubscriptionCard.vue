<script setup lang="ts">
/**
 * 订阅卡片组件
 *
 * 采用精美的玻璃态设计风格
 */
import { computed } from 'vue'
import { Pencil, Trash2 } from 'lucide-vue-next'
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { Subscription } from '@/types/subscription'
import {
  PLATFORM_DISPLAY_NAMES,
  ENTITY_TYPE_DISPLAY_NAMES,
  ACTION_DISPLAY_NAMES,
} from '@/types/subscription'

interface Props {
  subscription: Subscription
}

const props = defineProps<Props>()

interface Emits {
  (e: 'edit', subscription: Subscription): void
  (e: 'delete', id: number): void
  (e: 'action-click', subscription: Subscription, action: string): void
}

const emit = defineEmits<Emits>()

// 平台显示名称
const platformDisplay = computed(() => {
  return PLATFORM_DISPLAY_NAMES[props.subscription.platform] || props.subscription.platform
})

// 实体类型显示名称
const entityTypeDisplay = computed(() => {
  return ENTITY_TYPE_DISPLAY_NAMES[props.subscription.entity_type] || props.subscription.entity_type
})

// 获取动作的显示名称
function getActionDisplayName(action: string): string {
  return ACTION_DISPLAY_NAMES[action] || action
}

// 处理编辑
function handleEdit() {
  emit('edit', props.subscription)
}

// 处理删除
function handleDelete() {
  emit('delete', props.subscription.id)
}

// 处理动作点击
function handleActionClick(action: string) {
  emit('action-click', props.subscription, action)
}

// 平台颜色方案
const platformColors = computed(() => {
  const colorMap: Record<string, { from: string; to: string; border: string; shadow: string }> = {
    'github': { from: 'from-gray-500/20', to: 'to-slate-600/20', border: 'border-gray-500/40', shadow: 'shadow-gray-500/20' },
    'bilibili': { from: 'from-pink-500/20', to: 'to-rose-500/20', border: 'border-pink-500/40', shadow: 'shadow-pink-500/20' },
    'youtube': { from: 'from-red-500/20', to: 'to-rose-600/20', border: 'border-red-500/40', shadow: 'shadow-red-500/20' },
    'twitter': { from: 'from-sky-500/20', to: 'to-blue-500/20', border: 'border-sky-500/40', shadow: 'shadow-sky-500/20' },
    'weibo': { from: 'from-orange-500/20', to: 'to-amber-500/20', border: 'border-orange-500/40', shadow: 'shadow-orange-500/20' },
    'rss': { from: 'from-orange-500/20', to: 'to-yellow-500/20', border: 'border-orange-500/40', shadow: 'shadow-orange-500/20' },
  }
  return colorMap[props.subscription.platform] || { from: 'from-indigo-500/20', to: 'to-blue-500/20', border: 'border-indigo-500/40', shadow: 'shadow-indigo-500/20' }
})

// 卡片整体样式
const cardClass = computed(() => {
  if (!props.subscription.is_active) {
    return 'border-border/30 bg-card/30 hover:border-border/50 hover:shadow-md'
  }
  return `border-border/40 bg-card/50 hover:border-${platformColors.value.border.split('-')[1]}/60 hover:shadow-lg hover:${platformColors.value.shadow}`
})

// 顶部状态条样式
const statusBarClass = computed(() => {
  if (!props.subscription.is_active) {
    return 'bg-gradient-to-r from-gray-400/50 to-gray-500/50'
  }
  return `bg-gradient-to-r ${platformColors.value.from.replace('/20', '/70')} ${platformColors.value.to.replace('/20', '/70')} group-hover:shadow-md group-hover:${platformColors.value.shadow}`
})

// 背景渐变
const backgroundGradient = computed(() => {
  if (!props.subscription.is_active) {
    return 'group-hover:opacity-5 bg-gradient-to-br from-gray-500/10 to-slate-500/10'
  }
  return `group-hover:opacity-5 bg-gradient-to-br ${platformColors.value.from} ${platformColors.value.to}`
})

// 头像容器样式（有图片时）
const avatarContainerClass = computed(() => {
  if (!props.subscription.is_active) {
    return 'ring-2 ring-gray-400/20'
  }
  return `ring-2 ring-${platformColors.value.border.split('-')[1]}/30 group-hover:ring-${platformColors.value.border.split('-')[1]}/50 group-hover:shadow-lg group-hover:${platformColors.value.shadow}`
})

// 图标容器样式（无图片时）
const iconContainerClass = computed(() => {
  if (!props.subscription.is_active) {
    return 'bg-gradient-to-br from-gray-500/20 to-slate-500/20 ring-2 ring-gray-400/20 text-muted-foreground'
  }
  return `bg-gradient-to-br ${platformColors.value.from} ${platformColors.value.to} ring-2 ring-${platformColors.value.border.split('-')[1]}/30 group-hover:ring-${platformColors.value.border.split('-')[1]}/50 group-hover:shadow-lg group-hover:${platformColors.value.shadow}`
})
</script>

<template>
  <Card
    class="subscription-card group relative overflow-hidden rounded-[20px] border backdrop-blur-sm transition-all duration-300"
    :class="cardClass"
  >
    <!-- 顶部状态条 -->
    <div class="absolute top-0 left-0 right-0 h-1 transition-all duration-500" :class="statusBarClass" />

    <!-- 状态指示渐变背景 -->
    <div
      class="absolute inset-0 opacity-0 transition-opacity duration-300"
      :class="backgroundGradient"
    />

    <!-- 卡片头部 -->
    <CardHeader class="relative space-y-3 pb-3">
      <div class="flex items-start gap-3">
        <!-- 头像 -->
        <div
          v-if="subscription.avatar_url"
          class="flex-shrink-0 transition-all duration-300"
          :class="avatarContainerClass"
        >
          <img
            :src="subscription.avatar_url"
            :alt="subscription.display_name"
            class="h-12 w-12 rounded-xl object-cover"
          />
        </div>
        <div
          v-else
          class="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl text-lg font-semibold transition-all duration-300"
          :class="iconContainerClass"
        >
          {{ subscription.display_name[0] }}
        </div>

        <!-- 标题和元信息 -->
        <div class="min-w-0 flex-1">
          <h3 class="truncate text-base font-semibold">
            {{ subscription.display_name }}
          </h3>
          <div class="mt-1 flex items-center gap-1.5">
            <Badge variant="secondary" class="text-[10px] px-1.5 py-0 rounded-md">
              {{ platformDisplay }}
            </Badge>
            <Badge variant="outline" class="text-[10px] px-1.5 py-0 rounded-md">
              {{ entityTypeDisplay }}
            </Badge>
            <Badge
              v-if="!subscription.is_active"
              variant="destructive"
              class="text-[10px] px-1.5 py-0 rounded-md animate-pulse"
            >
              已禁用
            </Badge>
          </div>
        </div>
      </div>

      <!-- 描述 -->
      <p v-if="subscription.description" class="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
        {{ subscription.description }}
      </p>
    </CardHeader>

    <CardContent class="relative space-y-3 pb-3">
      <!-- 标签 -->
      <div v-if="subscription.tags.length > 0" class="flex flex-wrap gap-1.5">
        <Badge
          v-for="tag in subscription.tags.slice(0, 4)"
          :key="tag"
          variant="outline"
          class="rounded-full text-[10px] px-2 py-0 border-border/40 bg-background/30 transition hover:bg-background/50"
        >
          {{ tag }}
        </Badge>
        <Badge
          v-if="subscription.tags.length > 4"
          variant="outline"
          class="rounded-full text-[10px] px-2 py-0 border-border/40 bg-background/30"
        >
          +{{ subscription.tags.length - 4 }}
        </Badge>
      </div>

      <!-- 支持的操作 -->
      <div v-if="subscription.supported_actions.length > 0" class="space-y-2">
        <p class="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          支持的操作
        </p>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="action in subscription.supported_actions"
            :key="action"
            class="inline-flex items-center rounded-lg border border-border/40 bg-background/50 px-2.5 py-1 text-xs font-medium transition-all duration-200 hover:scale-105 hover:border-primary/40 hover:bg-primary/10 hover:text-primary hover:shadow-sm"
            @click="handleActionClick(action)"
          >
            {{ getActionDisplayName(action) }}
          </button>
        </div>
      </div>
    </CardContent>

    <CardFooter class="relative border-t border-border/20 pt-3 flex gap-2">
      <Button
        variant="ghost"
        size="sm"
        class="flex-1 rounded-xl text-xs h-8 transition-all duration-200 hover:scale-105"
        @click="handleEdit"
      >
        <Pencil class="mr-1.5 h-3.5 w-3.5" />
        编辑
      </Button>
      <Button
        variant="ghost"
        size="sm"
        class="flex-1 rounded-xl text-xs h-8 text-destructive hover:text-destructive hover:bg-destructive/10 transition-all duration-200 hover:scale-105"
        @click="handleDelete"
      >
        <Trash2 class="mr-1.5 h-3.5 w-3.5" />
        删除
      </Button>
    </CardFooter>
  </Card>
</template>
