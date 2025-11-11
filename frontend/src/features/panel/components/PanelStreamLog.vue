<template>
  <Card>
    <CardHeader>
      <p class="text-[11px] uppercase tracking-[0.4em] text-muted-foreground">流式进度</p>
      <div class="flex items-center justify-between text-sm text-muted-foreground">
        <span>AI Channel</span>
        <span v-if="fetchSnapshot" class="rounded-full bg-muted px-2 py-0.5 text-xs">
          items {{ fetchSnapshot.items_count }} / blocks {{ fetchSnapshot.block_count }}
        </span>
      </div>
    </CardHeader>
    <CardContent class="space-y-3">
      <div class="flex max-h-72 flex-col gap-2 overflow-y-auto rounded-xl border border-border/50 bg-muted/30 p-3 font-mono text-xs">
        <template v-if="log.length">
          <article
            v-for="item in log"
            :key="item.timestamp + item.type"
            class="rounded-lg border border-border/40 bg-background/80 p-3"
            :class="logVariant(item.type)"
          >
            <div class="mb-1 flex items-center justify-between text-[11px] uppercase tracking-wide">
              <span>{{ formatTime(item.timestamp) }}</span>
              <span>{{ renderType(item) }}</span>
            </div>
            <p class="text-sm text-foreground">{{ renderDetail(item) }}</p>
          </article>
        </template>
        <p v-else class="text-center text-sm text-muted-foreground">等待流式输出...</p>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import type { PanelStreamFetchPayload, StreamMessage } from "@/shared/types/panel";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

defineProps<{
  log: StreamMessage[];
  fetchSnapshot: PanelStreamFetchPayload | null;
}>();

function formatTime(input: string): string {
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return input;
  return date.toLocaleTimeString("zh-CN", { hour12: false });
}

function renderType(message: StreamMessage): string {
  if (message.type === "stage") return `Stage · ${message.stage}`;
  if (message.type === "data") return `Data · ${message.stage}`;
  if (message.type === "error") return "Error";
  return "Complete";
}

function renderDetail(message: StreamMessage): string {
  switch (message.type) {
    case "stage":
      return message.message;
    case "data":
      if (message.stage === "intent") {
        return `${message.data.intent_type} (${(message.data.confidence * 100).toFixed(1)}%)`;
      }
      if (message.stage === "fetch") {
        const payload = message.data;
        return `items=${payload.items_count}, blocks=${payload.block_count}, cache=${payload.cache_hit ?? "-"}`;
      }
      return typeof message.data?.message === "string" ? message.data.message : "";
    case "error":
      return `${message.error_code}: ${message.error_message}`;
    case "complete":
      return message.message;
    default:
      return "";
  }
}

function logVariant(type: StreamMessage["type"]) {
  if (type === "error") return "border-red-400/40 bg-red-500/10 text-red-200";
  if (type === "data") return "border-sky-400/40 bg-sky-500/10 text-sky-200";
  if (type === "stage") return "border-indigo-400/40 bg-indigo-500/10 text-indigo-200";
  if (type === "complete") return "border-emerald-400/40 bg-emerald-500/10 text-emerald-200";
  return "";
}
</script>
