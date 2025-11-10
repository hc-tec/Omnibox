<template>
  <section class="toolbar">
    <form class="toolbar-main" @submit.prevent="submit">
      <div class="field">
        <label for="query">需求描述</label>
        <input
          id="query"
          v-model="localQuery"
          type="text"
          placeholder="例如：推荐最新的 bilibili 热搜"
          :disabled="loading || streamLoading"
          required
        />
      </div>

      <div class="field slim">
        <label for="datasource">数据源（可选）</label>
        <input
          id="datasource"
          v-model="localDatasource"
          type="text"
          placeholder="如：bilibili"
          :disabled="loading || streamLoading"
        />
      </div>

      <div class="actions">
        <button type="button" class="btn ghost" :disabled="!canReset" @click="$emit('reset')">
          清空组件
        </button>
        <button type="button" class="btn outline" :disabled="streamLoading" @click="stream">
          {{ streamLoading ? "流式处理中…" : "实时模式" }}
        </button>
        <button type="button" class="btn subtle" :disabled="!streamLoading" @click="$emit('stop-stream')">
          停止流式
        </button>
        <button type="submit" class="btn primary" :disabled="loading">
          {{ loading ? "正在生成…" : "生成面板" }}
        </button>
      </div>
    </form>
    <p class="toolbar-hint">
      默认使用 append 模式持续补充组件；如需清空，使用右侧“清空组件”。可选流式模式实时查看处理进度。
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

interface Emits {
  (event: "submit", payload: { query: string; datasource?: string | null }): void;
  (event: "stream", payload: { query: string; datasource?: string | null }): void;
  (event: "stop-stream"): void;
  (event: "reset"): void;
}

const props = defineProps<{
  loading: boolean;
  streamLoading: boolean;
  defaultQuery: string;
  canReset: boolean;
}>();

const emit = defineEmits<Emits>();
const localQuery = ref(props.defaultQuery);
const localDatasource = ref("");

watch(
  () => props.defaultQuery,
  (value) => {
    localQuery.value = value;
  }
);

const payload = computed(() => ({
  query: localQuery.value.trim(),
  datasource: localDatasource.value.trim() || null,
}));

function submit() {
  emit("submit", payload.value);
}

function stream() {
  emit("stream", payload.value);
}
</script>

<style scoped>
.toolbar {
  background: linear-gradient(135deg, #f8fafc 0%, #ffffff 45%, #eff6ff 100%);
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 18px;
  padding: 20px 24px;
  box-shadow: 0 20px 40px rgba(15, 23, 42, 0.08);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar-main {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) minmax(200px, 280px) auto;
  gap: 16px;
  align-items: flex-end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field.slim {
  max-width: 280px;
}

label {
  font-size: 13px;
  font-weight: 500;
  color: #0f172a;
}

input {
  height: 44px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.6);
  padding: 0 14px;
  font-size: 15px;
  transition: border-color 0.2s, box-shadow 0.2s;
  background: rgba(255, 255, 255, 0.92);
}

input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
  outline: none;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.btn {
  height: 44px;
  padding: 0 18px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn.primary {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.35);
}

.btn.primary:disabled {
  background: rgba(148, 163, 184, 0.7);
  box-shadow: none;
  cursor: not-allowed;
}

.btn.outline {
  background: #fff;
  border: 1px solid rgba(37, 99, 235, 0.4);
  color: #1d4ed8;
}

.btn.subtle {
  background: #ffffff;
  border: 1px dashed rgba(148, 163, 184, 0.7);
  color: #64748b;
}

.btn.ghost {
  background: transparent;
  border: 1px solid transparent;
  color: #64748b;
}

.btn:disabled {
  color: rgba(148, 163, 184, 0.9);
  border-color: rgba(148, 163, 184, 0.3);
  cursor: not-allowed;
}

.toolbar-hint {
  margin: 0;
  font-size: 13px;
  color: #475569;
}

@media (max-width: 1024px) {
  .toolbar-main {
    grid-template-columns: 1fr;
  }
  .field.slim {
    max-width: unset;
  }
  .actions {
    justify-content: flex-start;
  }
}
</style>
