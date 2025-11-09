# StatisticCard 组件前端实现指南

> 创建时间：2025-11-09
> 更新时间：2025-11-09
> 状态：✅ 后端契约已完成，等待前端实现
> **技术栈**: Vue 3 + shadcn-vue

---

## 1. 组件概述

**StatisticCard** 是用于展示关键指标和统计数据的卡片组件，适用于 KPI、增长率、总数等数据的展示。

### 核心特性
- ✅ 使用 shadcn-vue Card 作为容器
- ✅ 支持数值、单位、趋势展示
- ✅ 支持变化量和变化文本
- ✅ 趋势图标（上升/下降/持平）
- ✅ 响应式数字格式化
- ✅ Vue 3 Composition API
- ✅ TypeScript 完整支持

---

## 2. 数据契约

### TypeScript 接口（已完成）

```typescript
// frontend/src/shared/types/panelContracts.ts
export interface StatisticCardRecord {
  id: string;
  metric_title: string;
  metric_value: number;
  metric_unit?: string | null;
  metric_delta_text?: string | null;
  metric_delta_value?: number | null;
  metric_trend?: "up" | "down" | "flat" | null;
  description?: string | null;
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
```

---

## 4. Props 定义

```typescript
interface StatisticCardProps {
  data: {
    items: StatisticCardRecord[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {
    titleField: string;
    valueField: string;
    trendField?: string;
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
└── StatisticCard/
    ├── StatisticCard.vue       # 主组件
    ├── utils.ts                # 工具函数
    └── __tests__/
        └── StatisticCard.spec.ts
```

### 5.2 主组件

```vue
<!-- frontend/src/features/panel/components/StatisticCard/StatisticCard.vue -->
<script setup lang="ts">
import { computed } from 'vue';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { StatisticCardRecord } from '@/shared/types/panelContracts';
import { formatNumber, getTrendIcon, getTrendColor } from './utils';

interface Props {
  data: {
    items: StatisticCardRecord[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {
    titleField: string;
    valueField: string;
    trendField?: string;
  };
  options?: {
    span?: number;
  };
  title?: string;
  id: string;
}

const props = withDefaults(defineProps<Props>(), {
  options: () => ({
    span: 6,
  }),
});

const record = computed(() => {
  return props.data.items?.[0] || null;
});

const isEmpty = computed(() => {
  return !record.value;
});

const metricTitle = computed(() => {
  if (!record.value) return '';
  return String((record.value as any)[props.props.titleField] || record.value.metric_title || '');
});

const metricValue = computed(() => {
  if (!record.value) return 0;
  return Number((record.value as any)[props.props.valueField] || record.value.metric_value || 0);
});

const metricUnit = computed(() => {
  return record.value?.metric_unit || null;
});

const metricDeltaText = computed(() => {
  return record.value?.metric_delta_text || null;
});

const metricDeltaValue = computed(() => {
  return record.value?.metric_delta_value || null;
});

const metricTrend = computed(() => {
  if (!record.value) return null;
  const trendValue = props.props.trendField
    ? (record.value as any)[props.props.trendField]
    : record.value.metric_trend;
  return trendValue as 'up' | 'down' | 'flat' | null;
});

const description = computed(() => {
  return record.value?.description || null;
});

const trendIcon = computed(() => {
  return getTrendIcon(metricTrend.value);
});

const trendColor = computed(() => {
  return getTrendColor(metricTrend.value);
});

const formattedValue = computed(() => {
  return formatNumber(metricValue.value);
});
</script>

<template>
  <Card>
    <CardHeader class="pb-2">
      <CardDescription>{{ metricTitle }}</CardDescription>
    </CardHeader>

    <CardContent>
      <div v-if="isEmpty" class="flex h-[80px] items-center justify-center text-muted-foreground text-sm">
        暂无数据
      </div>

      <div v-else>
        <!-- 主数值 -->
        <div class="flex items-baseline gap-2">
          <div class="text-3xl font-bold tracking-tight">
            {{ formattedValue }}
          </div>
          <div v-if="metricUnit" class="text-sm text-muted-foreground">
            {{ metricUnit }}
          </div>
        </div>

        <!-- 趋势指示 -->
        <div v-if="metricTrend || metricDeltaText" class="mt-2 flex items-center gap-2 text-sm">
          <!-- 趋势图标 -->
          <div
            v-if="trendIcon"
            :class="['flex items-center gap-1', trendColor]"
            v-html="trendIcon"
          ></div>

          <!-- 变化文本 -->
          <span v-if="metricDeltaText" class="text-muted-foreground">
            {{ metricDeltaText }}
          </span>
        </div>

        <!-- 补充说明 -->
        <p v-if="description" class="mt-2 text-xs text-muted-foreground line-clamp-2">
          {{ description }}
        </p>
      </div>
    </CardContent>
  </Card>
</template>
```

---

### 5.3 工具函数

```typescript
// frontend/src/features/panel/components/StatisticCard/utils.ts

/**
 * 格式化数字为易读形式
 */
export function formatNumber(value: number): string {
  if (value === 0) return '0';

  const absValue = Math.abs(value);

  // 万、亿单位
  if (absValue >= 100000000) {
    return (value / 100000000).toFixed(2) + '亿';
  }
  if (absValue >= 10000) {
    return (value / 10000).toFixed(2) + '万';
  }

  // 千分位分隔
  return value.toLocaleString('zh-CN');
}

/**
 * 获取趋势图标 SVG
 */
export function getTrendIcon(trend: 'up' | 'down' | 'flat' | null): string | null {
  if (!trend) return null;

  const icons = {
    up: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4">
      <path fill-rule="evenodd" d="M8 14a.75.75 0 0 1-.75-.75V4.56L4.03 7.78a.75.75 0 0 1-1.06-1.06l4.5-4.5a.75.75 0 0 1 1.06 0l4.5 4.5a.75.75 0 0 1-1.06 1.06L8.75 4.56v8.69A.75.75 0 0 1 8 14Z" clip-rule="evenodd" />
    </svg>`,
    down: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4">
      <path fill-rule="evenodd" d="M8 2a.75.75 0 0 1 .75.75v8.69l3.22-3.22a.75.75 0 1 1 1.06 1.06l-4.5 4.5a.75.75 0 0 1-1.06 0l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.22 3.22V2.75A.75.75 0 0 1 8 2Z" clip-rule="evenodd" />
    </svg>`,
    flat: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4">
      <path d="M2 8a.75.75 0 0 1 .75-.75h10.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 8Z" />
    </svg>`,
  };

  return icons[trend] || null;
}

/**
 * 获取趋势颜色 CSS 类
 */
export function getTrendColor(trend: 'up' | 'down' | 'flat' | null): string {
  if (!trend) return 'text-muted-foreground';

  const colors = {
    up: 'text-green-600 dark:text-green-500',
    down: 'text-red-600 dark:text-red-500',
    flat: 'text-gray-500 dark:text-gray-400',
  };

  return colors[trend] || 'text-muted-foreground';
}
```

---

## 6. 集成到面板系统

```typescript
// frontend/src/features/panel/components/index.ts
import StatisticCard from './StatisticCard/StatisticCard.vue';

export const PanelComponents = {
  ListPanel: () => import('./ListPanel/ListPanel.vue'),
  StatisticCard,  // 更新
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
// frontend/src/features/panel/components/StatisticCard/__tests__/StatisticCard.spec.ts
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import StatisticCard from '../StatisticCard.vue';
import type { StatisticCardRecord } from '@/shared/types/panelContracts';

describe('StatisticCard', () => {
  const mockData: StatisticCardRecord = {
    id: 'total-stars',
    metric_title: '总 Stars',
    metric_value: 12345,
    metric_unit: '个',
    metric_delta_text: '+5.6% vs 上周',
    metric_delta_value: 657,
    metric_trend: 'up',
    description: '本周新增 657 个 Stars',
  };

  it('renders card with data', () => {
    const wrapper = mount(StatisticCard, {
      props: {
        id: 'test-card',
        data: { items: [mockData], schema: {}, stats: {} },
        props: {
          titleField: 'metric_title',
          valueField: 'metric_value',
          trendField: 'metric_trend',
        },
      },
    });

    expect(wrapper.text()).toContain('总 Stars');
    expect(wrapper.text()).toContain('1.23万');
    expect(wrapper.text()).toContain('+5.6% vs 上周');
  });

  it('shows empty state when no data', () => {
    const wrapper = mount(StatisticCard, {
      props: {
        id: 'test-card',
        data: { items: [], schema: {}, stats: {} },
        props: {
          titleField: 'metric_title',
          valueField: 'metric_value',
        },
      },
    });

    expect(wrapper.text()).toContain('暂无数据');
  });

  it('formats large numbers correctly', () => {
    const largeData: StatisticCardRecord = {
      id: 'large-number',
      metric_title: '访问量',
      metric_value: 123456789,
    };

    const wrapper = mount(StatisticCard, {
      props: {
        id: 'test-card',
        data: { items: [largeData], schema: {}, stats: {} },
        props: {
          titleField: 'metric_title',
          valueField: 'metric_value',
        },
      },
    });

    expect(wrapper.text()).toContain('1.23亿');
  });
});
```

---

## 8. 后端适配器示例

```python
from services.panel.adapters import route_adapter, SourceInfo, RouteAdapterResult, AdapterBlockPlan
from services.panel.view_models import validate_records

@route_adapter("/github/repo/stats", manifest=REPO_STATS_MANIFEST)
def github_repo_stats_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    """GitHub 仓库统计适配器"""
    # 从数据中提取统计信息
    total_stars = sum(item.get("stars", 0) for item in records)
    last_week_stars = 8765  # 假设从历史数据获取

    delta_value = total_stars - last_week_stars
    delta_percent = (delta_value / last_week_stars * 100) if last_week_stars > 0 else 0

    statistic_record = {
        "id": "total-stars",
        "metric_title": "总 Stars",
        "metric_value": total_stars,
        "metric_unit": "个",
        "metric_delta_text": f"{delta_percent:+.1f}% vs 上周",
        "metric_delta_value": delta_value,
        "metric_trend": "up" if delta_value > 0 else "down" if delta_value < 0 else "flat",
        "description": f"本周新增 {delta_value} 个 Stars",
    }

    validated = validate_records("StatisticCard", [statistic_record])

    return RouteAdapterResult(
        records=validated,
        block_plans=[
            AdapterBlockPlan(
                component_id="StatisticCard",
                props={
                    "title_field": "metric_title",
                    "value_field": "metric_value",
                    "trend_field": "metric_trend",
                },
                options={"span": 6},
                confidence=0.95,
            )
        ],
        stats={"total_stars": total_stars},
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
- [ ] 添加 Card 组件
- [ ] 实现 StatisticCard.vue 组件
- [ ] 实现工具函数
- [ ] 单元测试
- [ ] 集成到面板系统

---

## 10. 设计说明

### 视觉层次
1. **指标名称**：顶部，灰色小字
2. **主数值**：最大，粗体，3xl 字号
3. **单位**：跟随数值，小字号
4. **趋势指示**：带颜色图标 + 变化文本
5. **补充说明**：底部，最小字号

### 颜色规范
- **上升趋势**：绿色 (`text-green-600`)
- **下降趋势**：红色 (`text-red-600`)
- **持平趋势**：灰色 (`text-gray-500`)

### 响应式
- 在小屏幕上，卡片宽度为 `span: 6`（50%）
- 支持自适应字体缩放

---

## 11. 使用场景示例

### 场景 1: GitHub Stars 统计
```json
{
  "id": "total-stars",
  "metric_title": "总 Stars",
  "metric_value": 12345,
  "metric_unit": "个",
  "metric_delta_text": "+5.6% vs 上周",
  "metric_trend": "up"
}
```

### 场景 2: 用户增长
```json
{
  "id": "new-users",
  "metric_title": "新增用户",
  "metric_value": 1234,
  "metric_delta_text": "+234 vs 昨天",
  "metric_trend": "up"
}
```

### 场景 3: 跌幅统计
```json
{
  "id": "error-rate",
  "metric_title": "错误率",
  "metric_value": 2.5,
  "metric_unit": "%",
  "metric_delta_text": "-0.5% vs 上月",
  "metric_trend": "down",
  "description": "错误率持续下降"
}
```

---

## 附录：参考资源

- **shadcn-vue Card**: https://www.shadcn-vue.com/docs/components/card.html
- **Vue 3 文档**: https://vuejs.org/
- **Heroicons**: https://heroicons.com/ (趋势图标)
