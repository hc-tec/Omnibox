<script setup lang="ts">
/**
 * 通知铃铛组件
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { Bell, Check, CheckCheck, X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { useDashboardStore } from '../stores/dashboardStore'

// 点击外部关闭
const popoverRef = ref<HTMLElement | null>(null)
function handleClickOutside(event: MouseEvent) {
  if (popoverRef.value && !popoverRef.value.contains(event.target as Node)) {
    open.value = false
  }
}

const store = useDashboardStore()
const open = ref(false)

onMounted(async () => {
  await store.refreshUnreadCount()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

async function handleOpen(isOpen: boolean) {
  open.value = isOpen
  if (isOpen) {
    await store.loadNotifications()
  }
}

async function handleMarkRead(notificationId: string) {
  await store.markRead(notificationId)
}

async function handleMarkAllRead() {
  await store.markAllRead()
}

function formatTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return date.toLocaleDateString()
}
</script>

<template>
  <div ref="popoverRef" class="relative">
    <Button
      variant="ghost"
      size="icon"
      class="relative"
      @click.stop="handleOpen(!open)"
    >
      <Bell class="w-5 h-5" />
      <Badge
        v-if="store.unreadCount > 0"
        class="absolute -top-1 -right-1 h-5 min-w-5 px-1 text-xs"
        variant="destructive"
      >
        {{ store.unreadCount > 99 ? '99+' : store.unreadCount }}
      </Badge>
    </Button>

    <div
      v-if="open"
      class="absolute right-0 top-10 z-50 w-80 rounded-md border bg-popover shadow-md"
    >
      <!-- 标题栏 -->
      <div class="flex items-center justify-between p-3 border-b">
        <h3 class="font-medium">通知</h3>
        <Button
          v-if="store.unreadCount > 0"
          variant="ghost"
          size="sm"
          class="h-7 text-xs"
          @click="handleMarkAllRead"
        >
          <CheckCheck class="w-3.5 h-3.5 mr-1" />
          全部已读
        </Button>
      </div>

      <!-- 通知列表 -->
      <div class="h-[300px] overflow-y-auto">
        <div v-if="store.notifications.length === 0" class="p-4 text-center text-sm text-muted-foreground">
          暂无通知
        </div>

        <div v-else class="divide-y">
          <div
            v-for="notification in store.notifications"
            :key="notification.notification_id"
            class="p-3 hover:bg-muted/50 cursor-pointer"
            :class="{ 'bg-primary/5': notification.status !== 'read' }"
            @click="handleMarkRead(notification.notification_id)"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium truncate">
                  {{ notification.title }}
                </p>
                <p class="text-xs text-muted-foreground line-clamp-2 mt-1">
                  {{ notification.message }}
                </p>
                <p class="text-xs text-muted-foreground mt-1">
                  {{ formatTime(notification.created_at) }}
                </p>
              </div>
              <div v-if="notification.status !== 'read'" class="shrink-0">
                <div class="w-2 h-2 rounded-full bg-primary" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部 -->
      <Separator />
      <div class="p-2 text-center">
        <Button variant="ghost" size="sm" class="w-full text-xs">
          查看全部通知
        </Button>
      </div>
    </div>
  </div>
</template>
