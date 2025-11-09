# 前端架构与技术约束

> 创建时间：2025-11-09
> **重要**：修改任何前端代码前必读此文档

---

## 1. 技术栈选型

### 1.1 核心框架

| 技术 | 版本 | 用途 | 状态 |
|------|------|------|------|
| **Vue 3** | ^3.4.38 | 前端框架 | ✅ 已安装 |
| **TypeScript** | ^5.4.5 | 类型系统 | ✅ 已安装 |
| **Vite** | ^5.4.8 | 构建工具 | ✅ 已安装 |
| **Pinia** | ^2.1.7 | 状态管理 | ✅ 已安装 |
| **Axios** | ^1.7.7 | HTTP 请求 | ✅ 已安装 |

### 1.2 UI 组件库

| 技术 | 用途 | 状态 |
|------|------|------|
| **shadcn-vue** | UI 组件库（Card, Table, Button 等） | ✅ 已安装 |
| **Radix Vue** | shadcn-vue 底层无障碍组件 | ✅ 已安装 |
| **Tailwind CSS** | 样式工具库 | ✅ 已安装 |
| **@tailwindcss/typography** | Markdown 渲染样式 | ✅ 已安装 |

**已安装的 shadcn-vue 组件**：
- Card（卡片）
- Badge（徽章）
- Separator（分隔符）
- Alert（警告提示）
- Table（表格）
- Button（按钮）
- Progress（进度条）
- Dialog（对话框）

### 1.3 图表可视化库

| 技术 | 用途 | 状态 |
|------|------|------|
| **ECharts** | 图表可视化（柱状图、折线图、饼图等） | ✅ 已安装 |
| **vue-echarts** | ECharts 的 Vue 3 封装 | ✅ 已安装 |

### 1.4 其他关键依赖

| 技术 | 用途 | 状态 |
|------|------|------|
| **@tanstack/vue-table** | 高级表格功能（排序、分页） | ✅ 已安装 |
| **marked** | Markdown 渲染 | ✅ 已安装 |

**完整安装指南**：参见 `frontend/SETUP.md`

---

## 2. 项目结构

```
frontend/
├── src/
│   ├── App.vue              # 根组件
│   ├── main.ts              # 应用入口
│   ├── components/          # shadcn-vue 组件目录
│   │   └── ui/              # UI 基础组件
│   │       ├── card/
│   │       ├── table/
│   │       └── ...
│   ├── features/            # 功能模块
│   │   └── panel/           # 面板功能
│   │       ├── components/  # 面板组件（BarChart, Table 等）
│   │       ├── stores/      # Pinia stores
│   │       └── types/       # 类型定义
│   ├── services/            # API 服务
│   ├── shared/              # 共享资源
│   │   └── types/           # 共享类型定义
│   │       └── panelContracts.ts  # 面板数据契约
│   ├── store/               # 全局 stores
│   ├── styles/              # 全局样式
│   │   └── globals.css      # Tailwind CSS + 主题变量
│   └── utils/               # 工具函数
├── package.json
├── tsconfig.json
└── vite.config.mts
```

---

## 3. 组件开发规范

### 3.1 面板组件开发规范

**✅ 必须遵循**：
1. **使用 shadcn-vue + ECharts** 组合
   - 容器组件（Card, Table）使用 shadcn-vue
   - 图表可视化（柱状图、折线图、饼图）使用 ECharts
   - ❌ **禁止使用 React 或其他框架的组件**

2. **Vue 3 Composition API**
   - 使用 `<script setup lang="ts">` 语法
   - 使用 `ref`, `computed`, `watch` 等组合式 API
   - ❌ 禁止使用 Options API

3. **TypeScript 强类型**
   - 所有组件必须定义 Props 接口
   - 使用 `defineProps<T>()` 定义类型
   - 导入类型使用 `import type { ... }`

4. **数据契约一致性**
   - 前端 TypeScript 接口必须与后端 Pydantic 模型一致
   - 契约定义在 `frontend/src/shared/types/panelContracts.ts`
   - 后端契约定义在 `docs/backend-panel-view-models.md`

### 3.2 组件文件结构

**标准结构**（以 BarChart 为例）：
```
features/panel/components/BarChart/
├── BarChart.vue          # 主组件（Vue SFC）
├── useBarChart.ts        # ECharts 配置逻辑（组合式函数）
├── utils.ts              # 数据转换工具
└── __tests__/
    └── BarChart.spec.ts  # 单元测试
```

**组件模板**：
```vue
<script setup lang="ts">
import { computed } from 'vue';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart as EChartsBar } from 'echarts/charts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { BarChartRecord } from '@/shared/types/panelContracts';

// 注册 ECharts 组件（按需引入）
use([CanvasRenderer, EChartsBar]);

interface Props {
  data: { items: BarChartRecord[]; /* ... */ };
  props: { xField: string; yField: string; };
  options?: { horizontal?: boolean; };
  title?: string;
  id: string;
}

const props = withDefaults(defineProps<Props>(), {
  options: () => ({}),
});

const chartOption = computed(() => {
  // ECharts 配置逻辑
});
</script>

<template>
  <Card>
    <CardHeader v-if="title">
      <CardTitle>{{ title }}</CardTitle>
    </CardHeader>
    <CardContent>
      <VChart :option="chartOption" class="h-[280px]" />
    </CardContent>
  </Card>
</template>
```

---

## 4. ECharts 集成规范

### 4.1 按需引入（推荐）

```typescript
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components';

// 注册需要的组件
use([
  CanvasRenderer,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
]);
```

### 4.2 全局注册 vue-echarts（可选）

```typescript
// frontend/src/main.ts
import { createApp } from 'vue';
import VChart from 'vue-echarts';

const app = createApp(App);
app.component('VChart', VChart);  // 全局注册
```

### 4.3 响应式调整

```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';

const chartRef = ref<InstanceType<typeof VChart>>();
let resizeObserver: ResizeObserver | null = null;

onMounted(() => {
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => {
      chartRef.value?.resize();
    });
    const container = chartRef.value.$el?.parentElement;
    if (container) resizeObserver.observe(container);
  }
});

onUnmounted(() => {
  resizeObserver?.disconnect();
});
</script>

<template>
  <VChart ref="chartRef" :option="option" autoresize />
</template>
```

---

## 5. shadcn-vue 使用规范

### 5.1 安装与配置

**初始化（首次）**：
```bash
npx shadcn-vue@latest init
```

配置选项：
- TypeScript: **Yes**
- Framework: **Vite**
- Style: **Default**
- Base color: **Slate**（或其他）
- CSS variables: **Yes**

**添加组件**：
```bash
npx shadcn-vue@latest add card
npx shadcn-vue@latest add table
npx shadcn-vue@latest add badge
npx shadcn-vue@latest add button
```

### 5.2 主题配置

在 `frontend/src/styles/globals.css` 中配置主题变量：

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    /* ... 更多主题变量 */

    /* 图表颜色变量 */
    --chart-1: 220 70% 50%;
    --chart-2: 340 75% 55%;
    --chart-3: 160 60% 45%;
    --chart-4: 30 80% 55%;
    --chart-5: 280 65% 60%;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    /* ... 深色主题变量 */
  }
}
```

### 5.3 组件使用示例

```vue
<script setup lang="ts">
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle>标题</CardTitle>
      <CardDescription>描述</CardDescription>
    </CardHeader>
    <CardContent>
      <Badge>标签</Badge>
    </CardContent>
  </Card>
</template>
```

---

## 6. 数据契约管理

### 6.1 契约定义位置

- **前端**：`frontend/src/shared/types/panelContracts.ts`
- **后端**：`services/panel/view_models.py`
- **文档**：`docs/backend-panel-view-models.md`

### 6.2 契约一致性检查清单

新增或修改组件时，必须确保：
- [ ] 前端 TypeScript 接口已定义
- [ ] 后端 Pydantic 模型已定义
- [ ] 契约文档已更新
- [ ] `validate_records()` 已添加验证分支
- [ ] 前端 `componentManifest.ts` 已注册
- [ ] 后端测试已通过
- [ ] 前端测试已通过

### 6.3 示例对比

**前端 TypeScript**：
```typescript
export interface BarChartRecord {
  id: string;
  x: string;
  y: number;
  series?: string | null;
  color?: string | null;
  tooltip?: string | null;
  [key: string]: unknown;
}
```

**后端 Pydantic**：
```python
class BarChartRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Unique record identifier")
    x: str = Field(..., description="X axis category")
    y: float = Field(..., description="Y axis numeric value")
    series: Optional[str] = Field(None, description="Series identifier")
    color: Optional[str] = Field(None, description="Custom bar color")
    tooltip: Optional[str] = Field(None, description="Custom tooltip text")
```

---

## 7. 常见错误与避坑指南

### 7.1 ❌ 禁止事项

1. **禁止使用 React 语法**
   - ❌ `useState`, `useEffect`, `JSX`
   - ✅ 使用 Vue 3 的 `ref`, `watch`, `<template>`

2. **禁止使用其他 UI 库**
   - ❌ Element Plus, Ant Design Vue, Naive UI
   - ✅ 只使用 shadcn-vue

3. **禁止使用其他图表库（图表组件）**
   - ❌ Recharts, Chart.js, ApexCharts
   - ✅ 只使用 ECharts

4. **禁止混用 Options API**
   - ❌ `data()`, `methods`, `computed:{}`
   - ✅ 只使用 Composition API

### 7.2 ⚠️ 注意事项

1. **Props 命名约定**
   - 后端使用 `snake_case`（`x_field`, `y_field`）
   - 前端接收时使用 `camelCase`（`xField`, `yField`）
   - 在组件内部映射转换

2. **ECharts 按需引入**
   - 只引入使用的组件（减少打包体积）
   - 使用 `use()` 注册组件

3. **响应式图表**
   - 必须监听容器大小变化
   - 使用 `ResizeObserver` 或 `autoresize` 属性

---

## 8. 性能优化建议

### 8.1 组件懒加载

```typescript
export const PanelComponents = {
  ListPanel: () => import('./ListPanel/ListPanel.vue'),
  LineChart: () => import('./LineChart/LineChart.vue'),
  BarChart: () => import('./BarChart/BarChart.vue'),
};
```

### 8.2 ECharts 图表优化

1. **按需引入组件**（已说明）
2. **数据抽样**（大数据量时）
3. **虚拟滚动**（长列表）
4. **防抖/节流**（resize 事件）

---

## 9. 测试策略

### 9.1 测试框架

- **Vitest**：单元测试
- **@vue/test-utils**：组件测试

### 9.2 测试清单

每个组件必须包含：
- [ ] 渲染测试（有数据时）
- [ ] 空状态测试（无数据时）
- [ ] Props 验证测试
- [ ] 交互测试（如有）

---

## 10. 开发流程

### 10.1 新增组件流程

1. **后端定义契约** → `view_models.py`
2. **更新契约文档** → `docs/backend-panel-view-models.md`
3. **前端定义类型** → `panelContracts.ts`
4. **注册组件清单** → `componentManifest.ts`
5. **实现组件** → `features/panel/components/[ComponentName]/`
6. **编写测试** → `__tests__/`
7. **集成验证** → 端到端测试

### 10.2 修改组件流程

1. **检查契约变更** → 是否破坏兼容性
2. **同步更新** → 前后端类型定义
3. **更新文档** → 契约文档
4. **更新测试** → 覆盖新逻辑
5. **回归测试** → 确保无破坏

---

## 11. 已实现组件清单

### 11.1 面板组件实现状态

| 组件名称 | 文件路径 | 使用技术 | 状态 | 备注 |
|---------|---------|---------|------|------|
| **ListPanelBlock** | `features/panel/components/blocks/ListPanelBlock.vue` | shadcn-vue (Card, Badge, Separator) | ✅ 已实现 | 列表展示，支持标题、描述、元数据 |
| **StatisticCardBlock** | `features/panel/components/blocks/StatisticCardBlock.vue` | shadcn-vue (Card) | ✅ 已实现 | 指标卡片，支持趋势指示器、数字格式化 |
| **LineChartBlock** | `features/panel/components/blocks/LineChartBlock.vue` | shadcn-vue (Card) + ECharts | ✅ 已实现 | 折线图/面积图，支持多系列、时间轴 |
| **BarChartBlock** | `features/panel/components/blocks/BarChartBlock.vue` | shadcn-vue (Card) + ECharts | ✅ 已实现 | 柱状图，支持纵向/横向、堆叠模式 |
| **PieChartBlock** | `features/panel/components/blocks/PieChartBlock.vue` | shadcn-vue (Card) + ECharts | ✅ 已实现 | 饼图/环形图，支持南丁格尔图、可滚动图例 |
| **TableBlock** | `features/panel/components/blocks/TableBlock.vue` | shadcn-vue (Table, Button) + TanStack Table | ✅ 已实现 | 表格，支持排序、分页、自动列检测 |
| **ImageGalleryBlock** | `features/panel/components/blocks/ImageGalleryBlock.vue` | shadcn-vue (Card, Dialog, Button) | ✅ 已实现 | 图片画廊，支持网格布局、Lightbox 灯箱 |
| **FallbackRichTextBlock** | `features/panel/components/blocks/FallbackRichTextBlock.vue` | shadcn-vue (Card, Alert) + marked | ✅ 已实现 | 兜底渲染，支持 Markdown、XSS 防护 |

### 11.2 组件特性对照表

| 组件 | 数据契约 | 响应式图表 | 嵌套支持 | 自定义样式 | 交互功能 |
|-----|---------|----------|---------|-----------|---------|
| ListPanelBlock | ✅ `ListPanelRecord` | N/A | ✅ 支持 children | ❌ 无需 | ✅ 点击跳转 |
| StatisticCardBlock | ✅ `StatisticCardRecord` | N/A | ✅ 支持 children | ❌ 无需 | - |
| LineChartBlock | ✅ `LineChartRecord` | ✅ ResizeObserver | ✅ 支持 children | ✅ 颜色、区域填充 | ✅ Tooltip |
| BarChartBlock | ✅ `BarChartRecord` | ✅ ResizeObserver | ✅ 支持 children | ✅ 颜色、方向、堆叠 | ✅ Tooltip |
| PieChartBlock | ✅ `PieChartRecord` | ✅ ResizeObserver | ✅ 支持 children | ✅ 颜色、环形、玫瑰图 | ✅ Tooltip |
| TableBlock | ✅ `TableViewModel` | N/A | ✅ 支持 children | ❌ 无需 | ✅ 排序、分页 |
| ImageGalleryBlock | ✅ `ImageGalleryRecord` | N/A | ✅ 支持 children | ✅ 列数、宽高比 | ✅ Lightbox 查看 |
| FallbackRichTextBlock | ✅ `FallbackRichTextRecord` | N/A | ✅ 支持 children | ❌ 无需 | - |

### 11.3 组件嵌套架构

所有组件均支持 `UIBlock.children` 嵌套架构，可实现以下组合：
- Card 容器包含多个 StatisticCard
- Tabs 容器包含多个 Chart/Table
- Grid 布局容器包含混合组件

详见 `.agentdocs/panel-nested-components-design.md`

### 11.4 组件注册

所有组件已在以下位置注册：
- **前端清单**：`frontend/src/shared/componentManifest.ts`
- **前端路由器**：`frontend/src/features/panel/components/blocks/DynamicBlockRenderer.vue`
- **后端验证器**：`services/panel/view_models.py` 的 `validate_records()`

---

## 12. 参考资源

### 12.1 官方文档

- **Vue 3**: https://vuejs.org/
- **Vite**: https://vitejs.dev/
- **Pinia**: https://pinia.vuejs.org/
- **shadcn-vue**: https://www.shadcn-vue.com/
- **ECharts**: https://echarts.apache.org/zh/index.html
- **vue-echarts**: https://github.com/ecomfe/vue-echarts
- **Tailwind CSS**: https://tailwindcss.com/

### 12.2 项目内文档

- `docs/backend-panel-view-models.md` - 数据契约文档
- `frontend/SETUP.md` - 前端依赖安装指南
- `.agentdocs/panel-nested-components-design.md` - 组件嵌套架构设计
- `.agentdocs/backend-architecture.md` - 后端架构文档

---

## 13. 全局重要记忆

**技术栈铁律**：
- ✅ 前端框架：**Vue 3 + TypeScript**
- ✅ UI 组件库：**shadcn-vue**（不是 shadcn-ui for React！）
- ✅ 图表库：**ECharts**（不是 Recharts！）
- ✅ 组合方式：shadcn-vue Card/Table + ECharts 图表

**开发规范**：
- 使用 Composition API（`<script setup>`）
- 严格 TypeScript 类型检查
- 契约优先，前后端一致
- 组件可复用，逻辑可测试

**重要约束**：
- ❌ 禁止 React 语法
- ❌ 禁止 Options API
- ❌ 禁止其他 UI 库
- ❌ 禁止其他图表库（针对图表组件）
