<template>
  <div class="chat-interaction px-4 py-3">
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, markRaw, nextTick } from 'vue'
import {
  Send,
  Loader2,
  FileText,
  BarChart3,
  Download,
  Sparkles,
} from 'lucide-vue-next'

// ========== State ==========
const inputText = ref('')
const loading = ref(false)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

// ========== 快捷操作配置 ==========
const quickActions = [
  { label: '生成摘要', icon: markRaw(FileText), action: 'summary' },
  { label: '对比分析', icon: markRaw(BarChart3), action: 'compare' },
  { label: '生成洞察', icon: markRaw(Sparkles), action: 'insight' },
  { label: '导出报告', icon: markRaw(Download), action: 'export' },
]

// ========== Computed ==========

const canSend = computed(() => {
  return inputText.value.trim().length > 0 && !loading.value
})

const sendButtonClass = computed(() => ({
  'bg-primary text-primary-foreground hover:bg-primary/90': canSend.value,
  'bg-muted text-muted-foreground cursor-not-allowed': !canSend.value,
}))

// ========== Methods ==========

async function handleSend() {
  if (!canSend.value) return

  const text = inputText.value.trim()
  loading.value = true

  try {
    // 注：此处需要后端实现 chat API 或集成现有 chat 服务
    // 目前仅模拟处理，实际应调用：
    // const response = await chatApi.sendWorkspaceCommand(text, { context: currentContext })
    console.log('发送指令:', text)

    // 模拟处理延迟
    await new Promise(resolve => setTimeout(resolve, 800))

    // 清空输入
    inputText.value = ''
    resetTextareaHeight()
  } catch (e) {
    console.error('指令处理失败:', e)
  } finally {
    loading.value = false
  }
}

function handleQuickAction(action: { label: string; action: string }) {
  console.log('快捷操作:', action.action)

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
