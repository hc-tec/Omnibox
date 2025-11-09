# LineChart 组件前端实现指南

> 创建时间：2025-11-09
> 更新时间：2025-11-09
> 状态：✅ 后端契约已完成，等待前端实现
> **技术栈**: Vue 3 + shadcn-vue + ECharts

---

## 1. 组件概述

**LineChart** 是用于展示趋势和时间序列数据的可视化组件，主要用于展示数据随时间的变化。

### 核心特性
- ✅ 基于 ECharts 折线图
- ✅ 使用 shadcn-vue Card 作为容器
- ✅ 支持多序列展示
- ✅ 支持面积图模式
- ✅ 支持时间轴和数值轴
- ✅ Vue 3 Composition API
- ✅ TypeScript 完整支持
- ✅ 响应式设计

---

## 2. 数据契约

### TypeScript 接口（已完成）

```typescript
// frontend/src/shared/types/panelContracts.ts
export interface LineChartRecord {
  id: string;
  x: string | number;  // 横轴值（时间或数值）
  y: number;  // 纵轴数值
  series?: string | null;  // 序列名称
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
interface LineChartProps {
  data: {
    items: LineChartRecord[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {
    xField: string;
    yField: string;
    seriesField?: string;
  };
  options?: {
    areaStyle?: boolean;
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
└── LineChart/
    ├── LineChart.vue       # 主组件
    ├── useLineChart.ts     # ECharts 配置逻辑
    ├── utils.ts            # 数据转换工具
    └── __tests__/
        └── LineChart.spec.ts
```

### 5.2 主组件

```vue
<!-- frontend/src/features/panel/components/LineChart/LineChart.vue -->
<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart as EChartsLine } from 'echarts/charts';
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
import type { LineChartRecord } from '@/shared/types/panelContracts';
import { useLineChartOption } from './useLineChart';

// 注册 ECharts 组件
use([CanvasRenderer, EChartsLine, GridComponent, TooltipComponent, LegendComponent]);

interface Props {
  data: {
    items: LineChartRecord[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {
    xField: string;
    yField: string;
    seriesField?: string;
  };
  options?: {
    areaStyle?: boolean;
    span?: number;
  };
  title?: string;
  id: string;
}

const props = withDefaults(defineProps<Props>(), {
  options: () => ({
    areaStyle: false,
    span: 12,
  }),
});

const chartRef = ref<InstanceType<typeof VChart>>();

// 生成 ECharts 配置
const option = computed(() => {
  return useLineChartOption(
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
// frontend/src/features/panel/components/LineChart/useLineChart.ts
import type { EChartsOption } from 'echarts';
import type { LineChartRecord } from '@/shared/types/panelContracts';
import { transformDataForECharts, getSeriesList, isTimeAxis } from './utils';

interface FieldMapping {
  xField: string;
  yField: string;
  seriesField?: string;
}

interface ChartOptions {
  areaStyle?: boolean;
  span?: number;
}

export function useLineChartOption(
  records: LineChartRecord[],
  mapping: FieldMapping,
  options: ChartOptions = {}
): EChartsOption {
  const { areaStyle = false } = options;

  // 转换数据
  const { xAxisData, seriesData } = transformDataForECharts(records, mapping);
  const seriesList = getSeriesList(records, mapping.seriesField);
  const isTime = isTimeAxis(xAxisData);

  // 构建 series 配置
  const series = seriesList.map((seriesName) => ({
    name: seriesName,
    type: 'line',
    data: seriesData[seriesName],
    smooth: true,
    areaStyle: areaStyle ? {} : undefined,
    emphasis: {
      focus: 'series',
    },
  }));

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
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
      type: isTime ? 'time' : 'category',
      data: isTime ? undefined : xAxisData,
      boundaryGap: !areaStyle,
      axisLabel: {
        rotate: xAxisData.length > 10 ? 45 : 0,
      },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (value: number) => {
          return value.toLocaleString();
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
// frontend/src/features/panel/components/LineChart/utils.ts
import type { LineChartRecord } from '@/shared/types/panelContracts';

interface FieldMapping {
  xField: string;
  yField: string;
  seriesField?: string;
}

/**
 * 将 LineChartRecord[] 转换为 ECharts 需要的格式
 */
export function transformDataForECharts(
  records: LineChartRecord[],
  mapping: FieldMapping
): {
  xAxisData: Array<string | number>;
  seriesData: Record<string, number[]>;
} {
  const { xField, yField, seriesField } = mapping;

  // 收集所有 x 轴数据
  const xAxisSet = new Set<string | number>();
  const dataMap = new Map<string, Map<string | number, number>>();

  for (const record of records) {
    const xValue = (record as any)[xField] || record.x;
    const yValue = Number((record as any)[yField] || record.y);
    const seriesValue = seriesField
      ? String((record as any)[seriesField] || 'default')
      : 'default';

    xAxisSet.add(xValue);

    if (!dataMap.has(seriesValue)) {
      dataMap.set(seriesValue, new Map());
    }
    dataMap.get(seriesValue)!.set(xValue, yValue);
  }

  // 按时间或数值排序 x 轴
  const xAxisData = Array.from(xAxisSet).sort((a, b) => {
    // 尝试作为日期比较
    const dateA = new Date(a);
    const dateB = new Date(b);
    if (!isNaN(dateA.getTime()) && !isNaN(dateB.getTime())) {
      return dateA.getTime() - dateB.getTime();
    }
    // 尝试作为数字比较
    if (typeof a === 'number' && typeof b === 'number') {
      return a - b;
    }
    // 字符串比较
    return String(a).localeCompare(String(b));
  });

  const seriesData: Record<string, number[]> = {};

  for (const [seriesName, dataPointMap] of dataMap.entries()) {
    seriesData[seriesName] = xAxisData.map((x) => dataPointMap.get(x) || 0);
  }

  return { xAxisData, seriesData };
}

/**
 * 获取所有唯一的序列名称
 */
export function getSeriesList(
  records: LineChartRecord[],
  seriesField?: string
): string[] {
  if (!seriesField) return ['default'];

  const seriesSet = new Set<string>();
  for (const record of records) {
    const value = (record as any)[seriesField] || record.series || 'default';
    seriesSet.add(String(value));
  }
  return Array.from(seriesSet);
}

/**
 * 判断 x 轴是否为时间轴
 */
export function isTimeAxis(xAxisData: Array<string | number>): boolean {
  if (xAxisData.length === 0) return false;

  // 检查前几个数据点是否为有效日期
  const sampleSize = Math.min(5, xAxisData.length);
  let validDateCount = 0;

  for (let i = 0; i < sampleSize; i++) {
    const value = xAxisData[i];
    const date = new Date(value);
    if (!isNaN(date.getTime())) {
      validDateCount++;
    }
  }

  // 如果大部分样本都是有效日期，则认为是时间轴
  return validDateCount / sampleSize > 0.8;
}
```

---

## 6. 集成到面板系统

```typescript
// frontend/src/features/panel/components/index.ts
import LineChart from './LineChart/LineChart.vue';

export const PanelComponents = {
  ListPanel: () => import('./ListPanel/ListPanel.vue'),
  StatisticCard: () => import('./StatisticCard/StatisticCard.vue'),
  LineChart,  // 更新
  BarChart: () => import('./BarChart/BarChart.vue'),
  PieChart: () => import('./PieChart/PieChart.vue'),
  Table: () => import('./Table/Table.vue'),
  FallbackRichText: () => import('./FallbackRichText/FallbackRichText.vue'),
};
```

---

## 7. 测试用例

```typescript
// frontend/src/features/panel/components/LineChart/__tests__/LineChart.spec.ts
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import LineChart from '../LineChart.vue';
import type { LineChartRecord } from '@/shared/types/panelContracts';

describe('LineChart', () => {
  const mockData: LineChartRecord[] = [
    { id: '1', x: '2024-01-01', y: 100, series: 'Python' },
    { id: '2', x: '2024-01-02', y: 120, series: 'Python' },
    { id: '3', x: '2024-01-03', y: 150, series: 'Python' },
    { id: '4', x: '2024-01-01', y: 80, series: 'JavaScript' },
    { id: '5', x: '2024-01-02', y: 90, series: 'JavaScript' },
    { id: '6', x: '2024-01-03', y: 110, series: 'JavaScript' },
  ];

  it('renders chart with data', () => {
    const wrapper = mount(LineChart, {
      props: {
        id: 'test-chart',
        data: { items: mockData, schema: {}, stats: {} },
        props: { xField: 'x', yField: 'y', seriesField: 'series' },
        title: '语言 Stars 趋势',
      },
    });

    expect(wrapper.text()).toContain('语言 Stars 趋势');
  });

  it('shows empty state when no data', () => {
    const wrapper = mount(LineChart, {
      props: {
        id: 'test-chart',
        data: { items: [], schema: {}, stats: {} },
        props: { xField: 'x', yField: 'y' },
      },
    });

    expect(wrapper.text()).toContain('暂无数据');
  });

  it('renders area chart when areaStyle is true', () => {
    const wrapper = mount(LineChart, {
      props: {
        id: 'test-chart',
        data: { items: mockData, schema: {}, stats: {} },
        props: { xField: 'x', yField: 'y' },
        options: { areaStyle: true },
      },
    });

    expect(wrapper.exists()).toBe(true);
  });
});
```

---

## 8. 后端适配器示例

```python
@route_adapter("/github/trending/weekly", manifest=TRENDING_WEEKLY_MANIFEST)
def github_trending_weekly_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    """GitHub 每周趋势"""
    # 假设数据源提供了每天的 Star 增长数据
    line_chart_records = []

    # 模拟 7 天的数据
    dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07"]
    languages = {
        "Python": [100, 120, 150, 180, 200, 230, 250],
        "JavaScript": [80, 90, 110, 130, 140, 160, 180],
        "Rust": [50, 60, 75, 90, 100, 110, 120],
    }

    for lang, values in languages.items():
        for idx, (date, value) in enumerate(zip(dates, values)):
            line_chart_records.append({
                "id": f"{lang}-{date}",
                "x": date,
                "y": value,
                "series": lang,
                "tooltip": f"{lang} • {date}: {value} stars",
            })

    validated = validate_records("LineChart", line_chart_records)

    return RouteAdapterResult(
        records=validated,
        block_plans=[
            AdapterBlockPlan(
                component_id="LineChart",
                props={"x_field": "x", "y_field": "y", "series_field": "series"},
                options={"area_style": False, "span": 12},
                title="GitHub 语言趋势（7天）",
                confidence=0.90,
            )
        ],
        stats={"total_records": len(validated)},
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
- [ ] 安装 ECharts 和 vue-echarts（如果尚未安装）
- [ ] 实现 LineChart.vue 组件
- [ ] 实现 useLineChart.ts 逻辑
- [ ] 数据转换工具
- [ ] 单元测试
- [ ] 集成到面板系统

---

## 10. 使用场景示例

### 场景 1: GitHub Stars 趋势
```json
[
  { "id": "1", "x": "2024-01-01", "y": 100, "series": "Python" },
  { "id": "2", "x": "2024-01-02", "y": 120, "series": "Python" },
  { "id": "3", "x": "2024-01-03", "y": 150, "series": "Python" }
]
```

### 场景 2: 访问量趋势（面积图）
```json
[
  { "id": "1", "x": "2024-01-01", "y": 1234 },
  { "id": "2", "x": "2024-01-02", "y": 2345 },
  { "id": "3", "x": "2024-01-03", "y": 3456 }
]
```
配置：`options: { areaStyle: true }`

### 场景 3: 多指标对比
```json
[
  { "id": "1", "x": "2024-01", "y": 100, "series": "收入" },
  { "id": "2", "x": "2024-01", "y": 80, "series": "成本" },
  { "id": "3", "x": "2024-02", "y": 120, "series": "收入" },
  { "id": "4", "x": "2024-02", "y": 85, "series": "成本" }
]
```

---

## 附录：参考资源

- **shadcn-vue 官方文档**: https://www.shadcn-vue.com/
- **ECharts 官方文档**: https://echarts.apache.org/zh/index.html
- **vue-echarts 文档**: https://github.com/ecomfe/vue-echarts
- **ECharts 折线图示例**: https://echarts.apache.org/examples/zh/index.html#chart-type-line
- **ECharts 面积图示例**: https://echarts.apache.org/examples/zh/editor.html?c=area-basic
