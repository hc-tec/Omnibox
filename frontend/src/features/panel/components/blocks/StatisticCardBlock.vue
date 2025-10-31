<template>
  <div class="stat-card">
    <div class="stat-value">{{ formatNumber(value) }}</div>
    <div class="stat-title">{{ title }}</div>
    <div v-if="trend !== null" class="stat-trend" :class="{ positive: trend >= 0 }">
      <span v-if="trend >= 0">▲</span>
      <span v-else>▼</span>
      {{ Math.abs(trend).toFixed(2) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ComponentAbility } from "../../../../shared/componentManifest";
import type { UIBlock, DataBlock } from "../../../../shared/types/panel";

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const data = props.data ?? props.dataBlock?.records?.[0] ?? {};

function resolveField(propName: string, fallback: string): string {
  const camel = propName.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[propName] ?? fallback) as string;
}

const titleField = resolveField("title_field", "title");
const valueField = resolveField("value_field", "value");
const trendField = resolveField("trend_field", "trend");

const title = String((data as Record<string, unknown>)[titleField] ?? props.block.title ?? "指标");
const value = (data as Record<string, unknown>)[valueField] ?? 0;
const trendRaw = (data as Record<string, unknown>)[trendField];
const trend = trendRaw === undefined ? null : Number(trendRaw);

function formatNumber(input: unknown): string {
  const num = Number(input);
  if (Number.isNaN(num)) return String(input ?? "-");
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(num);
}
</script>

<style scoped>
.stat-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 6px;
  height: 100%;
  padding: 18px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.12), rgba(59, 130, 246, 0.08));
  color: #0f172a;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
}

.stat-title {
  font-size: 14px;
  color: #475569;
}

.stat-trend {
  margin-top: auto;
  font-size: 14px;
  color: #b91c1c;
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-trend.positive {
  color: #15803d;
}
</style>
