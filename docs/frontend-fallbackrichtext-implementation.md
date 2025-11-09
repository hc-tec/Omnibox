# FallbackRichText 组件前端实现指南

> 创建时间：2025-11-09
> 更新时间：2025-11-09
> 状态：✅ 后端契约已完成，等待前端实现
> **技术栈**: Vue 3 + shadcn-vue

---

## 1. 组件概述

**FallbackRichText** 是兜底渲染组件，用于展示无法结构化处理的原始数据或调试信息。

### 核心特性
- ✅ 使用 shadcn-vue Card 作为容器
- ✅ 支持 Markdown 渲染
- ✅ 支持 HTML 渲染
- ✅ 支持代码块高亮
- ✅ 用于调试和兜底展示
- ✅ Vue 3 Composition API
- ✅ TypeScript 完整支持

---

## 2. 数据契约

### TypeScript 接口（已完成）

```typescript
// frontend/src/shared/types/panelContracts.ts
export interface FallbackRichTextRecord {
  id: string;
  title?: string | null;
  content: string;  // Markdown 或 HTML 内容
  [key: string]: unknown;
}
```

---

## 3. 安装依赖

### 3.1 安装 shadcn-vue（首次）

```bash
cd frontend
npx shadcn-vue@latest init
```

### 3.2 添加所需组件

```bash
npx shadcn-vue@latest add card
npx shadcn-vue@latest add alert
```

### 3.3 安装 Markdown 渲染库

```bash
npm install marked
npm install -D @types/marked
```

---

## 4. Props 定义

```typescript
interface FallbackRichTextProps {
  data: {
    items: FallbackRichTextRecord[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {
    titleField: string;
    descriptionField?: string;
  };
  options?: {
    span?: number;
  };
  id: string;
  title?: string;
}
```

---

## 5. 核心实现

### 5.1 文件结构

```
frontend/src/features/panel/components/
└── FallbackRichText/
    ├── FallbackRichText.vue       # 主组件
    ├── utils.ts                   # Markdown 渲染工具
    └── __tests__/
        └── FallbackRichText.spec.ts
```

### 5.2 主组件

```vue
<!-- frontend/src/features/panel/components/FallbackRichText/FallbackRichText.vue -->
<script setup lang="ts">
import { computed } from 'vue';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert';
import type { FallbackRichTextRecord } from '@/shared/types/panelContracts';
import { renderMarkdown, sanitizeHtml } from './utils';

interface Props {
  data: {
    items: FallbackRichTextRecord[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {
    titleField: string;
    descriptionField?: string;
  };
  options?: {
    span?: number;
  };
  title?: string;
  id: string;
}

const props = withDefaults(defineProps<Props>(), {
  options: () => ({
    span: 12,
  }),
});

const record = computed(() => {
  return props.data.items?.[0] || null;
});

const isEmpty = computed(() => {
  return !record.value;
});

const recordTitle = computed(() => {
  if (!record.value) return null;
  const titleValue = (record.value as any)[props.props.titleField] || record.value.title;
  return titleValue || null;
});

const content = computed(() => {
  if (!record.value) return '';
  const descField = props.props.descriptionField || 'content';
  return (record.value as any)[descField] || record.value.content || '';
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
</script>

<template>
  <Card>
    <CardHeader v-if="title || recordTitle">
      <CardTitle>{{ title || recordTitle }}</CardTitle>
      <CardDescription v-if="data.stats?.description">
        {{ data.stats.description }}
      </CardDescription>
    </CardHeader>

    <CardContent>
      <div v-if="isEmpty" class="flex h-[200px] items-center justify-center text-muted-foreground">
        暂无数据
      </div>

      <div v-else>
        <!-- 调试警告 -->
        <Alert variant="default" class="mb-4">
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
          <AlertTitle>兜底渲染</AlertTitle>
          <AlertDescription>
            当前数据无法结构化展示，正在使用兜底渲染模式。如需更好的展示效果，请为此数据源创建专用适配器。
          </AlertDescription>
        </Alert>

        <!-- 渲染内容 -->
        <div
          class="prose prose-slate dark:prose-invert max-w-none"
          v-html="renderedContent"
        ></div>
      </div>
    </CardContent>
  </Card>
</template>

<style scoped>
/* Prose 样式调整 */
.prose {
  font-size: 0.875rem;
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
```

---

### 5.3 工具函数

```typescript
// frontend/src/features/panel/components/FallbackRichText/utils.ts
import { marked } from 'marked';

/**
 * 渲染 Markdown 为 HTML
 */
export function renderMarkdown(markdown: string): string {
  try {
    return marked.parse(markdown) as string;
  } catch (error) {
    console.error('Failed to parse markdown:', error);
    return `<pre>${escapeHtml(markdown)}</pre>`;
  }
}

/**
 * 清理 HTML，防止 XSS 攻击
 */
export function sanitizeHtml(html: string): string {
  // 简单的清理：移除 script 标签和事件处理器
  let cleaned = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');

  // 移除事件处理器属性
  cleaned = cleaned.replace(/\son\w+\s*=\s*["'][^"']*["']/gi, '');

  return cleaned;
}

/**
 * HTML 转义
 */
export function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return text.replace(/[&<>"']/g, (char) => map[char]);
}
```

---

## 6. Tailwind Typography 配置

在项目中添加 Tailwind Typography 插件以支持 prose 样式：

```bash
npm install -D @tailwindcss/typography
```

更新 `tailwind.config.js`:

```javascript
// tailwind.config.js
module.exports = {
  // ...其他配置
  plugins: [
    require('@tailwindcss/typography'),
    // ...其他插件
  ],
}
```

---

## 7. 集成到面板系统

```typescript
// frontend/src/features/panel/components/index.ts
import FallbackRichText from './FallbackRichText/FallbackRichText.vue';

export const PanelComponents = {
  ListPanel: () => import('./ListPanel/ListPanel.vue'),
  StatisticCard: () => import('./StatisticCard/StatisticCard.vue'),
  LineChart: () => import('./LineChart/LineChart.vue'),
  BarChart: () => import('./BarChart/BarChart.vue'),
  PieChart: () => import('./PieChart/PieChart.vue'),
  Table: () => import('./Table/Table.vue'),
  FallbackRichText,  // 更新
};
```

---

## 8. 测试用例

```typescript
// frontend/src/features/panel/components/FallbackRichText/__tests__/FallbackRichText.spec.ts
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import FallbackRichText from '../FallbackRichText.vue';
import type { FallbackRichTextRecord } from '@/shared/types/panelContracts';

describe('FallbackRichText', () => {
  const markdownData: FallbackRichTextRecord = {
    id: 'fallback-1',
    title: '原始数据',
    content: `# 标题\n\n这是一段 **Markdown** 文本。\n\n\`\`\`json\n{"key": "value"}\n\`\`\``,
  };

  const htmlData: FallbackRichTextRecord = {
    id: 'fallback-2',
    content: '<p>这是一段 <strong>HTML</strong> 内容</p>',
  };

  it('renders markdown content', () => {
    const wrapper = mount(FallbackRichText, {
      props: {
        id: 'test-fallback',
        data: { items: [markdownData], schema: {}, stats: {} },
        props: {
          titleField: 'title',
          descriptionField: 'content',
        },
      },
    });

    expect(wrapper.text()).toContain('原始数据');
    expect(wrapper.html()).toContain('<h1');
  });

  it('renders HTML content', () => {
    const wrapper = mount(FallbackRichText, {
      props: {
        id: 'test-fallback',
        data: { items: [htmlData], schema: {}, stats: {} },
        props: {
          titleField: 'title',
        },
      },
    });

    expect(wrapper.html()).toContain('<strong>HTML</strong>');
  });

  it('shows empty state when no data', () => {
    const wrapper = mount(FallbackRichText, {
      props: {
        id: 'test-fallback',
        data: { items: [], schema: {}, stats: {} },
        props: {
          titleField: 'title',
        },
      },
    });

    expect(wrapper.text()).toContain('暂无数据');
  });

  it('shows fallback warning alert', () => {
    const wrapper = mount(FallbackRichText, {
      props: {
        id: 'test-fallback',
        data: { items: [markdownData], schema: {}, stats: {} },
        props: {
          titleField: 'title',
        },
      },
    });

    expect(wrapper.text()).toContain('兜底渲染');
    expect(wrapper.text()).toContain('无法结构化展示');
  });
});
```

---

## 9. 后端适配器示例

```python
from services.panel.adapters import route_adapter, SourceInfo, RouteAdapterResult, AdapterBlockPlan
from services.panel.view_models import validate_records
import json

@route_adapter("/unknown/data-source", manifest=UNKNOWN_MANIFEST)
def unknown_data_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    """无法结构化处理的数据源"""
    # 将原始数据转为 JSON 字符串，用于调试
    raw_json = json.dumps(records[:5], indent=2, ensure_ascii=False)  # 只展示前 5 条

    fallback_record = {
        "id": "fallback-debug",
        "title": "原始数据（调试用）",
        "content": f"```json\n{raw_json}\n```\n\n> 数据源: {source_info.route}\n> 记录数: {len(records)}",
    }

    validated = validate_records("FallbackRichText", [fallback_record])

    return RouteAdapterResult(
        records=validated,
        block_plans=[
            AdapterBlockPlan(
                component_id="FallbackRichText",
                props={
                    "title_field": "title",
                    "description_field": "content",
                },
                options={"span": 12},
                confidence=0.5,  # 低置信度，表示兜底渲染
            )
        ],
        stats={
            "reason": "unsupported payload structure",
            "total_records": len(records),
        },
    )
```

---

## 10. 开发清单

### 后端部分 ✅ 已完成
- [x] 契约文档定义
- [x] Pydantic 模型定义
- [x] 契约验证函数
- [x] TypeScript 类型定义

### 前端部分 ⏳ 待实现
- [ ] 安装 shadcn-vue（如果尚未安装）
- [ ] 添加 Card、Alert 组件
- [ ] 安装 marked 和 @tailwindcss/typography
- [ ] 实现 FallbackRichText.vue 组件
- [ ] 实现工具函数
- [ ] 配置 Tailwind Typography
- [ ] 单元测试
- [ ] 集成到面板系统

---

## 11. 设计说明

### 使用场景
1. **调试模式**：展示原始 API 返回数据
2. **兜底渲染**：无适配器时的默认展示
3. **错误提示**：展示错误信息和堆栈
4. **Markdown 文档**：展示 README、文档等

### 安全考虑
- 对用户输入的 HTML 进行清理，防止 XSS 攻击
- 移除所有 `<script>` 标签
- 移除所有事件处理器（`onclick`、`onerror` 等）

### 样式规范
- 使用 Tailwind Typography 的 `prose` 类
- 代码块使用 muted 背景色
- 链接使用 primary 主题色
- 支持深色模式

---

## 12. 使用场景示例

### 场景 1: 调试原始数据
```json
{
  "id": "debug-1",
  "title": "API 原始响应",
  "content": "```json\n{\"status\": \"success\", \"data\": [...]}\n```"
}
```

### 场景 2: Markdown 文档
```json
{
  "id": "readme",
  "title": "项目说明",
  "content": "# 项目介绍\n\n这是一个示例项目...\n\n## 特性\n- 特性1\n- 特性2"
}
```

### 场景 3: 错误提示
```json
{
  "id": "error",
  "title": "数据处理错误",
  "content": "**错误**: 无法解析数据源\n\n请检查数据源配置是否正确。"
}
```

---

## 附录：参考资源

- **shadcn-vue Card**: https://www.shadcn-vue.com/docs/components/card.html
- **shadcn-vue Alert**: https://www.shadcn-vue.com/docs/components/alert.html
- **marked 文档**: https://marked.js.org/
- **Tailwind Typography**: https://tailwindcss.com/docs/typography-plugin
- **XSS 防护指南**: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
