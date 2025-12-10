<!--
  执行时间线组件 - Manus 风格流式视图

  特点：左侧垂直连接线 + 简洁卡片设计
-->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import UserQueryEntry from './entries/UserQueryEntry.vue'
import ThinkingEntry from './entries/ThinkingEntry.vue'
import ToolCallEntry from './entries/ToolCallEntry.vue'
import PanelEntry from './entries/PanelEntry.vue'
import ErrorEntry from './entries/ErrorEntry.vue'
import MessageEntry from './entries/MessageEntry.vue'
import { Sparkles } from 'lucide-vue-next'

const store = useWorkspaceStore()

// 时间线容器引用，用于自动滚动
const timelineRef = ref<HTMLElement | null>(null)

// 计算属性：时间线条目
const timelineEntries = computed(() => store.timelineEntries)

// 是否显示空状态
const isEmpty = computed(() => timelineEntries.value.length === 0)

// 监听条目变化，自动滚动到底部
watch(
  () => timelineEntries.value.length,
  async () => {
    await nextTick()
    if (timelineRef.value) {
      timelineRef.value.scrollTop = timelineRef.value.scrollHeight
    }
  }
)

// 监听滚动目标变化，滚动到指定条目
watch(
  () => store.scrollToEntryId,
  async (entryId) => {
    if (!entryId) return

    await nextTick()
    const element = document.getElementById(`timeline-entry-${entryId}`)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
      // 高亮效果
      element.classList.add('highlight-entry')
      setTimeout(() => {
        element.classList.remove('highlight-entry')
      }, 1500)
    }
    // 清除滚动目标
    store.clearScrollTarget()
  }
)

// 获取连接点颜色（根据类型和状态）
function getDotColor(entry: typeof timelineEntries.value[0]) {
  switch (entry.type) {
    case 'user_query':
      return 'bg-primary'
    case 'thinking':
      return 'bg-purple-500'
    case 'tool_call':
      // 根据工具调用状态返回对应颜色
      switch (entry.toolCall?.status) {
        case 'success':
          return 'bg-green-500'
        case 'error':
          return 'bg-red-500'
        case 'running':
          return 'bg-blue-500'
        default:
          return 'bg-muted-foreground'
      }
    case 'panel':
      return 'bg-green-500'
    case 'message':
      return 'bg-emerald-500'
    case 'error':
      return 'bg-red-500'
    default:
      return 'bg-muted-foreground'
  }
}

// 判断条目是否处于“运行中”以展示炫光
function isEntryActive(entry: typeof timelineEntries.value[0], index: number) {
  switch (entry.type) {
    case 'thinking':
      // 最新的思考，且尚未完成流程时提示“进行中”
      return index === timelineEntries.value.length - 1
    case 'tool_call':
      return entry.toolCall?.status === 'running' || entry.toolCall?.status === 'pending'
    case 'user_query':
      // 刚提交且还未有其他事件时，视为等待中
      return index === timelineEntries.value.length - 1 && timelineEntries.value.length === 1
    case 'message':
      // 流式信息，若是最新一条且流程未结束
      return index === timelineEntries.value.length - 1 && store.isRunning
    case 'panel':
    case 'error':
    default:
      return false
  }
}
</script>

<template>
  <div class="h-full flex flex-col bg-background">
    <!-- 时间线内容区 -->
    <div
      ref="timelineRef"
      class="flex-1 overflow-y-auto py-4 scroll-smooth"
    >
      <!-- 空状态 -->
      <div
        v-if="isEmpty"
        class="h-full flex flex-col items-center justify-center text-muted-foreground px-4"
      >
        <Sparkles class="h-12 w-12 mb-4 opacity-30" />
        <p class="text-lg font-medium">开始对话</p>
        <p class="text-sm opacity-70">在下方输入查询，查看执行流程</p>
      </div>

      <!-- Manus 风格时间线 -->
      <div v-else class="flex flex-col">
        <div
          v-for="(entry, index) in timelineEntries"
          :id="`timeline-entry-${entry.id}`"
          :key="entry.id"
          class="flex gap-3 px-4 animate-in fade-in slide-in-from-bottom-2 duration-200 transition-colors"
        >
          <!-- 左侧连接线 + 圆点 -->
          <div class="flex flex-col items-center w-5 flex-shrink-0 pt-1">
            <div class="w-2 h-2 rounded-full flex-shrink-0 z-10" :class="getDotColor(entry)" />
            <div
              v-if="index < timelineEntries.length - 1"
              class="w-0.5 flex-1 bg-gradient-to-b from-border to-border/30 mt-1 min-h-5"
            />
          </div>

          <!-- 右侧内容 -->
          <div class="flex-1 min-w-0 pb-4" :class="{ 'pb-0': index === timelineEntries.length - 1 }">
            <!-- 用户查询 -->
            <UserQueryEntry
              v-if="entry.type === 'user_query'"
              :entry="entry"
              :is-active="isEntryActive(entry, index)"
            />

            <!-- 思考 -->
            <ThinkingEntry
              v-else-if="entry.type === 'thinking'"
              :entry="entry"
              :is-active="isEntryActive(entry, index)"
            />

            <!-- 工具调用 -->
            <ToolCallEntry
              v-else-if="entry.type === 'tool_call'"
              :entry="entry"
              :is-active="isEntryActive(entry, index)"
            />

            <!-- 面板 -->
            <PanelEntry
              v-else-if="entry.type === 'panel'"
              :entry="entry"
              :is-active="isEntryActive(entry, index)"
            />

            <!-- 错误 -->
            <ErrorEntry
              v-else-if="entry.type === 'error'"
              :entry="entry"
            />

            <!-- 消息 -->
            <MessageEntry
              v-else-if="entry.type === 'message'"
              :entry="entry"
              :is-active="isEntryActive(entry, index)"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* 导航高亮动画 */
.highlight-entry {
  background-color: hsl(var(--primary) / 0.1);
  border-radius: 0.5rem;
  animation: highlight-pulse 1.5s ease-out;
}

@keyframes highlight-pulse {
  0% {
    background-color: hsl(var(--primary) / 0.2);
  }
  100% {
    background-color: transparent;
  }
}
</style>
