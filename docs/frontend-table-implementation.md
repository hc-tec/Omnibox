# Table 组件前端实现指南

> 创建时间：2025-11-09
> 更新时间：2025-11-09
> 状态：✅ 后端契约已完成，等待前端实现
> **技术栈**: Vue 3 + shadcn-vue

---

## 1. 组件概述

**Table** 是用于展示结构化数据的表格组件，支持排序、分页、多列展示等功能。

### 核心特性
- ✅ 基于 shadcn-vue Table 组件
- ✅ 底层使用 TanStack Table v8
- ✅ 支持自定义列定义（类型、对齐、宽度）
- ✅ 支持列排序
- ✅ 支持分页
- ✅ 支持多种列类型（文本、数字、日期、货币、标签）
- ✅ Vue 3 Composition API
- ✅ TypeScript 完整支持
- ✅ 响应式设计

---

## 2. 数据契约

### TypeScript 接口（已完成）

```typescript
// frontend/src/shared/types/panelContracts.ts
export interface TableColumn {
  key: string;
  label: string;
  type?: "text" | "number" | "date" | "currency" | "tag" | null;
  sortable?: boolean;
  align?: "left" | "center" | "right" | null;
  width?: number | null;  // 相对宽度，0.0 ~ 1.0
}

export interface TableViewModel {
  columns: TableColumn[];
  rows: Record<string, any>[];
}
```

### 数据示例

```json
{
  "columns": [
    {
      "key": "name",
      "label": "项目名称",
      "type": "text",
      "sortable": true,
      "align": "left",
      "width": 0.4
    },
    {
      "key": "stars",
      "label": "Stars",
      "type": "number",
      "sortable": true,
      "align": "right",
      "width": 0.2
    },
    {
      "key": "language",
      "label": "语言",
      "type": "tag",
      "sortable": false,
      "align": "center",
      "width": 0.2
    },
    {
      "key": "updated_at",
      "label": "更新时间",
      "type": "date",
      "sortable": true,
      "align": "left",
      "width": 0.2
    }
  ],
  "rows": [
    {
      "name": "octocat/hello-world",
      "stars": 12345,
      "language": "Python",
      "updated_at": "2024-01-15T10:30:00Z"
    },
    {
      "name": "user/awesome",
      "stars": 9876,
      "language": "JavaScript",
      "updated_at": "2024-01-14T08:20:00Z"
    }
  ]
}
```

---

## 3. 安装依赖

### 3.1 安装 shadcn-vue Table 组件

```bash
cd frontend
npx shadcn-vue@latest add table
npx shadcn-vue@latest add badge  # 用于 tag 类型列
npx shadcn-vue@latest add button  # 用于排序按钮
npx shadcn-vue@latest add card  # 用于容器
```

### 3.2 安装 TanStack Table

```bash
npm install @tanstack/vue-table
```

### 3.3 安装图标库（可选）

```bash
npm install lucide-vue-next
```

---

## 4. Props 定义

```typescript
interface TableProps {
  data: {
    items: TableViewModel[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {};  // Table 不需要字段映射，数据自包含列定义
  options?: {
    pagination?: boolean;
    pageSize?: number;
    span?: number;
  };
  id: string;
  title?: string;
}
```

---

## 5. 核心实现

### 5.1 文件结构

```
frontend/src/features/panel/components/
└── Table/
    ├── Table.vue          # 主组件
    ├── utils.ts           # 工具函数（格式化等）
    └── __tests__/
        └── Table.spec.ts
```

### 5.2 主组件

```vue
<!-- frontend/src/features/panel/components/Table/Table.vue -->
<script setup lang="ts">
import { computed, ref } from 'vue';
import {
  useVueTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  type ColumnDef,
  type SortingState,
  FlexRender,
} from '@tanstack/vue-table';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table as UITable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { ArrowUpDown, ChevronLeft, ChevronRight } from 'lucide-vue-next';
import type { TableViewModel, TableColumn } from '@/shared/types/panelContracts';
import { formatCellValue, getAlignClass } from './utils';

interface Props {
  data: {
    items: TableViewModel[];
    schema: any;
    stats: Record<string, any>;
  };
  props: {};
  options?: {
    pagination?: boolean;
    pageSize?: number;
    span?: number;
  };
  title?: string;
  id: string;
}

const props = withDefaults(defineProps<Props>(), {
  options: () => ({
    pagination: true,
    pageSize: 20,
    span: 12,
  }),
});

// 提取 TableViewModel（通常只有一个元素）
const tableData = computed(() => {
  if (!props.data.items || props.data.items.length === 0) {
    return { columns: [], rows: [] };
  }
  return props.data.items[0];
});

const sorting = ref<SortingState>([]);

// 将 TableColumn[] 转换为 TanStack Table 的 ColumnDef[]
const columns = computed<ColumnDef<Record<string, any>>[]>(() => {
  return tableData.value.columns.map((col: TableColumn) => ({
    accessorKey: col.key,
    header: ({ column }) => {
      if (!col.sortable) {
        return h('div', { class: getAlignClass(col.align) }, col.label);
      }
      return h(
        Button,
        {
          variant: 'ghost',
          size: 'sm',
          class: '-ml-3 h-8',
          onClick: () => column.toggleSorting(column.getIsSorted() === 'asc'),
        },
        () => [
          h('span', { class: getAlignClass(col.align) }, col.label),
          h(ArrowUpDown, { class: 'ml-2 h-4 w-4' }),
        ]
      );
    },
    cell: (info) => {
      const value = info.getValue();
      const formatted = formatCellValue(value, col.type);
      return h('div', { class: getAlignClass(col.align) }, formatted);
    },
    enableSorting: col.sortable ?? false,
    meta: {
      align: col.align || 'left',
      width: col.width,
    },
  }));
});

const table = useVueTable({
  get data() {
    return tableData.value.rows;
  },
  get columns() {
    return columns.value;
  },
  state: {
    get sorting() {
      return sorting.value;
    },
  },
  onSortingChange: (updaterOrValue) => {
    sorting.value =
      typeof updaterOrValue === 'function'
        ? updaterOrValue(sorting.value)
        : updaterOrValue;
  },
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
  getPaginationRowModel: props.options?.pagination
    ? getPaginationRowModel()
    : undefined,
  initialState: {
    pagination: props.options?.pagination
      ? { pageSize: props.options.pageSize || 20 }
      : undefined,
  },
});

const isEmpty = computed(() => {
  return !tableData.value.columns || tableData.value.columns.length === 0;
});
</script>

<template>
  <Card>
    <CardHeader v-if="title">
      <CardTitle>{{ title }}</CardTitle>
      <CardDescription v-if="data.stats?.description">
        {{ data.stats.description }}
      </CardDescription>
    </CardHeader>

    <CardContent>
      <div
        v-if="isEmpty"
        class="flex h-[320px] items-center justify-center text-muted-foreground"
      >
        暂无数据
      </div>

      <template v-else>
        <div class="rounded-md border">
          <UITable>
            <TableHeader>
              <TableRow
                v-for="headerGroup in table.getHeaderGroups()"
                :key="headerGroup.id"
              >
                <TableHead
                  v-for="header in headerGroup.headers"
                  :key="header.id"
                  :style="{
                    width: header.column.columnDef.meta?.width
                      ? `${header.column.columnDef.meta.width * 100}%`
                      : 'auto',
                  }"
                >
                  <FlexRender
                    v-if="!header.isPlaceholder"
                    :render="header.column.columnDef.header"
                    :props="header.getContext()"
                  />
                </TableHead>
              </TableRow>
            </TableHeader>

            <TableBody>
              <template v-if="table.getRowModel().rows?.length">
                <TableRow
                  v-for="row in table.getRowModel().rows"
                  :key="row.id"
                  :data-state="row.getIsSelected() ? 'selected' : undefined"
                >
                  <TableCell
                    v-for="cell in row.getVisibleCells()"
                    :key="cell.id"
                  >
                    <FlexRender
                      :render="cell.column.columnDef.cell"
                      :props="cell.getContext()"
                    />
                  </TableCell>
                </TableRow>
              </template>
              <TableRow v-else>
                <TableCell
                  :colspan="columns.length"
                  class="h-24 text-center"
                >
                  无结果
                </TableCell>
              </TableRow>
            </TableBody>
          </UITable>
        </div>

        <div
          v-if="options?.pagination"
          class="flex items-center justify-between space-x-2 py-4"
        >
          <div class="text-sm text-muted-foreground">
            第 {{ table.getState().pagination.pageIndex + 1 }} 页，共
            {{ table.getPageCount() }} 页
          </div>
          <div class="flex space-x-2">
            <Button
              variant="outline"
              size="sm"
              :disabled="!table.getCanPreviousPage()"
              @click="table.previousPage()"
            >
              <ChevronLeft class="h-4 w-4" />
              上一页
            </Button>
            <Button
              variant="outline"
              size="sm"
              :disabled="!table.getCanNextPage()"
              @click="table.nextPage()"
            >
              下一页
              <ChevronRight class="h-4 w-4" />
            </Button>
          </div>
        </div>
      </template>
    </CardContent>
  </Card>
</template>
```

---

### 5.3 工具函数

```typescript
// frontend/src/features/panel/components/Table/utils.ts
import { h } from 'vue';
import { Badge } from '@/components/ui/badge';

/**
 * 根据列类型格式化单元格值
 */
export function formatCellValue(
  value: any,
  type?: "text" | "number" | "date" | "currency" | "tag" | null
) {
  if (value === null || value === undefined) {
    return h('span', { class: 'text-muted-foreground' }, '-');
  }

  switch (type) {
    case 'number':
      return typeof value === 'number'
        ? value.toLocaleString()
        : value;

    case 'currency':
      return typeof value === 'number'
        ? `¥${value.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
          })}`
        : value;

    case 'date':
      try {
        const date = new Date(value);
        return date.toLocaleDateString('zh-CN');
      } catch {
        return value;
      }

    case 'tag':
      return h(Badge, { variant: 'secondary' }, () => value);

    case 'text':
    default:
      return String(value);
  }
}

/**
 * 获取对齐样式类名
 */
export function getAlignClass(align?: 'left' | 'center' | 'right' | null): string {
  switch (align) {
    case 'center':
      return 'text-center';
    case 'right':
      return 'text-right';
    default:
      return 'text-left';
  }
}
```

---

## 6. 集成到面板系统

```typescript
// frontend/src/features/panel/components/index.ts
import Table from './Table/Table.vue';

export const PanelComponents = {
  ListPanel: () => import('./ListPanel/ListPanel.vue'),
  StatisticCard: () => import('./StatisticCard/StatisticCard.vue'),
  LineChart: () => import('./LineChart/LineChart.vue'),
  BarChart: () => import('./BarChart/BarChart.vue'),
  Table,  // 新增
  FallbackRichText: () => import('./FallbackRichText/FallbackRichText.vue'),
};
```

---

## 7. 测试用例

```typescript
// frontend/src/features/panel/components/Table/__tests__/Table.spec.ts
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import Table from '../Table.vue';
import type { TableViewModel } from '@/shared/types/panelContracts';

describe('Table', () => {
  const mockTableData: TableViewModel = {
    columns: [
      { key: 'name', label: '项目名称', type: 'text', sortable: true, align: 'left', width: 0.4 },
      { key: 'stars', label: 'Stars', type: 'number', sortable: true, align: 'right', width: 0.2 },
      { key: 'language', label: '语言', type: 'tag', sortable: false, align: 'center', width: 0.2 },
      { key: 'updated_at', label: '更新时间', type: 'date', sortable: true, align: 'left', width: 0.2 },
    ],
    rows: [
      {
        name: 'octocat/hello-world',
        stars: 12345,
        language: 'Python',
        updated_at: '2024-01-15T10:30:00Z',
      },
      {
        name: 'user/awesome',
        stars: 9876,
        language: 'JavaScript',
        updated_at: '2024-01-14T08:20:00Z',
      },
    ],
  };

  it('renders table with data', () => {
    const wrapper = mount(Table, {
      props: {
        id: 'test-table',
        data: { items: [mockTableData], schema: {}, stats: {} },
        props: {},
        title: 'GitHub 项目',
      },
    });

    expect(wrapper.text()).toContain('GitHub 项目');
    expect(wrapper.text()).toContain('项目名称');
    expect(wrapper.text()).toContain('Stars');
    expect(wrapper.text()).toContain('octocat/hello-world');
    expect(wrapper.text()).toContain('12,345');
  });

  it('shows empty state when no data', () => {
    const wrapper = mount(Table, {
      props: {
        id: 'test-table',
        data: { items: [], schema: {}, stats: {} },
        props: {},
      },
    });

    expect(wrapper.text()).toContain('暂无数据');
  });
});
```

---

## 8. 后端适配器示例

```python
from services.panel.view_models import TableViewModel, TableColumn

@route_adapter("/github/repos/compare", manifest=COMPARE_MANIFEST)
def github_repos_compare_adapter(
    source_info: SourceInfo,
    records: Sequence[Dict[str, Any]],
    context: Optional[AdapterExecutionContext] = None,
) -> RouteAdapterResult:
    table_model = TableViewModel(
        columns=[
            TableColumn(
                key="name",
                label="项目名称",
                type="text",
                sortable=True,
                align="left",
                width=0.3,
            ),
            TableColumn(
                key="stars",
                label="Stars",
                type="number",
                sortable=True,
                align="right",
                width=0.15,
            ),
            TableColumn(
                key="language",
                label="语言",
                type="tag",
                sortable=False,
                align="center",
                width=0.2,
            ),
            TableColumn(
                key="updated_at",
                label="更新时间",
                type="date",
                sortable=True,
                align="left",
                width=0.2,
            ),
        ],
        rows=[
            {
                "name": item["name"],
                "stars": item["stargazers_count"],
                "language": item["language"],
                "updated_at": item["updated_at"],
            }
            for item in records
        ],
    )

    validated = validate_records("Table", [table_model.model_dump()])

    return RouteAdapterResult(
        records=validated,
        block_plans=[
            AdapterBlockPlan(
                component_id="Table",
                props={},
                options={
                    "pagination": True,
                    "page_size": 20,
                    "span": 12,
                },
                title="GitHub 项目对比",
                confidence=0.90,
            )
        ],
        stats={"total_rows": len(table_model.rows)},
    )
```

---

## 9. 开发清单

### 后端部分 ✅ 已完成
- [x] 契约文档更新
- [x] Pydantic 模型定义
- [x] 契约验证函数
- [x] 单元测试
- [x] TypeScript 类型定义
- [x] 组件清单注册

### 前端部分 ⏳ 待实现
- [ ] 安装 shadcn-vue Table 组件
- [ ] 安装 @tanstack/vue-table
- [ ] 实现 Table.vue 组件
- [ ] 工具函数（格式化等）
- [ ] 单元测试
- [ ] 集成到面板系统

---

## 10. 注意事项

### 10.1 性能优化

1. **虚拟滚动**: 如果数据量超过 1000 行，考虑使用 `@tanstack/vue-virtual`
2. **分页策略**: 默认每页 20 行，可根据实际情况调整
3. **排序性能**: TanStack Table 内置排序性能较好

### 10.2 无障碍支持

1. shadcn-vue Table 已内置 ARIA 属性
2. 确保键盘可导航
3. 排序按钮提供明确的状态指示

### 10.3 列类型处理

- **text**: 直接显示字符串
- **number**: 千分位格式化（如 `12,345`）
- **date**: ISO8601 → 本地化日期格式
- **currency**: 货币格式（如 `¥1,234.56`）
- **tag**: 使用 shadcn-vue Badge 组件

---

## 附录：参考资源

- **shadcn-vue Table 文档**: https://www.shadcn-vue.com/docs/components/table.html
- **TanStack Table 官方文档**: https://tanstack.com/table/v8
- **shadcn-vue Badge 文档**: https://www.shadcn-vue.com/docs/components/badge.html
- **Vue 3 官方文档**: https://vuejs.org/
