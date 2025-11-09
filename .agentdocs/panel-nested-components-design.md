# 面板组件嵌套架构设计

> 创建时间：2025-11-09
> 状态：设计中

---

## 1. 需求分析

### 嵌套场景

**场景 1：容器组件**
```
Card
├── StatisticCard (子组件1)
├── StatisticCard (子组件2)
└── LineChart (子组件3)
```

**场景 2：Tab 组件**
```
Tabs
├── Tab 1
│   ├── ListPanel
│   └── BarChart
└── Tab 2
    ├── PieChart
    └── StatisticCard
```

**场景 3：Grid 布局 + 嵌套**
```
Grid (2列)
├── Column 1
│   └── Card
│       ├── StatisticCard
│       └── LineChart
└── Column 2
    └── Card
        └── Table
```

---

## 2. 方案设计

### 方案 A：UIBlock 支持 children（推荐）

#### 优点
- ✅ 结构直观，易于理解
- ✅ 组件自包含，便于序列化和传输
- ✅ 支持递归渲染

#### 缺点
- ⚠️ 数据结构变复杂
- ⚠️ 需要递归处理

#### TypeScript 接口

```typescript
interface UIBlock {
  id: string;
  component: string;

  // 数据来源（二选一）
  data_ref?: string | null;  // 引用 data_blocks 中的数据
  data?: Record<string, unknown> | null;  // 内联数据

  // 组件配置
  props: Record<string, unknown>;
  options: Record<string, unknown>;

  // 嵌套支持 ✨
  children?: UIBlock[] | null;  // 子组件列表

  // 其他
  interactions?: InteractionDefinition[];
  confidence?: number | null;
  title?: string | null;
}
```

#### 后端返回示例

```python
# Python 后端返回
{
  "blocks": [
    {
      "id": "root-card",
      "component": "Card",
      "props": {"title": "数据概览"},
      "options": {"span": 12},
      "children": [
        {
          "id": "stat-1",
          "component": "StatisticCard",
          "data": {
            "items": [{"metric_title": "总访问", "metric_value": 12345}]
          },
          "props": {},
          "options": {"span": 6}
        },
        {
          "id": "stat-2",
          "component": "StatisticCard",
          "data": {
            "items": [{"metric_title": "新增用户", "metric_value": 234}]
          },
          "props": {},
          "options": {"span": 6}
        },
        {
          "id": "chart-1",
          "component": "LineChart",
          "data_ref": "data-block-1",
          "props": {"x_field": "date", "y_field": "count"},
          "options": {"span": 12}
        }
      ]
    }
  ]
}
```

---

### 方案 B：保持扁平 + Layout 管理（当前方案）

#### 优点
- ✅ 布局和组件分离
- ✅ 数据结构简单

#### 缺点
- ❌ 不直观，难以理解嵌套关系
- ❌ 复杂嵌套需要很多 LayoutNode

#### 当前结构

```typescript
{
  "layout": {
    "nodes": [
      {"id": "root", "type": "row", "children": ["card-1"]},
      {"id": "card-1", "type": "cell", "children": ["stat-1", "stat-2"]}
    ]
  },
  "blocks": [
    {"id": "stat-1", "component": "StatisticCard", ...},
    {"id": "stat-2", "component": "StatisticCard", ...}
  ]
}
```

---

## 3. 推荐方案：混合模式

结合两种方案的优点：

### 核心思想
- **Layout** 管理顶层布局（Grid、Row、Column）
- **UIBlock.children** 管理组件级嵌套（Card、Tabs、Accordion）

### TypeScript 接口

```typescript
interface UIBlock {
  id: string;
  component: string;

  // 数据
  data_ref?: string | null;
  data?: Record<string, unknown> | null;

  // 配置
  props: Record<string, unknown>;
  options: Record<string, unknown>;

  // 嵌套 ✨
  children?: UIBlock[] | null;

  // 元信息
  interactions?: InteractionDefinition[];
  confidence?: number | null;
  title?: string | null;
}

interface LayoutNode {
  type: "row" | "column" | "grid" | "cell";
  id: string;

  // 可以引用 UIBlock 的 id，也可以包含子 LayoutNode
  children: string[] | LayoutNode[];

  props?: {
    span?: number;
    columns?: number;  // for grid
    gap?: number;
    responsive?: Record<string, unknown>;
  };
}
```

### 示例：复杂嵌套

```json
{
  "layout": {
    "nodes": [
      {
        "type": "grid",
        "id": "main-grid",
        "props": {"columns": 2, "gap": 4},
        "children": ["block-1", "block-2"]
      }
    ]
  },
  "blocks": [
    {
      "id": "block-1",
      "component": "Card",
      "props": {"title": "统计数据"},
      "children": [
        {
          "id": "block-1-stat-1",
          "component": "StatisticCard",
          "data": {...}
        },
        {
          "id": "block-1-stat-2",
          "component": "StatisticCard",
          "data": {...}
        }
      ]
    },
    {
      "id": "block-2",
      "component": "Tabs",
      "children": [
        {
          "id": "tab-1",
          "component": "TabPanel",
          "props": {"label": "趋势"},
          "children": [
            {
              "id": "tab-1-chart",
              "component": "LineChart",
              "data_ref": "data-1"
            }
          ]
        },
        {
          "id": "tab-2",
          "component": "TabPanel",
          "props": {"label": "列表"},
          "children": [
            {
              "id": "tab-2-list",
              "component": "ListPanel",
              "data_ref": "data-2"
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 4. 前端渲染器实现

### 递归组件渲染器

```vue
<!-- DynamicBlockRenderer.vue -->
<template>
  <component
    :is="resolveComponent(block.component)"
    :block="block"
    :ability="ability"
    :data="resolvedData"
    :data-block="dataBlock"
  >
    <!-- 递归渲染子组件 -->
    <template v-if="block.children && block.children.length > 0">
      <DynamicBlockRenderer
        v-for="child in block.children"
        :key="child.id"
        :block="child"
        :data-blocks="dataBlocks"
      />
    </template>
  </component>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { UIBlock, DataBlock } from '@/shared/types/panel';

interface Props {
  block: UIBlock;
  dataBlocks: Record<string, DataBlock>;
}

const props = defineProps<Props>();

const resolvedData = computed(() => {
  if (props.block.data) {
    return props.block.data;
  }
  if (props.block.data_ref) {
    return props.dataBlocks[props.block.data_ref];
  }
  return null;
});
</script>
```

### 容器组件示例

```vue
<!-- CardBlock.vue -->
<template>
  <Card>
    <CardHeader v-if="block.title">
      <CardTitle>{{ block.title }}</CardTitle>
    </CardHeader>
    <CardContent>
      <!-- 渲染子组件 ✨ -->
      <div class="space-y-4">
        <slot />  <!-- 递归渲染的子组件会插入这里 -->
      </div>
    </CardContent>
  </Card>
</template>
```

---

## 5. 后端适配器示例

### Python 返回嵌套结构

```python
from services.panel.adapters import RouteAdapterResult, AdapterBlockPlan

def github_overview_adapter(source_info, records, context):
    """返回嵌套的 Card + StatisticCard"""

    # 构建嵌套的 UIBlock
    card_block = {
        "id": "overview-card",
        "component": "Card",
        "props": {"title": "GitHub 数据概览"},
        "options": {"span": 12},
        "children": [
            {
                "id": "stat-stars",
                "component": "StatisticCard",
                "data": {
                    "items": [{
                        "id": "1",
                        "metric_title": "总 Stars",
                        "metric_value": 12345,
                        "metric_trend": "up"
                    }]
                },
                "props": {},
                "options": {"span": 6}
            },
            {
                "id": "stat-forks",
                "component": "StatisticCard",
                "data": {
                    "items": [{
                        "id": "2",
                        "metric_title": "总 Forks",
                        "metric_value": 3456,
                        "metric_trend": "up"
                    }]
                },
                "props": {},
                "options": {"span": 6}
            }
        ]
    }

    return RouteAdapterResult(
        records=[],  # 数据已内联在 children 中
        block_plans=[card_block],
        stats={}
    )
```

---

## 6. 组件分类

### 容器组件（支持 children）
- Card - 卡片容器
- Tabs - 标签页容器
- Accordion - 手风琴容器
- Grid - 网格容器
- Row - 行容器
- Column - 列容器

### 数据组件（不支持 children）
- ListPanel - 列表
- StatisticCard - 指标卡片
- LineChart - 折线图
- BarChart - 柱状图
- PieChart - 饼图
- Table - 表格

---

## 7. 实施步骤

1. ✅ 更新 TypeScript 类型定义（`panel.ts`）
2. ✅ 更新后端 Pydantic 模型
3. ✅ 实现递归渲染器（`DynamicBlockRenderer.vue`）
4. ✅ 实现容器组件（Card、Tabs 等）
5. ✅ 更新适配器示例
6. ✅ 添加测试

---

## 8. 向后兼容

为了保持向后兼容：

```typescript
// 如果 children 为 null 或 undefined，按原来的方式渲染
if (!block.children || block.children.length === 0) {
  // 原来的渲染逻辑
}
```

---

## 9. 总结

**推荐使用混合模式**：
- Layout 管理顶层布局
- UIBlock.children 管理组件嵌套
- 前端递归渲染器处理嵌套
- 容器组件通过 `<slot />` 接收子组件

这样既保持了架构的清晰性，又支持了灵活的组件嵌套。
