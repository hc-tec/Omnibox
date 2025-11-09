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

      <VChart
        v-else
        ref="chartRef"
        :option="chartOption"
        class="h-[320px] w-full"
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

const nameField = getProp('name_field', 'name');
const valueField = getProp('value_field', 'value');

// 图表选项
const roseType = getOption<false | 'radius' | 'area'>('rose_type', false); // false | 'radius' | 'area'
const radius = getOption<string | [string, string]>('radius', '50%'); // '50%' | ['40%', '70%'] for donut
const showLabel = getOption('show_label', true);
const colors = getOption<string[] | null>('colors', null);

const chartOption = computed<EChartsOption>(() => {
  if (isEmpty.value) return {};

  // 转换数据为 {name, value} 格式
  const pieData = items.map((record) => {
    const name = String((record as any)[nameField] || record.name || '未知');
    const value = Number((record as any)[valueField] || record.value || 0);
    return { name, value };
  });

  // 按值排序（从大到小）
  pieData.sort((a, b) => b.value - a.value);

  return {
    color: colors || undefined,
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const percent = params.percent.toFixed(1);
        return `${params.marker} ${params.name}<br/>数量: ${params.value.toLocaleString()} (${percent}%)`;
      },
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
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
        radius: radius,
        roseType: roseType || undefined,
        data: pieData,
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
            const percent = params.percent.toFixed(1);
            return `{b}: {d}%`;
          },
        },
        labelLine: {
          show: showLabel,
        },
      },
    ],
  };
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
</script>
