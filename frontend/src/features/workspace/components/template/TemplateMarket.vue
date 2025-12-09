<script setup lang="ts">
/**
 * 模板市场页面
 *
 * Phase 4: 展示所有可用模板，支持搜索、筛选、分页
 */

import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import {
  Search,
  SlidersHorizontal,
  RefreshCw,
  Upload,
  ChevronLeft,
  Loader2,
} from 'lucide-vue-next'
import { useTemplateStore } from '../../stores/templateStore'
import { TEMPLATE_CATEGORIES } from '../../types/template'
import type { TemplateResponse } from '../../types/template'
import TemplateCard from './TemplateCard.vue'
import TemplateDetail from './TemplateDetail.vue'
import VariableFormDialog from './VariableFormDialog.vue'
import TemplateImportDialog from './TemplateImportDialog.vue'

const router = useRouter()
const store = useTemplateStore()

// 对话框状态
const detailOpen = ref(false)
const instantiateOpen = ref(false)
const importOpen = ref(false)
const selectedTemplate = ref<TemplateResponse | null>(null)

// 搜索防抖
const searchInput = ref('')
let searchTimeout: ReturnType<typeof setTimeout> | null = null

watch(searchInput, (value) => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    store.setFilter('search', value)
  }, 300)
})

// 初始化
onMounted(async () => {
  await Promise.all([
    store.loadTemplates(),
    store.loadCategories(),
  ])
})

// 分类选择
function handleCategorySelect(category: string | null) {
  store.setFilter('category', category === 'all' ? null : category)
}

// 排序选择
function handleSortChange(value: string) {
  store.setFilter('sortBy', value as 'usage_count' | 'created_at' | 'name')
}

// 刷新
async function handleRefresh() {
  await store.loadTemplates()
}

// 查看详情
function handleViewTemplate(template: TemplateResponse) {
  selectedTemplate.value = template
  detailOpen.value = true
}

// 使用模板
function handleUseTemplate(template: TemplateResponse) {
  selectedTemplate.value = template
  instantiateOpen.value = true
}

// 实例化完成
function handleInstantiated(workflowId: string) {
  instantiateOpen.value = false
  // 跳转到工作台
  router.push(`/workspace/${workflowId}`)
}

// 导入完成
function handleImported() {
  importOpen.value = false
  store.loadTemplates()
}

// 返回工作台
function goBack() {
  router.push('/workspace')
}
</script>

<template>
  <div class="template-market h-full flex flex-col bg-background">
    <!-- 顶部导航 -->
    <header class="flex items-center justify-between px-4 py-3 border-b">
      <div class="flex items-center gap-3">
        <Button variant="ghost" size="icon" @click="goBack">
          <ChevronLeft class="w-5 h-5" />
        </Button>
        <h1 class="text-lg font-semibold">模板市场</h1>
        <Badge variant="secondary">
          {{ store.total }} 个模板
        </Badge>
      </div>

      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" @click="importOpen = true">
          <Upload class="w-4 h-4 mr-1" />
          导入
        </Button>
        <Button variant="ghost" size="icon" @click="handleRefresh" :disabled="store.loading">
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': store.loading }" />
        </Button>
      </div>
    </header>

    <!-- 筛选栏 -->
    <div class="px-4 py-3 border-b space-y-3">
      <!-- 搜索框 -->
      <div class="relative">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          v-model="searchInput"
          placeholder="搜索模板..."
          class="pl-9"
        />
      </div>

      <!-- 分类 + 排序 -->
      <div class="flex items-center gap-3">
        <!-- 分类选择 -->
        <div class="flex items-center gap-1 flex-wrap">
          <Button
            variant="ghost"
            size="sm"
            :class="{ 'bg-primary/10': !store.filters.category }"
            @click="handleCategorySelect(null)"
          >
            全部
            <Badge v-if="store.total" variant="secondary" class="ml-1">
              {{ store.total }}
            </Badge>
          </Button>
          <Button
            v-for="cat in store.categories"
            :key="cat.category"
            variant="ghost"
            size="sm"
            :class="{ 'bg-primary/10': store.filters.category === cat.category }"
            @click="handleCategorySelect(cat.category)"
          >
            {{ cat.label }}
            <Badge v-if="cat.count" variant="secondary" class="ml-1">
              {{ cat.count }}
            </Badge>
          </Button>
        </div>

        <Separator orientation="vertical" class="h-6" />

        <!-- 排序 -->
        <div class="flex items-center gap-2">
          <SlidersHorizontal class="w-4 h-4 text-muted-foreground" />
          <Select :model-value="store.filters.sortBy" @update:model-value="handleSortChange">
            <SelectTrigger class="w-32 h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="usage_count">最多使用</SelectItem>
              <SelectItem value="created_at">最新创建</SelectItem>
              <SelectItem value="name">按名称</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>

    <!-- 模板网格 -->
    <div class="flex-1 overflow-auto p-4">
      <!-- 加载中 -->
      <div v-if="store.loading && store.templates.length === 0" class="flex items-center justify-center h-64">
        <Loader2 class="w-8 h-8 animate-spin text-muted-foreground" />
      </div>

      <!-- 空状态 -->
      <div v-else-if="store.templates.length === 0" class="flex flex-col items-center justify-center h-64 text-muted-foreground">
        <Search class="w-12 h-12 mb-4" />
        <p>没有找到匹配的模板</p>
        <Button variant="link" @click="store.resetFilters()">
          清除筛选条件
        </Button>
      </div>

      <!-- 模板列表 -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <TemplateCard
          v-for="template in store.templates"
          :key="template.template_id"
          :template="template"
          @view="handleViewTemplate"
          @use="handleUseTemplate"
        />
      </div>

      <!-- 加载更多 -->
      <div v-if="store.hasMore" class="flex justify-center mt-6">
        <Button
          variant="outline"
          @click="store.loadMore()"
          :disabled="store.loading"
        >
          <Loader2 v-if="store.loading" class="w-4 h-4 mr-2 animate-spin" />
          加载更多
        </Button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div
      v-if="store.error"
      class="fixed bottom-4 right-4 bg-destructive text-destructive-foreground px-4 py-2 rounded-md shadow-lg"
    >
      {{ store.error }}
    </div>

    <!-- 对话框 -->
    <TemplateDetail
      v-model:open="detailOpen"
      :template="selectedTemplate"
      @use="handleUseTemplate"
    />

    <VariableFormDialog
      v-model:open="instantiateOpen"
      :template="selectedTemplate"
      @instantiated="handleInstantiated"
    />

    <TemplateImportDialog
      v-model:open="importOpen"
      @imported="handleImported"
    />
  </div>
</template>

<style scoped>
.template-market {
  min-height: 100vh;
}
</style>
