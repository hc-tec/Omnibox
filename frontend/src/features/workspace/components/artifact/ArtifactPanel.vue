<template>
  <div class="artifact-panel flex h-full flex-col">
    <!-- 头部 -->
    <header class="flex items-center justify-between border-b border-border/20 px-4 py-3">
      <div class="flex items-center gap-2">
        <h3 class="text-sm font-semibold text-foreground">数据产物</h3>
        <span
          v-if="artifacts.length > 0"
          class="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary"
        >
          {{ artifacts.length }}
        </span>
      </div>
      <button
        class="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-background hover:text-foreground"
        title="折叠面板"
        @click="$emit('collapse')"
      >
        <PanelRightClose class="h-4 w-4" />
      </button>
    </header>

    <!-- 产物列表 -->
    <div class="flex-1 overflow-auto p-3">
      <div v-if="loading" class="flex items-center justify-center py-8">
        <Loader2 class="h-5 w-5 animate-spin text-muted-foreground" />
      </div>

      <div v-else-if="artifacts.length === 0" class="py-8 text-center">
        <Database class="mx-auto h-10 w-10 text-muted-foreground/50" />
        <p class="mt-2 text-xs text-muted-foreground">暂无数据产物</p>
        <p class="mt-1 text-[10px] text-muted-foreground/70">
          执行工作流后将自动生成
        </p>
      </div>

      <div v-else class="space-y-2">
        <ArtifactListItem
          v-for="artifact in artifacts"
          :key="artifact.artifact_id"
          :artifact="artifact"
          :selected="artifact.artifact_id === selectedArtifactId"
          @click="selectArtifact(artifact.artifact_id)"
          @preview="handlePreview(artifact)"
        />
      </div>
    </div>

    <!-- 选中产物预览 -->
    <div
      v-if="selectedArtifact"
      class="border-t border-border/20"
    >
      <ArtifactPreview :artifact="selectedArtifact" />
    </div>

    <!-- 操作按钮 -->
    <div
      v-if="selectedArtifact"
      class="border-t border-border/20 p-3"
    >
      <div class="flex gap-2">
        <button
          class="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-border/40 bg-background/50 px-3 py-2 text-xs font-medium text-foreground transition hover:bg-background"
          @click="handleExport"
        >
          <Download class="h-3.5 w-3.5" />
          导出
        </button>
        <button
          class="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-border/40 bg-background/50 px-3 py-2 text-xs font-medium text-foreground transition hover:bg-background"
          @click="handlePin"
        >
          <Pin class="h-3.5 w-3.5" />
          Pin
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import {
  PanelRightClose,
  Loader2,
  Database,
  Download,
  Pin,
} from 'lucide-vue-next'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { useDashboardStore } from '../../../dashboard/stores/dashboardStore'
import * as workspaceApi from '../../services/workspaceApi'
import ArtifactListItem from './ArtifactListItem.vue'
import ArtifactPreview from './ArtifactPreview.vue'
import type { Artifact } from '../../types/workspace'

// ========== Emits ==========
defineEmits<{
  collapse: []
}>()

// ========== Store ==========
const store = useWorkspaceStore()
const dashboardStore = useDashboardStore()
const {
  artifacts,
  selectedArtifactId,
  selectedArtifact,
  loading,
  currentWorkflowId,
} = storeToRefs(store)

const { selectArtifact } = store

// ========== Methods ==========

function handlePreview(artifact: Artifact) {
  // 在画布中预览
  selectArtifact(artifact.artifact_id)
}

async function handleExport() {
  if (!selectedArtifact.value || !currentWorkflowId.value) return

  try {
    // 获取完整的产物数据
    const artifact = await workspaceApi.getArtifact(
      currentWorkflowId.value,
      selectedArtifact.value.artifact_id
    )

    // 创建下载
    const blob = new Blob([JSON.stringify(artifact, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedArtifact.value.name || 'artifact'}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('导出失败:', e)
  }
}

async function handlePin() {
  if (!selectedArtifact.value) return

  try {
    await dashboardStore.pinArtifact({
      artifact_id: selectedArtifact.value.artifact_id,
      name: selectedArtifact.value.name,
      refresh_interval: 'manual',
    })
    alert('已 Pin 到仪表盘')
  } catch (e) {
    console.error('Pin 失败:', e)
    alert('Pin 失败，请稍后重试')
  }
}
</script>

<style scoped>
.artifact-panel {
  scrollbar-width: thin;
  scrollbar-color: rgba(100, 100, 100, 0.3) rgba(0, 0, 0, 0.1);
}

.artifact-panel::-webkit-scrollbar {
  width: 6px;
}

.artifact-panel::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
}

.artifact-panel::-webkit-scrollbar-thumb {
  background: rgba(100, 100, 100, 0.3);
  border-radius: 3px;
}
</style>
