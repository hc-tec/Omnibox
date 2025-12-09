<template>
  <div class="context-panel flex h-full flex-col">
    <!-- 头部 -->
    <header class="flex items-center justify-between border-b border-border/20 px-4 py-3">
      <div class="flex items-center gap-2">
        <h3 class="text-sm font-semibold text-foreground">执行上下文</h3>
      </div>
      <Button
        variant="ghost"
        size="icon"
        class="h-7 w-7"
        title="折叠面板"
        @click="$emit('collapse')"
      >
        <PanelRightClose class="h-4 w-4" />
      </Button>
    </header>

    <!-- Session 状态 -->
    <div
      v-if="sessionStore.hasSession"
      class="border-b border-border/20 px-4 py-3"
    >
      <div class="flex items-center gap-2 text-xs text-muted-foreground">
        <span class="flex items-center gap-1">
          <span class="h-1.5 w-1.5 rounded-full bg-green-500"></span>
          Session 活跃
        </span>
        <span>|</span>
        <span>对话 {{ sessionStore.chatHistoryCount }}</span>
        <span>|</span>
        <span>步骤 {{ sessionStore.stepsCount }}</span>
      </div>
    </div>

    <!-- 标签页 -->
    <Tabs v-model="activeTab" class="flex flex-1 flex-col overflow-hidden">
      <TabsList class="mx-3 mt-3 grid w-auto grid-cols-2">
        <TabsTrigger value="panels" class="gap-1.5 text-xs">
          <LayoutGrid class="h-3.5 w-3.5" />
          面板
          <Badge v-if="workspaceStore.panelPreviews.length > 0" variant="secondary" class="ml-1 px-1.5 py-0 text-[10px]">
            {{ workspaceStore.panelPreviews.length }}
          </Badge>
        </TabsTrigger>
        <TabsTrigger value="artifacts" class="gap-1.5 text-xs">
          <Database class="h-3.5 w-3.5" />
          产物
          <Badge v-if="workspaceStore.artifacts.length > 0" variant="secondary" class="ml-1 px-1.5 py-0 text-[10px]">
            {{ workspaceStore.artifacts.length }}
          </Badge>
        </TabsTrigger>
      </TabsList>

      <!-- 面板列表 -->
      <TabsContent value="panels" class="flex-1 overflow-auto p-3">
        <div v-if="workspaceStore.panelPreviews.length > 0" class="space-y-2">
          <div
            v-for="panel in workspaceStore.panelPreviews"
            :key="panel.id"
            class="cursor-pointer rounded-lg border border-border/40 bg-background/50 p-3 transition hover:border-border/60 hover:bg-background/80"
            :class="{
              'border-primary/40 bg-primary/5':
                panel.id === workspaceStore.selectedPanelId,
            }"
            @click="handlePanelClick(panel.id)"
          >
            <div class="flex items-start gap-2">
              <LayoutGrid class="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" />
              <div class="flex-1 min-w-0">
                <p class="text-xs font-medium text-foreground truncate">
                  {{ panel.title }}
                </p>
                <p
                  v-if="panel.sourceQuery"
                  class="mt-0.5 text-[10px] text-muted-foreground truncate"
                >
                  {{ panel.sourceQuery }}
                </p>
                <p class="mt-1 text-[10px] text-muted-foreground">
                  {{ formatTimestamp(panel.createdAt) }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="py-8 text-center">
          <LayoutGrid class="mx-auto h-10 w-10 text-muted-foreground/50" />
          <p class="mt-2 text-xs text-muted-foreground">暂无面板</p>
          <p class="mt-1 text-[10px] text-muted-foreground/70">
            面板是可视化展示结果
          </p>
        </div>
      </TabsContent>

      <!-- 数据产物列表 -->
      <TabsContent value="artifacts" class="flex-1 overflow-auto p-3">
        <div v-if="workspaceStore.artifacts.length > 0" class="space-y-2">
          <div
            v-for="artifact in workspaceStore.artifacts"
            :key="artifact.artifact_id"
            class="cursor-pointer rounded-lg border border-border/40 bg-background/50 p-3 transition hover:border-border/60 hover:bg-background/80"
            :class="{
              'border-primary/40 bg-primary/5':
                artifact.artifact_id === workspaceStore.selectedArtifactId,
            }"
            @click="workspaceStore.selectArtifact(artifact.artifact_id)"
          >
            <div class="flex items-start gap-2">
              <Database class="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
              <div class="flex-1 min-w-0">
                <p class="text-xs font-medium text-foreground truncate">
                  {{ artifact.name }}
                </p>
                <p class="mt-0.5 text-[10px] text-muted-foreground truncate">
                  {{ artifact.description || artifact.artifact_type }}
                </p>
                <div class="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
                  <span>{{ artifact.artifact_type }}</span>
                  <span v-if="artifact.schema_info?.total_count">
                    {{ artifact.schema_info.total_count }} 条
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="py-8 text-center">
          <Database class="mx-auto h-10 w-10 text-muted-foreground/50" />
          <p class="mt-2 text-xs text-muted-foreground">暂无数据产物</p>
          <p class="mt-1 text-[10px] text-muted-foreground/70">
            数据产物是执行过程中的中间数据
          </p>
        </div>
      </TabsContent>
    </Tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  PanelRightClose,
  Database,
  LayoutGrid,
} from 'lucide-vue-next'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { useSessionStore } from '../../stores/sessionStore'

// ========== Emits ==========
defineEmits<{
  collapse: []
}>()

// ========== Store ==========
const workspaceStore = useWorkspaceStore()
const sessionStore = useSessionStore()

// ========== State ==========
type TabValue = 'artifacts' | 'panels'
const activeTab = ref<TabValue>('panels')

// ========== Methods ==========

/**
 * 处理面板点击：选中面板并导航到时间线对应位置
 */
function handlePanelClick(panelId: string) {
  // 选中面板
  workspaceStore.selectPanel(panelId)

  // 导航到时间线对应位置
  const panel = workspaceStore.panelPreviews.find(p => p.id === panelId)
  if (panel?.timelineEntryId) {
    workspaceStore.scrollToTimelineEntry(panel.timelineEntryId)
  }
}

function formatTimestamp(timestamp: string): string {
  if (!timestamp) return ''
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return timestamp
  }
}
</script>

<style scoped>
.context-panel {
  scrollbar-width: thin;
  scrollbar-color: rgba(100, 100, 100, 0.3) rgba(0, 0, 0, 0.1);
}

.context-panel::-webkit-scrollbar {
  width: 6px;
}

.context-panel::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
}

.context-panel::-webkit-scrollbar-thumb {
  background: rgba(100, 100, 100, 0.3);
  border-radius: 3px;
}
</style>
