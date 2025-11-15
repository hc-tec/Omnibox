<template>
  <Dialog :open="open" @update:open="onOpenChange">
    <DialogPortalPrimitive>
      <DialogOverlayPrimitive
        class="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0"
      />
      <DialogContent
        class="fixed right-0 top-0 z-50 h-screen w-full max-w-lg translate-x-0 translate-y-0 flex flex-col rounded-none border-l border-border/40 bg-background shadow-2xl data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right"
      >
        <!-- Header -->
        <div class="shrink-0 border-b border-border/30 px-6 py-5">
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-1.5">
                <div class="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
                <span class="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                  Card Inspector
                </span>
              </div>
              <h2 class="text-2xl font-bold text-foreground">
                调试信息
              </h2>
            </div>
            <button
              @click="emit('close')"
              class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border/50 bg-background text-muted-foreground transition-all hover:border-border hover:bg-muted hover:text-foreground"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M18 6 6 18"/><path d="m6 6 12 12"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Content -->
        <div class="flex-1 overflow-y-auto px-6 py-6">
          <div class="space-y-5">
            <!-- 基础信息 -->
            <section>
              <h3 class="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                基础信息
              </h3>
              <div class="space-y-2">
                <div class="flex items-center justify-between rounded-lg border border-border/40 bg-muted/20 px-4 py-3">
                  <span class="text-sm text-muted-foreground">意图类型</span>
                  <span class="font-mono text-sm font-semibold text-foreground">
                    {{ metadata?.intent_type || 'N/A' }}
                  </span>
                </div>
                <div class="flex items-center justify-between rounded-lg border border-border/40 bg-muted/20 px-4 py-3">
                  <span class="text-sm text-muted-foreground">状态</span>
                  <span
                    class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
                    :class="statusClass"
                  >
                    <span class="h-1.5 w-1.5 rounded-full bg-current" />
                    {{ metadata?.status || 'pending' }}
                  </span>
                </div>
                <div class="flex items-center justify-between rounded-lg border border-border/40 bg-muted/20 px-4 py-3">
                  <span class="text-sm text-muted-foreground">置信度</span>
                  <span class="font-mono text-sm font-semibold text-foreground">
                    {{ formatConfidence(metadata?.intent_confidence) }}
                  </span>
                </div>
              </div>
            </section>

            <!-- 数据来源 -->
            <section v-if="metadata?.generated_path || metadata?.source || metadata?.cache_hit">
              <h3 class="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                数据来源
              </h3>
              <div class="space-y-2">
                <div v-if="metadata?.generated_path" class="rounded-lg border border-border/40 bg-muted/20 px-4 py-3">
                  <div class="mb-1.5 text-xs text-muted-foreground">RSS Hub 路径</div>
                  <div class="break-all font-mono text-sm text-foreground">
                    {{ metadata.generated_path }}
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <div v-if="metadata?.source" class="rounded-lg border border-border/40 bg-muted/20 px-4 py-3">
                    <div class="mb-1 text-xs text-muted-foreground">来源</div>
                    <div class="font-mono text-sm font-semibold text-foreground">
                      {{ metadata.source }}
                    </div>
                  </div>
                  <div v-if="metadata?.cache_hit" class="rounded-lg border border-border/40 bg-muted/20 px-4 py-3">
                    <div class="mb-1 text-xs text-muted-foreground">缓存</div>
                    <div class="font-mono text-sm font-semibold text-foreground">
                      {{ metadata.cache_hit }}
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <!-- 响应消息 -->
            <section v-if="message">
              <h3 class="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                响应消息
              </h3>
              <div class="rounded-lg border border-border/40 bg-muted/20 px-4 py-3">
                <p class="text-sm leading-relaxed text-foreground">{{ message }}</p>
              </div>
            </section>

            <!-- 推理过程 -->
            <section v-if="metadata?.reasoning">
              <h3 class="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                推理过程
              </h3>
              <div class="rounded-lg border border-border/40 bg-muted/20 px-4 py-3">
                <p class="text-sm leading-relaxed text-foreground">{{ metadata.reasoning }}</p>
              </div>
            </section>

            <!-- 流式日志 -->
            <section v-if="log && log.length > 0">
              <h3 class="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                接口调用日志
              </h3>
              <div class="space-y-2 max-h-96 overflow-y-auto">
                <div
                  v-for="(item, index) in log"
                  :key="index"
                  class="rounded-lg border p-3"
                  :class="getLogClass(item)"
                >
                  <div class="mb-2 flex items-center justify-between text-xs">
                    <span class="font-mono text-muted-foreground">
                      {{ formatTimestamp(item.timestamp) }}
                    </span>
                    <span class="font-semibold uppercase">
                      {{ getLogType(item) }}
                    </span>
                  </div>
                  <p class="font-mono text-sm leading-relaxed">
                    {{ getLogDetail(item) }}
                  </p>
                </div>
              </div>
            </section>

            <!-- Fetch Snapshot -->
            <section v-if="fetchSnapshot">
              <h3 class="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Fetch 快照
              </h3>
              <div class="grid grid-cols-2 gap-2">
                <div class="rounded-lg border border-border/40 bg-muted/20 px-4 py-3">
                  <div class="mb-1 text-xs text-muted-foreground">条目数</div>
                  <div class="font-mono text-lg font-bold text-foreground">
                    {{ fetchSnapshot.items_count }}
                  </div>
                </div>
                <div class="rounded-lg border border-border/40 bg-muted/20 px-4 py-3">
                  <div class="mb-1 text-xs text-muted-foreground">数据块数</div>
                  <div class="font-mono text-lg font-bold text-foreground">
                    {{ fetchSnapshot.block_count }}
                  </div>
                </div>
              </div>
            </section>

            <!-- 空状态 -->
            <section v-if="!hasAnyData" class="py-12 text-center">
              <svg class="mx-auto h-16 w-16 text-muted-foreground/30 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p class="text-sm text-muted-foreground">暂无调试信息</p>
            </section>
          </div>
        </div>
      </DialogContent>
    </DialogPortalPrimitive>
  </Dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { PanelResponse, PanelStreamFetchPayload, StreamMessage } from "@/shared/types/panel";
import Dialog from "@/components/ui/dialog/Dialog.vue";
import DialogContent from "@/components/ui/dialog/DialogContent.vue";
import { DialogOverlay as DialogOverlayPrimitive, DialogPortal as DialogPortalPrimitive } from "reka-ui";

const props = defineProps<{
  open: boolean;
  metadata?: PanelResponse["metadata"];
  message?: string;
  log?: StreamMessage[];
  fetchSnapshot?: PanelStreamFetchPayload | null;
}>();

const emit = defineEmits<{
  (event: "close"): void;
}>();

const onOpenChange = (value: boolean) => {
  if (!value) emit("close");
};

const statusClass = computed(() => {
  const status = props.metadata?.status?.toLowerCase() || '';
  if (status.includes('success')) return 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20';
  if (status.includes('error')) return 'bg-red-500/10 text-red-500 border border-red-500/20';
  if (status.includes('clarification')) return 'bg-amber-500/10 text-amber-500 border border-amber-500/20';
  return 'bg-muted/50 text-muted-foreground border border-border/40';
});

const hasAnyData = computed(() => {
  return !!(
    props.metadata?.intent_type ||
    props.metadata?.generated_path ||
    props.message ||
    (props.log && props.log.length > 0) ||
    props.fetchSnapshot
  );
});

function formatConfidence(value?: number | null): string {
  if (value === undefined || value === null) return 'N/A';
  return `${(value * 100).toFixed(1)}%`;
}

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString('zh-CN', { hour12: false });
  } catch {
    return ts;
  }
}

function getLogType(msg: StreamMessage): string {
  if (msg.type === 'stage') return `Stage: ${msg.stage}`;
  if (msg.type === 'data') return `Data: ${msg.stage}`;
  if (msg.type === 'error') return 'Error';
  if (msg.type === 'complete') return 'Complete';
  return msg.type;
}

function getLogDetail(msg: StreamMessage): string {
  if (msg.type === 'stage') {
    return msg.message;
  }
  if (msg.type === 'data') {
    if (msg.stage === 'intent') {
      return `${msg.data.intent_type} (${(msg.data.confidence * 100).toFixed(1)}%)`;
    }
    if (msg.stage === 'fetch') {
      return `items=${msg.data.items_count}, blocks=${msg.data.block_count}, cache=${msg.data.cache_hit || '-'}`;
    }
    return JSON.stringify(msg.data);
  }
  if (msg.type === 'error') {
    return `${msg.error_code}: ${msg.error_message}`;
  }
  if (msg.type === 'complete') {
    return msg.message;
  }
  return 'Unknown log type';
}

function getLogClass(msg: StreamMessage): string {
  if (msg.type === 'error') return 'border-red-500/40 bg-red-500/5 text-red-400';
  if (msg.type === 'data') return 'border-blue-500/40 bg-blue-500/5 text-blue-300';
  if (msg.type === 'stage') return 'border-indigo-500/40 bg-indigo-500/5 text-indigo-300';
  if (msg.type === 'complete') return 'border-emerald-500/40 bg-emerald-500/5 text-emerald-300';
  return 'border-border/40 bg-muted/20 text-foreground';
}
</script>
