<template>
  <header class="toolbar">
    <form class="toolbar-form" @submit.prevent="submit">
      <div class="form-field">
        <label for="query">查询内容</label>
        <input
          id="query"
          v-model="localQuery"
          type="text"
          placeholder="例如：虎扑步行街最新帖子"
          :disabled="loading || streamLoading"
          required
        />
      </div>

      <div class="form-field">
        <label for="datasource">数据源（可选）</label>
        <input
          id="datasource"
          v-model="localDatasource"
          type="text"
          placeholder="例如：hupu"
          :disabled="loading || streamLoading"
        />
      </div>

      <div class="action-group">
        <button type="submit" class="primary" :disabled="loading">
          {{ loading ? "请求中..." : "发送 REST 请求" }}
        </button>
        <button type="button" class="secondary" :disabled="streamLoading" @click="stream">
          {{ streamLoading ? "流式处理中..." : "开始 WebSocket" }}
        </button>
        <button type="button" class="ghost" :disabled="!streamLoading" @click="$emit('stop-stream')">
          停止流式
        </button>
      </div>
    </form>
  </header>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

interface Emits {
  (event: "submit", payload: { query: string; datasource?: string | null }): void;
  (event: "stream", payload: { query: string; datasource?: string | null }): void;
  (event: "stop-stream"): void;
}

const props = defineProps<{
  loading: boolean;
  streamLoading: boolean;
  defaultQuery: string;
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
  background: #f8fafc;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 14px;
  padding: 20px;
}

.toolbar-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px 20px;
  align-items: end;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

label {
  font-size: 13px;
  font-weight: 500;
  color: #0f172a;
}

input {
  height: 38px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.6);
  padding: 0 12px;
  font-size: 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
  outline: none;
}

.action-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

button {
  height: 38px;
  padding: 0 18px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.primary {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #ffffff;
}

.primary:disabled {
  background: rgba(148, 163, 184, 0.6);
  cursor: not-allowed;
}

.secondary {
  background: #ffffff;
  border: 1px solid rgba(37, 99, 235, 0.35);
  color: #1d4ed8;
}

.secondary:disabled {
  border-color: rgba(148, 163, 184, 0.4);
  color: rgba(100, 116, 139, 0.8);
  cursor: not-allowed;
}

.ghost {
  background: transparent;
  border: 1px solid transparent;
  color: #64748b;
}

.ghost:disabled {
  color: rgba(148, 163, 184, 0.8);
  cursor: not-allowed;
}
</style>
