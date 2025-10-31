<template>
  <section class="log-card">
    <header>
      <h2>流式进度</h2>
      <span v-if="fetchSnapshot" class="fetch-info">
        数据获取：{{ fetchSnapshot.items_count }} 条 / {{ fetchSnapshot.block_count }} 块
      </span>
    </header>

    <ol>
      <li v-for="item in log" :key="item.timestamp + item.type">
        <span class="timestamp">{{ formatTime(item.timestamp) }}</span>
        <span class="type">{{ renderType(item) }}</span>
        <span class="detail">{{ renderDetail(item) }}</span>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import type { StreamMessage, PanelStreamFetchPayload } from "../../../shared/types/panel";

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
  if (message.type === "stage") return `阶段: ${message.stage}`;
  if (message.type === "data") return `数据: ${message.stage}`;
  if (message.type === "error") return "错误";
  return "完成";
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
      if (message.stage === "summary") {
        return message.data.message;
      }
      return "";
    case "error":
      return `${message.error_code}: ${message.error_message}`;
    case "complete":
      return message.message;
    default:
      return "";
  }
}
</script>

<style scoped>
.log-card {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.8);
  padding: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}

header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}

h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.fetch-info {
  font-size: 12px;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.12);
  padding: 4px 8px;
  border-radius: 999px;
}

ol {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 220px;
  overflow-y: auto;
}

li {
  display: grid;
  grid-template-columns: 80px 90px 1fr;
  gap: 8px;
  font-size: 13px;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(148, 163, 184, 0.08);
}

.timestamp {
  color: #475569;
}

.type {
  font-weight: 600;
  color: #1d4ed8;
}

.detail {
  color: #0f172a;
}
</style>
