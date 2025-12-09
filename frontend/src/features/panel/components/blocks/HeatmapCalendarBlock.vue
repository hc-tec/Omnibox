<template>
  <Card class="h-full">
    <CardHeader v-if="block.title">
      <CardTitle>{{ block.title }}</CardTitle>
    </CardHeader>
    <CardContent :class="{ 'pt-6': !block.title }">
      <div v-if="isEmpty" class="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
        暂无数据
      </div>
      <div v-else ref="containerRef" class="w-full overflow-x-auto">
        <!-- 月份标签（定位到每月第一周上方） -->
        <div class="mb-1 relative" :style="{ paddingLeft: `${labelWidth}px`, height: '16px' }">
          <span
            v-for="month in monthPositions"
            :key="month.key"
            class="absolute text-xs text-muted-foreground"
            :style="{ left: `${labelWidth + month.offset}px` }"
          >
            {{ month.label }}
          </span>
        </div>

        <!-- 热力图主体 -->
        <div class="flex">
          <!-- 星期标签（7行，对应周一到周日） -->
          <div
            class="shrink-0 flex flex-col mr-1"
            :style="{ width: `${labelWidth - 4}px` }"
          >
            <div
              v-for="(label, idx) in weekdayLabels"
              :key="idx"
              class="flex items-center justify-end pr-1 text-xs text-muted-foreground"
              :style="{ height: `${dynamicCellSize + cellGap}px` }"
            >
              {{ label }}
            </div>
          </div>

          <!-- 日期格子 -->
          <TooltipProvider :delay-duration="100">
            <div class="flex" :style="{ gap: `${cellGap}px` }">
              <div
                v-for="(week, weekIndex) in calendarWeeks"
                :key="weekIndex"
                class="flex flex-col"
                :style="{ gap: `${cellGap}px` }"
              >
                <template v-for="(day, dayIndex) in week" :key="dayIndex">
                  <!-- 空白格子不需要 Tooltip -->
                  <div
                    v-if="day.isEmpty"
                    class="rounded-sm bg-transparent"
                    :style="{ width: `${dynamicCellSize}px`, height: `${dynamicCellSize}px` }"
                  />
                  <!-- 有数据的格子使用 Tooltip -->
                  <Tooltip v-else>
                    <TooltipTrigger as-child>
                      <div
                        class="rounded-sm transition-all cursor-pointer hover:ring-2 hover:ring-primary/50"
                        :class="getLevelClass(day.level)"
                        :style="{ width: `${dynamicCellSize}px`, height: `${dynamicCellSize}px` }"
                      />
                    </TooltipTrigger>
                    <TooltipContent
                      side="top"
                      :side-offset="4"
                      class="!bg-[var(--background)] border-border shadow-md"
                    >
                      <span class="font-medium">{{ formatDate(day.date) }}</span>
                      <span class="text-muted-foreground ml-2">{{ day.value }} {{ valueUnit }}</span>
                    </TooltipContent>
                  </Tooltip>
                </template>
              </div>
            </div>
          </TooltipProvider>
        </div>

        <!-- 图例 -->
        <div class="mt-4 flex items-center justify-end gap-2 text-xs text-muted-foreground">
          <span>少</span>
          <div
            v-for="level in 5"
            :key="level"
            class="rounded-sm"
            :class="getLevelClass(level - 1)"
            :style="{ width: `${Math.min(dynamicCellSize, 14)}px`, height: `${Math.min(dynamicCellSize, 14)}px` }"
          />
          <span>多</span>
        </div>

        <!-- 统计信息 -->
        <div v-if="showStats" class="mt-3 flex justify-center gap-6 text-sm">
          <div class="text-center">
            <div class="font-semibold">{{ totalValue }}</div>
            <div class="text-xs text-muted-foreground">总计</div>
          </div>
          <div class="text-center">
            <div class="font-semibold">{{ activeDays }}</div>
            <div class="text-xs text-muted-foreground">活跃天数</div>
          </div>
          <div class="text-center">
            <div class="font-semibold">{{ maxStreak }}</div>
            <div class="text-xs text-muted-foreground">最长连续</div>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import type { UIBlock, DataBlock } from '@/shared/types/panel';
import type { ComponentAbility } from '@/shared/componentManifest';

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

// 容器引用和响应式尺寸
const containerRef = ref<HTMLElement | null>(null);
const containerWidth = ref(0);

let resizeObserver: ResizeObserver | null = null;

onMounted(() => {
  if (containerRef.value) {
    containerWidth.value = containerRef.value.clientWidth;
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        containerWidth.value = entry.contentRect.width;
      }
    });
    resizeObserver.observe(containerRef.value);
  }
});

onUnmounted(() => {
  resizeObserver?.disconnect();
});

// 数据源
const items = computed(() => {
  return (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];
});

const isEmpty = computed(() => items.value.length === 0);

// 字段映射
function getProp(key: string, fallback: string): string {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[key] ?? fallback) as string;
}

function getOption<T>(key: string, fallback: T): T {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  const options = props.block.options ?? {};
  if (camel in options) return options[camel] as T;
  if (key in options) return options[key] as T;
  return fallback;
}

const dateField = getProp('date_field', 'date');
const valueField = getProp('value_field', 'value');
const showStats = getOption<boolean>('show_stats', true);
const weeksToShow = getOption<number>('weeks', 52);
const valueUnit = getOption<string>('value_unit', '次');

const cellGap = 2;
const labelWidth = 28; // 左侧星期标签宽度

// 星期标签（7行：周一到周日）
const weekdayLabels = ['一', '二', '三', '四', '五', '六', '日'];

// 动态计算格子大小以填满容器
const dynamicCellSize = computed(() => {
  const weekCount = calendarWeeks.value.length || 52;
  const availableWidth = containerWidth.value - labelWidth;
  if (availableWidth <= 0) return 12; // 默认值
  // 计算每个格子的宽度：(可用宽度 - 间隙总数) / 周数
  const size = (availableWidth - (weekCount - 1) * cellGap) / weekCount;
  // 限制在合理范围内 [8, 20]
  return Math.max(8, Math.min(20, Math.floor(size)));
});

// 构建日期到值的映射
const dateValueMap = computed(() => {
  const map = new Map<string, number>();
  for (const item of items.value) {
    const date = String(item[dateField] ?? '');
    const value = Number(item[valueField] ?? 0);
    if (date) {
      // 标准化日期格式为 YYYY-MM-DD
      const d = new Date(date);
      if (!isNaN(d.getTime())) {
        const key = d.toISOString().split('T')[0];
        map.set(key, (map.get(key) ?? 0) + value);
      }
    }
  }
  return map;
});

// 计算日历格子
interface CalendarDay {
  date: string;
  value: number;
  level: number;
  isEmpty: boolean;
}

const calendarWeeks = computed<CalendarDay[][]>(() => {
  const weeks: CalendarDay[][] = [];
  const today = new Date();
  const endDate = new Date(today);
  const startDate = new Date(today);
  startDate.setDate(startDate.getDate() - weeksToShow * 7 + 1);

  // 调整到周一开始
  const startDayOfWeek = startDate.getDay();
  const adjustDays = startDayOfWeek === 0 ? 6 : startDayOfWeek - 1;
  startDate.setDate(startDate.getDate() - adjustDays);

  // 计算最大值用于归一化
  const values = Array.from(dateValueMap.value.values());
  const maxValue = Math.max(...values, 1);

  let currentDate = new Date(startDate);
  let currentWeek: CalendarDay[] = [];

  while (currentDate <= endDate) {
    const dateStr = currentDate.toISOString().split('T')[0];
    const value = dateValueMap.value.get(dateStr) ?? 0;
    const level = value === 0 ? 0 : Math.min(Math.ceil((value / maxValue) * 4), 4);

    currentWeek.push({
      date: dateStr,
      value,
      level,
      isEmpty: currentDate > today,
    });

    if (currentWeek.length === 7) {
      weeks.push(currentWeek);
      currentWeek = [];
    }

    currentDate.setDate(currentDate.getDate() + 1);
  }

  // 处理最后一周
  if (currentWeek.length > 0) {
    while (currentWeek.length < 7) {
      currentWeek.push({ date: '', value: 0, level: 0, isEmpty: true });
    }
    weeks.push(currentWeek);
  }

  return weeks;
});

// 月份标签位置（基于每月第一周的索引定位）
const monthPositions = computed(() => {
  const positions: { key: string; label: string; offset: number }[] = [];
  const weeks = calendarWeeks.value;

  if (weeks.length === 0) return positions;

  let lastMonth = '';

  for (let weekIndex = 0; weekIndex < weeks.length; weekIndex++) {
    const week = weeks[weekIndex];
    // 找到这一周中属于新月份的第一天
    for (const day of week) {
      if (!day.isEmpty && day.date) {
        const month = day.date.substring(0, 7);
        if (month !== lastMonth) {
          // 新月份开始，记录位置
          positions.push({
            key: month,
            label: getMonthLabel(month),
            offset: weekIndex * (dynamicCellSize.value + cellGap),
          });
          lastMonth = month;
        }
        break; // 只检查每周的第一个有效天
      }
    }
  }

  return positions;
});

function getMonthLabel(yearMonth: string): string {
  const [, month] = yearMonth.split('-');
  const monthNames = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
  return monthNames[parseInt(month, 10) - 1] || '';
}

// 格式化日期为友好格式（如 "2024-12-02" -> "12月2日"）
function formatDate(dateStr: string): string {
  const [, month, day] = dateStr.split('-');
  return `${parseInt(month, 10)}月${parseInt(day, 10)}日`;
}

// 等级颜色
function getLevelClass(level: number): string {
  switch (level) {
    case 0:
      return 'bg-muted';
    case 1:
      return 'bg-green-200 dark:bg-green-900';
    case 2:
      return 'bg-green-300 dark:bg-green-700';
    case 3:
      return 'bg-green-400 dark:bg-green-500';
    case 4:
      return 'bg-green-500 dark:bg-green-400';
    default:
      return 'bg-muted';
  }
}

// 统计信息
const totalValue = computed(() => {
  let sum = 0;
  for (const val of dateValueMap.value.values()) {
    sum += val;
  }
  return sum.toLocaleString();
});

const activeDays = computed(() => {
  let count = 0;
  for (const val of dateValueMap.value.values()) {
    if (val > 0) count++;
  }
  return count;
});

const maxStreak = computed(() => {
  const weeks = calendarWeeks.value;
  let maxStreak = 0;
  let currentStreak = 0;

  for (const week of weeks) {
    for (const day of week) {
      if (!day.isEmpty && day.value > 0) {
        currentStreak++;
        maxStreak = Math.max(maxStreak, currentStreak);
      } else if (!day.isEmpty) {
        currentStreak = 0;
      }
    }
  }

  return maxStreak;
});
</script>
