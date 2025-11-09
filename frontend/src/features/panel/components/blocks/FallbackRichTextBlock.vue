<template>
  <Card>
    <CardHeader v-if="block.title || recordTitle">
      <CardTitle>{{ block.title || recordTitle }}</CardTitle>
      <CardDescription v-if="dataBlock?.stats?.description">
        {{ dataBlock.stats.description }}
      </CardDescription>
    </CardHeader>

    <CardContent>
      <div v-if="isEmpty" class="flex h-[200px] items-center justify-center text-muted-foreground">
        暂无数据
      </div>

      <div v-else>
        <!-- 调试警告 -->
        <div class="fallback-alert">
          <div class="fallback-alert__icon">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 16 16"
              fill="currentColor"
              class="h-4 w-4"
            >
              <path
                fill-rule="evenodd"
                d="M6.701 2.25c.577-1 2.02-1 2.598 0l5.196 9a1.5 1.5 0 0 1-1.299 2.25H2.804a1.5 1.5 0 0 1-1.3-2.25l5.197-9ZM8 4a.75.75 0 0 1 .75.75v3a.75.75 0 1 1-1.5 0v-3A.75.75 0 0 1 8 4Zm0 8a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
                clip-rule="evenodd"
              />
            </svg>
          </div>
          <div>
            <p class="fallback-alert__title">兜底渲染</p>
            <p class="fallback-alert__description">
              当前数据无法结构化展示，正在使用兜底渲染模式。如需更好的展示效果，请为此数据源创建专用适配器。
            </p>
          </div>
        </div>

        <!-- 渲染内容 -->
        <div
          class="prose prose-slate dark:prose-invert max-w-none"
          v-html="renderedContent"
        ></div>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { marked } from 'marked';
import type { ComponentAbility } from '@/shared/componentManifest';
import type { UIBlock, DataBlock } from '@/shared/types/panel';

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const record = (props.data ?? props.dataBlock?.records?.[0]) as Record<string, unknown> | null | undefined;

const isEmpty = computed(() => {
  return !record;
});

function getProp(key: string): string | undefined {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[key]) as string | undefined;
}

const recordTitle = computed(() => {
  if (!record) return null;
  const titleField = getProp('title_field') ?? 'title';
  const titleValue = (record as Record<string, unknown>)[titleField];
  return titleValue ? String(titleValue) : null;
});

const content = computed(() => {
  if (!record) return '';
  const descField = getProp('description_field') ?? 'content';
  return String((record as Record<string, unknown>)[descField] || '');
});

const renderedContent = computed(() => {
  const rawContent = content.value;

  // 如果内容包含 HTML 标签，进行清理后直接使用
  if (/<[^>]+>/.test(rawContent)) {
    return sanitizeHtml(rawContent);
  }

  // 否则作为 Markdown 渲染
  return renderMarkdown(rawContent);
});

function renderMarkdown(markdown: string): string {
  try {
    return marked.parse(markdown) as string;
  } catch (error) {
    console.error('Failed to parse markdown:', error);
    return `<pre>${escapeHtml(markdown)}</pre>`;
  }
}

function sanitizeHtml(html: string): string {
  // 简单的清理：移除 script 标签和事件处理器
  let cleaned = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
  // 移除事件处理器属性
  cleaned = cleaned.replace(/\son\w+\s*=\s*["'][^"']*["']/gi, '');
  return cleaned;
}

function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return text.replace(/[&<>"']/g, (char) => map[char]);
}
</script>

<style scoped>
/* Prose 样式调整 */
.prose {
  font-size: 0.875rem;
}

.fallback-alert {
  display: flex;
  gap: 12px;
  border-radius: 8px;
  border: 1px solid rgba(250, 204, 21, 0.4);
  background-color: rgba(250, 204, 21, 0.12);
  padding: 12px;
  margin-bottom: 16px;
  color: #713f12;
  font-size: 14px;
}

.fallback-alert__icon {
  margin-top: 2px;
  color: #c2410c;
}

.fallback-alert__title {
  font-weight: 600;
  margin: 0 0 4px 0;
}

.fallback-alert__description {
  margin: 0;
  font-size: 12px;
  color: #7c2d12;
}

.prose :deep(pre) {
  background-color: hsl(var(--muted));
  border-radius: 0.375rem;
  padding: 1rem;
  overflow-x: auto;
}

.prose :deep(code) {
  background-color: hsl(var(--muted));
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  font-size: 0.875em;
}

.prose :deep(pre code) {
  background-color: transparent;
  padding: 0;
}

.prose :deep(a) {
  color: hsl(var(--primary));
  text-decoration: underline;
}

.prose :deep(a:hover) {
  color: hsl(var(--primary) / 0.8);
}
</style>
