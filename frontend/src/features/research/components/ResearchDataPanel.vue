<template>
  <div class="research-data-panel h-full overflow-auto p-6">
    <!-- 空状态 -->
    <div
      v-if="store.state.panels.length === 0 && store.state.analyses.length === 0"
      class="flex h-full items-center justify-center"
    >
      <div class="text-center">
        <Loader2 v-if="store.isActive" class="mx-auto h-12 w-12 animate-spin text-muted-foreground" />
        <Database v-else class="mx-auto h-12 w-12 text-muted-foreground/50" />
        <p class="mt-4 text-sm text-muted-foreground">
          {{ store.isActive ? "正在获取研究数据..." : "暂无数据" }}
        </p>
      </div>
    </div>

    <!-- 数据内容 -->
    <div v-else class="space-y-8">
      <!-- 数据面板和分析结果交错显示 -->
      <div
        v-for="(item, index) in mergedItems"
        :key="item.id"
        class="research-item"
      >
        <!-- 数据面板 -->
        <div v-if="item.type === 'panel'" class="panel-section">
          <div class="mb-3 flex items-center gap-2">
            <div class="h-px flex-1 bg-border/20" />
            <div class="flex items-center gap-2 text-xs text-muted-foreground">
              <Database class="h-3 w-3" />
              <span>数据面板 #{{ item.panel.step_id }}</span>
              <span>·</span>
              <span>{{ item.panel.source_query }}</span>
            </div>
            <div class="h-px flex-1 bg-border/20" />
          </div>

          <!-- 渲染面板内容 -->
          <div class="panel-content space-y-4">
            <div
              v-for="block in item.panel.panel_payload.blocks"
              :key="block.id"
              class="block-wrapper"
            >
              <DynamicBlockRenderer
                :block="block"
                :data-blocks="item.panel.data_blocks"
              />
            </div>
          </div>
        </div>

        <!-- 分析结果 -->
        <div v-else-if="item.type === 'analysis'" class="analysis-section">
          <div class="mb-3 flex items-center gap-2">
            <div class="h-px flex-1 bg-border/20" />
            <div class="flex items-center gap-2 text-xs text-muted-foreground">
              <Lightbulb class="h-3 w-3" />
              <span>分析结果 #{{ item.analysis.step_id }}</span>
            </div>
            <div class="h-px flex-1 bg-border/20" />
          </div>

          <!-- 渲染分析内容 -->
          <div class="analysis-content rounded-xl border border-border/40 bg-background/50 p-6">
            <div class="prose prose-sm max-w-none dark:prose-invert">
              <div v-html="renderMarkdown(item.analysis.analysis_text)" />
            </div>

            <div class="mt-4 text-xs text-muted-foreground">
              {{ formatTimestamp(item.analysis.timestamp) }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useResearchViewStore } from "@/store/researchViewStore";
import type { ResearchPanel, ResearchAnalysis } from "@/store/researchViewStore";
import DynamicBlockRenderer from "@/features/panel/components/blocks/DynamicBlockRenderer.vue";
import { Database, Loader2, Lightbulb } from "lucide-vue-next";
import { marked } from "marked";

// ========== Store ==========
const store = useResearchViewStore();

// ========== 类型定义 ==========
interface MergedItem {
  id: string;
  type: "panel" | "analysis";
  timestamp: string;
  panel?: ResearchPanel;
  analysis?: ResearchAnalysis;
}

// ========== 计算属性 ==========

/**
 * 合并数据面板和分析结果，按时间戳排序
 */
const mergedItems = computed<MergedItem[]>(() => {
  const items: MergedItem[] = [];

  // 添加数据面板
  store.state.panels.forEach((panel) => {
    items.push({
      id: `panel-${panel.step_id}`,
      type: "panel",
      timestamp: panel.timestamp,
      panel,
    });
  });

  // 添加分析结果
  store.state.analyses.forEach((analysis) => {
    items.push({
      id: `analysis-${analysis.step_id}`,
      type: "analysis",
      timestamp: analysis.timestamp,
      analysis,
    });
  });

  // 按时间戳排序（早到晚）
  items.sort((a, b) => {
    return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
  });

  return items;
});

// ========== 方法 ==========

/**
 * 渲染 Markdown
 */
function renderMarkdown(text: string): string {
  try {
    return marked.parse(text) as string;
  } catch (err) {
    console.error("[ResearchDataPanel] Markdown parsing failed:", err);
    return text;
  }
}

/**
 * 格式化时间戳
 */
function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return timestamp;
  }
}
</script>

<style scoped>
.research-data-panel {
  /* 自定义滚动条样式 */
  scrollbar-width: thin;
  scrollbar-color: rgba(100, 100, 100, 0.3) rgba(0, 0, 0, 0.1);
}

.research-data-panel::-webkit-scrollbar {
  width: 8px;
}

.research-data-panel::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
}

.research-data-panel::-webkit-scrollbar-thumb {
  background: rgba(100, 100, 100, 0.3);
  border-radius: 4px;
}

.research-data-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 100, 100, 0.5);
}

.research-item {
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Prose 样式（Markdown 渲染） */
.prose {
  color: var(--foreground);
}

.prose h1,
.prose h2,
.prose h3,
.prose h4 {
  color: var(--foreground);
  font-weight: 600;
  margin-top: 1.5em;
  margin-bottom: 0.75em;
}

.prose h1 {
  font-size: 1.5em;
}

.prose h2 {
  font-size: 1.25em;
}

.prose h3 {
  font-size: 1.1em;
}

.prose p {
  margin-top: 0.75em;
  margin-bottom: 0.75em;
  line-height: 1.75;
}

.prose ul,
.prose ol {
  margin-top: 0.75em;
  margin-bottom: 0.75em;
  padding-left: 1.5em;
}

.prose li {
  margin-top: 0.25em;
  margin-bottom: 0.25em;
}

.prose code {
  background: rgba(100, 100, 100, 0.1);
  padding: 0.2em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
}

.prose pre {
  background: rgba(0, 0, 0, 0.05);
  padding: 1em;
  border-radius: 8px;
  overflow-x: auto;
  margin-top: 1em;
  margin-bottom: 1em;
}

.prose pre code {
  background: transparent;
  padding: 0;
}

.prose strong {
  font-weight: 600;
  color: var(--foreground);
}

.prose a {
  color: #3b82f6;
  text-decoration: underline;
}

.prose a:hover {
  color: #2563eb;
}

.prose blockquote {
  border-left: 4px solid rgba(100, 100, 100, 0.2);
  padding-left: 1em;
  margin-left: 0;
  color: var(--muted-foreground);
  font-style: italic;
}
</style>
