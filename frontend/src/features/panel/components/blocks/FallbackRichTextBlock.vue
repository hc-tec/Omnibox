<template>
  <div class="fallback-card">
    <h4>{{ title }}</h4>
    <p v-if="description">{{ description }}</p>
    <p v-else class="empty">暂无描述信息</p>
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
const descriptionField = resolveField("description_field", "description");

const title = String((data as Record<string, unknown>)[titleField] ?? props.block.title ?? "未命名内容");
const description = (data as Record<string, unknown>)[descriptionField]
  ? String((data as Record<string, unknown>)[descriptionField])
  : null;
</script>

<style scoped>
.fallback-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.8);
  border: 1px dashed rgba(148, 163, 184, 0.6);
}

h4 {
  margin: 0;
  font-size: 16px;
  color: #0f172a;
}

p {
  margin: 0;
  line-height: 1.6;
  color: #475569;
  font-size: 14px;
}

.empty {
  color: #94a3b8;
}
</style>
