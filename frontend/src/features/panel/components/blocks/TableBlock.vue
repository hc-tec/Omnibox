<template>
  <Card>
    <CardHeader v-if="block.title">
      <CardTitle>{{ block.title }}</CardTitle>
      <CardDescription v-if="dataBlock?.stats?.description">
        {{ dataBlock.stats.description }}
      </CardDescription>
    </CardHeader>

    <CardContent>
      <div v-if="isEmpty" class="flex h-[200px] items-center justify-center text-muted-foreground">
        暂无数据
      </div>

      <div v-else class="space-y-4">
        <!-- Table -->
        <div class="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow v-for="headerGroup in table.getHeaderGroups()" :key="headerGroup.id">
                <TableHead
                  v-for="header in headerGroup.headers"
                  :key="header.id"
                  :class="[
                    header.column.getCanSort() ? 'cursor-pointer select-none' : '',
                  ]"
                  @click="header.column.getToggleSortingHandler()?.($event)"
                >
                  <div class="flex items-center">
                    <FlexRender
                      v-if="!header.isPlaceholder"
                      :render="header.column.columnDef.header"
                      :props="header.getContext()"
                    />
                    <span v-if="header.column.getIsSorted()" class="ml-2">
                      {{ header.column.getIsSorted() === 'asc' ? '↑' : '↓' }}
                    </span>
                  </div>
                </TableHead>
              </TableRow>
            </TableHeader>

            <TableBody>
              <TableRow
                v-for="row in table.getRowModel().rows"
                :key="row.id"
                :data-state="row.getIsSelected() ? 'selected' : undefined"
              >
                <TableCell v-for="cell in row.getVisibleCells()" :key="cell.id">
                  <FlexRender
                    :render="cell.column.columnDef.cell"
                    :props="cell.getContext()"
                  />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <!-- Pagination -->
        <div v-if="enablePagination" class="flex items-center justify-between">
          <div class="text-sm text-muted-foreground">
            共 {{ table.getRowCount() }} 条记录
          </div>
          <div class="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              :disabled="!table.getCanPreviousPage()"
              @click="table.previousPage()"
            >
              上一页
            </Button>
            <span class="text-sm text-muted-foreground">
              第 {{ table.getState().pagination.pageIndex + 1 }} /
              {{ table.getPageCount() }} 页
            </span>
            <Button
              variant="outline"
              size="sm"
              :disabled="!table.getCanNextPage()"
              @click="table.nextPage()"
            >
              下一页
            </Button>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed, h } from 'vue';
import {
  FlexRender,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  useVueTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/vue-table';
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
import { Button } from '@/components/ui/button';
import type { ComponentAbility } from '@/shared/componentManifest';
import type { UIBlock, DataBlock } from '@/shared/types/panel';
import { ref } from 'vue';

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const items = (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];

const isEmpty = computed(() => {
  return items.length === 0;
});

function getOption<T>(key: string, fallback: T): T {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.options?.[camel] ?? props.block.options?.[key] ?? fallback) as T;
}

const enablePagination = getOption('enable_pagination', true);
const pageSize = getOption('page_size', 10);
const enableSorting = getOption('enable_sorting', true);

// 构建列定义
const columns = computed<ColumnDef<Record<string, unknown>>[]>(() => {
  if (items.length === 0) return [];

  // 从 props.block.props.columns 获取列配置，或自动检测
  const columnsConfig = props.block.props.columns as Array<{
    field: string;
    header: string;
    sortable?: boolean;
    width?: string;
  }> | undefined;

  if (columnsConfig && columnsConfig.length > 0) {
    // 使用显式配置的列
    return columnsConfig.map((col) => ({
      accessorKey: col.field,
      header: col.header,
      enableSorting: enableSorting && (col.sortable ?? true),
      cell: ({ getValue }: any) => {
        const value = getValue();
        return formatCellValue(value);
      },
    }));
  } else {
    // 自动检测列（从第一条记录）
    const firstItem = items[0];
    const detectedColumns = Object.keys(firstItem).map((key) => ({
      accessorKey: key,
      header: formatHeader(key),
      enableSorting: enableSorting,
      cell: ({ getValue }: any) => {
        const value = getValue();
        return formatCellValue(value);
      },
    }));
    return detectedColumns;
  }
});

function formatHeader(key: string): string {
  // 将字段名转换为友好的标题
  // 例如: created_at -> 创建时间, user_name -> 用户名
  const headerMap: Record<string, string> = {
    title: '标题',
    link: '链接',
    description: '描述',
    author: '作者',
    published_at: '发布时间',
    created_at: '创建时间',
    updated_at: '更新时间',
    count: '数量',
    score: '分数',
    rank: '排名',
  };
  return headerMap[key] || key;
}

function formatCellValue(value: unknown): string | ReturnType<typeof h> {
  if (value === null || value === undefined) {
    return '-';
  }
  if (typeof value === 'string' && value.startsWith('http')) {
    // 如果是链接，渲染为可点击的链接
    return h(
      'a',
      {
        href: value,
        target: '_blank',
        class: 'text-primary hover:underline',
      },
      '查看'
    );
  }
  if (typeof value === 'number') {
    return value.toLocaleString();
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }
  if (Array.isArray(value)) {
    return value.join(', ');
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

// 排序状态
const sorting = ref<SortingState>([]);

// 创建表格实例
const table = useVueTable({
  get data() {
    return items;
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
      typeof updaterOrValue === 'function' ? updaterOrValue(sorting.value) : updaterOrValue;
  },
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: enableSorting ? getSortedRowModel() : undefined,
  getPaginationRowModel: enablePagination ? getPaginationRowModel() : undefined,
  initialState: {
    pagination: {
      pageSize: pageSize,
    },
  },
});
</script>
