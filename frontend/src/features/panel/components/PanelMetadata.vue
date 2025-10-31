<template>
  <section class="metadata-card">
    <h2>响应信息</h2>
    <dl v-if="metadata">
      <div v-if="metadata.intent_type">
        <dt>意图类型</dt>
        <dd>{{ metadata.intent_type }}</dd>
      </div>
      <div v-if="metadata.intent_confidence !== undefined">
        <dt>意图置信度</dt>
        <dd>{{ formatPercent(metadata.intent_confidence) }}</dd>
      </div>
      <div v-if="metadata.generated_path">
        <dt>生成路径</dt>
        <dd>{{ metadata.generated_path }}</dd>
      </div>
      <div v-if="metadata.source">
        <dt>数据来源</dt>
        <dd>{{ metadata.source }}</dd>
      </div>
      <div v-if="metadata.cache_hit">
        <dt>缓存命中</dt>
        <dd>{{ metadata.cache_hit }}</dd>
      </div>
    </dl>
    <p class="message">{{ message }}</p>
  </section>
</template>

<script setup lang="ts">
import type { PanelResponse } from "../../../shared/types/panel";

defineProps<{
  metadata: PanelResponse["metadata"];
  message: string;
}>();

function formatPercent(value: number | undefined | null): string {
  if (value === undefined || value === null) return "-";
  return `${(value * 100).toFixed(1)}%`;
}
</script>

<style scoped>
.metadata-card {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.8);
  padding: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}

h2 {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

dl {
  margin: 0;
  display: grid;
  gap: 8px;
}

dt {
  font-size: 12px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

dd {
  margin: 0;
  font-size: 14px;
  color: #1e293b;
}

.message {
  margin: 16px 0 0;
  font-size: 13px;
  color: #475569;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(37, 99, 235, 0.08);
}
</style>
