<template>
  <Card>
    <CardHeader v-if="block.title">
      <CardTitle>{{ block.title }}</CardTitle>
      <CardDescription v-if="dataBlock?.stats?.description">
        {{ dataBlock.stats.description }}
      </CardDescription>
    </CardHeader>

    <CardContent>
      <div v-if="isEmpty" class="flex h-[280px] items-center justify-center text-muted-foreground">
        暂无数据
      </div>

      <VChart
        v-else
        ref="chartRef"
        :option="chartOption"
        class="h-[280px] w-full"
        autoresize
      />
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
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
import type { ComponentAbility } from '@/shared/componentManifest';
import type { UIBlock, DataBlock } from '@/shared/types/panel';
import type { EChartsOption } from 'echarts';

// 注册 ECharts 组件
use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent]);

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const chartRef = ref<InstanceType<typeof VChart>>();

const items = (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];

const isEmpty = computed(() => {
  return items.length === 0;
});

function getProp(key: string, fallback: string): string {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[key] ?? fallback) as string;
}

function getOption<T>(key: string, fallback: T): T {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.options?.[camel] ?? props.block.options?.[key] ?? fallback) as T;
}

const xField = getProp('x_field', 'x');
const yField = getProp('y_field', 'y');
const seriesField = getProp('series_field', 'series');

// 图表选项
const orientation = getOption('orientation', 'vertical'); // vertical | horizontal
const stacked = getOption('stacked', false);
const showLabel = getOption('show_label', false);
const barWidth = getOption('bar_width', null);
const colors = getOption<string[] | null>('colors', null);

const chartOption = computed<EChartsOption>(() => {
  if (isEmpty.value) return {};

  // 转换数据
  const { xAxisData, seriesData, seriesList } = transformData();

  const isHorizontal = orientation === 'horizontal';

  const series = seriesList.map((seriesName) => ({
    name: seriesName,
    type: 'bar' as const,
    data: seriesData[seriesName],
    stack: stacked ? 'total' : undefined,
    barWidth: barWidth || undefined,
    label: {
      show: showLabel,
      position: stacked ? 'inside' : 'top',
      formatter: (params: any) => {
        return params.value.toLocaleString();
      },
    },
    emphasis: {
      focus: 'series' as const,
    },
  }));

  const baseOption: EChartsOption = {
    color: colors || undefined,
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
    series,
  };

  if (isHorizontal) {
    // 横向柱状图
    return {
      ...baseOption,
      xAxis: {
        type: 'value',
        axisLabel: {
          formatter: (value: number) => value.toLocaleString(),
        },
      },
      yAxis: {
        type: 'category',
        data: xAxisData,
        axisLabel: {
          rotate: xAxisData.length > 10 ? 45 : 0,
        },
      },
    };
  } else {
    // 纵向柱状图
    return {
      ...baseOption,
      xAxis: {
        type: 'category',
        data: xAxisData,
        axisLabel: {
          rotate: xAxisData.length > 10 ? 45 : 0,
        },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: (value: number) => value.toLocaleString(),
        },
      },
    };
  }
});

function transformData() {
  const xAxisSet = new Set<string | number>();
  const dataMap = new Map<string, Map<string | number, number>>();

  for (const record of items) {
    const xValue = (record as any)[xField] || record.x;
    const yValue = Number((record as any)[yField] || record.y);
    const seriesValue = (record as any)[seriesField] || record.series || 'default';
    const seriesName = String(seriesValue);

    xAxisSet.add(xValue);

    if (!dataMap.has(seriesName)) {
      dataMap.set(seriesName, new Map());
    }
    dataMap.get(seriesName)!.set(xValue, yValue);
  }

  // 按类目或数值排序 x 轴
  const xAxisData = Array.from(xAxisSet).sort((a, b) => {
    if (typeof a === 'number' && typeof b === 'number') {
      return a - b;
    }
    return String(a).localeCompare(String(b));
  });

  const seriesList = Array.from(dataMap.keys());
  const seriesData: Record<string, number[]> = {};

  for (const [seriesName, dataPointMap] of dataMap.entries()) {
    seriesData[seriesName] = xAxisData.map((x) => dataPointMap.get(x) || 0);
  }

  return { xAxisData, seriesData, seriesList };
}

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
</script>
