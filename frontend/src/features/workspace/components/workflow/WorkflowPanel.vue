<template>
  <div class="workflow-panel flex h-full flex-col">
    <!-- 头部 -->
    <header class="flex items-center justify-between border-b border-border/20 px-4 py-3">
      <h3 class="text-sm font-semibold text-foreground">工作流</h3>
      <div class="flex items-center gap-1">
        <button
          class="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-background hover:text-foreground"
          title="新建工作流"
          @click="handleCreate"
        >
          <Plus class="h-4 w-4" />
        </button>
        <button
          class="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-background hover:text-foreground"
          title="折叠面板"
          @click="$emit('collapse')"
        >
          <PanelLeftClose class="h-4 w-4" />
        </button>
      </div>
    </header>

    <!-- 工作流列表 -->
    <div class="flex-1 overflow-auto p-3">
      <div v-if="loading" class="flex items-center justify-center py-8">
        <Loader2 class="h-5 w-5 animate-spin text-muted-foreground" />
      </div>

      <div v-else-if="workflows.length === 0" class="py-8 text-center">
        <Workflow class="mx-auto h-10 w-10 text-muted-foreground/50" />
        <p class="mt-2 text-xs text-muted-foreground">暂无工作流</p>
        <button
          class="mt-3 inline-flex items-center gap-1 rounded-lg border border-border/40 bg-background/50 px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-background"
          @click="handleCreate"
        >
          <Plus class="h-3 w-3" />
          创建工作流
        </button>
      </div>

      <div v-else class="space-y-2">
        <WorkflowListItem
          v-for="workflow in workflows"
          :key="workflow.workflow_id"
          :workflow="workflow"
          :selected="workflow.workflow_id === currentWorkflowId"
          @click="selectWorkflow(workflow.workflow_id)"
        />
      </div>
    </div>

    <!-- 当前工作流的步骤 -->
    <div
      v-if="currentWorkflow"
      class="border-t border-border/20"
    >
      <!-- 步骤头部 -->
      <div class="flex items-center justify-between px-4 py-2">
        <h4 class="text-xs font-semibold text-muted-foreground">执行步骤</h4>
        <span class="text-[10px] text-muted-foreground">
          {{ currentWorkflowSteps.length }} 个步骤
        </span>
      </div>

      <!-- 步骤列表 -->
      <div class="max-h-[280px] overflow-auto px-3 pb-3">
        <WorkflowStepTree
          :steps="currentWorkflowSteps"
          :step-statuses="stepStatuses"
          :current-step-id="currentRun?.current_step_id"
          @step-click="handleStepClick"
        />
      </div>

      <!-- 执行控制 -->
      <div class="border-t border-border/20 p-3">
        <!-- 进度条 -->
        <div v-if="isRunning || isCompleted || isFailed" class="mb-3">
          <div class="mb-1 flex items-center justify-between text-[10px]">
            <span class="text-muted-foreground">进度</span>
            <span class="font-semibold text-foreground">{{ progressPercentage }}%</span>
          </div>
          <div class="h-1.5 w-full overflow-hidden rounded-full bg-border/20">
            <div
              class="h-full rounded-full transition-all duration-300"
              :class="{
                'bg-blue-500': isRunning,
                'bg-green-500': isCompleted,
                'bg-red-500': isFailed,
              }"
              :style="{ width: `${progressPercentage}%` }"
            />
          </div>
        </div>

        <!-- 执行按钮 -->
        <div class="flex gap-2">
          <button
            v-if="!currentRun || isCompleted || isFailed"
            class="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground transition hover:bg-primary/90"
            @click="() => startRun()"
          >
            <Play class="h-3.5 w-3.5" />
            执行
          </button>

          <template v-else-if="isRunning">
            <button
              class="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-border/40 bg-background/50 px-3 py-2 text-xs font-medium text-foreground transition hover:bg-background"
              @click="pauseRun"
            >
              <Pause class="h-3.5 w-3.5" />
              暂停
            </button>
            <button
              class="flex items-center justify-center rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs font-medium text-red-500 transition hover:bg-red-500/20"
              @click="cancelRun"
            >
              <X class="h-3.5 w-3.5" />
            </button>
          </template>

          <button
            v-else-if="isPaused"
            class="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground transition hover:bg-primary/90"
            @click="resumeRun"
          >
            <Play class="h-3.5 w-3.5" />
            继续
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import {
  Plus,
  PanelLeftClose,
  Loader2,
  Workflow,
  Play,
  Pause,
  X,
} from 'lucide-vue-next'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import WorkflowListItem from './WorkflowListItem.vue'
import WorkflowStepTree from './WorkflowStepTree.vue'
import type { WorkflowStep } from '../../types/workspace'

// ========== Emits ==========
defineEmits<{
  collapse: []
}>()

// ========== Store ==========
const store = useWorkspaceStore()
const {
  workflows,
  currentWorkflowId,
  currentWorkflow,
  currentWorkflowSteps,
  currentRun,
  stepStatuses,
  loading,
  isRunning,
  isPaused,
  isCompleted,
  isFailed,
  progressPercentage,
} = storeToRefs(store)

const {
  selectWorkflow,
  selectStep,
  startRun,
  pauseRun,
  resumeRun,
  cancelRun,
  openCreateWorkflowDialog,
} = store

// ========== Methods ==========

function handleCreate() {
  openCreateWorkflowDialog()
}

function handleStepClick(step: WorkflowStep) {
  selectStep(step)
}
</script>

<style scoped>
.workflow-panel {
  scrollbar-width: thin;
  scrollbar-color: rgba(100, 100, 100, 0.3) rgba(0, 0, 0, 0.1);
}

.workflow-panel::-webkit-scrollbar {
  width: 6px;
}

.workflow-panel::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
}

.workflow-panel::-webkit-scrollbar-thumb {
  background: rgba(100, 100, 100, 0.3);
  border-radius: 3px;
}
</style>
