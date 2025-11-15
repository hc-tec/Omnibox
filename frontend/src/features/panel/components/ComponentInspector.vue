<template>
  <Dialog :open="open" @update:open="onOpenChange">
    <DialogPortalPrimitive>
      <DialogOverlayPrimitive
        class="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0"
      />
      <DialogContent
        class="fixed left-1/2 top-1/2 z-50 w-full max-w-5xl -translate-x-1/2 -translate-y-1/2 flex flex-col max-h-[90vh] rounded-2xl border border-border/30 bg-background/95 backdrop-blur-xl shadow-2xl data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0 data-[state=open]:zoom-in-95 data-[state=closed]:zoom-out-95"
      >
        <!-- 顶部状态条 -->
        <div class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-blue-500 rounded-t-2xl" />

        <!-- Header -->
        <div class="relative flex items-start justify-between gap-3 p-5 pb-4 border-b border-border/30">
          <div class="flex items-start gap-3 flex-1 min-w-0">
            <!-- 图标 -->
            <div class="flex-shrink-0 mt-0.5">
              <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 shadow-lg shadow-indigo-500/20">
                <svg class="h-5 w-5 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
              </div>
            </div>

            <!-- 标题 -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1 flex-wrap">
                <Badge variant="secondary" class="text-[10px] uppercase tracking-wider font-semibold">
                  Component Inspector
                </Badge>
                <Badge variant="outline" class="text-[10px]">
                  {{ block?.component || 'Unknown' }}
                </Badge>
                <span v-if="block?.confidence !== undefined" class="text-[10px] text-muted-foreground">
                  置信度 {{ (block.confidence * 100).toFixed(0) }}%
                </span>
              </div>
              <h3 class="text-sm font-semibold leading-snug text-foreground">
                {{ componentName || '组件调试信息' }}
              </h3>
            </div>
          </div>

          <!-- 关闭按钮 -->
          <Button
            variant="ghost"
            size="icon"
            class="h-8 w-8 opacity-0 hover:opacity-100 transition-opacity -mr-2 -mt-1"
            @click="emit('close')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 6 6 18"/><path d="m6 6 12 12"/>
            </svg>
          </Button>
        </div>

        <!-- Tabs -->
        <Tabs v-model="activeTab" class="flex-1 flex flex-col overflow-hidden">
          <TabsList class="shrink-0 mx-5 mt-4 bg-muted/40">
            <TabsTrigger value="overview">概览</TabsTrigger>
            <TabsTrigger value="props">Props</TabsTrigger>
            <TabsTrigger value="options">Options</TabsTrigger>
            <TabsTrigger value="raw">Raw JSON</TabsTrigger>
          </TabsList>

          <!-- Content -->
          <div class="flex-1 overflow-y-auto px-5 py-4">
            <!-- Overview Tab -->
            <TabsContent value="overview" class="mt-0 space-y-4">
              <!-- 基础信息 -->
              <section class="space-y-3">
                <h4 class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">基础信息</h4>
                <div class="grid grid-cols-2 gap-3">
                  <div class="rounded-xl border border-border/40 bg-muted/20 p-3.5">
                    <p class="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">组件类型</p>
                    <Badge variant="secondary" class="text-xs font-mono">{{ block?.component || 'N/A' }}</Badge>
                  </div>
                  <div class="rounded-xl border border-border/40 bg-muted/20 p-3.5">
                    <p class="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">组件 ID</p>
                    <code class="text-xs font-mono text-foreground break-all">{{ block?.id || 'N/A' }}</code>
                  </div>
                  <div v-if="block?.title" class="col-span-2 rounded-xl border border-border/40 bg-muted/20 p-3.5">
                    <p class="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">标题</p>
                    <p class="text-sm font-medium text-foreground">{{ block.title }}</p>
                  </div>
                  <div v-if="block?.confidence !== undefined" class="rounded-xl border border-border/40 bg-muted/20 p-3.5">
                    <p class="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">置信度</p>
                    <Badge :variant="block.confidence > 0.8 ? 'default' : 'secondary'" class="text-xs">
                      {{ formatConfidence(block.confidence) }}
                    </Badge>
                  </div>
                  <div v-if="block?.data_ref" class="rounded-xl border border-border/40 bg-muted/20 p-3.5">
                    <p class="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">数据引用</p>
                    <code class="text-xs font-mono text-foreground break-all">{{ block.data_ref }}</code>
                  </div>
                </div>
              </section>

              <!-- 数据块信息 -->
              <section v-if="dataBlock" class="space-y-3">
                <h4 class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">数据块信息</h4>
                <div class="grid grid-cols-2 gap-3">
                  <div class="rounded-xl border border-border/40 bg-muted/20 p-3.5">
                    <p class="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">数据源</p>
                    <Badge variant="outline" class="text-xs">{{ dataBlock.source_info?.datasource || 'N/A' }}</Badge>
                  </div>
                  <div class="rounded-xl border border-border/40 bg-muted/20 p-3.5">
                    <p class="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">记录数</p>
                    <p class="text-sm font-semibold text-primary">
                      {{ dataBlock.stats?.total || dataBlock.records?.length || 0 }}
                    </p>
                  </div>
                  <div class="col-span-2 rounded-xl border border-border/40 bg-muted/20 p-3.5">
                    <p class="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">路由</p>
                    <code class="text-xs font-mono text-foreground break-all">
                      {{ dataBlock.source_info?.route || 'N/A' }}
                    </code>
                  </div>
                  <div v-if="dataBlock.source_info?.fetched_at" class="col-span-2 rounded-xl border border-border/40 bg-muted/20 p-3.5">
                    <p class="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">获取时间</p>
                    <p class="text-xs text-foreground">
                      {{ new Date(dataBlock.source_info.fetched_at).toLocaleString('zh-CN') }}
                    </p>
                  </div>
                </div>
              </section>

              <!-- 数据字段 -->
              <section v-if="dataBlock?.schema_summary" class="space-y-3">
                <h4 class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">数据字段</h4>
                <div class="space-y-2.5">
                  <div
                    v-for="field in dataBlock.schema_summary.fields"
                    :key="field.name"
                    class="rounded-xl border border-border/40 bg-muted/20 p-3.5"
                  >
                    <div class="flex items-center justify-between mb-2">
                      <code class="text-sm font-mono font-semibold text-foreground">{{ field.name }}</code>
                      <Badge variant="secondary" class="text-[10px]">{{ field.type }}</Badge>
                    </div>
                    <p v-if="field.sample && field.sample.length > 0" class="text-xs text-muted-foreground">
                      示例: {{ field.sample[0] }}
                    </p>
                  </div>
                </div>
              </section>
            </TabsContent>

            <!-- Props Tab -->
            <TabsContent value="props" class="mt-0">
              <div v-if="block?.props && Object.keys(block.props).length > 0" class="rounded-xl border border-border/40 bg-muted/20 p-4 overflow-x-auto">
                <pre class="text-xs font-mono text-foreground leading-relaxed">{{ JSON.stringify(block.props, null, 2) }}</pre>
              </div>
              <div v-else class="py-16 text-center">
                <div class="text-5xl mb-4 opacity-20">📭</div>
                <p class="text-sm text-muted-foreground">没有 Props 数据</p>
              </div>
            </TabsContent>

            <!-- Options Tab -->
            <TabsContent value="options" class="mt-0">
              <div v-if="block?.options && Object.keys(block.options).length > 0" class="rounded-xl border border-border/40 bg-muted/20 p-4 overflow-x-auto">
                <pre class="text-xs font-mono text-foreground leading-relaxed">{{ JSON.stringify(block.options, null, 2) }}</pre>
              </div>
              <div v-else class="py-16 text-center">
                <div class="text-5xl mb-4 opacity-20">📭</div>
                <p class="text-sm text-muted-foreground">没有 Options 数据</p>
              </div>
            </TabsContent>

            <!-- Raw Tab -->
            <TabsContent value="raw" class="mt-0 space-y-4">
              <section class="space-y-3">
                <h4 class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">UIBlock</h4>
                <div class="rounded-xl border border-border/40 bg-muted/20 p-4 overflow-x-auto">
                  <pre class="text-xs font-mono text-foreground leading-relaxed">{{ JSON.stringify(block, null, 2) }}</pre>
                </div>
              </section>
              <section v-if="dataBlock" class="space-y-3">
                <h4 class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">DataBlock</h4>
                <div class="rounded-xl border border-border/40 bg-muted/20 p-4 overflow-x-auto">
                  <pre class="text-xs font-mono text-foreground leading-relaxed">{{ JSON.stringify(dataBlock, null, 2) }}</pre>
                </div>
              </section>
            </TabsContent>
          </div>
        </Tabs>
      </DialogContent>
    </DialogPortalPrimitive>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { UIBlock, DataBlock } from '@/shared/types/panel';
import Dialog from '@/components/ui/dialog/Dialog.vue';
import DialogContent from '@/components/ui/dialog/DialogContent.vue';
import { DialogOverlay as DialogOverlayPrimitive, DialogPortal as DialogPortalPrimitive } from 'reka-ui';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

const props = defineProps<{
  open: boolean;
  block?: UIBlock | null;
  dataBlock?: DataBlock | null;
}>();

const emit = defineEmits<{
  (event: 'close'): void;
}>();

const activeTab = ref('overview');

const componentName = computed(() => {
  if (!props.block) return '';
  const labels: Record<string, string> = {
    ListPanel: '洞察列表',
    LineChart: '趋势图',
    BarChart: '对比图',
    PieChart: '占比分析',
    Table: '数据表',
    StatisticCard: '指标卡片',
    ImageGallery: '图像画廊',
    MediaCardGrid: '媒体卡片',
  };
  return labels[props.block.component] || props.block.component || '未知组件';
});

const onOpenChange = (value: boolean) => {
  if (!value) emit('close');
};

function formatConfidence(value?: number | null): string {
  if (value === undefined || value === null) return 'N/A';
  return `${(value * 100).toFixed(1)}%`;
}
</script>

<style scoped>
/* 自定义滚动条 */
.overflow-y-auto::-webkit-scrollbar {
  width: 6px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: transparent;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: hsl(var(--border));
  border-radius: 3px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: hsl(var(--muted-foreground) / 0.3);
}

.overflow-x-auto::-webkit-scrollbar {
  height: 6px;
}

.overflow-x-auto::-webkit-scrollbar-track {
  background: transparent;
}

.overflow-x-auto::-webkit-scrollbar-thumb {
  background: hsl(var(--border));
  border-radius: 3px;
}

.overflow-x-auto::-webkit-scrollbar-thumb:hover {
  background: hsl(var(--muted-foreground) / 0.3);
}
</style>
