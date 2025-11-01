# 智能面板组件视图模型约定（Contract-First 最佳实践）

> 目标：在前后端对接前，先行确定组件可用的数据契约，确保适配器实现与前端渲染逻辑严格一致，避免“字段猜测”和隐式依赖。

---

## 1. 基础原则

1. **契约先行**：所有组件的视图模型（View Model）由前后端共同维护在本文件或共享 Schema 中，未经更新契约不得修改组件字段。
2. **单一职责**：每个组件的视图模型只描述自身渲染所需的信息；跨组件共享字段必须显式注明。
3. **版本治理**：组件契约采用 `component_id@vX` 版本号（默认 v1）。破坏性变更必须新增版本并保留旧版本直至完全迁移。
4. **验证与生成**：
   - 前端依据契约生成 TypeScript 类型 / JSON Schema；
   - 后端适配器输出前先使用相同 Schema 校验；
   - CI/单测禁止“未验证视图模型”的适配器合入。
5. **文档流程**：
   - 新增组件 → 在本文件登记视图模型 → 更新前端 `componentManifest` → 编写适配器；
   - 变更组件 → 升级版本号并描述兼容策略。

---

## 2. 组件视图模型

### 2.1 ListPanel@v1

**描述**：通用列表（标题 + 链接 + 描述）。

```ts
interface ListPanelRecord {
  id: string;
  title: string;
  link?: string | null;
  summary?: string | null;
  published_at?: string | null;      // ISO8601
  author?: string | null;
  categories?: string[] | null;
  [ext: string]: unknown;            // 允许适配器扩展
}

interface ListPanelProps {
  title_field: "title";
  link_field?: "link";
  description_field?: "summary";
  pub_date_field?: "published_at";
}

interface ListPanelOptions {
  show_description?: boolean;
  span?: number;                     // 默认 12
}
```

**适配器约束**：
- 必须至少提供 `title`。
- `published_at` 推荐转换为 UTC ISO 字符串。
- 对应前端组件：`ListPanel`。

---

### 2.2 NumberView@v1（计数/指标卡）

**描述**：展示单个指标及其趋势。

```ts
interface NumberViewRecord {
  id: string;
  label: string;
  value: number;
  unit?: string | null;              // 例如 "人"、"%"
  delta?: {
    value: number;                   // 趋势数值
    label?: string | null;           // 例如 "较昨日"
    trend?: "up" | "down" | "flat";  // 决定 UI 颜色/图标
  } | null;
  description?: string | null;       // 补充信息
}

interface NumberViewProps {
  label_field: "label";
  value_field: "value";
  unit_field?: "unit";
  delta_field?: "delta";
  description_field?: "description";
}

interface NumberViewOptions {
  span?: number;                     // 默认 6
  highlight_threshold?: number | null;
}
```

**适配器约束**：
- 若无法获取数值，请勿返回 NumberView，改用 FallbackRichText。
- `delta.trend` 应根据 value 正负或业务规则计算。

---

### 2.3 TableView@v1（结构化表格）

**描述**：显示多列数据，支持排序/分页等。

```ts
interface TableColumn {
  key: string;                       // 对应 records[*] 的字段
  label: string;                     // 表头显示名称
  type?: "text" | "number" | "date" | "currency" | "tag";
  sortable?: boolean;
  align?: "left" | "center" | "right";
  width?: number;                    // 0-1，表示比例宽度
}

type TableRecord = Record<string, unknown>;

interface TableViewProps {
  columns: TableColumn[];
  data_field: "rows";
}

interface TableViewOptions {
  span?: number;
  page_size?: number;
  enable_download?: boolean;
}

interface TableViewData {
  rows: TableRecord[];
}
```

**适配器约束**：
- `columns[*].key` 必须存在于 `rows[*]` 中。
- 若数值/日期字段需格式化，建议适配器同时提供原始值和格式化字符串（例如 `amount_raw` + `amount_display`），并在 columns 中指向显示字段。

---

### 2.4 LineChart@v1（折线图）

```ts
interface LineChartRecord {
  x: string | number;                // 横轴
  y: number;                         // 纵轴值
  series?: string | null;            // 系列名称
  tooltip?: string | null;
}

interface LineChartProps {
  x_field: "x";
  y_field: "y";
  series_field?: "series";
}

interface LineChartOptions {
  span?: number;
  area_style?: boolean;
  smoothing?: boolean;
}
```

**适配器约束**：
- 时间轴请统一使用 ISO8601 字符串。
- 若无 `series` 字段，视为单系列。

---

### 2.5 FallbackRichText@v1

用于展示无结构数据或作为兜底。

```ts
interface FallbackRecord {
  title?: string | null;
  content: string;                   // Markdown/HTML 均可，前端统一渲染
}

interface FallbackProps {
  title_field?: "title";
  description_field: "content";
}

interface FallbackOptions {
  span?: number;                     // 默认 12
}
```

**适配器约束**：
- 若无法整理数据，应直接返回 FallbackRichText，并将原始 JSON 格式化为 Markdown 代码块，便于调试。

---

## 3. 组件扩展流程

1. **需求提出**：前端/产品明确组件需求，列出 UI 预期与交互。
2. **契约设计**：
   - 与后端协商视图模型，草案写入本文件；
   - 同步更新前端 `componentManifest`、后端 `AdapterBlockPlan` 约定。
3. **Schema 生成**：
   - 推荐使用 JSON Schema 或自定义 dataclass/Pydantic 定义；
   - 生成 TypeScript 类型，供前端静态检查。
4. **适配器实现**：
   - 编写路由适配器，确保产出的 `records`、`props`、`options` 符合契约；
   - 使用单元测试 + Schema 校验保障输出正确。
5. **联调与验收**：
   - Mock 数据对齐 → 真正数据验收 → 回归测试；
   - 不得跳过 Schema 校验直接上线。
6. **变更管理**：
   - 非兼容变更：新增版本号（例如 `TableView@v2`），保留旧版本处理逻辑；
   - 兼容变更：更新文档并同步告知适配器、前端开发。

---

## 4. 推荐工具链

- **Schema 定义**：Pydantic v2 / dataclasses + `pydantic.json_schema()`。
- **验证**：后端在单元测试中使用 Schema 校验适配器输出；前端使用 `zod` 或 Typescript 类型检查。
- **Mock 生成**：将契约样例放入 `tests/fixtures/panel/`，适配器与前端联调可共用。
- **Diff 审核**：引入 JSON Schema Diff 工具，在 CI 中检测破坏性变更。

---

## 5. 下一步建议

1. 在本文件基础上为所有现有组件补齐契约并标注版本号。
2. 建立自动化测试（后端适配器输出 → Schema 校验）与前端故事本（Storybook）示例，保障契约一致性。
3. 当引入新组件时，先更新契约再开发代码，杜绝“先写代码再对齐字段”的流程。
