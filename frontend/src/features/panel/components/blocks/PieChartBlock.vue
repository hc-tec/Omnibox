<template>
  <Card>
    <CardHeader v-if="block.title">
      <CardTitle>{{ block.title }}</CardTitle>
      <CardDescription v-if="dataBlock?.stats?.description">
        {{ dataBlock.stats.description }}
      </CardDescription>
    </CardHeader>

    <CardContent>
      <div v-if="isEmpty" class="flex h-[320px] items-center justify-center text-muted-foreground">
        暂无数据
      </div>

      <div v-else class="chart-container" style="height: 320px; min-height: 320px; width: 100%; min-width: 280px;">
        <VChart
          v-if="isReady"
          ref="chartRef"
          :key="chartKey"
          :option="chartOption"
          :update-options="{ notMerge: true }"
          :init-options="{ renderer: 'canvas' }"
          style="height: 100%; width: 100%;"
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
import { PieChart } from 'echarts/charts';
import {
  TitleComponent,
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
use([CanvasRenderer, PieChart, TitleComponent, TooltipComponent, LegendComponent]);

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
const nameField = computed(() => {
  return (props.block.props['nameField'] ?? props.block.props['name_field'] ?? 'name') as string;
});

const valueField = computed(() => {
  return (props.block.props['valueField'] ?? props.block.props['value_field'] ?? 'value') as string;
});

// 图表选项（响应式）
const roseType = computed(() => {
  return (props.block.options?.roseType ?? props.block.options?.['rose_type'] ?? false) as false | 'radius' | 'area';
});

const radius = computed(() => {
  return (props.block.options?.radius ?? props.block.options?.['radius'] ?? '50%') as string | [string, string];
});

const showLabel = computed(() => {
  return (props.block.options?.showLabel ?? props.block.options?.['show_label'] ?? true) as boolean;
});

// 默认饼图颜色调色板
const DEFAULT_PIE_COLORS = [
  '#5470c6', // 蓝色
  '#91cc75', // 绿色
  '#fac858', // 黄色
  '#ee6666', // 红色
  '#73c0de', // 浅蓝
  '#3ba272', // 深绿
  '#fc8452', // 橙色
  '#9a60b4', // 紫色
  '#ea7ccc', // 粉色
];

const colors = computed(() => {
  return (props.block.options?.colors ?? props.block.options?.['colors'] ?? DEFAULT_PIE_COLORS) as string[];
});

const chartOption = computed<EChartsOption>(() => {
  if (isEmpty.value) return {};

  const nameKey = nameField.value;
  const valueKey = valueField.value;

  // 转换数据为 {name, value} 格式
  const pieData = items.value.map((record) => {
    const name = String((record as any)[nameKey] ?? (record as any).name ?? '未知');
    const value = Number((record as any)[valueKey] ?? (record as any).value ?? 0);
    return { name, value };
  });

  // 按值排序（从大到小）
  pieData.sort((a, b) => b.value - a.value);

  return {
    color: colors.value,
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const percent = params.percent.toFixed(1);
        return `${params.marker} ${params.name}<br/>数量: ${params.value.toLocaleString()} (${percent}%)`;
      },
    },
    legend: {
      orient: 'horizontal',
      bottom: '5%',
      left: 'center',
      type: 'scroll', // 支持滚动，避免图例过多时溢出
      formatter: (name: string) => {
        const item = pieData.find((d) => d.name === name);
        if (item) {
          return `${name}: ${item.value.toLocaleString()}`;
        }
        return name;
      },
    },
    series: [
      {
        type: 'pie',
        radius: radius.value,
        center: ['50%', '45%'], // 居中，稍微上移给底部图例留空间
        roseType: roseType.value || undefined,
        data: pieData,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
        label: {
          show: showLabel.value,
          formatter: '{b}: {d}%',
        },
        labelLine: {
          show: showLabel.value,
        },
      },
    ],
  };
});

// 监听 chartOption 变化，手动刷新图表
watch(chartOption, (newOption) => {
  if (chartRef.value && newOption && Object.keys(newOption).length > 0) {
    nextTick(() => {
      chartRef.value?.setOption(newOption, { notMerge: true });
      chartRef.value?.resize();
    });
  }
}, { deep: true });

// 响应式调整
let resizeObserver: ResizeObserver | null = null;

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
