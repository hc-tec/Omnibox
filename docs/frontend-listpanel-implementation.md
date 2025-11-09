# ListPanel 组件前端实现指南

> 创建时间：2025-11-09
> 更新时间：2025-11-09
> 状态：✅ 后端契约已完成，等待前端实现
> **技术栈**: Vue 3 + shadcn-vue

---

## 1. 组件概述

**ListPanel** 是用于展示列表类信息的核心组件，适用于文章、帖子、视频、动态等内容的列表展示。

### 核心特性
- ✅ 使用 shadcn-vue Card 作为容器
- ✅ 支持标题、摘要、时间、作者、标签展示
- ✅ 支持链接跳转
- ✅ 支持空状态展示
- ✅ Vue 3 Composition API
- ✅ TypeScript 完整支持
- ✅ 响应式设计

---

## 2. 数据契约

### TypeScript 接口（已完成）

```typescript
// frontend/src/shared/types/panelContracts.ts
export interface ListPanelRecord {
  id: string;
  title: string;
  link?: string | null;
  summary?: string | null;
  published_at?: string | null;
  author?: string | null;
  categories?: string[] | null;
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

按提示配置：
- TypeScript: Yes
- Framework: Vite
- Style: Default
- Base color: Slate (或其他)
- CSS variables: Yes

### 3.2 添加所需组件

```bash
npx shadcn-vue@latest add card
npx shadcn-vue@latest add badge
npx shadcn-vue@latest add separator
```

---

## 4. Props 定义

```typescript
interface ListPanelProps {
  data: {
    items: ListPanelRecord[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {
    titleField: string;
    linkField: string;
    descriptionField?: string;
    pubDateField?: string;
  };
  options?: {
    showDescription?: boolean;
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
└── ListPanel/
    ├── ListPanel.vue       # 主组件
    ├── ListItem.vue        # 单个列表项组件
    ├── utils.ts            # 工具函数
    └── __tests__/
        └── ListPanel.spec.ts
```

### 5.2 主组件

```vue
<!-- frontend/src/features/panel/components/ListPanel/ListPanel.vue -->
<script setup lang="ts">
import { computed } from 'vue';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { ListPanelRecord } from '@/shared/types/panelContracts';
import ListItem from './ListItem.vue';

interface Props {
  data: {
    items: ListPanelRecord[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {
    titleField: string;
    linkField: string;
    descriptionField?: string;
    pubDateField?: string;
  };
  options?: {
    showDescription?: boolean;
    span?: number;
  };
  title?: string;
  id: string;
}

const props = withDefaults(defineProps<Props>(), {
  options: () => ({
    showDescription: true,
    span: 12,
  }),
});

const isEmpty = computed(() => {
  return !props.data.items || props.data.items.length === 0;
});

const showDescription = computed(() => {
  return props.options?.showDescription ?? true;
});
</script>

<template>
  <Card>
    <CardHeader v-if="title">
      <CardTitle>{{ title }}</CardTitle>
      <CardDescription v-if="data.stats?.description">
        {{ data.stats.description }}
      </CardDescription>
    </CardHeader>

    <CardContent>
      <div
        v-if="isEmpty"
        class="flex h-[200px] items-center justify-center text-muted-foreground"
      >
        暂无数据
      </div>

      <div v-else class="space-y-4">
        <ListItem
          v-for="item in data.items"
          :key="item.id"
          :item="item"
          :title-field="props.titleField"
          :link-field="props.linkField"
          :description-field="props.descriptionField"
          :pub-date-field="props.pubDateField"
          :show-description="showDescription"
        />
      </div>
    </CardContent>
  </Card>
</template>
```

---

### 5.3 列表项组件

```vue
<!-- frontend/src/features/panel/components/ListPanel/ListItem.vue -->
<script setup lang="ts">
import { computed } from 'vue';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import type { ListPanelRecord } from '@/shared/types/panelContracts';
import { formatDate } from './utils';

interface Props {
  item: ListPanelRecord;
  titleField: string;
  linkField: string;
  descriptionField?: string;
  pubDateField?: string;
  showDescription?: boolean;
}

const props = defineProps<Props>();

const title = computed(() => {
  return String((props.item as any)[props.titleField] || props.item.title || '');
});

const link = computed(() => {
  const linkValue = props.linkField
    ? (props.item as any)[props.linkField]
    : props.item.link;
  return linkValue || null;
});

const description = computed(() => {
  if (!props.showDescription || !props.descriptionField) return null;
  return (props.item as any)[props.descriptionField] || props.item.summary || null;
});

const publishedAt = computed(() => {
  if (!props.pubDateField) return null;
  const dateValue = (props.item as any)[props.pubDateField] || props.item.published_at;
  return dateValue ? formatDate(dateValue) : null;
});

const author = computed(() => {
  return props.item.author || null;
});

const categories = computed(() => {
  return props.item.categories || [];
});

const handleClick = () => {
  if (link.value) {
    window.open(link.value, '_blank');
  }
};
</script>

<template>
  <div class="group">
    <div
      :class="[
        'rounded-lg border p-4 transition-colors',
        link ? 'cursor-pointer hover:bg-accent' : '',
      ]"
      @click="handleClick"
    >
      <!-- 标题行 -->
      <div class="mb-2 flex items-start justify-between gap-2">
        <h3
          :class="[
            'flex-1 text-base font-semibold leading-tight',
            link ? 'group-hover:text-primary' : '',
          ]"
        >
          {{ title }}
        </h3>
      </div>

      <!-- 摘要 -->
      <p
        v-if="description"
        class="mb-2 line-clamp-2 text-sm text-muted-foreground"
      >
        {{ description }}
      </p>

      <!-- 元数据 -->
      <div class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span v-if="author" class="flex items-center gap-1">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 16 16"
            fill="currentColor"
            class="h-3 w-3"
          >
            <path
              d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM12.735 14c.618 0 1.093-.561.872-1.139a6.002 6.002 0 0 0-11.215 0c-.22.578.254 1.139.872 1.139h9.47Z"
            />
          </svg>
          {{ author }}
        </span>

        <Separator v-if="author && publishedAt" orientation="vertical" class="h-3" />

        <span v-if="publishedAt" class="flex items-center gap-1">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 16 16"
            fill="currentColor"
            class="h-3 w-3"
          >
            <path
              fill-rule="evenodd"
              d="M4 1.75a.75.75 0 0 1 1.5 0V3h5V1.75a.75.75 0 0 1 1.5 0V3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2V1.75ZM4.5 6a1 1 0 0 0-1 1v4.5a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1h-7Z"
              clip-rule="evenodd"
            />
          </svg>
          {{ publishedAt }}
        </span>

        <template v-if="categories.length > 0">
          <Separator v-if="author || publishedAt" orientation="vertical" class="h-3" />
          <div class="flex gap-1">
            <Badge
              v-for="(category, index) in categories.slice(0, 3)"
              :key="index"
              variant="secondary"
              class="text-xs"
            >
              {{ category }}
            </Badge>
            <Badge v-if="categories.length > 3" variant="outline" class="text-xs">
              +{{ categories.length - 3 }}
            </Badge>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
```

---

### 5.4 工具函数

```typescript
// frontend/src/features/panel/components/ListPanel/utils.ts

/**
 * 格式化日期为相对时间或绝对时间
 */
export function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    // 相对时间
    if (diffMins < 1) {
      return '刚刚';
    }
    if (diffMins < 60) {
      return `${diffMins} 分钟前`;
    }
    if (diffHours < 24) {
      return `${diffHours} 小时前`;
    }
    if (diffDays < 7) {
      return `${diffDays} 天前`;
    }

    // 绝对时间
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const currentYear = now.getFullYear();

    if (year === currentYear) {
      return `${month}-${day}`;
    }
    return `${year}-${month}-${day}`;
  } catch {
    return dateString;
  }
}

/**
 * 清理 HTML 标签（用于摘要字段）
 */
export function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, '').trim();
}
```

---

## 6. 集成到面板系统

```typescript
// frontend/src/features/panel/components/index.ts
import ListPanel from './ListPanel/ListPanel.vue';

export const PanelComponents = {
  ListPanel,  // 更新
  StatisticCard: () => import('./StatisticCard/StatisticCard.vue'),
  LineChart: () => import('./LineChart/LineChart.vue'),
  BarChart: () => import('./BarChart/BarChart.vue'),
  PieChart: () => import('./PieChart/PieChart.vue'),
  Table: () => import('./Table/Table.vue'),
  FallbackRichText: () => import('./FallbackRichText/FallbackRichText.vue'),
};
```

---

## 7. 测试用例

```typescript
// frontend/src/features/panel/components/ListPanel/__tests__/ListPanel.spec.ts
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import ListPanel from '../ListPanel.vue';
import type { ListPanelRecord } from '@/shared/types/panelContracts';

describe('ListPanel', () => {
  const mockData: ListPanelRecord[] = [
    {
      id: '1',
      title: 'Vue 3.4 发布',
      link: 'https://example.com/1',
      summary: 'Vue 3.4 带来了更快的响应式系统和更好的类型支持',
      published_at: '2024-01-15T10:30:00Z',
      author: 'Evan You',
      categories: ['Vue', 'Release'],
    },
    {
      id: '2',
      title: 'TypeScript 5.3 新特性',
      link: 'https://example.com/2',
      summary: 'TypeScript 5.3 引入了导入属性等新功能',
      published_at: '2024-01-14T08:20:00Z',
      author: 'Microsoft',
      categories: ['TypeScript', 'News'],
    },
  ];

  it('renders list with data', () => {
    const wrapper = mount(ListPanel, {
      props: {
        id: 'test-list',
        data: { items: mockData, schema: {}, stats: {} },
        props: {
          titleField: 'title',
          linkField: 'link',
          descriptionField: 'summary',
          pubDateField: 'published_at',
        },
        title: '最新动态',
      },
    });

    expect(wrapper.text()).toContain('最新动态');
    expect(wrapper.text()).toContain('Vue 3.4 发布');
    expect(wrapper.text()).toContain('TypeScript 5.3 新特性');
  });

  it('shows empty state when no data', () => {
    const wrapper = mount(ListPanel, {
      props: {
        id: 'test-list',
        data: { items: [], schema: {}, stats: {} },
        props: {
          titleField: 'title',
          linkField: 'link',
        },
      },
    });

    expect(wrapper.text()).toContain('暂无数据');
  });

  it('hides description when showDescription is false', () => {
    const wrapper = mount(ListPanel, {
      props: {
        id: 'test-list',
        data: { items: mockData, schema: {}, stats: {} },
        props: {
          titleField: 'title',
          linkField: 'link',
          descriptionField: 'summary',
        },
        options: {
          showDescription: false,
        },
      },
    });

    expect(wrapper.text()).not.toContain('Vue 3.4 带来了更快的响应式系统');
  });
});
```

---

## 8. 后端适配器示例

```python
from services.panel.adapters import route_adapter, SourceInfo, RouteAdapterResult, AdapterBlockPlan
from services.panel.view_models import validate_records

@route_adapter("/bilibili/followings", manifest=FOLLOWINGS_MANIFEST)
def bilibili_followings_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    """B站关注动态适配器"""
    list_records = []

    for idx, item in enumerate(records[:20], start=1):
        list_records.append({
            "id": f"following-{idx}",
            "title": item.get("title", ""),
            "link": item.get("link"),
            "summary": strip_html_tags(item.get("description", "")),
            "published_at": item.get("pubDate"),
            "author": extract_author(item.get("description", "")),
            "categories": ["B站", "关注"],
        })

    validated = validate_records("ListPanel", list_records)

    return RouteAdapterResult(
        records=validated,
        block_plans=[
            AdapterBlockPlan(
                component_id="ListPanel",
                props={
                    "title_field": "title",
                    "link_field": "link",
                    "description_field": "summary",
                    "pub_date_field": "published_at",
                },
                options={"show_description": True, "span": 12},
                title="最新关注动态",
                confidence=0.95,
            )
        ],
        stats={"total_items": len(validated)},
    )
```

---

## 9. 开发清单

### 后端部分 ✅ 已完成
- [x] 契约文档定义
- [x] Pydantic 模型定义
- [x] 契约验证函数
- [x] TypeScript 类型定义

### 前端部分 ⏳ 待实现
- [ ] 安装 shadcn-vue（如果尚未安装）
- [ ] 添加 Card、Badge、Separator 组件
- [ ] 实现 ListPanel.vue 组件
- [ ] 实现 ListItem.vue 子组件
- [ ] 实现工具函数
- [ ] 单元测试
- [ ] 集成到面板系统

---

## 10. 设计说明

### 交互设计
- 整个列表项可点击（当有 link 时）
- Hover 时背景色变化，标题颜色高亮
- 在新标签页打开链接（`target="_blank"`）

### 信息层次
1. **标题**：最重要，字体最大，粗体
2. **摘要**：次要，灰色文本，限制 2 行
3. **元数据**：最次要，小字号，包括作者、时间、标签

### 响应式
- 移动端：标签最多显示 3 个，超出显示 "+N"
- 桌面端：完整显示所有信息

---

## 附录：参考资源

- **shadcn-vue Card**: https://www.shadcn-vue.com/docs/components/card.html
- **shadcn-vue Badge**: https://www.shadcn-vue.com/docs/components/badge.html
- **shadcn-vue Separator**: https://www.shadcn-vue.com/docs/components/separator.html
- **Vue 3 文档**: https://vuejs.org/
