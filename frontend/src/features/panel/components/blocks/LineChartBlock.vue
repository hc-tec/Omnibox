<template>
  <div class="chart-card">
    <table>
      <thead>
        <tr>
          <th>{{ xFieldLabel }}</th>
          <th>{{ yFieldLabel }}</th>
          <th v-if="seriesFieldLabel">系列</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="itemKey(item)">
          <td>{{ formatX(item) }}</td>
          <td>{{ formatNumber(item[yField]) }}</td>
          <td v-if="seriesFieldLabel">{{ item[seriesField] ?? "-" }}</td>
        </tr>
      </tbody>
    </table>
    <p class="chart-hint">后续可替换为真正的可视化（如 Ant Design Plots）。</p>
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

const items = (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];
const xField = resolveField("x_field", "timestamp");
const yField = resolveField("y_field", "value");
const seriesField = resolveField("series_field", "series");

const xFieldLabel = props.block.props["xField"] ?? xField;
const yFieldLabel = props.block.props["yField"] ?? yField;
const seriesFieldLabel = props.block.props["seriesField"] ?? (seriesField ? seriesField : null);

function resolveField(propName: string, fallback: string): string {
  const camel = propName.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[propName] ?? fallback) as string;
}

function formatX(item: Record<string, unknown>): string {
  const raw = item[xField];
  if (!raw) return "-";
  const date = new Date(String(raw));
  if (Number.isNaN(date.getTime())) {
    return String(raw);
  }
  return date.toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatNumber(value: unknown): string {
  const num = Number(value);
  if (Number.isNaN(num)) return String(value ?? "-");
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(num);
}

function itemKey(item: Record<string, unknown>): string {
  return String(item["timestamp"] ?? item["id"] ?? Math.random());
}
</script>

<style scoped>
.chart-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  padding: 6px 10px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.6);
  text-align: left;
  font-size: 13px;
}

th {
  background: rgba(226, 232, 240, 0.4);
  font-weight: 600;
  color: #0f172a;
}

.chart-hint {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}
</style>
