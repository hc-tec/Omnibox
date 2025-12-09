<template>
  <div class="chat-interaction px-4 py-3">
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
          class="w-full resize-none rounded-xl border border-border/40 bg-background/50 px-4 py-2.5 pr-10 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/40 focus:outline-none focus:ring-1 focus:ring-primary/20"
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
      <button
        class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl transition"
        :class="sendButtonClass"
        :disabled="!canSend"
        @click="handleSend"
      >
        <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
        <Send v-else class="h-4 w-4" />
      </button>
    </div>

    <!-- 快捷操作 -->
    <div class="mt-2 flex flex-wrap items-center gap-2">
      <button
        v-for="action in quickActions"
        :key="action.label"
        class="inline-flex items-center gap-1 rounded-lg border border-border/40 bg-background/50 px-2.5 py-1 text-[11px] text-muted-foreground transition hover:border-border/60 hover:bg-background hover:text-foreground"
        @click="handleQuickAction(action)"
      >
        <component :is="action.icon" class="h-3 w-3" />
        {{ action.label }}
      </button>

      <!-- 保存为模板按钮 -->
      <button
        v-if="sessionStore.canSaveAsTemplate"
        class="inline-flex items-center gap-1 rounded-lg border border-primary/40 bg-primary/5 px-2.5 py-1 text-[11px] text-primary transition hover:bg-primary/10"
        @click="showSaveDialog = true"
      >
        <Save class="h-3 w-3" />
        保存为模板
      </button>
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
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { useSessionStore } from '../../stores/sessionStore'
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

// ========== 快捷操作配置 ==========
const quickActions = [
  { label: '生成摘要', icon: markRaw(FileText), action: 'summary' },
  { label: '对比分析', icon: markRaw(BarChart3), action: 'compare' },
  { label: '生成洞察', icon: markRaw(Sparkles), action: 'insight' },
  { label: '导出报告', icon: markRaw(Download), action: 'export' },
]

// ========== Computed ==========

const loading = computed(() => sessionStore.executing)

const canSend = computed(() => {
  return inputText.value.trim().length > 0 && !loading.value
})

const sendButtonClass = computed(() => ({
  'bg-primary text-primary-foreground hover:bg-primary/90': canSend.value,
  'bg-muted text-muted-foreground cursor-not-allowed': !canSend.value,
}))

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
  // 组件卸载时不关闭 Session，让其保持活跃
  // 如果需要关闭，可以调用 sessionStore.closeSession()
})

// ========== Methods ==========

async function handleSend() {
  if (!canSend.value) return

  const text = inputText.value.trim()

  try {
    // 确保有活跃的 Session
    await sessionStore.ensureSession()

    // 构建上下文
    const context: Record<string, unknown> = {}
    if (selectedArtifact.value) {
      context.artifact_refs = [selectedArtifact.value.artifact_id]
    }

    // 使用 Session API 执行查询
    const result = await sessionStore.chat(text, context)

    // 将 data_stash 转换为 artifacts 显示在产物面板
    if (result.data && Array.isArray(result.data)) {
      store.addArtifactsFromDataStash(result.data)
    }

    // panel_previews 是 emit_panel_preview 工具推送的面板数据
    // Planner 会自己决定何时调用该工具
    if (result.panel_previews && result.panel_previews.length > 0) {
      // emit_panel_preview 可能被调用多次，每次都是一个面板
      // 这里使用所有面板数据
      for (const preview of result.panel_previews) {
        store.currentStepOutput = {
          stepId: 0,
          stepName: '查询结果',
          artifactId: undefined,
          data: preview,
        }
      }
    }

    emit('result', result.data, result.final_report || result.message)

    // 清空输入
    inputText.value = ''
    resetTextareaHeight()
  } catch (e) {
    console.error('指令处理失败:', e)
    emit('error', e instanceof Error ? e.message : '未知错误')
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
