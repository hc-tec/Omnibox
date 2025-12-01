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

      <div v-else class="chart-container h-[280px] w-full">
        <VChart
          v-if="isReady"
          ref="chartRef"
          :key="chartKey"
          :option="chartOption"
          :update-options="{ notMerge: true }"
          :init-options="{ renderer: 'canvas' }"
          class="h-full w-full"
          autoresize
        />
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, nextTick, watch } from 'vue';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
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
use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent]);

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const chartRef = ref<InstanceType<typeof VChart>>();

// 延迟渲染标志，确保 DOM 准备好后再渲染图表
const isReady = ref(false);

// 响应式数据源：当 props.data 或 props.dataBlock 变化时自动更新
const items = computed(() =>
  (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? []
);

const isEmpty = computed(() => {
  return items.value.length === 0;
});

// 用于强制 VChart 重新渲染的 key
const chartKey = computed(() => {
  return `chart-${items.value.length}-${JSON.stringify(items.value.slice(0, 1))}`;
});

// 响应式获取 props（确保 props 更新时能正确响应）
const xField = computed(() => {
  return (props.block.props['xField'] ?? props.block.props['x_field'] ?? 'x') as string;
});

const yField = computed(() => {
  return (props.block.props['yField'] ?? props.block.props['y_field'] ?? 'y') as string;
});

const seriesField = computed(() => {
  return (props.block.props['seriesField'] ?? props.block.props['series_field'] ?? 'series') as string;
});

const chartOption = computed<EChartsOption>(() => {
  if (isEmpty.value) return {};

  // 转换数据
  const { xAxisData, seriesData, seriesList } = transformData();

  // 判断是否为时间轴
  const isTime = isTimeAxis(xAxisData);

  const defaultColors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de'];
  const series = seriesList.map((seriesName, index) => ({
    name: seriesName,
    type: 'line' as const,
    data: seriesData[seriesName],
    smooth: true,
    itemStyle: {
      color: defaultColors[index % defaultColors.length],
    },
    lineStyle: {
      color: defaultColors[index % defaultColors.length],
    },
    areaStyle: props.block.options?.area_style ? {} : undefined,
    emphasis: {
      focus: 'series' as const,
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
      boundaryGap: false,
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
});

function transformData() {
  const xAxisSet = new Set<string | number>();
  const dataMap = new Map<string, Map<string | number, number>>();

  const xKey = xField.value;
  const yKey = yField.value;
  const seriesKey = seriesField.value;

  for (const record of items.value) {
    const xValue = (record as any)[xKey] ?? (record as any).x;
    const yValue = Number((record as any)[yKey] ?? (record as any).y ?? 0);
    const seriesValue = (record as any)[seriesKey] ?? (record as any).series ?? 'default';
    const seriesName = String(seriesValue);

    xAxisSet.add(xValue);

    if (!dataMap.has(seriesName)) {
      dataMap.set(seriesName, new Map());
    }
    dataMap.get(seriesName)!.set(xValue, yValue);
  }

  // 按时间或数值排序 x 轴
  const xAxisData = Array.from(xAxisSet).sort((a, b) => {
    const dateA = new Date(a);
    const dateB = new Date(b);
    if (!isNaN(dateA.getTime()) && !isNaN(dateB.getTime())) {
      return dateA.getTime() - dateB.getTime();
    }
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

function isTimeAxis(xAxisData: Array<string | number>): boolean {
  if (xAxisData.length === 0) return false;

  const sampleSize = Math.min(5, xAxisData.length);
  let validDateCount = 0;

  for (let i = 0; i < sampleSize; i++) {
    const value = xAxisData[i];
    const date = new Date(value);
    if (!isNaN(date.getTime())) {
      validDateCount++;
    }
  }

  return validDateCount / sampleSize > 0.8;
}

// 响应式调整
let resizeObserver: ResizeObserver | null = null;

// 监听 chartOption 变化，手动刷新图表
watch(chartOption, (newOption) => {
  if (chartRef.value && newOption && Object.keys(newOption).length > 0) {
    nextTick(() => {
      chartRef.value?.setOption(newOption, { notMerge: true });
      chartRef.value?.resize();
    });
  }
}, { deep: true });

onMounted(() => {
  // 使用 nextTick 确保 DOM 完全渲染后再标记为就绪
  nextTick(() => {
    isReady.value = true;

    // 再等一个 tick 确保 VChart 挂载后设置 ResizeObserver
    nextTick(() => {
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
  });
});

onUnmounted(() => {
  resizeObserver?.disconnect();
});
</script>
