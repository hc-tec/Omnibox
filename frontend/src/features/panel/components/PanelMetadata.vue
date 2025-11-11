<template>
  <Card>
    <CardHeader>
      <p class="text-[11px] uppercase tracking-[0.4em] text-muted-foreground">响应信息</p>
      <div class="flex items-center justify-between">
        <CardTitle class="text-xl">{{ metadata?.intent_type ?? "等待识别" }}</CardTitle>
        <span class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold uppercase"
          :class="statusVariant">
          <span class="h-2 w-2 rounded-full bg-current"></span>
          {{ metadata?.status ?? "pending" }}
        </span>
      </div>
    </CardHeader>
    <CardContent class="space-y-4">
      <div class="grid gap-3 md:grid-cols-3">
        <MetadataStat label="意图置信度" :value="formatPercent(metadata?.intent_confidence)" />
        <MetadataStat label="缓存命中" :value="metadata?.cache_hit ?? 'none'" />
        <MetadataStat label="数据来源" :value="metadata?.source ?? 'unknown'" />
      </div>
      <dl class="space-y-3 text-sm text-muted-foreground">
        <div v-if="metadata?.generated_path" class="space-y-1">
          <dt class="text-xs uppercase tracking-wider">生成路径</dt>
          <dd class="text-foreground">{{ metadata.generated_path }}</dd>
        </div>
        <div v-if="metadata?.reasoning" class="space-y-1">
          <dt class="text-xs uppercase tracking-wider">推理过程</dt>
          <dd class="text-foreground">{{ metadata.reasoning }}</dd>
        </div>
      </dl>
      <p class="rounded-2xl border border-border/70 bg-muted/40 px-4 py-3 text-sm text-foreground">
        {{ message }}
      </p>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { PanelResponse } from "@/shared/types/panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import MetadataStat from "./internal/MetadataStat.vue";

const props = defineProps<{
  metadata: PanelResponse["metadata"];
  message: string;
}>();

const statusVariant = computed(() => {
  const status = (props.metadata?.status ?? "").toLowerCase();
  if (status.includes("success")) return "border-emerald-500/50 text-emerald-400";
  if (status.includes("error")) return "border-red-500/50 text-red-400";
  if (status.includes("clarification")) return "border-amber-500/50 text-amber-400";
  return "border-border text-muted-foreground";
});

function formatPercent(value?: number | null) {
  if (value === undefined || value === null) return "--";
  return `${(value * 100).toFixed(1)}%`;
}
</script>
