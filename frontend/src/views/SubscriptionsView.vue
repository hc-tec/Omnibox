<script setup lang="ts">
/**
 * 订阅管理页面
 *
 * 采用与主界面一致的玻璃态设计风格
 */
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ArrowLeft, Plus, Filter, Search } from 'lucide-vue-next'
import { useSubscriptionStore } from '@/store/subscriptionStore'
import { usePanelActions } from '@/features/panel/usePanelActions'
import SubscriptionCard from '@/components/subscription/SubscriptionCard.vue'
import SubscriptionForm from '@/components/subscription/SubscriptionForm.vue'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type {
  Subscription,
  SubscriptionCreateRequest,
  SubscriptionUpdateRequest,
} from '@/types/subscription'
import { ACTION_DISPLAY_NAMES } from '@/types/subscription'

// Router and Store
const router = useRouter()
const subscriptionStore = useSubscriptionStore()
const { subscriptions, total, loading, error } = storeToRefs(subscriptionStore)
const { submit: submitPanelQuery } = usePanelActions()

// 表单状态
const formOpen = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const editingSubscription = ref<Subscription | null>(null)

// 过滤器
const platformFilter = ref<string>('all')
const entityTypeFilter = ref<string>('all')
const searchQuery = ref<string>('')

// 分页状态
const currentLimit = ref(100)
const canLoadMore = computed(() => {
  return subscriptions.value && total.value > subscriptions.value.length
})

// 过滤后的订阅列表
const filteredSubscriptions = computed(() => {
  const subs = subscriptions.value || []
  let result = subs

  // 平台过滤
  if (platformFilter.value !== 'all') {
    result = result.filter((sub) => sub.platform === platformFilter.value)
  }

  // 实体类型过滤
  if (entityTypeFilter.value !== 'all') {
    result = result.filter((sub) => sub.entity_type === entityTypeFilter.value)
  }

  // 搜索过滤
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter((sub) =>
      sub.display_name.toLowerCase().includes(query) ||
      sub.description?.toLowerCase().includes(query) ||
      sub.aliases.some(alias => alias.toLowerCase().includes(query))
    )
  }

  return result
})

// 获取所有平台
const platforms = computed(() => {
  const subs = subscriptions.value || []
  const uniquePlatforms = new Set(subs.map((sub) => sub.platform))
  return Array.from(uniquePlatforms).sort()
})

// 获取所有实体类型
const entityTypes = computed(() => {
  const subs = subscriptions.value || []
  const uniqueTypes = new Set(subs.map((sub) => sub.entity_type))
  return Array.from(uniqueTypes).sort()
})

// 页面加载时获取订阅列表
onMounted(async () => {
  await loadSubscriptions()
})

// 加载订阅列表
async function loadSubscriptions() {
  try {
    // 后端API限制limit最大为100
    await subscriptionStore.fetchSubscriptions({ limit: currentLimit.value })
  } catch (err) {
    console.error('加载订阅列表失败:', err)
  }
}

// 加载更多订阅
async function loadMore() {
  try {
    const currentOffset = subscriptions.value?.length || 0
    await subscriptionStore.fetchSubscriptions(
      {
        limit: 100,
        offset: currentOffset,
      },
      true  // 追加模式
    )
  } catch (err) {
    console.error('加载更多失败:', err)
  }
}

// 打开添加表单
function handleAdd() {
  formMode.value = 'create'
  editingSubscription.value = null
  formOpen.value = true
}

// 打开编辑表单
function handleEdit(subscription: Subscription) {
  formMode.value = 'edit'
  editingSubscription.value = subscription
  formOpen.value = true
}

// 删除订阅
async function handleDelete(id: number) {
  if (!confirm('确定要删除这个订阅吗？')) {
    return
  }

  try {
    await subscriptionStore.deleteSubscription(id)
  } catch (err) {
    console.error('删除订阅失败:', err)
    alert('删除订阅失败')
  }
}

// 提交表单
async function handleFormSubmit(data: SubscriptionCreateRequest | SubscriptionUpdateRequest) {
  try {
    if (formMode.value === 'create') {
      await subscriptionStore.createSubscription(data as SubscriptionCreateRequest)
    } else if (editingSubscription.value) {
      await subscriptionStore.updateSubscription(
        editingSubscription.value.id,
        data as SubscriptionUpdateRequest
      )
    }

    // 操作成功，关闭表单
    formOpen.value = false
  } catch (err: any) {
    console.error('提交表单失败:', err)

    // 操作失败，显示错误信息但保持表单打开，让用户可以修改数据
    if (err.response?.status === 409) {
      alert('订阅已存在，请检查并修改后重试')
    } else {
      alert('操作失败：' + (err.response?.data?.detail || err.message))
    }

    // 注意：不关闭表单，用户数据得以保留
  }
}

// 点击动作按钮
async function handleActionClick(subscription: Subscription, action: string) {
  console.log('触发查询:', subscription, action)

  // 获取动作的中文显示名称
  const actionDisplayName = ACTION_DISPLAY_NAMES[action] || action

  // 构建查询字符串
  const query = `${subscription.display_name}的${actionDisplayName}`

  try {
    // 提交查询到面板
    await submitPanelQuery({ query })

    // 导航回主页面查看结果
    await router.push({ path: '/' })
  } catch (err) {
    console.error('查询失败:', err)
    alert('查询失败，请稍后重试')
  }
}

// 清空错误
function clearError() {
  subscriptionStore.clearError()
}

// 返回主页
function goBack() {
  router.push({ path: '/' })
}
</script>

<template>
  <div class="app-shell relative min-h-screen overflow-hidden bg-background text-foreground">
    <!-- 渐变背景装饰 -->
    <div class="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-background/40 to-background" />
    <div class="pointer-events-none absolute -top-40 right-1/4 h-[520px] w-[520px] rounded-full bg-[#5b8cff]/30 blur-[180px]" />
    <div class="pointer-events-none absolute -bottom-52 left-1/5 h-[620px] w-[620px] rounded-full bg-emerald-400/25 blur-[200px]" />

    <div class="relative z-10 flex min-h-screen flex-col gap-4 px-6 py-6 md:px-12 md:py-8">
      <!-- 顶部导航栏 -->
      <header class="app-chrome flex items-center justify-between rounded-[24px] border border-border/30 bg-[var(--shell-surface)]/75 px-5 py-3 backdrop-blur">
        <div class="flex items-center gap-3">
          <button
            type="button"
            class="inline-flex h-9 items-center gap-2 rounded-xl border border-border/40 bg-background/50 px-3 text-sm font-medium transition hover:bg-background"
            @click="goBack"
          >
            <ArrowLeft class="h-4 w-4" />
            返回主页
          </button>

          <div class="h-6 w-px bg-border/40" />

          <div>
            <p class="text-[10px] uppercase tracking-[0.5em] text-muted-foreground">Subscription</p>
            <p class="text-lg font-semibold leading-tight">订阅管理</p>
          </div>
        </div>

        <button
          class="inline-flex h-9 items-center gap-2 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-500 px-4 text-sm font-semibold text-white shadow-lg shadow-indigo-500/35 transition hover:scale-95"
          @click="handleAdd"
        >
          <Plus class="h-4 w-4" />
          添加订阅
        </button>
      </header>

      <!-- 主内容区域 -->
      <main class="desktop-stage relative flex-1 rounded-[32px] border border-border/20 bg-[var(--canvas-gradient)]/95 backdrop-blur">
        <div class="canvas-flow mx-auto w-full px-6 py-8 md:px-10" style="max-width: clamp(320px, calc(100vw - 4rem), 2400px);">

          <!-- 错误提示 -->
          <Alert v-if="error" variant="destructive" class="mb-6">
            <AlertTitle>错误</AlertTitle>
            <AlertDescription class="flex items-center justify-between">
              <span>{{ error }}</span>
              <Button variant="ghost" size="sm" @click="clearError">
                关闭
              </Button>
            </AlertDescription>
          </Alert>

          <!-- 搜索和过滤器 -->
          <div class="mb-6 flex flex-wrap items-center gap-3">
            <!-- 搜索框 -->
            <div class="relative flex-1 min-w-[200px] max-w-md">
              <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="searchQuery"
                placeholder="搜索订阅..."
                class="pl-10 rounded-xl border-border/40 bg-background/50 backdrop-blur"
              />
            </div>

            <!-- 平台过滤 -->
            <div class="flex items-center gap-2">
              <Filter class="h-4 w-4 text-muted-foreground" />
              <Select v-model="platformFilter">
                <SelectTrigger class="w-32 rounded-xl border-border/40 bg-background/50 backdrop-blur">
                  <SelectValue placeholder="平台" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部平台</SelectItem>
                  <SelectItem v-for="platform in platforms" :key="platform" :value="platform">
                    {{ platform }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <!-- 实体类型过滤 -->
            <Select v-model="entityTypeFilter">
              <SelectTrigger class="w-32 rounded-xl border-border/40 bg-background/50 backdrop-blur">
                <SelectValue placeholder="类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部类型</SelectItem>
                <SelectItem v-for="type in entityTypes" :key="type" :value="type">
                  {{ type }}
                </SelectItem>
              </SelectContent>
            </Select>

            <div class="ml-auto text-sm text-muted-foreground">
              {{ filteredSubscriptions?.length || 0 }} 个订阅
            </div>
          </div>

          <!-- 加载状态（仅在初次加载时显示）-->
          <div v-if="loading && (!subscriptions || subscriptions.length === 0)" class="flex flex-col items-center justify-center py-20">
            <div class="h-12 w-12 animate-spin rounded-full border-4 border-primary/20 border-t-primary"></div>
            <p class="mt-4 text-sm text-muted-foreground">加载中...</p>
          </div>

          <!-- 空状态 -->
          <div
            v-else-if="!filteredSubscriptions || filteredSubscriptions.length === 0"
            class="flex flex-col items-center justify-center rounded-[24px] border-2 border-dashed border-border/40 bg-muted/5 py-20"
          >
            <div class="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted/20">
              <Plus class="h-8 w-8 text-muted-foreground" />
            </div>
            <p class="mb-2 text-lg font-semibold">还没有订阅</p>
            <p class="mb-6 text-sm text-muted-foreground">
              {{ searchQuery ? '没有匹配的结果' : '点击上方按钮添加第一个订阅' }}
            </p>
            <Button v-if="!searchQuery" @click="handleAdd" class="rounded-xl">
              添加订阅
            </Button>
          </div>

          <!-- 订阅列表（网格布局）-->
          <div v-else>
            <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              <SubscriptionCard
                v-for="subscription in filteredSubscriptions"
                :key="subscription.id"
                :subscription="subscription"
                @edit="handleEdit"
                @delete="handleDelete"
                @action-click="handleActionClick"
              />
            </div>

            <!-- 加载更多按钮 -->
            <div v-if="canLoadMore && !searchQuery && platformFilter === 'all' && entityTypeFilter === 'all'" class="mt-8 flex justify-center">
              <Button
                @click="loadMore"
                :disabled="loading"
                variant="outline"
                class="rounded-xl border-border/40 bg-background/50 backdrop-blur hover:bg-background"
              >
                {{ loading ? '加载中...' : `加载更多 (${subscriptions.length}/${total})` }}
              </Button>
            </div>
          </div>

          <!-- 底部HUD -->
          <div class="mt-10 flex flex-wrap items-center justify-center gap-4 text-[11px] uppercase tracking-[0.35em] text-muted-foreground/80">
            <span class="rounded-full border border-border/60 px-4 py-1">订阅管理</span>
            <span>{{ filteredSubscriptions?.length || 0 }} 项</span>
          </div>
        </div>
      </main>
    </div>

    <!-- 表单对话框 -->
    <SubscriptionForm
      v-model:open="formOpen"
      :mode="formMode"
      :subscription="editingSubscription"
      @submit="handleFormSubmit"
    />
  </div>
</template>
