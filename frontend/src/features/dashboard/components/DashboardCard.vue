<script setup lang="ts">
/**
 * 仪表盘卡片组件
 */
import { ref, computed } from 'vue'
import { RefreshCw, MoreVertical, Settings, Trash2, Bell, X } from 'lucide-vue-next'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { DashboardCard as DashboardCardType, CardData } from '../types/dashboard'
import { REFRESH_INTERVAL_LABELS } from '../types/dashboard'

// 下拉菜单状态
const menuOpen = ref(false)

interface Props {
  card: DashboardCardType
  data?: CardData
  loading?: boolean
  editMode?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  editMode: false,
})

const emit = defineEmits<{
  refresh: []
  settings: []
  delete: []
}>()

// 计算刷新标签
const refreshLabel = computed(() => {
  return REFRESH_INTERVAL_LABELS[props.card.refresh_interval] || '手动刷新'
})

// 格式化时间
function formatTime(isoString?: string): string {
  if (!isoString) return '从未刷新'
  const date = new Date(isoString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return date.toLocaleDateString()
}

// 获取卡片类型图标
const cardTypeLabel = computed(() => {
  switch (props.card.card_type) {
    case 'artifact':
      return '数据'
    case 'workflow':
      return '工作流'
    default:
      return '自定义'
  }
})
</script>

<template>
  <Card
    class="dashboard-card h-full flex flex-col"
    :class="{
      'is-loading': loading,
      'edit-mode': editMode,
    }"
  >
    <!-- 卡片头部 -->
    <CardHeader class="p-3 pb-2 flex-none">
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-2 min-w-0">
          <CardTitle class="text-sm font-medium truncate">
            {{ card.name }}
          </CardTitle>
          <Badge variant="outline" class="text-xs shrink-0">
            {{ cardTypeLabel }}
          </Badge>
          <Badge
            v-if="card.refresh_interval !== 'manual'"
            variant="secondary"
            class="text-xs shrink-0"
          >
            {{ refreshLabel }}
          </Badge>
        </div>

        <div class="flex items-center gap-1 shrink-0">
          <!-- 刷新按钮 -->
          <Button
            variant="ghost"
            size="icon"
            class="h-7 w-7"
            :disabled="loading"
            @click="emit('refresh')"
          >
            <RefreshCw
              class="w-3.5 h-3.5"
              :class="{ 'animate-spin': loading }"
            />
          </Button>

          <!-- 更多操作 -->
          <div class="relative">
            <Button
              variant="ghost"
              size="icon"
              class="h-7 w-7"
              @click="menuOpen = !menuOpen"
            >
              <MoreVertical class="w-3.5 h-3.5" />
            </Button>
            <div
              v-if="menuOpen"
              class="absolute right-0 top-8 z-50 min-w-[120px] rounded-md border bg-popover p-1 shadow-md"
            >
              <button
                class="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent"
                @click="emit('settings'); menuOpen = false"
              >
                <Settings class="w-4 h-4" />
                设置
              </button>
              <button
                class="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-destructive hover:bg-accent"
                @click="emit('delete'); menuOpen = false"
              >
                <Trash2 class="w-4 h-4" />
                删除
              </button>
            </div>
          </div>
        </div>
      </div>
    </CardHeader>

    <!-- 卡片内容 -->
    <CardContent class="p-3 pt-0 flex-1 overflow-hidden">
      <!-- 加载状态 -->
      <div v-if="loading && !data" class="space-y-2">
        <div class="h-4 w-full bg-muted animate-pulse rounded" />
        <div class="h-4 w-3/4 bg-muted animate-pulse rounded" />
        <div class="h-20 w-full bg-muted animate-pulse rounded" />
      </div>

      <!-- 数据展示 -->
      <div v-else-if="data && !data.error" class="h-full">
        <!-- 简单数据预览 -->
        <div class="text-sm text-muted-foreground">
          <template v-if="data.data">
            <pre class="text-xs overflow-auto max-h-[200px] p-2 bg-muted/50 rounded">{{
              JSON.stringify(data.data, null, 2).slice(0, 500)
            }}</pre>
          </template>
          <template v-else>
            暂无数据
          </template>
        </div>
      </div>

      <!-- 错误状态 -->
      <div
        v-else-if="data?.error"
        class="text-sm text-destructive"
      >
        {{ data.error }}
      </div>

      <!-- 无数据状态 -->
      <div
        v-else
        class="h-full flex items-center justify-center text-sm text-muted-foreground"
      >
        点击刷新获取数据
      </div>
    </CardContent>

    <!-- 卡片底部 -->
    <CardFooter class="p-3 pt-0 flex-none">
      <div class="flex items-center justify-between w-full text-xs text-muted-foreground">
        <span>{{ formatTime(card.last_refresh_at) }}</span>
        <span v-if="card.triggers.length" class="flex items-center gap-1">
          <Bell class="w-3 h-3" />
          {{ card.triggers.length }} 个触发器
        </span>
      </div>
    </CardFooter>
  </Card>
</template>

<style scoped>
.dashboard-card {
  background: hsl(var(--card));
  border: 1px solid hsl(var(--border) / 0.5);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.dashboard-card:hover {
  border-color: hsl(var(--border));
}

.dashboard-card.edit-mode {
  border-style: dashed;
  border-color: hsl(var(--primary) / 0.5);
}

.dashboard-card.is-loading {
  opacity: 0.8;
}
</style>
