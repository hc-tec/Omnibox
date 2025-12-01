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

// 响应式获取 props 和 options（确保 props 更新时能正确响应）
const xField = computed(() => {
  const camel = 'xField';
  return (props.block.props[camel] ?? props.block.props['x_field'] ?? 'x') as string;
});

const yField = computed(() => {
  const camel = 'yField';
  return (props.block.props[camel] ?? props.block.props['y_field'] ?? 'y') as string;
});

const seriesField = computed(() => {
  const camel = 'seriesField';
  return (props.block.props[camel] ?? props.block.props['series_field'] ?? 'series') as string;
});

// 图表选项（响应式）
const orientation = computed(() => {
  return (props.block.options?.orientation ?? props.block.options?.['orientation'] ?? 'vertical') as string;
});

const stacked = computed(() => {
  return (props.block.options?.stacked ?? props.block.options?.['stacked'] ?? false) as boolean;
});

const showLabel = computed(() => {
  return (props.block.options?.showLabel ?? props.block.options?.['show_label'] ?? false) as boolean;
});

const barWidth = computed(() => {
  return (props.block.options?.barWidth ?? props.block.options?.['bar_width'] ?? null) as string | number | null;
});

const colors = computed(() => {
  return (props.block.options?.colors ?? props.block.options?.['colors'] ?? null) as string[] | null;
});

const chartOption = computed<EChartsOption>(() => {
  if (isEmpty.value) return {};

  // 转换数据
  const { xAxisData, seriesData, seriesList } = transformData();


  const isHorizontal = orientation.value === 'horizontal';

  const series = seriesList.map((seriesName, index) => ({
    name: seriesName,
    type: 'bar' as const,
    data: seriesData[seriesName],
    stack: stacked.value ? 'total' : undefined,
    barWidth: barWidth.value || 'auto',
    itemStyle: {
      color: colors.value?.[index] || '#5470c6',
    },
    label: {
      show: showLabel.value,
      position: (stacked.value ? 'inside' : 'top') as 'inside' | 'top',
      formatter: (params: any) => {
        return params.value.toLocaleString();
      },
    },
    emphasis: {
      focus: 'series' as const,
    },
  }));

  const baseOption: EChartsOption = {
    color: colors.value || undefined,
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
    const option = {
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
    return option;
  }
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
        // 初始化时也手动设置一次
        chart?.resize();
      }
    });
  });
});

onUnmounted(() => {
  resizeObserver?.disconnect();
});
</script>
