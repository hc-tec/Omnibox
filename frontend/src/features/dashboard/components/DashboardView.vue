<script setup lang="ts">
/**
 * 仪表盘主视图
 *
 * Phase 5: Dashboard UI
 */
import { onMounted, computed } from 'vue'
import { RefreshCw, Plus, LayoutDashboard, Settings } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useDashboardStore } from '../stores/dashboardStore'
import DashboardGrid from './DashboardGrid.vue'
import DashboardCard from './DashboardCard.vue'
import NotificationBell from './NotificationBell.vue'
import AddCardDialog from './AddCardDialog.vue'
import CardSettingsDialog from './CardSettingsDialog.vue'

const store = useDashboardStore()

// 计算属性
const hasCards = computed(() => store.cards.length > 0)

// 生命周期
onMounted(async () => {
  await store.loadCards()
  await store.loadNotifications()

  // 加载每个卡片的数据
  for (const card of store.cards) {
    store.getCardData(card.card_id)
  }
})

// 事件处理
async function handleRefreshAll() {
  await store.refreshAll()
}

function handleAddCard() {
  store.openAddCardDialog()
}

async function handleRefreshCard(cardId: string) {
  await store.refreshCard(cardId)
}

async function handleDeleteCard(cardId: string) {
  if (confirm('确定要删除这个卡片吗？')) {
    await store.deleteCard(cardId)
  }
}

function handleSettingsCard(cardId: string) {
  store.openSettingsDialog(cardId)
}

async function handleLayoutChange(layouts: Array<{ card_id: string; x: number; y: number; width: number; height: number }>) {
  await store.updateLayout(layouts)
}
</script>

<template>
  <div class="dashboard-view h-full flex flex-col bg-background">
    <!-- 顶部工具栏 -->
    <header class="dashboard-header flex items-center justify-between px-6 py-4 border-b border-border/50">
      <div class="flex items-center gap-3">
        <LayoutDashboard class="w-6 h-6 text-primary" />
        <h1 class="text-xl font-semibold">监控仪表盘</h1>
        <Badge variant="secondary" class="ml-2">
          {{ store.cards.length }} 个卡片
        </Badge>
      </div>

      <div class="flex items-center gap-2">
        <!-- 通知铃铛 -->
        <NotificationBell />

        <!-- 刷新按钮 -->
        <Button
          variant="outline"
          size="sm"
          :disabled="store.loading"
          @click="handleRefreshAll"
        >
          <RefreshCw
            class="w-4 h-4 mr-2"
            :class="{ 'animate-spin': store.loading }"
          />
          全部刷新
        </Button>

        <!-- 编辑模式 -->
        <Button
          variant="outline"
          size="sm"
          :class="{ 'bg-primary/10': store.editMode }"
          @click="store.toggleEditMode"
        >
          <Settings class="w-4 h-4 mr-2" />
          {{ store.editMode ? '完成编辑' : '编辑布局' }}
        </Button>

        <!-- 添加卡片 -->
        <Button size="sm" @click="handleAddCard">
          <Plus class="w-4 h-4 mr-2" />
          添加卡片
        </Button>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="flex-1 overflow-auto p-6">
      <!-- 卡片网格 -->
      <DashboardGrid
        v-if="hasCards"
        :cards="store.sortedCards"
        :edit-mode="store.editMode"
        @layout-change="handleLayoutChange"
      >
        <template #card="{ card }">
          <DashboardCard
            :card="card"
            :data="store.cardDataMap[card.card_id]"
            :loading="store.isCardLoading(card.card_id)"
            :edit-mode="store.editMode"
            @refresh="handleRefreshCard(card.card_id)"
            @settings="handleSettingsCard(card.card_id)"
            @delete="handleDeleteCard(card.card_id)"
          />
        </template>
      </DashboardGrid>

      <!-- 空状态 -->
      <div
        v-else
        class="empty-state flex flex-col items-center justify-center h-full text-center"
      >
        <div class="p-6 rounded-full bg-muted/50 mb-4">
          <LayoutDashboard class="w-12 h-12 text-muted-foreground" />
        </div>
        <h2 class="text-lg font-medium mb-2">还没有添加任何卡片</h2>
        <p class="text-sm text-muted-foreground mb-6 max-w-md">
          从工作流结果或数据产物中 Pin 卡片到这里，实时监控数据变化
        </p>
        <Button @click="handleAddCard">
          <Plus class="w-4 h-4 mr-2" />
          添加第一个卡片
        </Button>
      </div>
    </main>

    <!-- 错误提示 -->
    <div
      v-if="store.error"
      class="fixed bottom-4 right-4 bg-destructive text-destructive-foreground px-4 py-2 rounded-lg shadow-lg"
    >
      {{ store.error }}
      <button class="ml-2 underline" @click="store.clearError">关闭</button>
    </div>

    <!-- 对话框 -->
    <AddCardDialog />
    <CardSettingsDialog />
  </div>
</template>

<style scoped>
.dashboard-view {
  background: linear-gradient(
    135deg,
    hsl(var(--background)) 0%,
    hsl(var(--muted) / 0.3) 100%
  );
}
</style>
