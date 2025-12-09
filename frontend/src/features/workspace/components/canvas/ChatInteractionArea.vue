<template>
  <div class="px-4 py-3">
    <!-- Session 状态指示器 -->
    <div
      v-if="sessionStore.hasSession"
      class="mb-2 flex items-center gap-2 text-[10px] text-muted-foreground"
    >
      <span class="flex items-center gap-1">
        <span class="h-1.5 w-1.5 rounded-full bg-green-500"></span>
        Session 活跃
      </span>
      <span>|</span>
      <span>数据: {{ sessionStore.dataStashCount }}</span>
      <span>|</span>
      <span>对话: {{ sessionStore.chatHistoryCount }}</span>
      <span>|</span>
      <span>步骤: {{ sessionStore.stepsCount }}</span>
    </div>

    <!-- 输入区域 -->
    <div class="flex items-end gap-2">
      <div class="relative flex-1">
        <textarea
          ref="textareaRef"
          v-model="inputText"
          placeholder="输入指令，如：把数据做成对比表格..."
          class="flex min-h-[40px] w-full resize-none rounded-md border border-input bg-transparent px-3 py-2 pr-10 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          rows="1"
          @keydown.enter.exact.prevent="handleSend"
          @input="autoResize"
        />
        <!-- 字符计数 -->
        <span
          v-if="inputText.length > 0"
          class="absolute bottom-2.5 right-3 text-[10px] text-muted-foreground"
        >
          {{ inputText.length }}
        </span>
      </div>

      <!-- 发送按钮 -->
      <Button
        size="icon"
        class="h-10 w-10 flex-shrink-0"
        :disabled="!canSend"
        @click="handleSend"
      >
        <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
        <Send v-else class="h-4 w-4" />
      </Button>
    </div>

    <!-- 快捷操作 -->
    <div class="mt-2 flex flex-wrap items-center gap-2">
      <Button
        v-for="action in quickActions"
        :key="action.label"
        variant="outline"
        size="sm"
        class="h-7 gap-1 text-[11px]"
        @click="handleQuickAction(action)"
      >
        <component :is="action.icon" class="h-3 w-3" />
        {{ action.label }}
      </Button>

      <!-- 保存为模板按钮 -->
      <Button
        v-if="sessionStore.canSaveAsTemplate"
        variant="outline"
        size="sm"
        class="h-7 gap-1 border-primary/40 bg-primary/5 text-[11px] text-primary hover:bg-primary/10"
        @click="showSaveDialog = true"
      >
        <Save class="h-3 w-3" />
        保存为模板
      </Button>
    </div>

    <!-- 保存为模板对话框 -->
    <SaveAsTemplateDialog
      v-model:open="showSaveDialog"
      :session-id="sessionStore.sessionId"
      :steps-count="sessionStore.stepsCount"
      @saved="handleTemplateSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, markRaw, nextTick, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import {
  Send,
  Loader2,
  FileText,
  BarChart3,
  Download,
  Sparkles,
  Save,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { useSessionStore } from '../../stores/sessionStore'
import { useSessionWebSocket } from '../../composables/useSessionWebSocket'
import SaveAsTemplateDialog from './SaveAsTemplateDialog.vue'

// ========== Store ==========
const store = useWorkspaceStore()
const sessionStore = useSessionStore()
const { selectedArtifact, currentStepOutput } = storeToRefs(store)

// ========== Emits ==========
const emit = defineEmits<{
  result: [data: unknown, message: string]
  error: [message: string]
}>()

// ========== State ==========
const inputText = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const showSaveDialog = ref(false)
const wsExecuting = ref(false)

// ========== WebSocket ==========
let sessionWs: ReturnType<typeof useSessionWebSocket> | null = null

function createWebSocket(sessionId: string) {
  return useSessionWebSocket({
    sessionId,
    onComplete: (success, message) => {
      wsExecuting.value = false
      emit('result', null, message)
    },
    onError: (errorMsg) => {
      wsExecuting.value = false
      emit('error', errorMsg)
    },
  })
}

// ========== 快捷操作配置 ==========
const quickActions = [
  { label: '生成摘要', icon: markRaw(FileText), action: 'summary' },
  { label: '对比分析', icon: markRaw(BarChart3), action: 'compare' },
  { label: '生成洞察', icon: markRaw(Sparkles), action: 'insight' },
  { label: '导出报告', icon: markRaw(Download), action: 'export' },
]

// ========== Computed ==========

const loading = computed(() => sessionStore.executing || wsExecuting.value)

const canSend = computed(() => {
  return inputText.value.trim().length > 0 && !loading.value
})

// ========== Lifecycle ==========

onMounted(async () => {
  // 确保有活跃的 Session
  try {
    await sessionStore.ensureSession()
  } catch (e) {
    console.error('创建 Session 失败:', e)
  }
})

onUnmounted(() => {
  // 断开 WebSocket 连接
  if (sessionWs) {
    sessionWs.disconnect()
    sessionWs = null
  }
  // 组件卸载时不关闭 Session，让其保持活跃
})

// ========== Methods ==========

async function handleSend() {
  if (!canSend.value) return

  const text = inputText.value.trim()

  // 1. 添加用户查询到时间线
  store.addUserQueryEntry(text)

  // 清空输入（提前清空，让用户感觉更流畅）
  inputText.value = ''
  resetTextareaHeight()

  try {
    // 确保有活跃的 Session
    await sessionStore.ensureSession()

    const sessionId = sessionStore.sessionId
    if (!sessionId) {
      throw new Error('Session 未创建')
    }

    // 构建上下文
    const context: Record<string, unknown> = {}
    if (selectedArtifact.value) {
      context.artifact_refs = [selectedArtifact.value.artifact_id]
    }

    // 2. 添加思考条目（表示开始处理）
    store.addThinkingEntry('分析查询并规划执行步骤...')

    // 使用 WebSocket 流式执行
    wsExecuting.value = true

    // 创建新的 WebSocket 连接
    sessionWs = createWebSocket(sessionId)

    // 连接并发送查询
    await sessionWs.connect()
    sessionWs.sendQuery(text, context)

    // WebSocket 的消息处理在 useSessionWebSocket 中完成
    // 执行完成时会通过 onComplete/onError 回调更新 wsExecuting
  } catch (e) {
    console.error('指令处理失败:', e)
    const errorMsg = e instanceof Error ? e.message : '未知错误'

    wsExecuting.value = false

    // 添加错误条目到时间线
    store.addErrorEntry(errorMsg)

    emit('error', errorMsg)
  }
}

function handleQuickAction(action: { label: string; action: string }) {
  // 根据操作类型填充输入框
  const prompts: Record<string, string> = {
    summary: '请为当前数据生成摘要',
    compare: '请对数据进行对比分析',
    insight: '请从数据中提取关键洞察',
    export: '请将分析结果导出为报告',
  }

  inputText.value = prompts[action.action] || ''
  nextTick(() => {
    textareaRef.value?.focus()
  })
}

function handleTemplateSaved(result: {
  workflowId: string
  workflowName: string
}) {
  emit('result', null, `已保存为模板：${result.workflowName}`)
}

function autoResize() {
  if (!textareaRef.value) return

  // 重置高度以获取正确的 scrollHeight
  textareaRef.value.style.height = 'auto'

  // 设置新高度，最大 120px（约 5 行）
  const newHeight = Math.min(textareaRef.value.scrollHeight, 120)
  textareaRef.value.style.height = `${newHeight}px`
}

function resetTextareaHeight() {
  if (!textareaRef.value) return
  textareaRef.value.style.height = 'auto'
}
</script>
