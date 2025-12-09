<template>
  <div class="main-canvas flex h-full flex-col">
    <!-- 头部：视图切换 + 当前信息 -->
    <header class="flex items-center justify-between border-b border-border/20 bg-[var(--shell-surface)]/95 px-4 py-2 backdrop-blur">
      <!-- 视图切换标签 -->
      <div class="flex items-center gap-1 rounded-lg border border-border/40 bg-background/50 p-1">
        <button
          v-for="view in views"
          :key="view.value"
          class="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition"
          :class="viewButtonClass(view.value)"
          @click="setCanvasView(view.value)"
        >
          <component :is="view.icon" class="h-3.5 w-3.5" />
          {{ view.label }}
        </button>
      </div>

      <!-- 当前上下文信息 -->
      <div class="flex items-center gap-3">
        <!-- 当前步骤 -->
        <div
          v-if="currentStepOutput"
          class="flex items-center gap-2 rounded-lg border border-border/40 bg-background/50 px-3 py-1.5"
        >
          <span class="text-[10px] text-muted-foreground">当前:</span>
          <span class="text-xs font-medium text-foreground">
            {{ currentStepOutput.stepName }}
          </span>
        </div>

        <!-- 当前产物 -->
        <div
          v-if="selectedArtifact"
          class="flex items-center gap-2 rounded-lg border border-primary/40 bg-primary/5 px-3 py-1.5"
        >
          <Database class="h-3.5 w-3.5 text-primary" />
          <span class="text-xs font-medium text-primary">
            {{ selectedArtifact.name }}
          </span>
        </div>
      </div>
    </header>

    <!-- 主内容区域 -->
    <div class="canvas-viewport flex-1 overflow-auto bg-background p-4">
      <!-- 有数据时显示 PanelBoard -->
      <div v-if="hasContent" class="h-full">
        <!-- 图表视图 -->
        <div v-if="canvasView === 'chart'" class="h-full">
          <PanelBoard
            v-if="panelData.layout"
            :layout="panelData.layout"
            :blocks="panelData.blocks"
            :data-blocks="panelData.dataBlocks"
          />
          <CanvasEmptyState v-else message="暂无图表数据" />
        </div>

        <!-- 表格视图 -->
        <div v-else-if="canvasView === 'table'" class="h-full overflow-auto">
          <div v-if="tableData.rows.length > 0" class="rounded-lg border border-border/40 bg-background/50">
            <table class="w-full text-sm">
              <thead class="border-b border-border/40 bg-muted/30">
                <tr>
                  <th
                    v-for="col in tableData.columns"
                    :key="col"
                    class="px-4 py-2 text-left font-medium text-muted-foreground"
                  >
                    {{ col }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(row, idx) in tableData.rows"
                  :key="idx"
                  class="border-b border-border/20 hover:bg-muted/10"
                >
                  <td
                    v-for="col in tableData.columns"
                    :key="col"
                    class="px-4 py-2 text-foreground"
                  >
                    {{ row[col] ?? '-' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <CanvasEmptyState v-else message="暂无表格数据" />
        </div>

        <!-- 文本视图 -->
        <div v-else-if="canvasView === 'text'" class="h-full overflow-auto">
          <div v-if="textContent" class="rounded-lg border border-border/40 bg-background/50 p-4">
            <div class="prose prose-sm prose-invert max-w-none">
              <div v-if="selectedArtifact" class="mb-4">
                <h3 class="text-lg font-semibold text-foreground">{{ selectedArtifact.name }}</h3>
                <p class="text-muted-foreground">{{ selectedArtifact.description || '暂无描述' }}</p>
              </div>
              <div v-if="selectedArtifact?.schema_info" class="mb-4">
                <h4 class="text-sm font-medium text-foreground mb-2">数据结构</h4>
                <ul class="text-sm text-muted-foreground space-y-1">
                  <li v-for="field in selectedArtifact.schema_info.fields" :key="field.name">
                    <span class="font-mono text-primary">{{ field.name }}</span>
                    <span class="text-muted-foreground/70"> ({{ field.type }})</span>
                  </li>
                </ul>
                <p class="text-xs text-muted-foreground mt-2">
                  共 {{ selectedArtifact.schema_info.total_count }} 条记录
                </p>
              </div>
              <div v-if="selectedArtifact?.statistics" class="mb-4">
                <h4 class="text-sm font-medium text-foreground mb-2">统计信息</h4>
                <pre class="text-xs bg-muted/20 rounded p-2 overflow-auto">{{ JSON.stringify(selectedArtifact.statistics, null, 2) }}</pre>
              </div>
            </div>
          </div>
          <CanvasEmptyState v-else message="暂无文本内容" />
        </div>

        <!-- 原始视图 -->
        <div v-else-if="canvasView === 'raw'" class="h-full">
          <div class="rounded-lg border border-border/40 bg-background/50 p-4">
            <pre class="overflow-auto text-xs text-muted-foreground">
{{ JSON.stringify(currentStepOutput?.data || selectedArtifact, null, 2) }}
            </pre>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <CanvasEmptyState v-else />
    </div>

    <!-- 底部：对话交互区 -->
    <div class="border-t border-border/20 bg-[var(--shell-surface)]/95 backdrop-blur">
      <ChatInteractionArea />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import {
  BarChart3,
  Table2,
  FileText,
  Code2,
  Database,
} from 'lucide-vue-next'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { usePanelStore } from '@/store/panelStore'
import PanelBoard from '@/features/panel/components/PanelBoard.vue'
import ChatInteractionArea from './ChatInteractionArea.vue'
import CanvasEmptyState from './CanvasEmptyState.vue'
import type { CanvasView } from '../../types/workspace'
import type { LayoutTree, UIBlock, DataBlock } from '@/shared/types/panel'

// ========== Store ==========
const store = useWorkspaceStore()
const panelStore = usePanelStore()
const {
  canvasView,
  currentStepOutput,
  selectedArtifact,
} = storeToRefs(store)

const { setCanvasView } = store

// ========== 初始化：workspace 使用紧凑模式 ==========
onMounted(() => {
  panelStore.state.sizePreset = 'compact'
})

// ========== 视图配置 ==========
const views = [
  { value: 'chart' as CanvasView, label: '图表', icon: markRaw(BarChart3) },
  { value: 'table' as CanvasView, label: '表格', icon: markRaw(Table2) },
  { value: 'text' as CanvasView, label: '文本', icon: markRaw(FileText) },
  { value: 'raw' as CanvasView, label: '原始', icon: markRaw(Code2) },
]

// ========== Computed ==========

const hasContent = computed(() => {
  return currentStepOutput.value || selectedArtifact.value
})

// 定义返回类型
interface PanelDataResult {
  layout: LayoutTree | null
  blocks: UIBlock[]
  dataBlocks: Record<string, DataBlock>
}

// 从产物或步骤输出构建面板数据
const panelData = computed((): PanelDataResult => {
  const artifact = selectedArtifact.value
  const stepOutput = currentStepOutput.value

  // 优先使用步骤输出数据
  if (stepOutput?.data) {
    const data = stepOutput.data as Record<string, unknown>
    if (data.layout && data.blocks) {
      // 在 workspace 中强制使用全宽布局，避免卡片过窄
      const originalLayout = data.layout as LayoutTree
      const adaptedLayout: LayoutTree = {
        ...originalLayout,
        nodes: originalLayout.nodes.map(node => {
          const existingGrid = node.props?.grid || { x: 0, y: 0, w: 12, h: 6 }
          return {
            ...node,
            props: {
              ...node.props,
              grid: {
                ...existingGrid,
                w: 12, // 强制全宽
                size: 'full',
              },
            },
          }
        }),
      }
      return {
        layout: adaptedLayout,
        blocks: data.blocks as UIBlock[],
        dataBlocks: (data.dataBlocks || data.data_blocks || {}) as Record<string, DataBlock>,
      }
    }
  }

  // 使用产物数据构建面板
  if (artifact) {
    // 如果产物有建议的视图，使用第一个
    if (artifact.suggested_views && artifact.suggested_views.length > 0) {
      const view = artifact.suggested_views[0]
      const blockId = `block-${artifact.artifact_id}`

      // 构建符合 LayoutTree 类型的布局
      const layout: LayoutTree = {
        mode: 'replace',
        nodes: [
          {
            type: 'cell',
            id: blockId,
            children: [],
            props: {
              grid: { x: 0, y: 0, w: 12, h: 6 },
            },
          },
        ],
      }

      // 构建符合 UIBlock 类型的块
      const blocks: UIBlock[] = [
        {
          id: blockId,
          component: view.component,
          data_ref: artifact.artifact_id,
          props: view.props || {},
          options: {},
        },
      ]

      // 构建符合 DataBlock 类型的数据块
      const dataBlocks: Record<string, DataBlock> = {
        [artifact.artifact_id]: {
          id: artifact.artifact_id,
          source_info: {
            datasource: 'workspace',
            route: 'artifact',
            params: { artifact_id: artifact.artifact_id },
          },
          records: [],
          stats: artifact.statistics || {},
          schema_summary: {
            fields: artifact.schema_info?.fields?.map(f => ({
              name: f.name,
              type: f.type,
              sample: f.sample_values || [],
            })) || [],
            stats: {},
            schema_digest: '',
          },
        },
      }

      return { layout, blocks, dataBlocks }
    }
  }

  return {
    layout: null,
    blocks: [],
    dataBlocks: {},
  }
})

// 表格数据：从产物或步骤输出提取
const tableData = computed(() => {
  const artifact = selectedArtifact.value
  const stepOutput = currentStepOutput.value

  // 从步骤输出数据中提取表格
  if (stepOutput?.data) {
    const data = stepOutput.data as Record<string, unknown>
    // 如果数据中有 records 数组
    if (Array.isArray(data.records) && data.records.length > 0) {
      const rows = data.records as Record<string, unknown>[]
      const columns = Object.keys(rows[0])
      return { columns, rows }
    }
    // 如果数据块中有数据
    const dataBlocks = (data.dataBlocks || data.data_blocks) as Record<string, { records?: unknown[] }> | undefined
    if (dataBlocks) {
      const firstBlock = Object.values(dataBlocks)[0]
      if (firstBlock?.records && Array.isArray(firstBlock.records) && firstBlock.records.length > 0) {
        const rows = firstBlock.records as Record<string, unknown>[]
        const columns = Object.keys(rows[0])
        return { columns, rows }
      }
    }
  }

  // 从产物 schema 构建示例表格
  if (artifact?.schema_info?.fields) {
    const columns = artifact.schema_info.fields.map(f => f.name)
    // 使用 sample_values 构建示例行
    const sampleRow: Record<string, unknown> = {}
    artifact.schema_info.fields.forEach(f => {
      sampleRow[f.name] = f.sample_values?.[0] ?? '-'
    })
    return { columns, rows: [sampleRow] }
  }

  return { columns: [], rows: [] }
})

// 文本内容：判断是否有可显示的文本
const textContent = computed(() => {
  return selectedArtifact.value || currentStepOutput.value
})

// ========== Methods ==========

function viewButtonClass(view: CanvasView) {
  return {
    'bg-primary text-primary-foreground': canvasView.value === view,
    'text-muted-foreground hover:text-foreground hover:bg-background/80': canvasView.value !== view,
  }
}
</script>

<style scoped>
.canvas-viewport {
  scrollbar-width: thin;
  scrollbar-color: rgba(100, 100, 100, 0.3) rgba(0, 0, 0, 0.1);
}

.canvas-viewport::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.canvas-viewport::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
}

.canvas-viewport::-webkit-scrollbar-thumb {
  background: rgba(100, 100, 100, 0.3);
  border-radius: 4px;
}

.canvas-viewport::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 100, 100, 0.5);
}
</style>
