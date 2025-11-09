# PieChart 组件前端实现指南

> 创建时间：2025-11-09
> 更新时间：2025-11-09
> 状态：✅ 后端契约已完成，等待前端实现
> **技术栈**: Vue 3 + shadcn-vue + ECharts

---

## 1. 组件概述

**PieChart** 是用于展示占比和分类统计的可视化组件，主要用于展示各部分在整体中的比例关系。

### 核心特性
- ✅ 基于 ECharts 饼图/环形图
- ✅ 使用 shadcn-vue Card 作为容器
- ✅ 支持饼图/环形图切换
- ✅ 支持自定义扇区颜色
- ✅ 支持百分比标签显示
- ✅ 支持图例展示
- ✅ Vue 3 Composition API
- ✅ TypeScript 完整支持
- ✅ 响应式设计

---

## 2. 数据契约

### TypeScript 接口（已完成）

```typescript
// frontend/src/shared/types/panelContracts.ts
export interface PieChartRecord {
  id: string;
  name: string;  // 分类名称
  value: number;  // 数值
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
interface PieChartProps {
  data: {
    items: PieChartRecord[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {
    nameField: string;
    valueField: string;
  };
  options?: {
    donut?: boolean;
    showLegend?: boolean;
    showLabel?: boolean;
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
└── PieChart/
    ├── PieChart.vue       # 主组件
    ├── usePieChart.ts     # ECharts 配置逻辑
    ├── utils.ts           # 数据转换工具
    └── __tests__/
        └── PieChart.spec.ts
```

### 5.2 主组件

```vue
<!-- frontend/src/features/panel/components/PieChart/PieChart.vue -->
<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { PieChart as EChartsPie } from 'echarts/charts';
import {
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
import type { PieChartRecord } from '@/shared/types/panelContracts';
import { usePieChartOption } from './usePieChart';

// 注册 ECharts 组件
use([CanvasRenderer, EChartsPie, TooltipComponent, LegendComponent]);

interface Props {
  data: {
    items: PieChartRecord[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {
    nameField: string;
    valueField: string;
  };
  options?: {
    donut?: boolean;
    showLegend?: boolean;
    showLabel?: boolean;
    span?: number;
  };
  title?: string;
  id: string;
}

const props = withDefaults(defineProps<Props>(), {
  options: () => ({
    donut: false,
    showLegend: true,
    showLabel: true,
    span: 12,
  }),
});

const chartRef = ref<InstanceType<typeof VChart>>();

// 生成 ECharts 配置
const option = computed(() => {
  return usePieChartOption(
    props.data.items,
    {
      nameField: props.props.nameField,
      valueField: props.props.valueField,
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
        class="flex h-[320px] items-center justify-center text-muted-foreground"
      >
        暂无数据
      </div>

      <VChart
        v-else
        ref="chartRef"
        :option="option"
        class="h-[320px] w-full"
        autoresize
      />
    </CardContent>
  </Card>
</template>
```

---

### 5.3 ECharts 配置逻辑

```typescript
// frontend/src/features/panel/components/PieChart/usePieChart.ts
import type { EChartsOption } from 'echarts';
import type { PieChartRecord } from '@/shared/types/panelContracts';
import { transformDataForECharts } from './utils';

interface FieldMapping {
  nameField: string;
  valueField: string;
}

interface ChartOptions {
  donut?: boolean;
  showLegend?: boolean;
  showLabel?: boolean;
  span?: number;
}

export function usePieChartOption(
  records: PieChartRecord[],
  mapping: FieldMapping,
  options: ChartOptions = {}
): EChartsOption {
  const { donut = false, showLegend = true, showLabel = true } = options;

  // 转换数据
  const chartData = transformDataForECharts(records, mapping);

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const { name, value, percent } = params;
        const record = records.find((r) => r.name === name);
        if (record?.tooltip) {
          return record.tooltip;
        }
        return `${name}<br/>${value.toLocaleString()} (${percent}%)`;
      },
    },
    legend: {
      show: showLegend,
      orient: 'vertical',
      left: 'left',
      top: 'middle',
    },
    series: [
      {
        name: '数据分布',
        type: 'pie',
        radius: donut ? ['40%', '70%'] : '70%',
        center: showLegend ? ['60%', '50%'] : ['50%', '50%'],
        data: chartData,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
        label: {
          show: showLabel,
          formatter: (params: any) => {
            return `{b}: {d}%`;
          },
        },
        itemStyle: {
          borderRadius: donut ? 8 : 0,
          borderColor: '#fff',
          borderWidth: 2,
        },
      },
    ],
  };
}
```

---

### 5.4 数据转换工具

```typescript
// frontend/src/features/panel/components/PieChart/utils.ts
import type { PieChartRecord } from '@/shared/types/panelContracts';

interface FieldMapping {
  nameField: string;
  valueField: string;
}

/**
 * 将 PieChartRecord[] 转换为 ECharts 需要的格式
 */
export function transformDataForECharts(
  records: PieChartRecord[],
  mapping: FieldMapping
): Array<{ name: string; value: number; itemStyle?: { color?: string } }> {
  const { nameField, valueField } = mapping;

  return records.map((record) => {
    const name = String((record as any)[nameField] || record.name);
    const value = Number((record as any)[valueField] || record.value);

    const result: { name: string; value: number; itemStyle?: { color?: string } } = {
      name,
      value,
    };

    // 如果有自定义颜色，添加 itemStyle
    if (record.color) {
      result.itemStyle = { color: record.color };
    }

    return result;
  });
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
import PieChart from './PieChart/PieChart.vue';

export const PanelComponents = {
  ListPanel: () => import('./ListPanel/ListPanel.vue'),
  StatisticCard: () => import('./StatisticCard/StatisticCard.vue'),
  LineChart: () => import('./LineChart/LineChart.vue'),
  BarChart: () => import('./BarChart/BarChart.vue'),
  PieChart,  // 新增
  Table: () => import('./Table/Table.vue'),
  FallbackRichText: () => import('./FallbackRichText/FallbackRichText.vue'),
};
```

---

## 8. 测试用例

```typescript
// frontend/src/features/panel/components/PieChart/__tests__/PieChart.spec.ts
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import PieChart from '../PieChart.vue';
import type { PieChartRecord } from '@/shared/types/panelContracts';

describe('PieChart', () => {
  const mockData: PieChartRecord[] = [
    { id: '1', name: 'Python', value: 1234, color: '#3776ab' },
    { id: '2', name: 'JavaScript', value: 2100, color: '#f7df1e' },
    { id: '3', name: 'Rust', value: 999, color: '#dea584' },
    { id: '4', name: 'Go', value: 876, color: '#00add8' },
  ];

  it('renders chart with data', () => {
    const wrapper = mount(PieChart, {
      props: {
        id: 'test-chart',
        data: { items: mockData, schema: {}, stats: {} },
        props: { nameField: 'name', valueField: 'value' },
        title: '编程语言项目分布',
      },
    });

    expect(wrapper.text()).toContain('编程语言项目分布');
  });

  it('shows empty state when no data', () => {
    const wrapper = mount(PieChart, {
      props: {
        id: 'test-chart',
        data: { items: [], schema: {}, stats: {} },
        props: { nameField: 'name', valueField: 'value' },
      },
    });

    expect(wrapper.text()).toContain('暂无数据');
  });

  it('renders donut chart when donut option is true', () => {
    const wrapper = mount(PieChart, {
      props: {
        id: 'test-chart',
        data: { items: mockData, schema: {}, stats: {} },
        props: { nameField: 'name', valueField: 'value' },
        options: { donut: true },
      },
    });

    // 检查组件是否成功渲染
    expect(wrapper.exists()).toBe(true);
  });
});
```

---

## 9. 后端适配器示例

```python
@route_adapter("/github/languages/stats", manifest=LANGUAGES_MANIFEST)
def github_languages_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    """GitHub 各语言项目占比"""
    # 假设数据源提供了各语言的项目数量
    language_stats = [
        {"language": "Python", "count": 1234, "color": "#3776ab"},
        {"language": "JavaScript", "count": 2100, "color": "#f7df1e"},
        {"language": "Rust", "count": 999, "color": "#dea584"},
        {"language": "Go", "count": 876, "color": "#00add8"},
        {"language": "TypeScript", "count": 1567, "color": "#3178c6"},
    ]

    pie_chart_records = []
    total = sum(item["count"] for item in language_stats)

    for idx, item in enumerate(language_stats, start=1):
        percentage = (item["count"] / total * 100) if total > 0 else 0
        pie_chart_records.append({
            "id": f"lang-{idx}",
            "name": item["language"],
            "value": item["count"],
            "color": item.get("color"),
            "tooltip": f"{item['language']}: {item['count']:,} projects ({percentage:.1f}%)",
        })

    validated = validate_records("PieChart", pie_chart_records)

    return RouteAdapterResult(
        records=validated,
        block_plans=[
            AdapterBlockPlan(
                component_id="PieChart",
                props={"name_field": "name", "value_field": "value"},
                options={"donut": False, "show_legend": True, "show_label": True, "span": 12},
                title="GitHub 各语言项目分布",
                confidence=0.90,
            )
        ],
        stats={"total_projects": total, "language_count": len(language_stats)},
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
- [x] componentManifest 更新

### 前端部分 ⏳ 待实现
- [ ] 安装 shadcn-vue（如果尚未安装）
- [ ] 安装 ECharts 和 vue-echarts（如果尚未安装）
- [ ] 实现 PieChart.vue 组件
- [ ] 实现 usePieChart.ts 逻辑
- [ ] 数据转换工具
- [ ] 单元测试
- [ ] 集成到面板系统

---

## 11. 使用场景示例

### 场景 1: 编程语言占比
```json
[
  { "id": "1", "name": "Python", "value": 1234, "color": "#3776ab" },
  { "id": "2", "name": "JavaScript", "value": 2100, "color": "#f7df1e" },
  { "id": "3", "name": "Rust", "value": 999, "color": "#dea584" }
]
```

### 场景 2: 流量来源分布
```json
[
  { "id": "1", "name": "搜索引擎", "value": 4532 },
  { "id": "2", "name": "直接访问", "value": 3210 },
  { "id": "3", "name": "社交媒体", "value": 2876 },
  { "id": "4", "name": "外部链接", "value": 1543 }
]
```

### 场景 3: 用户地域分布（环形图）
```json
[
  { "id": "1", "name": "中国", "value": 12345 },
  { "id": "2", "name": "美国", "value": 8765 },
  { "id": "3", "name": "日本", "value": 5432 },
  { "id": "4", "name": "其他", "value": 3210 }
]
```
配置：`options: { donut: true }`

---

## 附录：参考资源

- **shadcn-vue 官方文档**: https://www.shadcn-vue.com/
- **ECharts 官方文档**: https://echarts.apache.org/zh/index.html
- **vue-echarts 文档**: https://github.com/ecomfe/vue-echarts
- **ECharts 饼图示例**: https://echarts.apache.org/examples/zh/index.html#chart-type-pie
- **ECharts 环形图示例**: https://echarts.apache.org/examples/zh/editor.html?c=pie-doughnut
