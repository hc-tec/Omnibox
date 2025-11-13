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
</script>

<template>
  <Card class="group relative overflow-hidden rounded-[20px] border border-border/40 bg-card/50 backdrop-blur transition-all hover:border-border/60 hover:shadow-lg hover:shadow-black/5">
    <!-- 卡片头部 -->
    <CardHeader class="space-y-3 pb-3">
      <div class="flex items-start gap-3">
        <!-- 头像 -->
        <div
          v-if="subscription.avatar_url"
          class="flex-shrink-0"
        >
          <img
            :src="subscription.avatar_url"
            :alt="subscription.display_name"
            class="h-12 w-12 rounded-xl object-cover ring-2 ring-border/20"
          />
        </div>
        <div
          v-else
          class="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/20 to-blue-500/20 text-lg font-semibold ring-2 ring-border/20"
        >
          {{ subscription.display_name[0] }}
        </div>

        <!-- 标题和元信息 -->
        <div class="min-w-0 flex-1">
          <h3 class="truncate text-base font-semibold">
            {{ subscription.display_name }}
          </h3>
          <div class="mt-1 flex items-center gap-1.5">
            <Badge variant="secondary" class="text-[10px] px-1.5 py-0">
              {{ platformDisplay }}
            </Badge>
            <Badge variant="outline" class="text-[10px] px-1.5 py-0">
              {{ entityTypeDisplay }}
            </Badge>
            <Badge
              v-if="!subscription.is_active"
              variant="destructive"
              class="text-[10px] px-1.5 py-0"
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

    <CardContent class="space-y-3 pb-3">
      <!-- 标签 -->
      <div v-if="subscription.tags.length > 0" class="flex flex-wrap gap-1.5">
        <Badge
          v-for="tag in subscription.tags.slice(0, 4)"
          :key="tag"
          variant="outline"
          class="rounded-full text-[10px] px-2 py-0 border-border/40 bg-background/30"
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
            class="inline-flex items-center rounded-lg border border-border/40 bg-background/50 px-2.5 py-1 text-xs font-medium transition hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
            @click="handleActionClick(action)"
          >
            {{ getActionDisplayName(action) }}
          </button>
        </div>
      </div>
    </CardContent>

    <CardFooter class="border-t border-border/20 pt-3 flex gap-2">
      <Button
        variant="ghost"
        size="sm"
        class="flex-1 rounded-lg text-xs h-8"
        @click="handleEdit"
      >
        <Pencil class="mr-1.5 h-3.5 w-3.5" />
        编辑
      </Button>
      <Button
        variant="ghost"
        size="sm"
        class="flex-1 rounded-lg text-xs h-8 text-destructive hover:text-destructive hover:bg-destructive/10"
        @click="handleDelete"
      >
        <Trash2 class="mr-1.5 h-3.5 w-3.5" />
        删除
      </Button>
    </CardFooter>
  </Card>
</template>
