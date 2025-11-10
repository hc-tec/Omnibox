# 前端面板组件实现指南

> 创建时间：2025-11-09
> **重要**：所有面板组件必须使用 shadcn-vue + ECharts 技术栈

---

## 1. 组件总览

### 1.1 已实现组件（8个）

| 组件 | 文件 | 主要依赖 | 核心功能 |
|------|------|----------|---------|
| ListPanelBlock | `ListPanelBlock.vue` | shadcn-vue (Card, Badge, Separator) | 列表展示，支持标题、描述、元数据、标签 |
| StatisticCardBlock | `StatisticCardBlock.vue` | shadcn-vue (Card) | 指标卡片，支持趋势箭头、数字格式化（万、亿） |
| LineChartBlock | `LineChartBlock.vue` | shadcn-vue (Card) + ECharts | 折线图/面积图，支持多系列、时间轴、响应式 |
| BarChartBlock | `BarChartBlock.vue` | shadcn-vue (Card) + ECharts | 柱状图，支持纵向/横向、堆叠、响应式 |
| PieChartBlock | `PieChartBlock.vue` | shadcn-vue (Card) + ECharts | 饼图/环形图，支持南丁格尔图、可滚动图例 |
| TableBlock | `TableBlock.vue` | shadcn-vue (Table, Button) + TanStack Table | 表格，支持排序、分页、自动列检测 |
| ImageGalleryBlock | `ImageGalleryBlock.vue` | shadcn-vue (Card, Dialog, Button) | 图片画廊，支持网格布局、Lightbox 灯箱预览 |
| FallbackRichTextBlock | `FallbackRichTextBlock.vue` | shadcn-vue (Card, Alert) + marked | 兜底渲染，支持 Markdown、XSS 防护 |

### 1.2 组件目录结构

```
frontend/src/features/panel/components/blocks/
├── ListPanelBlock.vue          # ✅ 已实现
├── StatisticCardBlock.vue      # ✅ 已实现
├── LineChartBlock.vue          # ✅ 已实现
├── BarChartBlock.vue           # ✅ 已实现
├── PieChartBlock.vue           # ✅ 已实现
├── TableBlock.vue              # ✅ 已实现
├── ImageGalleryBlock.vue       # ✅ 已实现
├── FallbackRichTextBlock.vue   # ✅ 已实现
└── DynamicBlockRenderer.vue    # 动态组件路由器
```

---

## 2. 组件实现细节

### 2.1 ListPanelBlock

**数据契约**：`ListPanelRecord`

**核心功能**：
- 列表项展示（标题、描述、发布时间、作者）
- 标签展示（Badge）
- 点击跳转支持
- 空状态提示

**关键代码**：
```vue
<Card>
  <CardHeader v-if="block.title">
    <CardTitle>{{ block.title }}</CardTitle>
  </CardHeader>
  <CardContent>
    <div v-for="item in displayItems" class="group rounded-lg border p-4">
      <!-- 标题 -->
      <h3 class="text-lg font-semibold">{{ item.title }}</h3>

      <!-- 标签 -->
      <div v-if="item.categories" class="flex flex-wrap gap-2">
        <Badge v-for="tag in item.categories">{{ tag }}</Badge>
      </div>

      <Separator class="my-2" />

      <!-- 元数据 -->
      <div class="flex items-center gap-4 text-sm text-muted-foreground">
        <span v-if="item.author">{{ item.author }}</span>
        <span v-if="item.published_at">{{ formatDate(item.published_at) }}</span>
      </div>
    </div>
  </CardContent>
</Card>
```

**配置项**：
- `compact`: 紧凑模式（默认 `false`）- 减小内边距（p-2）和字体（text-sm）
- `max_items`: 最大显示条目数（默认 `20`）
- `show_description`: 是否显示描述（默认 `true`）
- `show_metadata`: 是否显示作者/时间（默认 `true`）
- `show_categories`: 是否显示标签（默认 `true`）
- `span`: 栅格占位（1-12）

**尺寸预设**（后端配置）：
使用 `services/panel/adapters/config_presets.py` 中的预设函数：

```python
from services.panel.adapters.config_presets import list_panel_size_preset

# 紧凑模式（5条，占1/3行）
compact_config = list_panel_size_preset("compact")
# -> {compact: True, max_items: 5, span: 4, show_*: False}

# 标准模式（10条，占半行）
normal_config = list_panel_size_preset("normal")
# -> {compact: False, max_items: 10, span: 6, show_*: True}

# 大型模式（20条，占全行）
large_config = list_panel_size_preset("large")
# -> {compact: False, max_items: 20, span: 12, show_*: True}

# 完整模式（50条，占全行）
full_config = list_panel_size_preset("full")
# -> {compact: False, max_items: 50, span: 12, show_*: True}
```

---

### 2.2 StatisticCardBlock

**数据契约**：`StatisticCardRecord`

**核心功能**：
- 指标标题和数值展示
- 趋势指示器（上升/下降/持平箭头）
- 数字格式化（万、亿）
- 变化文本展示

**关键代码**：
```vue
<Card>
  <CardHeader>
    <CardTitle class="text-sm font-medium text-muted-foreground">
      {{ item.metric_title }}
    </CardTitle>
  </CardHeader>
  <CardContent>
    <div class="text-3xl font-bold">
      {{ formatNumber(item.metric_value) }}
      <span v-if="item.metric_unit" class="text-base">{{ item.metric_unit }}</span>
    </div>

    <!-- 趋势箭头 -->
    <div v-if="item.metric_trend" :class="trendColorClass">
      <svg><!-- 箭头图标 --></svg>
      <span>{{ item.metric_delta_text }}</span>
    </div>
  </CardContent>
</Card>
```

**数字格式化逻辑**：
```typescript
function formatNumber(value: number): string {
  if (value >= 100000000) return `${(value / 100000000).toFixed(1)}亿`;
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return value.toLocaleString();
}
```

---

### 2.3 LineChartBlock

**数据契约**：`LineChartRecord`

**核心功能**：
- 折线图/面积图展示
- 多系列支持
- 自动识别时间轴
- 响应式图表调整

**ECharts 配置**：
```typescript
const chartOption = computed<EChartsOption>(() => {
  const isTime = /^\d{4}-\d{2}-\d{2}/.test(String(xAxisData[0]));

  return {
    tooltip: { trigger: 'axis' },
    legend: { show: seriesList.length > 1 },
    xAxis: {
      type: isTime ? 'time' : 'category',
      data: isTime ? undefined : xAxisData,
    },
    yAxis: { type: 'value' },
    series: seriesList.map(name => ({
      name,
      type: 'line',
      data: seriesData[name],
      smooth: true,
      areaStyle: areaStyle ? {} : undefined,
    })),
  };
});
```

**配置项**：
- `area_style`: 是否填充区域（默认 `false`）
- `smooth`: 是否平滑曲线（默认 `true`）

---

### 2.4 BarChartBlock

**数据契约**：`BarChartRecord`

**核心功能**：
- 纵向/横向柱状图切换
- 堆叠模式
- 自定义柱宽、颜色
- 数据标签显示

**ECharts 配置**：
```typescript
const chartOption = computed<EChartsOption>(() => {
  const isHorizontal = orientation === 'horizontal';

  return {
    color: colors || undefined,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { containLabel: true },
    xAxis: isHorizontal
      ? { type: 'value' }
      : { type: 'category', data: xAxisData },
    yAxis: isHorizontal
      ? { type: 'category', data: xAxisData }
      : { type: 'value' },
    series: seriesList.map(name => ({
      type: 'bar',
      data: seriesData[name],
      stack: stacked ? 'total' : undefined,
      label: { show: showLabel, position: 'top' },
    })),
  };
});
```

**配置项**：
- `orientation`: `'vertical'` | `'horizontal'`（默认 `'vertical'`）
- `stacked`: 是否堆叠（默认 `false`）
- `show_label`: 是否显示数据标签（默认 `false`）
- `bar_width`: 自定义柱宽（默认自动）
- `colors`: 自定义颜色数组

---

### 2.5 PieChartBlock

**数据契约**：`PieChartRecord`

**核心功能**：
- 饼图/环形图（通过 radius 控制）
- 南丁格尔图（玫瑰图）
- 可滚动图例（数据过多时）
- 自定义颜色

**ECharts 配置**：
```typescript
const chartOption = computed<EChartsOption>(() => {
  return {
    color: colors || undefined,
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        return `${params.marker} ${params.name}<br/>数量: ${params.value.toLocaleString()} (${params.percent.toFixed(1)}%)`;
      },
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      type: 'scroll', // 支持滚动
    },
    series: [{
      type: 'pie',
      radius: radius, // '50%' 或 ['40%', '70%']
      roseType: roseType || undefined,
      data: pieData,
    }],
  };
});
```

**配置项**：
- `radius`: `'50%'`（饼图）或 `['40%', '70%']`（环形图）
- `rose_type`: `false` | `'radius'` | `'area'`（南丁格尔图）
- `show_label`: 是否显示标签（默认 `true`）
- `colors`: 自定义颜色数组

---

### 2.6 TableBlock

**数据契约**：`TableViewModel`（包含 `columns` 和 `rows`）

**核心功能**：
- TanStack Table v8 驱动
- 列排序（点击表头）
- 分页功能
- 自动列检测或显式列配置
- 智能数据格式化（链接、数字、布尔值）

**关键代码**：
```typescript
const table = useVueTable({
  get data() { return items; },
  get columns() { return columns.value; },
  state: { get sorting() { return sorting.value; } },
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
  getPaginationRowModel: getPaginationRowModel(),
  initialState: { pagination: { pageSize: 10 } },
});
```

**列配置示例**：
```typescript
// 后端传递列配置
props: {
  columns: [
    { field: 'title', header: '标题', sortable: true },
    { field: 'stars', header: 'Stars', sortable: true },
  ]
}

// 自动检测列（无配置时）
const columns = Object.keys(firstItem).map(key => ({
  accessorKey: key,
  header: formatHeader(key),
  enableSorting: true,
}));
```

**配置项**：
- `enable_pagination`: 是否启用分页（默认 `true`）
- `page_size`: 每页条目数（默认 `10`）
- `enable_sorting`: 是否启用排序（默认 `true`）

---

### 2.7 ImageGalleryBlock

**数据契约**：`ImageGalleryRecord`

**核心功能**：
- 响应式网格布局（2-5 列）
- 图片懒加载
- Lightbox 灯箱查看
- 前后导航
- 图片加载失败占位图

**关键代码**：
```vue
<!-- 网格布局 -->
<div :class="gridClass">
  <div v-for="(image, index) in images"
       @click="openLightbox(index)"
       class="group cursor-pointer">
    <img :src="image.url" loading="lazy" />

    <!-- Hover 覆盖层 -->
    <div class="absolute inset-x-0 bottom-0 opacity-0 group-hover:opacity-100">
      <p>{{ image.title }}</p>
    </div>
  </div>
</div>

<!-- Lightbox Dialog -->
<Dialog :open="lightboxOpen">
  <DialogContent>
    <img :src="currentImage.url" />
    <Button @click="navigateLightbox(-1)">上一张</Button>
    <Button @click="navigateLightbox(1)">下一张</Button>
  </DialogContent>
</Dialog>
```

**配置项**：
- `columns`: 网格列数 `2` | `3` | `4` | `5`（默认 `3`）

---

### 2.8 FallbackRichTextBlock

**数据契约**：`FallbackRichTextRecord`

**核心功能**：
- Markdown 渲染（marked 库）
- HTML 清理防止 XSS
- 兜底警告提示（Alert）
- Tailwind Typography 样式

**关键代码**：
```vue
<Card>
  <CardContent>
    <Alert variant="default">
      <AlertTitle>兜底渲染</AlertTitle>
      <AlertDescription>
        当前数据无法结构化展示，正在使用兜底渲染模式。
      </AlertDescription>
    </Alert>

    <div class="prose prose-slate dark:prose-invert max-w-none"
         v-html="renderedContent">
    </div>
  </CardContent>
</Card>
```

**XSS 防护**：
```typescript
function sanitizeHtml(html: string): string {
  // 移除 <script> 标签
  let cleaned = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
  // 移除事件处理器
  cleaned = cleaned.replace(/\son\w+\s*=\s*["'][^"']*["']/gi, '');
  return cleaned;
}
```

---

## 3. 通用模式

### 3.1 Props 接口

所有组件均遵循统一的 Props 接口：

```typescript
interface Props {
  block: UIBlock;              // 组件元数据（id, component, props, options）
  ability: ComponentAbility | null;  // 组件能力定义
  data: Record<string, unknown> | null;  // 直接传入的数据
  dataBlock: DataBlock | null;  // 数据块（包含 records, stats）
}
```

### 3.2 数据获取

```typescript
// 优先使用 data.items，回退到 dataBlock.records
const items = (props.data?.items as Record<string, unknown>[])
  ?? props.dataBlock?.records ?? [];

// 空状态检测
const isEmpty = computed(() => items.length === 0);
```

### 3.3 字段映射

支持 `snake_case` 和 `camelCase` 自动映射：

```typescript
function getProp(key: string, fallback: string): string {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[key] ?? fallback) as string;
}

const titleField = getProp('title_field', 'title');
```

### 3.4 配置项获取

```typescript
function getOption<T>(key: string, fallback: T): T {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.options?.[camel] ?? props.block.options?.[key] ?? fallback) as T;
}

const showDescription = getOption('show_description', true);
```

### 3.5 响应式图表调整

所有 ECharts 组件均使用 ResizeObserver：

```typescript
const chartRef = ref<InstanceType<typeof VChart>>();
let resizeObserver: ResizeObserver | null = null;

onMounted(() => {
  if (chartRef.value) {
    const chart = chartRef.value;
    resizeObserver = new ResizeObserver(() => {
      chart?.resize();
    });
    const container = chart?.$el?.parentElement;
    if (container) resizeObserver.observe(container);
  }
});

onUnmounted(() => {
  resizeObserver?.disconnect();
});
```

---

## 4. 组件注册

### 4.1 DynamicBlockRenderer

所有组件通过 `DynamicBlockRenderer.vue` 动态路由：

```vue
<script setup lang="ts">
import { computed } from 'vue';
import ListPanelBlock from './ListPanelBlock.vue';
import StatisticCardBlock from './StatisticCardBlock.vue';
import LineChartBlock from './LineChartBlock.vue';
import BarChartBlock from './BarChartBlock.vue';
import PieChartBlock from './PieChartBlock.vue';
import TableBlock from './TableBlock.vue';
import ImageGalleryBlock from './ImageGalleryBlock.vue';
import FallbackRichTextBlock from './FallbackRichTextBlock.vue';

const componentMap = {
  ListPanel: ListPanelBlock,
  StatisticCard: StatisticCardBlock,
  LineChart: LineChartBlock,
  BarChart: BarChartBlock,
  PieChart: PieChartBlock,
  Table: TableBlock,
  ImageGallery: ImageGalleryBlock,
  FallbackRichText: FallbackRichTextBlock,
};

const resolvedComponent = computed(() => {
  return componentMap[props.block.component] || FallbackRichTextBlock;
});
</script>

<template>
  <component :is="resolvedComponent" v-bind="props" />
</template>
```

### 4.2 Component Manifest

前端清单定义在 `frontend/src/shared/componentManifest.ts`：

```typescript
export const COMPONENT_MANIFEST: Record<string, ComponentAbility> = {
  ListPanel: {
    id: 'ListPanel',
    name: '列表面板',
    description: '展示列表类信息',
    cost: 0.5,
    required: false,
    default_selected: true,
  },
  // ... 其他组件
};
```

---

## 5. 开发与测试

### 5.1 开发流程

1. **定义契约**：在 `docs/backend-panel-view-models.md` 定义数据契约
2. **实现组件**：在 `blocks/` 目录创建 Vue 组件
3. **注册组件**：在 `DynamicBlockRenderer.vue` 添加映射
4. **更新清单**：在 `componentManifest.ts` 注册能力
5. **测试验证**：使用真实数据验证

### 5.2 本地测试

```bash
cd frontend
npm run dev
```

通过后端 API 返回对应 component_id 测试组件渲染。

---

## 6. 重要约束

### 6.1 技术栈约束

- ✅ **必须使用** shadcn-vue（不是 React 的 shadcn-ui）
- ✅ **必须使用** ECharts（图表组件）
- ✅ **必须使用** Vue 3 Composition API（`<script setup>`）
- ❌ **禁止使用** React 语法
- ❌ **禁止使用** Options API
- ❌ **禁止使用** 其他 UI 库（Element Plus, Ant Design Vue 等）
- ❌ **禁止使用** 其他图表库（Recharts, Chart.js 等）

### 6.2 数据契约约束

- 所有组件必须严格遵循后端契约
- 字段映射支持 `snake_case` 和 `camelCase` 双向兼容
- 所有组件必须支持 `UIBlock.children` 嵌套架构

### 6.3 安全约束

- Markdown/HTML 渲染必须防止 XSS 攻击
- 图片 URL 必须验证有效性
- 用户输入必须清理和转义

---

## 7. 全局记忆

**已实现的 8 个组件**：
1. ListPanelBlock（列表）
2. StatisticCardBlock（指标卡片）
3. LineChartBlock（折线图）
4. BarChartBlock（柱状图）
5. PieChartBlock（饼图）
6. TableBlock（表格）
7. ImageGalleryBlock（图片画廊）
8. FallbackRichTextBlock（兜底渲染）

**所有组件均**：
- ✅ 使用 shadcn-vue + ECharts 技术栈
- ✅ 支持 `UIBlock.children` 嵌套
- ✅ 遵循统一的 Props 接口
- ✅ 实现响应式调整（图表组件）
- ✅ 提供空状态提示

**依赖安装状态**：
- ✅ shadcn-vue 已安装（Card, Badge, Separator, Alert, Table, Button, Progress, Dialog）
- ✅ ECharts + vue-echarts 已安装
- ✅ @tanstack/vue-table 已安装
- ✅ marked + @tailwindcss/typography 已安装

**文档链接**：
- 前端架构：`.agentdocs/frontend-architecture.md`
- 数据契约：`docs/backend-panel-view-models.md`
- 嵌套架构：`.agentdocs/panel-nested-components-design.md`
- 安装指南：`frontend/SETUP.md`

---

## 8. 组件尺寸配置系统

### 8.1 配置预设工具

位置：`services/panel/adapters/config_presets.py`

提供标准化的尺寸预设函数，让 AI planner 能够灵活控制组件大小。

#### ListPanel 尺寸预设

```python
from services.panel.adapters.config_presets import list_panel_size_preset

# 参数：size = "compact" | "normal" | "large" | "full"
config = list_panel_size_preset(
    size="compact",
    show_description=True,   # 可选覆盖
    show_metadata=True,      # 可选覆盖
    show_categories=True,    # 可选覆盖
)
```

**预设对照表**：

| 预设 | max_items | span | compact | 描述/元数据/标签 | 适用场景 |
|------|-----------|------|---------|----------------|---------|
| `"compact"` | 5 | 4 | ✅ | ❌ 强制隐藏 | 热搜榜单、侧边栏、导航 |
| `"normal"` | 10 | 6 | ❌ | ✅ 可配置 | 文章列表、帖子列表 |
| `"large"` | 20 | 12 | ❌ | ✅ 可配置 | 详细列表、主内容区 |
| `"full"` | 50 | 12 | ❌ | ✅ 可配置 | 完整目录、归档页 |

#### Chart 尺寸预设

```python
from services.panel.adapters.config_presets import chart_size_preset

config = chart_size_preset("normal")
# -> {span: 6}
```

| 预设 | span | 高度建议 | 适用场景 |
|------|------|---------|---------|
| `"compact"` | 4 | 200px | 小型仪表盘、多图并排 |
| `"normal"` | 6 | 280px | 标准图表、两图并排 |
| `"large"` | 12 | 320px | 主要图表、单图展示 |
| `"full"` | 12 | 400px | 详细图表、大屏展示 |

#### StatisticCard 尺寸预设

```python
from services.panel.adapters.config_presets import statistic_card_size_preset

config = statistic_card_size_preset("normal")
# -> {span: 3}
```

| 预设 | span | 每行数量 | 适用场景 |
|------|------|---------|---------|
| `"compact"` | 2 | 6个 | 密集仪表盘 |
| `"normal"` | 3 | 4个 | 标准仪表盘 |
| `"large"` | 4 | 3个 | 突出关键指标 |
| `"full"` | 6 | 2个 | 大型指标卡 |

### 8.2 使用示例

#### 基础使用

```python
from services.panel.adapters.config_presets import list_panel_size_preset

# 紧凑模式
compact = list_panel_size_preset("compact")
# 输出：{compact: True, max_items: 5, span: 4, show_description: False, ...}

# 标准模式（可覆盖部分配置）
normal = list_panel_size_preset("normal", show_description=False)
# 输出：{compact: False, max_items: 10, span: 6, show_description: False, ...}
```

#### 动态选择（AI planner）

```python
def determine_size(context: AdapterExecutionContext) -> str:
    """AI planner 根据上下文动态选择尺寸"""
    if context.requested_components and len(context.requested_components) > 3:
        # 页面组件多，使用紧凑模式
        return "compact"
    elif context.is_mobile_view:
        # 移动端，使用标准模式
        return "normal"
    else:
        # 桌面端，使用大型模式
        return "large"

size_config = list_panel_size_preset(determine_size(context))
```

### 8.3 前端组件配置支持

所有配置项都会传递到前端 Vue 组件的 `block.options`：

```vue
<!-- ListPanelBlock.vue -->
<script setup>
const compact = props.block.options?.compact === true;
const maxItems = Number(props.block.options?.maxItems ?? 20);
const showDescription = props.block.options?.showDescription !== false;
const showMetadata = props.block.options?.showMetadata !== false;
const showCategories = props.block.options?.showCategories !== false;
</script>

<template>
  <div :class="compact ? 'space-y-1' : 'space-y-4'">
    <div :class="compact ? 'p-2' : 'p-4'">
      <h3 :class="compact ? 'text-sm' : 'text-base'">{{ title }}</h3>
      <p v-if="showDescription">{{ description }}</p>
      <div v-if="showMetadata">{{ metadata }}</div>
    </div>
  </div>
</template>
```

---

## 9. 最佳实践案例

### 9.1 热搜榜单优化（B 站热搜）- 使用配置预设

**问题**：默认配置下热搜榜单占据空间过大。

**解决方案：使用紧凑模式预设**
```python
# services/panel/adapters/bilibili/hot_search.py
from services.panel.adapters.config_presets import list_panel_size_preset

# 使用紧凑模式预设
size_config = list_panel_size_preset("compact")

AdapterBlockPlan(
    component_id="ListPanel",
    props={
        "title_field": "title",
        "link_field": "link",
        "description_field": "summary",
        "pub_date_field": "published_at",
    },
    options=size_config,  # 自动配置：compact=True, max_items=5, span=4, show_*=False
    title="B站热搜",
    layout_hint=LayoutHint(span=size_config["span"], min_height=180),
)
```

**效果对比**：

| 配置 | 条目数 | 栅格占位 | 内边距 | 元数据显示 | 视觉占用 |
|------|--------|---------|--------|-----------|---------|
| **默认** | 20 | 12（全行） | p-4（大） | ✅ 全显示 | 🔴 很大 |
| **标准** | 10 | 6（半行） | p-4（大） | ✅ 全显示 | 🟡 中等 |
| **紧凑** | 5 | 4（1/3行） | p-2（小） | ❌ 全隐藏 | 🟢 很小 |

**AI planner 可动态选择尺寸**：
```python
# AI planner 根据上下文选择合适的尺寸
if context.has_other_components:
    # 页面有其他组件，使用紧凑模式节省空间
    config = list_panel_size_preset("compact")
elif context.is_main_content:
    # 热搜是主要内容，使用标准模式
    config = list_panel_size_preset("normal")
else:
    # 详细展示，使用大型模式
    config = list_panel_size_preset("large")
```

**适用场景**：
- 热搜榜单、排行榜 → `"compact"`
- 快捷导航菜单 → `"compact"`
- 文章列表（摘要） → `"normal"`
- 文章列表（详细） → `"large"`

### 9.2 图表组件占比优化

**默认配置**（占满整行）：
```python
AdapterBlockPlan(
    component_id="BarChart",
    options={"span": 12},  # 占满整行
    layout_hint=LayoutHint(span=12, min_height=280),
)
```

**优化配置**（并排显示）：
```python
# 方案1：两个图表并排
AdapterBlockPlan(
    component_id="BarChart",
    options={"span": 6},  # 占半行
    layout_hint=LayoutHint(span=6, min_height=280),
)

# 方案2：三个图表并排
AdapterBlockPlan(
    component_id="PieChart",
    options={"span": 4},  # 占1/3行
    layout_hint=LayoutHint(span=4, min_height=240),
)
```

### 9.3 混合布局示例

**场景**：GitHub Trending 页面

```python
# 顶部：3个指标卡片并排（各占4栅格）
StatisticCard(span=4) + StatisticCard(span=4) + StatisticCard(span=4)

# 中部：柱状图 + 饼图并排（各占6栅格）
BarChart(span=6) + PieChart(span=6)

# 底部：完整的项目列表（占满12栅格）
ListPanel(span=12, max_items=20)
```

**代码实现**：
```python
block_plans = [
    # 顶部指标卡片
    AdapterBlockPlan("StatisticCard", options={"span": 4}, ...),  # Star总数
    AdapterBlockPlan("StatisticCard", options={"span": 4}, ...),  # Fork总数
    AdapterBlockPlan("StatisticCard", options={"span": 4}, ...),  # 今日新增

    # 中部图表
    AdapterBlockPlan("BarChart", options={"span": 6}, ...),  # 语言分布
    AdapterBlockPlan("PieChart", options={"span": 6}, ...),  # 分类占比

    # 底部列表
    AdapterBlockPlan("ListPanel", options={"span": 12, "max_items": 20}, ...),
]
```

### 9.4 响应式设计建议

**栅格系统**（基于 12 栅格）：
- `span: 12` - 占满整行（移动端和桌面端都占满）
- `span: 6` - 占半行（桌面端并排，移动端可能堆叠）
- `span: 4` - 占1/3行（桌面端三列，移动端可能堆叠）
- `span: 3` - 占1/4行（桌面端四列，移动端可能堆叠）

**推荐配置**：
- **ListPanel**：紧凑模式 `span: 6`，标准模式 `span: 12`
- **StatisticCard**：通常 `span: 3` 或 `span: 4`（一行放3-4个）
- **Chart（柱状图/折线图/饼图）**：`span: 6` 或 `span: 12`
- **Table**：通常 `span: 12`（需要宽度展示多列）
- **ImageGallery**：`span: 12`（需要宽度展示网格）

## 10. 桌面端与宫格布局（新增）

- **Electron 集成**：前端提供 `npm run electron:dev`（并行启动 Vite 与 Electron）与 `npm run electron:build`（`vite build` + `tsc -p tsconfig.electron.json` + `electron-builder`）。主进程位于 `frontend/electron/main.ts`，预加载脚本 `frontend/electron/preload.ts` 会通过 `window.desktop` 暴露桌面 API。
- **布局 hint**：后台 `LayoutEngine` 会在 `LayoutNode.props.grid` 注入 `{x,y,w,h,minH}`，`PanelBoard.vue` 依赖 `vue-grid-layout` 渲染 12 栏宫格；若缺少 hint，则自动顺序排布。
- **Layout snapshot 回传**：`panelStore` 根据当前布局计算 `layout_snapshot` 并随 REST/WebSocket 请求下发，`ChatService`/PlannerContext 会接收该字段，Planner 可据此做 append/merge 策略。
- **清空/追加策略**：Toolbar 默认采用 append 模式持续新增组件，点击“清空组件”会触发 `panelStore.resetPanel()`，重新开始一次新的宫格排布。
