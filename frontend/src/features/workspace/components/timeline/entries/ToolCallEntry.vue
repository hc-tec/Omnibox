<!--
  工具调用条目组件 - Manus 风格
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { Wrench, CheckCircle2, XCircle, Loader2, ChevronDown, ChevronRight, Code } from 'lucide-vue-next'
import type { TimelineEntry } from '../../../types/workspace'

interface DataOperatorResult {
  type: string
  instruction: string
  code?: string
}

const props = defineProps<{
  entry: TimelineEntry
}>()

// 展开代码
const showCode = ref(false)

// 尝试解析 data_operator 结果（处理可能的双重编码和格式问题）
const parsedResult = computed<DataOperatorResult | null>(() => {
  const toolName = props.entry.toolCall?.tool_name
  const summary = props.entry.toolCall?.result_summary
  if (!summary) return null

  // 尝试多种方式解析
  const tryParse = (str: string): DataOperatorResult | null => {
    try {
      // 先尝试直接解析
      let parsed = JSON.parse(str.trim())

      // 处理双重编码
      if (typeof parsed === 'string') {
        parsed = JSON.parse(parsed)
      }

      if (parsed && parsed.type === 'data_operator' && parsed.instruction) {
        return parsed as DataOperatorResult
      }
    } catch {
      // 解析失败
    }
    return null
  }

  // 方法1：直接解析
  let result = tryParse(summary)
  if (result) return result

  // 方法2：尝试提取 JSON 部分（处理前面有额外字符的情况）
  const jsonMatch = summary.match(/\{[\s\S]*\}/)
  if (jsonMatch) {
    result = tryParse(jsonMatch[0])
    if (result) return result
  }

  // 方法3：如果工具名是 data_operator，尝试创建一个结构
  if (toolName === 'data_operator') {
    // 检查是否看起来像 JSON 结构
    if (summary.includes('"instruction"') && summary.includes('"type"')) {
      // 可能是截断的 JSON，尝试提取 instruction
      const instructionMatch = summary.match(/"instruction"\s*:\s*"([^"]+)"/)
      if (instructionMatch) {
        return {
          type: 'data_operator',
          instruction: instructionMatch[1],
        }
      }
    }
  }

  return null
})

// 是否为 data_operator 结果
const isDataOperator = computed(() => parsedResult.value !== null)

// 显示的摘要文本
const displaySummary = computed(() => {
  if (isDataOperator.value && parsedResult.value) {
    return parsedResult.value.instruction
  }
  return props.entry.toolCall?.result_summary
})

// 状态图标
const statusIcon = computed(() => {
  switch (props.entry.toolCall?.status) {
    case 'success':
      return CheckCircle2
    case 'error':
      return XCircle
    case 'running':
      return Loader2
    default:
      return Wrench
  }
})

// 状态样式
const statusColorClass = computed(() => {
  switch (props.entry.toolCall?.status) {
    case 'success':
      return 'border-l-green-500 text-green-500'
    case 'error':
      return 'border-l-red-500 text-red-500'
    case 'running':
      return 'border-l-blue-500 text-blue-500'
    default:
      return 'border-l-border text-muted-foreground'
  }
})

// 工具名称映射
const toolDisplayName = computed(() => {
  const name = props.entry.toolCall?.tool_name
  const nameMap: Record<string, string> = {
    'fetch_public_data': '获取数据',
    'data_operator': '数据处理',
    'emit_panel_preview': '生成面板',
    'filter_data': '筛选数据',
    'aggregate_data': '聚合数据',
    'extract_insights': '提取洞察',
  }
  return nameMap[name || ''] || name
})
</script>

<template>
  <div class="bg-muted/20 rounded-lg p-2.5 border-l-[3px]" :class="statusColorClass">
    <!-- 工具标题行 -->
    <div class="flex items-center gap-1.5">
      <component
        :is="statusIcon"
        class="h-3.5 w-3.5 flex-shrink-0"
        :class="{ 'animate-spin': entry.toolCall?.status === 'running' }"
      />
      <span class="text-[13px] font-medium text-foreground">{{ toolDisplayName }}</span>
      <span class="text-[11px] text-muted-foreground ml-auto">{{ entry.toolCall?.tool_name }}</span>
    </div>

    <!-- 摘要内容 -->
    <div v-if="displaySummary" class="mt-1.5 text-xs leading-relaxed text-foreground/80">
      {{ displaySummary }}
    </div>

    <!-- data_operator 的代码展示 -->
    <div v-if="isDataOperator && parsedResult?.code" class="mt-2">
      <button
        class="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors py-1"
        @click="showCode = !showCode"
      >
        <component :is="showCode ? ChevronDown : ChevronRight" class="h-3 w-3" />
        <Code class="h-3 w-3" />
        <span>{{ showCode ? '隐藏代码' : '查看代码' }}</span>
      </button>
      <pre
        v-if="showCode"
        class="mt-2 p-2.5 bg-background/80 rounded-md text-[11px] leading-relaxed overflow-x-auto max-h-48 font-mono border border-border/50"
      ><code>{{ parsedResult.code }}</code></pre>
    </div>

    <!-- 错误信息 -->
    <div v-if="entry.toolCall?.error" class="mt-1.5 text-xs text-red-500">
      {{ entry.toolCall.error }}
    </div>
  </div>
</template>
