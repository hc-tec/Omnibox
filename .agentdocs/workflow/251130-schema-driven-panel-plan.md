# 方案：Schema 驱动的 Panel 生成与可编程 UI 工作流（修订版）

## 背景与问题
1. **复杂分析→固定 UI 的断层**：现有流程在 data_operator 等算子执行后，只能产出“列表 + 轻量裁剪”，最终必然回落到 ListPanel，无法表达“指标卡”“聚类”“多源对比”等复杂洞察。
2. **混合数据源难以自适应**：当用户同时需要 B 站、知乎甚至私有资产的数据时，适配器无法理解“跨源字段”，只能写死或复制多份逻辑。
3. **LLM 不可直接读取原始数据**：任何将原文 / 全量列表送入 LLM 的做法都违背限制，现有的 geojson 截断只解决了一小部分场景。
4. **UI 可组合性缺失**：前端组件已经 manifest 化，仍缺少一个“受控但灵活”的桥梁，让 LLM 可以像前端同事一样拼装嵌套布局。

## 设计目标
- **绝不暴露原始数据**：LLM 只能接触 schema + summary + preview，不得直接读取 data_store 中的原始记录。
- **Schema → UI 解耦**：工具层负责产出“结构化洞察”，UI 渲染器依据 schema/DSL 映射组件；新增场景无需为每个数据源写补丁。
- **可编程但安全**：允许 LLM 生成 DSL / sandbox 代码来组合 UI，但所有动作均在 manifest + 受限运行环境内进行。
- **多源融合与嵌套布局**：支持在同一 Panel 中组合多平台数据、嵌套 Tab/Section/Metric + List 的复杂结构。

## 方案概述
### 1. Structured Data Envelope
工具输出统一封装成 envelope：
```jsonc
{
  "data_id": "lg-xxxx",
  "schema": { ... },            // 字段/类型定义，可支持 geojson、表格、树等
  "summary": "...",             // 500 字以内
  "preview": [{ ... }],         // 只保留 displayable 字段，自动截断
  "cursor": { "total": 300, "sampled": 20, "next": "..." },
  "metadata": { "source": "bilibili", "timestamp": "..." }
}
```
- LLM 可读取 schema/summary/preview/cursor，并可请求更多 preview（仍由 runtime 控制）。
- 多源合并时，算子需输出统一 schema，如 `platform` 枚举字段用于区分 B 站/知乎。

### 2. Insight Schema（分析层）
分析类算子 / LLM 产生的洞察结果使用 `display_schema` 描述：
```jsonc
{
  "kind": "metric_set" | "comparison" | "cluster" | "timeline" | "story_graph" | ...,
  "title": "高赞观点统计",
  "summary": "...",
  "fields": { ... },          // 不同 kind 的 payload
  "source_refs": ["lg-123"]
}
```
- kind 约定：metric_set、comparison、cluster、timeline、narrative、playbook、alert、story_graph、artifact_list 等。
- 所有 kind 都包含独立引用，前端可溯源/展开原始 data_id。

### 3. Panel DSL + Sandbox（增强）
1. **Component Manifest**：前端以 JSON 声明所有组件的 props schema、数据契约、是否允许 children，并对每个组件注明输入契约（ViewModel）。
2. **Panel DSL**：LLM 输出结构化 AST，支持数据绑定、转换管线与交互事件：
```jsonc
{
  "node": "TabGroup",
  "props": { "tabs": ["B站热搜","知乎热搜"] },
  "events": {
    "on_change": {
      "action": "refresh_panel",
      "params": { "filter_platform": "$event.value" }
    }
  },
  "children": [
    {
      "node": "ListPanel",
      "data_binding": {
        "data_id": "lg-123",
        "filters": { "platform": "bilibili" },
        "transformation": {
          "type": "inline_python",
          "code": "df[['title','rank','platform']].query('platform==\"bilibili\"')"
        }
      },
      "props": { "show_metadata": true }
    },
    ...
  ]
}
```
3. **Sandbox Runner**：提供受限 Python/DSL 环境，LLM 生成的代码只能调用白名单 API（DataFrame filter/aggregate）。输入为 envelope 的 preview + schema + cursor，输出为 **ViewModel**（遵循组件契约），禁止前端再加工数据。
4. **校验器 + 组件级退化**：DSL、ViewModel 均需通过校验。若某组件 props 不合法，仅替换该节点为 `ErrorCard/JsonViewer`，其余结构保持。严重异常才回退安全模板。

### 3.5 ViewModel 中间协议
- Sandbox 输出统一 `ViewModel` 格式，例如 `{ "data": [...], "props": {...} }`，直接映射到 Manifest。
- ViewModel 是日志/回放与复现的基线，便于定位数据→UI 过程中的问题。

## 关键工作流映射
| 工作流 | Envelope/Schema 重点 | UI DSL 例子 |
| --- | --- | --- |
| 爆款解构 | Transcript envelope + story_graph schema + gap_report | GraphNavigator + MetricCard + GapList |
| 观众心智 | Comment pagination envelope → sentiment metric_set → cluster | EmotionGauge + ListPanel(filter=negative) + Accordion(cluster) |
| 实时热点 | Alert schema + playbook schema + artifact_list | AlertBanner + MultiColumn + PlaybookCard |
| 创作灵感 | 私有语雀/GitHub/B站 envelope + related_assets schema | TabGroup（按来源）+ Nested List + Metric “已找到灵感 7 条” + 点击素材触发 server action |
| 诊断修复 | Multi-source search envelope + comparison schema | RankedList + SourceStatus + NarrativeSummary |
| 异构合成 | 股价 metric_set + 新闻 record_set + 社媒 record_set + context_brief | MetricCard + Timeline + SummaryList |

## 安全与合规
- **原始数据隔离**：LLM 永远无法看到 `data_store.load()` 的完整内容；preview 自动截断并过滤敏感字段。
- **Sandbox 限制**：CPU/时间/行数配额，禁止任何 I/O、网络访问，仅提供 DataFrame API；输出 ViewModel 必须通过契约校验。
- **Manifest 检索**：通过 RAG/索引仅注入本次需要的组件定义，避免将全部 manifest 塞进 LLM。
- **审批链路**：若 DSL 或 sandbox 结果不合法，组件级 fallback → `ErrorCard`，并写入日志用于后续优化。
- **溯源**：所有 schema/DSL 节点带 `source_refs`，前端 UI 可直接展示数据来源/失败节点。

## 实施路线
1. **定义模型**：
   - `StructuredEnvelope`, `DisplaySchema`, `PanelDSL`（Pydantic 模型 + 校验器）。
   - 明确各 schema kind 的字段规范与示例。
2. **数据层改造**：
   - 统一 data_operator/data_aggregator 输出 envelope + preview/cursor。
   - 多源场景实现 merge 工具（保留平台枚举）。
3. **Sandbox & DSL**：
   - 开发受限执行器（Mini Python/WASM），提供 filter/aggregate API，输出 ViewModel。
   - 构建 DSL 解析与前端渲染器，支持 children 嵌套、data_binding（含 transformation）、事件、server action。
4. **组件 manifest**：
   - 汇总现有 Panel 组件的 props/data_contract，补齐 MetricCard、ClusterList、Playbook、StoryGraph 等。
5. **场景验证**：
   - 以“观众心智”、“爆款解构”两个工作流试点，验证 schema→sandbox→ViewModel→DSL→UI 全链路，涵盖嵌套布局与交互。
   - 梳理 fallback 流程与监控指标（沙箱失败率、DSL 校验失败率、组件级退化次数）。
6. **扩展到事件驱动/私有数据**：
   - Trigger 节点输出 alert schema；私有插件 envelope 继承同一规范。
   - 引入任务历史面板、常驻任务调度与通知集成，支持 Webhook/飞书等通知通道。

## 成功标准
- 100% 检查点：LLM 任意节点都无法访问原始记录，只能看到 schema/preview。
- 解决 组件僵化：同一工作流可组合 Metric + List + Tab + Nested Section，无需后端写死。
- 多源/多场景复用：新增平台或分析指令，只需保证工具输出标准 schema；UI 自动适配。
- 可观测性：所有失败/回退都有明确日志，方便持续优化提示与模型；ViewModel/DSL 可回放复现。
- Skeleton 体验：初次响应 < 500ms（渲染骨架），后续数据流式填充。
- 研究流集成：`research_panel` / `research_analysis` / `research_complete` WebSocket 消息统一携带 `panel_spec`（envelope、display_schema、view_model、panel_dsl、rendered_preview），前端可在研究模式下复用相同的 SDUI 渲染逻辑。

---
通过 Structured Envelope + Display Schema + ViewModel + Panel DSL + Sandbox 的组合，我们既保持了数据安全，又给 Planner/Reflector 足够的可编程空间。复杂工作流不再依赖硬编码 adapter，而是由 LLM 在受控环境下拼装组件，实现真正的灵活 + 可控的 UI 生成链路，并具备交互闭环、Skeleton 体验与全面可观测性。

## 2025-11-30 实施进展（面向 Runtime/DSL 运行时）

### 1. DSL 渲染器容错机制
- **节点级兜底**：`PanelDSLRenderer` 现在会以 `_render_node_with_fallback()` 包裹所有节点；一旦数据绑定、Sandbox 转换或 ViewModel 引用失败，只会降级该节点，不影响其他节点。
- **降级视图结构**：降级块统一渲染为 `FallbackRichText`，在 `props/options` 中写入 `original_component` 与 `degraded=true`，便于前端标注异常来源并给出调试提示。
- **错误可观察性**：`SandboxExecutionError` 会带上具体信息，Renderer 会截断并塞入降级块内容中，防止 Runtime 静默失败。

### 2. ViewModel 引用与数据绑定对齐
- 当 DSL 中引用 `view_model_id` 时，Renderer 现在会显式验证该 ID 是否存在于传入的 `view_models` registry，并在缺失时抛出受控异常 → 触发降级渲染。
- 研究/查询链路在构建 panel_spec metadata 时会把同一 `view_models` registry 注入 `PanelRuntime.render_dsl()`，确保 preview/回放与实时渲染一致。

### 3. 组件白名单治理
- **默认白名单**：新增 `services/panel/component_whitelist.py`，自动从 `ComponentRegistry.default_components()` 收集所有数据组件 ID，并补充 TabGroup/Accordion/Section 等容器组件。
- **Runtime 入口**：`PanelRuntime` 默认开启 `enforce_component_whitelist`，在未显式传参时会加载上述白名单。若 DSL 中含未知组件会在 parse 阶段直接拒绝。
- **可控扩展**：Runtime 构造函数提供 `enforce_component_whitelist=False`，供实验阶段或脚本注入自定义节点；也允许调用方传入额外白名单集合。

### 4. 测试覆盖
- `tests/services/test_panel_structured_pipeline.py` 新增 10 个单测，覆盖：
  - 嵌套容器渲染、view_model 绑定、Runtime 接收 `PanelDSL` 模型实例。
  - envelope/view_model 缺失时的降级行为。
  - Runtime 默认/关闭白名单两种行为。
  - Sandbox inline python 的安全限制。

### 5. 前后端组件清单同步
- 新增 `component_whitelist.build_component_whitelist()` 对前端 `componentManifest.ts` 进行解析，后端白名单自动包含所有前端声明组件，杜绝“前端组件新增但后端拒绝”的不一致。
- 默认运行时仍可选传入 `extra_components` 或通过 `enforce_component_whitelist=False` 关闭校验，方便实验性组件落地。
- 新增单测验证自定义 manifest 文件解析，保证 regex 解析逻辑可控。

### 6. Sandbox 受控算子扩展
- 新增 `sort_by` / `slice` / `group_count` 三个内置算子，覆盖排序、区间切片、分组计数三类常用面板级操作，所有输出都保持“列表 + dict”结构，直接供组件消费。
- 内置算子统一通过 `TransformationSpec(type="builtin", code=...)` 调用，仍可叠加 `head` / `select_fields` 等操作，实现“先排序再取 Top-N”。
- 扩展后的环境依然禁止 I/O / data_store 访问，仅对 preview 数据做纯内存计算；错误通过 `SandboxExecutionError` 抛出并被 Renderer 降级。
- 单测补充 sort/slice/group 组合用例，确保受限环境行为可预期。
- 2025-11-30：新增 `rename_fields` 内置算子，支持字段重命名/映射，解决前端 props 与数据字段不一致的问题；依旧在受控映射表内执行。
- 2025-11-30：补充 `aggregate_numeric`（输出 count/sum/avg/min/max）与 `coerce_number`（字段类型转换）内置算子，满足 preview 级快速汇总与类型对齐需求，相关测试已覆盖。
- 2025-11-30：引入 `pipeline` TransformationSpec，支持通过 `steps` 列表顺序执行多个 builtin（如 rename_fields → coerce_number → aggregate_numeric），面板 DSL 可以直接声明组合流程，无需 inline_python。
  ```jsonc
  {
    "node": "StatisticCard",
    "data_binding": {
      "data_id": "lg-123",
      "transformation": {
        "type": "pipeline",
        "params": {
          "steps": [
            { "code": "rename_fields", "params": { "mapping": { "播放量": "views" } } },
            { "code": "coerce_number", "params": { "field": "views", "target_field": "views_num" } },
            { "code": "aggregate_numeric", "params": { "field": "views_num" } }
          ]
        }
      }
    },
    "props": { "title": "累计播放量" }
  }
  ```
  上述 DSL 将中文字段映射为标准字段 → 转换类型 → 输出统计指标，仅依赖 preview 数据即可驱动指标卡。

### 8. Planner 指南（草案）
- **Pipeline 优先**：Planner 在需要执行多步 preview 处理时，应优先生成 `transformation: { "type": "pipeline" }`，将多个 builtin 串联，避免 inline_python。
- **常见模式**：
  1. **列表过滤/排序**：`pipeline` 内使用 `sort_by` → `head`，之后绑定到 `ListPanel`。
  2. **聚合指标**：`rename_fields`（将平台特定字段映射到统一名称）→ `coerce_number`（获得 `*_num`）→ `aggregate_numeric`（产出 sum/avg）→ 绑定 `StatisticCard` 或 `MetricSet`。
  3. **分组计数**：`rename_fields` → `group_count`（限制 limit 5-10）→ `ListPanel`/`BarChart`。
- **命名约定**：
  - `rename_fields.mapping` 目标字段应与前端 props 使用的语义一致（如 `views`, `likes`, `platform`）。
  - `coerce_number.target_field` 建议使用 `<field>_num`，便于后续 agg/builtin 复用。
  - `aggregate_numeric` 返回 `count/sum/avg/min/max`，Planner 需指示组件 props 从这些字段读取值，如 `props.metric_value_field = "sum"`。
- **Prompt 实施**：`LLMComponentPlanner` 的 `_build_prompt` 已在 payload 中注入 `transformation_guidelines`，明确 pipeline 原则，并附带两个 JSON 示例（rename→coerce→aggregate、sort→head）。新增 `tests/services/test_llm_component_planner.py` 校验 prompt 含相关关键字。

### 7. 降级信息透出
- `panel_spec` 元数据新增 `degraded_components`，Runtime 在渲染 DSL 时收集所有被 Fallback 替换的节点，包含 block_id / 原组件 / 提示文案，前端无需解析 options 即可知晓退化情况。
- `build_panel_spec_metadata()` / `build_panel_spec_metadata_from_components()` 都输出该字段，并在异常时记录 `{"error": ...}` 方便追踪。
- 对应单测 `test_panel_spec_metadata_reports_degraded_blocks` 验证 metadata 确实包含退化节点列表。
- ChatService 会将 `panel_spec.degraded_components` 同步复制到顶层 `metadata["panel_degraded_components"]`，方便前端直接订阅，无需解析整个 panel_spec 结构。

TODO（下一阶段）
1. 观察真实 Planner 日志，收集 LLM 输出的 pipeline 质量，酌情扩充更多场景示例（如分组统计→图表），并持续通过自动化回归测试验证。
