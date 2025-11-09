# BarChart 组件前端实现指南

> 创建时间：2025-11-09
> 更新时间：2025-11-09
> 状态：✅ 后端契约已完成，等待前端实现
> **技术栈**: Vue 3 + shadcn-vue + ECharts

---

## 1. 组件概述

**BarChart** 是用于展示柱状图的可视化组件，主要用于排行榜、对比数据和统计数据的场景。

### 核心特性
- ✅ 基于 ECharts 柱状图
- ✅ 使用 shadcn-vue Card 作为容器
- ✅ 支持垂直/横向柱状图
- ✅ 支持多序列分组
- ✅ 支持自定义柱子颜色
- ✅ 支持堆叠模式
- ✅ Vue 3 Composition API
- ✅ TypeScript 完整支持
- ✅ 响应式设计

---

## 2. 数据契约

### TypeScript 接口（已完成）

```typescript
// frontend/src/shared/types/panelContracts.ts
export interface BarChartRecord {
  id: string;
  x: string;  // 横轴类目（如 "Python", "JavaScript"）
  y: number;  // 纵轴数值（如 1234）
  series?: string | null;  // 序列分组
  color?: string | null;  // 自定义颜色（十六进制）
  tooltip?: string | null;  // 自定义提示文本
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

### 3.2 添加 Card 组件

```bash
npx shadcn-vue@latest add card
```

### 3.3 安装 ECharts

```bash
npm install echarts vue-echarts
```

---

## 4. Props 定义

```typescript
interface BarChartProps {
  data: {
    items: BarChartRecord[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {
    xField: string;
    yField: string;
    seriesField?: string;
  };
  options?: {
    horizontal?: boolean;
    stacked?: boolean;
    showValues?: boolean;
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
└── BarChart/
    ├── BarChart.vue       # 主组件
    ├── useBarChart.ts     # ECharts 配置逻辑
    ├── utils.ts           # 数据转换工具
    └── __tests__/
        └── BarChart.spec.ts
```

### 5.2 主组件

```vue
<!-- frontend/src/features/panel/components/BarChart/BarChart.vue -->
<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart as EChartsBar } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { BarChartRecord } from '@/shared/types/panelContracts';
import { useBarChartOption } from './useBarChart';

// 注册 ECharts 组件
use([CanvasRenderer, EChartsBar, GridComponent, TooltipComponent, LegendComponent]);

interface Props {
  data: {
    items: BarChartRecord[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {
    xField: string;
    yField: string;
    seriesField?: string;
  };
  options?: {
    horizontal?: boolean;
    stacked?: boolean;
    showValues?: boolean;
    span?: number;
  };
  title?: string;
  id: string;
}

const props = withDefaults(defineProps<Props>(), {
  options: () => ({
    horizontal: false,
    stacked: false,
    showValues: true,
    span: 12,
  }),
});

const chartRef = ref<InstanceType<typeof VChart>>();

// 生成 ECharts 配置
const option = computed(() => {
  return useBarChartOption(
    props.data.items,
    {
      xField: props.props.xField,
      yField: props.props.yField,
      seriesField: props.props.seriesField,
    },
    props.options
  );
});

const isEmpty = computed(() => {
  return !props.data.items || props.data.items.length === 0;
});

// 响应式调整
let resizeObserver: ResizeObserver | null = null;

onMounted(() => {
  if (chartRef.value) {
    const chart = chartRef.value;
    resizeObserver = new ResizeObserver(() => {
      chart?.resize();
    });
    const container = chart?.$el?.parentElement;
    if (container) {
      resizeObserver.observe(container);
    }
  }
});

onUnmounted(() => {
  resizeObserver?.disconnect();
});

// 监听窗口大小变化
watch(() => props.data.items, () => {
  chartRef.value?.resize();
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
        class="flex h-[280px] items-center justify-center text-muted-foreground"
      >
        暂无数据
      </div>

      <VChart
        v-else
        ref="chartRef"
        :option="option"
        class="h-[280px] w-full"
        autoresize
      />
    </CardContent>
  </Card>
</template>
```

---

### 5.3 ECharts 配置逻辑

```typescript
// frontend/src/features/panel/components/BarChart/useBarChart.ts
import type { EChartsOption } from 'echarts';
import type { BarChartRecord } from '@/shared/types/panelContracts';
import { transformDataForECharts, getSeriesList } from './utils';

interface FieldMapping {
  xField: string;
  yField: string;
  seriesField?: string;
}

interface ChartOptions {
  horizontal?: boolean;
  stacked?: boolean;
  showValues?: boolean;
  span?: number;
}

export function useBarChartOption(
  records: BarChartRecord[],
  mapping: FieldMapping,
  options: ChartOptions = {}
): EChartsOption {
  const { horizontal = false, stacked = false, showValues = true } = options;

  // 转换数据
  const { categories, seriesData } = transformDataForECharts(records, mapping);
  const seriesList = getSeriesList(records, mapping.seriesField);

  // 构建 series 配置
  const series = seriesList.map((seriesName, index) => {
    // 查找该序列的自定义颜色
    const recordWithColor = records.find((item) => {
      const seriesValue = mapping.seriesField
        ? String((item as any)[mapping.seriesField] || 'default')
        : 'default';
      return seriesValue === seriesName && item.color;
    });

    return {
      name: seriesName,
      type: 'bar',
      data: seriesData[seriesName],
      itemStyle: {
        color: recordWithColor?.color,
      },
      label: {
        show: showValues,
        position: horizontal ? 'right' : 'top',
        formatter: (params: any) => {
          return params.value.toLocaleString();
        },
      },
      stack: stacked ? 'total' : undefined,
      barMaxWidth: 60,
    };
  });

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
      formatter: (params: any) => {
        if (!Array.isArray(params)) params = [params];
        let result = `${params[0].axisValue}<br/>`;
        params.forEach((item: any) => {
          result += `${item.marker} ${item.seriesName}: ${item.value.toLocaleString()}<br/>`;
        });
        return result;
      },
    },
    legend: {
      show: seriesList.length > 1,
      top: 0,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: horizontal ? 'value' : 'category',
      data: horizontal ? undefined : categories,
      axisLabel: {
        interval: 0,
        rotate: categories.length > 10 ? 45 : 0,
      },
    },
    yAxis: {
      type: horizontal ? 'category' : 'value',
      data: horizontal ? categories : undefined,
      axisLabel: {
        formatter: (value: number) => {
          return typeof value === 'number' ? value.toLocaleString() : value;
        },
      },
    },
    series,
  };
}
```

---

### 5.4 数据转换工具

```typescript
// frontend/src/features/panel/components/BarChart/utils.ts
import type { BarChartRecord } from '@/shared/types/panelContracts';

interface FieldMapping {
  xField: string;
  yField: string;
  seriesField?: string;
}

/**
 * 将 BarChartRecord[] 转换为 ECharts 需要的格式
 */
export function transformDataForECharts(
  records: BarChartRecord[],
  mapping: FieldMapping
): {
  categories: string[];
  seriesData: Record<string, number[]>;
} {
  const { xField, yField, seriesField } = mapping;

  // 收集所有 x 类目
  const categoriesSet = new Set<string>();
  const dataMap = new Map<string, Map<string, number>>();

  for (const record of records) {
    const xValue = String((record as any)[xField] || record.x);
    const yValue = Number((record as any)[yField] || record.y);
    const seriesValue = seriesField
      ? String((record as any)[seriesField] || 'default')
      : 'default';

    categoriesSet.add(xValue);

    if (!dataMap.has(seriesValue)) {
      dataMap.set(seriesValue, new Map());
    }
    dataMap.get(seriesValue)!.set(xValue, yValue);
  }

  const categories = Array.from(categoriesSet);
  const seriesData: Record<string, number[]> = {};

  for (const [seriesName, categoryMap] of dataMap.entries()) {
    seriesData[seriesName] = categories.map((cat) => categoryMap.get(cat) || 0);
  }

  return { categories, seriesData };
}

/**
 * 获取所有唯一的序列名称
 */
export function getSeriesList(
  records: BarChartRecord[],
  seriesField?: string
): string[] {
  if (!seriesField) return ['default'];

  const seriesSet = new Set<string>();
  for (const record of records) {
    const value = (record as any)[seriesField] || 'default';
    seriesSet.add(String(value));
  }
  return Array.from(seriesSet);
}
```

---

## 6. 注册 ECharts 全局（可选）

如果多个组件使用 ECharts，可以在 `main.ts` 中全局注册：

```typescript
// frontend/src/main.ts
import { createApp } from 'vue';
import ECharts from 'vue-echarts';
import App from './App.vue';

const app = createApp(App);

// 全局注册 vue-echarts 组件
app.component('VChart', ECharts);

app.mount('#app');
```

---

## 7. 集成到面板系统

```typescript
// frontend/src/features/panel/components/index.ts
import BarChart from './BarChart/BarChart.vue';

export const PanelComponents = {
  ListPanel: () => import('./ListPanel/ListPanel.vue'),
  StatisticCard: () => import('./StatisticCard/StatisticCard.vue'),
  LineChart: () => import('./LineChart/LineChart.vue'),
  BarChart,  // 新增
  FallbackRichText: () => import('./FallbackRichText/FallbackRichText.vue'),
};
```

---

## 8. 测试用例

```typescript
// frontend/src/features/panel/components/BarChart/__tests__/BarChart.spec.ts
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import BarChart from '../BarChart.vue';
import type { BarChartRecord } from '@/shared/types/panelContracts';

describe('BarChart', () => {
  const mockData: BarChartRecord[] = [
    { id: '1', x: 'Python', y: 1234, color: '#3776ab' },
    { id: '2', x: 'JavaScript', y: 2100, color: '#f7df1e' },
    { id: '3', x: 'Rust', y: 999, color: '#dea584' },
  ];

  it('renders chart with data', () => {
    const wrapper = mount(BarChart, {
      props: {
        id: 'test-chart',
        data: { items: mockData, schema: {}, stats: {} },
        props: { xField: 'x', yField: 'y' },
        title: '编程语言 Star 数',
      },
    });

    expect(wrapper.text()).toContain('编程语言 Star 数');
  });

  it('shows empty state when no data', () => {
    const wrapper = mount(BarChart, {
      props: {
        id: 'test-chart',
        data: { items: [], schema: {}, stats: {} },
        props: { xField: 'x', yField: 'y' },
      },
    });

    expect(wrapper.text()).toContain('暂无数据');
  });
});
```

---

## 9. 后端适配器示例

```python
@route_adapter("/github/trending/daily", manifest=TRENDING_MANIFEST)
def github_trending_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    bar_chart_records = []
    for idx, item in enumerate(top_repos, start=1):
        bar_chart_records.append({
            "id": f"repo-{idx}",
            "x": item["name"],
            "y": item["stars"],
            "color": get_language_color(item.get("language")),
        })

    validated = validate_records("BarChart", bar_chart_records)

    return RouteAdapterResult(
        records=validated,
        block_plans=[
            AdapterBlockPlan(
                component_id="BarChart",
                props={"x_field": "x", "y_field": "y"},
                options={"horizontal": False, "show_values": True, "span": 12},
                title="GitHub Trending - Top 10",
                confidence=0.85,
            )
        ],
        stats={"total_items": len(validated)},
    )
```

---

## 10. 开发清单

### 后端部分 ✅ 已完成
- [x] 契约文档更新
- [x] Pydantic 模型定义
- [x] 契约验证函数
- [x] 单元测试
- [x] TypeScript 类型定义

### 前端部分 ⏳ 待实现
- [ ] 安装 shadcn-vue
- [ ] 安装 ECharts 和 vue-echarts
- [ ] 实现 BarChart.vue 组件
- [ ] 实现 useBarChart.ts 逻辑
- [ ] 数据转换工具
- [ ] 单元测试
- [ ] 集成到面板系统

---

## 附录：参考资源

- **shadcn-vue 官方文档**: https://www.shadcn-vue.com/
- **ECharts 官方文档**: https://echarts.apache.org/zh/index.html
- **vue-echarts 文档**: https://github.com/ecomfe/vue-echarts
- **ECharts 柱状图示例**: https://echarts.apache.org/examples/zh/index.html#chart-type-bar
