<template>
  <Card class="overflow-hidden">
    <CardHeader class="pb-2">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div
            class="w-8 h-8 rounded-lg flex items-center justify-center"
            :class="getStatusBgClass(currentStatus)"
          >
            <svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <CardTitle class="text-base">{{ displayName }}</CardTitle>
        </div>
        <!-- 当前状态指示器 -->
        <div class="text-right">
          <div class="flex items-center gap-1.5 justify-end">
            <span class="w-2 h-2 rounded-full" :class="getStatusDotClass(currentStatus)"></span>
            <span class="text-sm font-medium" :class="getStatusTextClass(currentStatus)">
              {{ getStatusLabel(currentStatus) }}
            </span>
          </div>
          <div v-if="lastCheckTimeDisplay" class="text-xs text-muted-foreground mt-0.5">
            {{ lastCheckTimeDisplay }}
          </div>
          <div v-if="currentMetricValue !== null" class="text-xs text-muted-foreground/70">
            {{ currentMetricValue }}{{ metricUnit }}
          </div>
        </div>
      </div>
    </CardHeader>

    <CardContent class="pt-2">
      <!-- 状态时间线 -->
      <div class="mt-2">
        <div class="flex items-center justify-between text-xs text-muted-foreground mb-1">
          <span>{{ timelineStartLabel }}</span>
          <span>{{ timelineEndLabel }}</span>
        </div>
        <div class="flex gap-0.5 h-6">
          <TooltipProvider>
            <Tooltip v-for="(item, index) in historyBars" :key="index">
              <TooltipTrigger as-child>
                <div
                  class="flex-1 rounded-sm cursor-pointer transition-all hover:opacity-80 hover:scale-y-110"
                  :class="getStatusBgClass(getItemStatus(item))"
                ></div>
              </TooltipTrigger>
              <TooltipContent
                side="top"
                :side-offset="8"
                class="max-w-xs p-3 space-y-2"
              >
                <!-- Tooltip 头部：时间戳 -->
                <div class="space-y-0.5">
                  <div class="text-sm font-medium">{{ getItemField(item, 'timestamp') || '—' }}</div>
                  <!-- 主要指标 -->
                  <div
                    v-for="metric in primaryMetrics"
                    :key="metric.field"
                    class="font-semibold"
                    :class="getStatusTextClass(getItemStatus(item))"
                  >
                    {{ metric.label }}: {{ formatMetricValue(getItemField(item, metric.field), metric) }}
                  </div>
                </div>

                <!-- 状态计数 -->
                <div v-if="statusCountFields.length > 0" class="space-y-1 text-sm">
                  <div
                    v-for="countConfig in statusCountFields"
                    :key="countConfig.field"
                    class="flex items-center justify-between gap-6"
                  >
                    <div class="flex items-center gap-2">
                      <span class="w-2 h-2 rounded-full" :class="getStatusDotClass(countConfig.status)"></span>
                      <span>{{ countConfig.label }}</span>
                    </div>
                    <span class="font-medium">
                      {{ getItemField(item, countConfig.field) || 0 }} {{ countConfig.unit || '次' }}
                    </span>
                  </div>
                </div>

                <!-- 详情细分 -->
                <div
                  v-if="detailsField && getItemField(item, detailsField) && Object.keys(getItemField(item, detailsField) as object).length > 0"
                  class="pt-1 border-t border-border/50"
                >
                  <div class="flex items-center gap-2 mb-1">
                    <span class="w-2 h-2 rounded-full bg-muted-foreground/60"></span>
                    <span class="text-xs text-muted-foreground">{{ detailsLabel }}</span>
                  </div>
                  <div
                    v-for="(count, reason) in (getItemField(item, detailsField) as Record<string, number>)"
                    :key="reason"
                    class="flex items-center justify-between text-xs ml-4"
                  >
                    <span class="text-muted-foreground">• {{ getDetailLabel(reason as string) }}</span>
                    <span>{{ count }}</span>
                  </div>
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { UIBlock, DataBlock, ComponentAbility } from '@/shared/types/panel';

// ============ 类型定义 ============

interface StatusConfig {
  value: string;        // 状态值，如 'available'
  label: string;        // 显示标签，如 '可用'
  color: string;        // 颜色键名，如 'success', 'warning', 'error'
}

interface MetricConfig {
  field: string;        // 数据字段名
  label: string;        // 显示标签
  unit?: string;        // 单位，如 'ms', '%'
  decimals?: number;    // 小数位数
}

interface StatusCountConfig {
  field: string;        // 字段名，如 'available_count'
  status: string;       // 对应的状态值，用于颜色
  label: string;        // 显示标签
  unit?: string;        // 单位，默认 '次'
}

interface Props {
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}

const props = defineProps<Props>();

// ============ 配置获取 ============

function getProp<T>(key: string, fallback: T): T {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  const val = props.block.props?.[camel] ?? props.block.props?.[key];
  return (val !== undefined ? val : fallback) as T;
}

// 颜色映射表（预定义所有可能的颜色类，确保 Tailwind JIT 能识别）
const COLOR_MAP: Record<string, { bg600: string; bg500: string; text500: string }> = {
  success: { bg600: 'bg-emerald-600', bg500: 'bg-emerald-500', text500: 'text-emerald-500' },
  warning: { bg600: 'bg-amber-600', bg500: 'bg-amber-500', text500: 'text-amber-500' },
  error: { bg600: 'bg-red-600', bg500: 'bg-red-500', text500: 'text-red-500' },
  info: { bg600: 'bg-blue-600', bg500: 'bg-blue-500', text500: 'text-blue-500' },
  neutral: { bg600: 'bg-slate-600', bg500: 'bg-slate-500', text500: 'text-slate-500' },
  purple: { bg600: 'bg-purple-600', bg500: 'bg-purple-500', text500: 'text-purple-500' },
  cyan: { bg600: 'bg-cyan-600', bg500: 'bg-cyan-500', text500: 'text-cyan-500' },
  pink: { bg600: 'bg-pink-600', bg500: 'bg-pink-500', text500: 'text-pink-500' },
};

// 默认状态配置
const DEFAULT_STATUSES: StatusConfig[] = [
  { value: 'available', label: '可用', color: 'success' },
  { value: 'fluctuation', label: '波动', color: 'warning' },
  { value: 'unavailable', label: '不可用', color: 'error' },
];

// 默认主要指标
const DEFAULT_PRIMARY_METRICS: MetricConfig[] = [
  { field: 'availability_rate', label: '可用率', unit: '%', decimals: 2 },
  { field: 'latency_ms', label: '延迟', unit: 'ms', decimals: 0 },
];

// 默认状态计数配置
const DEFAULT_STATUS_COUNTS: StatusCountConfig[] = [
  { field: 'available_count', status: 'available', label: '可用', unit: '次' },
  { field: 'fluctuation_count', status: 'fluctuation', label: '波动', unit: '次' },
  { field: 'unavailable_count', status: 'unavailable', label: '不可用', unit: '次' },
];

// 默认详情标签映射
const DEFAULT_DETAIL_LABELS: Record<string, string> = {
  slow_response: '响应慢',
  timeout: '超时',
  error: '错误',
  high_latency: '高延迟',
  partial_failure: '部分失败',
};

// ============ 配置项 ============

// 状态配置
const statusConfigs = computed<StatusConfig[]>(() =>
  getProp('statuses', DEFAULT_STATUSES)
);

// 字段映射
const nameField = computed(() => getProp('name_field', 'name'));
const statusField = computed(() => getProp('status_field', 'current_status'));
const historyField = computed(() => getProp('history_field', 'history'));
const timestampField = computed(() => getProp('timestamp_field', 'last_check_time'));
const metricField = computed(() => getProp('metric_field', 'current_latency_ms'));
const itemStatusField = computed(() => getProp('item_status_field', 'status'));

// 指标配置
const primaryMetrics = computed<MetricConfig[]>(() =>
  getProp('primary_metrics', DEFAULT_PRIMARY_METRICS)
);
const statusCountFields = computed<StatusCountConfig[]>(() =>
  getProp('status_counts', DEFAULT_STATUS_COUNTS)
);
const metricUnit = computed(() => getProp('metric_unit', 'ms'));

// 详情配置
const detailsField = computed(() => getProp('details_field', 'fluctuation_details'));
const detailsLabel = computed(() => getProp('details_label', '详情细分'));
const detailLabels = computed<Record<string, string>>(() =>
  getProp('detail_labels', DEFAULT_DETAIL_LABELS)
);

// 时间线标签
const timelineStartLabel = computed(() => getProp('timeline_start_label', '近24小时'));
const timelineEndLabel = computed(() => getProp('timeline_end_label', '现在'));

// 示例数据配置
const sampleBarCount = computed(() => getProp('sample_bar_count', 48));
const sampleIntervalMinutes = computed(() => getProp('sample_interval_minutes', 30));

// ============ 数据获取 ============

const rawData = computed(() => {
  const items = (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];
  return items[0] ?? props.data ?? {};
});

const displayName = computed(() =>
  (rawData.value[nameField.value] as string) ?? props.block.title ?? '服务状态'
);

const currentStatus = computed(() =>
  (rawData.value[statusField.value] as string) ?? statusConfigs.value[0]?.value ?? 'available'
);

const currentMetricValue = computed(() => {
  const val = rawData.value[metricField.value];
  return val !== undefined ? val as number : null;
});

const lastCheckTimeDisplay = computed(() => {
  const time = rawData.value[timestampField.value] as string;
  if (!time) return '';
  try {
    const date = new Date(time);
    return `${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  } catch {
    return time;
  }
});

const historyBars = computed(() => {
  const history = rawData.value[historyField.value] as Record<string, unknown>[];
  if (history && history.length > 0) {
    return history;
  }
  return generateSampleHistory();
});

// ============ 辅助函数 ============

function getItemField(item: Record<string, unknown>, field: string): unknown {
  return item[field];
}

function getItemStatus(item: Record<string, unknown>): string {
  return (item[itemStatusField.value] as string) ?? statusConfigs.value[0]?.value ?? 'available';
}

function formatMetricValue(value: unknown, config: MetricConfig): string {
  if (value === undefined || value === null) return '—';
  const num = Number(value);
  if (isNaN(num)) return String(value);
  const formatted = config.decimals !== undefined ? num.toFixed(config.decimals) : String(num);
  return config.unit ? `${formatted}${config.unit}` : formatted;
}

function getDetailLabel(reason: string): string {
  return detailLabels.value[reason] ?? reason;
}

// ============ 状态样式 ============

function findStatusConfig(status: string): StatusConfig | undefined {
  return statusConfigs.value.find(s => s.value === status);
}

function getColorClasses(colorKey: string): { bg600: string; bg500: string; text500: string } {
  return COLOR_MAP[colorKey] ?? { bg600: 'bg-muted', bg500: 'bg-muted-foreground', text500: 'text-muted-foreground' };
}

function getStatusBgClass(status: string): string {
  const config = findStatusConfig(status);
  if (!config) return 'bg-muted';
  return getColorClasses(config.color).bg600;
}

function getStatusDotClass(status: string): string {
  const config = findStatusConfig(status);
  if (!config) return 'bg-muted-foreground';
  return getColorClasses(config.color).bg500;
}

function getStatusTextClass(status: string): string {
  const config = findStatusConfig(status);
  if (!config) return 'text-muted-foreground';
  return getColorClasses(config.color).text500;
}

function getStatusLabel(status: string): string {
  const config = findStatusConfig(status);
  return config?.label ?? '未知';
}

// ============ 示例数据生成 ============

function generateSampleHistory(): Record<string, unknown>[] {
  const bars: Record<string, unknown>[] = [];
  const now = new Date();
  const statuses = statusConfigs.value;
  const defaultStatus = statuses[0]?.value ?? 'available';
  const warningStatus = statuses.length > 1 ? statuses[1]?.value : defaultStatus;
  const errorStatus = statuses.length > 2 ? statuses[2]?.value : warningStatus;

  for (let i = sampleBarCount.value - 1; i >= 0; i--) {
    const time = new Date(now.getTime() - i * sampleIntervalMinutes.value * 60 * 1000);
    const rand = Math.random();

    let status = defaultStatus;
    if (rand > 0.95) {
      status = errorStatus;
    } else if (rand > 0.85) {
      status = warningStatus;
    }

    const item: Record<string, unknown> = {
      [itemStatusField.value]: status,
      timestamp: time.toLocaleString('zh-CN'),
    };

    // 生成主要指标的示例数据
    primaryMetrics.value.forEach(metric => {
      if (metric.field === 'availability_rate') {
        item[metric.field] = status === defaultStatus ? 99 + Math.random() :
                            status === warningStatus ? 95 + Math.random() * 4 :
                            80 + Math.random() * 15;
      } else if (metric.field.includes('latency') || metric.field.includes('ms')) {
        item[metric.field] = Math.floor(Math.random() * 2000) + 100;
      } else {
        item[metric.field] = Math.floor(Math.random() * 100);
      }
    });

    // 生成状态计数的示例数据
    statusCountFields.value.forEach(countConfig => {
      if (countConfig.status === status) {
        item[countConfig.field] = Math.floor(Math.random() * 5) + 1;
      } else if (countConfig.status === defaultStatus) {
        item[countConfig.field] = Math.floor(Math.random() * 10) + 5;
      } else {
        item[countConfig.field] = status === errorStatus ? Math.floor(Math.random() * 2) : 0;
      }
    });

    // 生成详情数据（仅非正常状态）
    if (status !== defaultStatus && detailsField.value) {
      const details: Record<string, number> = {};
      const detailKeys = Object.keys(detailLabels.value);
      if (detailKeys.length > 0 && Math.random() > 0.5) {
        const randomKey = detailKeys[Math.floor(Math.random() * detailKeys.length)];
        details[randomKey] = Math.floor(Math.random() * 3) + 1;
      }
      if (Object.keys(details).length > 0) {
        item[detailsField.value] = details;
      }
    }

    bars.push(item);
  }

  return bars;
}
</script>

<style scoped>
/* 动态 Tailwind 类需要在此确保被包含 */
</style>
