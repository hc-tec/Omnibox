<template>
  <div class="workspace-view min-h-screen bg-background text-foreground">
    <WorkspaceLayout />
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import WorkspaceLayout from '@/features/workspace/WorkspaceLayout.vue'
import { useWorkspaceStore } from '@/features/workspace/stores/workspaceStore'

// ========== Route ==========
const route = useRoute()

// ========== Store ==========
const store = useWorkspaceStore()

// ========== Lifecycle ==========

onMounted(async () => {
  // 加载工作流列表
  await store.loadWorkflows()

  // 如果 URL 中有 workflowId，自动选中
  const workflowId = route.params.workflowId as string
  if (workflowId) {
    store.selectWorkflow(workflowId)
  }

  // 如果 URL 中有 runId，加载执行状态
  const runId = route.params.runId as string
  if (runId) {
    // TODO: 加载执行状态
    console.log('加载执行状态:', runId)
  }
})

// 监听路由变化
watch(
  () => route.params.workflowId,
  (newId) => {
    if (newId && typeof newId === 'string') {
      store.selectWorkflow(newId)
    }
  }
)
</script>
