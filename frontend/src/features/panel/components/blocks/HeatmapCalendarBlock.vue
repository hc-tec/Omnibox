<template>
  <Card class="h-full">
    <CardHeader v-if="block.title">
      <CardTitle>{{ block.title }}</CardTitle>
    </CardHeader>
    <CardContent :class="{ 'pt-6': !block.title }">
      <div v-if="isEmpty" class="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
        暂无数据
      </div>
      <div v-else class="overflow-x-auto">
        <!-- 月份标签 -->
        <div class="mb-2 flex" :style="{ paddingLeft: '28px' }">
          <div
            v-for="month in monthLabels"
            :key="month.key"
            class="text-xs text-muted-foreground"
            :style="{ width: `${month.width * (cellSize + cellGap)}px` }"
          >
            {{ month.label }}
          </div>
        </div>

        <!-- 热力图主体 -->
        <div class="flex">
          <!-- 星期标签 -->
          <div class="mr-1 flex flex-col justify-around" :style="{ width: '24px' }">
            <span class="text-xs text-muted-foreground">一</span>
            <span class="text-xs text-muted-foreground">三</span>
            <span class="text-xs text-muted-foreground">五</span>
            <span class="text-xs text-muted-foreground">日</span>
          </div>

          <!-- 日期格子 -->
          <div class="flex gap-[2px]">
            <div
              v-for="(week, weekIndex) in calendarWeeks"
              :key="weekIndex"
              class="flex flex-col gap-[2px]"
            >
              <div
                v-for="(day, dayIndex) in week"
                :key="dayIndex"
                class="rounded-sm transition-all"
                :class="[
                  day.isEmpty ? 'bg-transparent' : getLevelClass(day.level),
                  day.isEmpty ? '' : 'cursor-pointer hover:ring-2 hover:ring-primary/50',
                ]"
                :style="{ width: `${cellSize}px`, height: `${cellSize}px` }"
                :title="day.isEmpty ? '' : `${day.date}: ${day.value} ${valueUnit}`"
              />
            </div>
          </div>
        </div>

        <!-- 图例 -->
        <div class="mt-4 flex items-center justify-end gap-2 text-xs text-muted-foreground">
          <span>少</span>
          <div
            v-for="level in 5"
            :key="level"
            class="rounded-sm"
            :class="getLevelClass(level - 1)"
            :style="{ width: `${cellSize}px`, height: `${cellSize}px` }"
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
import { computed } from 'vue';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { UIBlock, DataBlock } from '@/shared/types/panel';
import type { ComponentAbility } from '@/shared/componentManifest';

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

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

const cellSize = 12;
const cellGap = 2;

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

// 月份标签
const monthLabels = computed(() => {
  const labels: { key: string; label: string; width: number }[] = [];
  const weeks = calendarWeeks.value;

  if (weeks.length === 0) return labels;

  let currentMonth = '';
  let weekCount = 0;

  for (const week of weeks) {
    const firstValidDay = week.find((d) => !d.isEmpty && d.date);
    if (firstValidDay) {
      const month = firstValidDay.date.substring(0, 7);
      if (month !== currentMonth) {
        if (currentMonth && weekCount > 0) {
          labels.push({
            key: currentMonth,
            label: getMonthLabel(currentMonth),
            width: weekCount,
          });
        }
        currentMonth = month;
        weekCount = 1;
      } else {
        weekCount++;
      }
    }
  }

  if (currentMonth && weekCount > 0) {
    labels.push({
      key: currentMonth,
      label: getMonthLabel(currentMonth),
      width: weekCount,
    });
  }

  return labels;
});

function getMonthLabel(yearMonth: string): string {
  const [, month] = yearMonth.split('-');
  const monthNames = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
  return monthNames[parseInt(month, 10) - 1] || '';
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
