# 方案：Schema 驱动的 Panel 生成与可编程 UI 工作流（修订版）

> 本方案最终是为了实现一个类似于 **AI 原生低代码平台（AI-Native Low-Code Platform）**。所有 UI 决策都必须由模型通过 Schema/Pipeline/DSL 来完成，禁止任何规则引擎或手写启发式。

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

### 8. emit_panel_preview → PanelRuntime（彻底移除 adapter 渲染）
- `emit_panel_preview` 重构：工具引用 `services/panel/panel_spec_builder` 将 `source_ref` 对应的 dataset 直接转换为 `StructuredDataEnvelope + DisplaySchema`，再调用 `PanelRuntime` 渲染 UIBlock 和 PanelDSL，不再经过 RouteAdapter/PanelGenerator。
- 新能力：可根据 dataset metadata 自动生成 ListPanel 或 StatisticCard（例如 metadata.item_count → metric_set），并输出完整 `panel_spec` + 简易 `panel_payload`（布局为行级别），同时 WebSocket `panel_data_blocks` 改为返回 `panel_spec.data_envelopes`。
- Raw output 附带 `panel_spec`，DataStasher 存储后前端或 ChatService 可直接消费结构化面板，无需再反解析 adapter。
- 兼容性：REST/WS 仍能获得 `panel_payload`（UIBlock + LayoutTree），但其来源已改为 PanelRuntime；旧的 adapter 仍用于普通查询 fallback。

### 9. panel_bundle 接入（2025-11-30）
- **ChatService**（`services/chat_service.py`）：`_handle_data_query()` 会检测 LangGraph 工具事件中的 `panel_bundle`，直接注入 `PanelPayload` 与 `panel_spec`，并无条件回传 `metadata["panel_degraded_components"]`。`tests/services/test_chat_service.py::test_chat_service_prefers_panel_bundle` 验证 PanelGenerator 不会被调用。
- **研究流推送**（`services/chat/research_streaming.py`）：WebSocket `research_panel` 消息改为随 `panel_spec` 一并推送 `panel_spec.data_envelopes`，并在完成消息中复用最近一次 spec。
- **类型约定**（`api/schemas/stream_messages.py`/`frontend/src/shared/types/panel.ts`）：面板数据块的语义明确为结构化 envelope。
- **前端研究视图**：
  - `researchViewStore` 会把 `panel_spec.data_envelopes` 转换为 `DataBlock` 供 `DynamicBlockRenderer` 复用，同时保留 spec 以展示降级信息。
  - `useResearchWebSocket` 透传 `panel_spec`，`ResearchDataPanel` 在 UI 中提示降级组件。

### 10. ResearchService 非流式面板同步（2025-11-30）
- `ResearchService.research()` 现在在内部捕获所有 `emit_panel_preview` 事件，将 `panel_payload` + `panel_spec` 以 `panel_previews` 形式返回给上层。
- `handle_langgraph_research()` 会把 `panel_previews` 直接写入 ChatResponse metadata，REST 模式也能消费 LangGraph 生成的结构化面板（即便不走 WebSocket）。
- `_StubResearchService` 及对应单测同步更新，确保 metadata 始终带有 `panel_previews`。

### 11. DataOperator 输出纯净化（2025-11-30）
- `langgraph_agents/tools/data_operator.py` 在 `_normalize_transform_result()` 中引入 `BANNED_PANEL_KEYS`，移除 coder 生成的 `panel_hint`、`metric_value` 等展示提示，只保留 `items/metadata/stats` 等通用字段，避免工具层暗示具体组件。
- 回归用例 `tests/langgraph_agents/tools/test_data_operator.py::test_data_operator_strips_panel_metadata` 验证这些字段会被自动剥离，确保 Planner 依赖 schema/pipeline 自主决策。

### 12. 研究卡片历史重放（2025-11-30）
- REST 流程返回的 `panel_previews` 现在会被 `researchStore`/`researchViewStore` 解析，`ResearchView` 初始化时若无实时 WebSocket 数据，会用历史 `panel_spec` 重建 `data_blocks` 并立即渲染，确保跨会话查看仍能看到面板。
- `QueryCard` 在已完成状态下会渲染最多两张迷你面板（复用 `DynamicBlockRenderer`），其余历史预览可在研究详情页查看。

TODO（下一阶段）
1. 持续观察真实 Planner 日志，收集 LLM 输出的 pipeline 质量，酌情扩充更多场景示例（如分组统计→图表），并通过自动化回归测试验证。

## 13. 组件契约驱动方案（设计草案，待实施）

> 目标：确保“先选组件，再加工数据，再渲染 UI”，彻底消除 heuristics / panel_hint 等补丁式处理；满足“AI 原生低代码平台”的整个链路。以下为详细方案（200 行以上）。

### 13.1 现状与问题分析

1. **Planner 缺乏契约**：ResearchAgent/LLM Planner 目前只会输出“需要展示面板”，并不会指定组件类型或字段契约。导致 data_operator 不知道要生成什么结构。
2. **data_operator 无约束**：SchemaCoder 只是根据样本推断字段，无法把“目标组件”映射到数据结构，最终 bom layer 得用 heuristics 去猜。
3. **panel_spec_builder 仍靠 heuristics**：`_should_build_metric_set()` 等函数根据 metadata 做推断，无法覆盖所有场景，也难以维护。
4. **前端需要 fallback**：ResearchView/QueryCard 仍然需要推断组件类型，因此很难保证“用户说数字卡片 → 一定得到数字卡片”。

### 13.2 组件契约设计

1. **统一契约描述**：在 `.agentdocs/` 中补充一个 `component_contracts.md`，列出所有支持的组件（ListPanel、StatisticCard、LineChart 等）的必填字段/props、数据格式、典型 pipeline 示例。
2. **契约示例**（简化版）：
   - `StatisticCard`：
     ```jsonc
     {
       "component_id": "StatisticCard",
       "data_contract": {
         "items": [
           {
             "metric_title": "播放量",
             "metric_value": 1234,
             "metric_trend": "up",
             "metric_delta_text": "+12%"
           }
         ]
       },
       "props_contract": {
         "title": "指标标题",
         "value_field": "metric_value"
       }
     }
     ```
   - `ListPanel`、`LineChart` 等同理。

### 13.3 Planner/ResearchAgent 变更

1. **提示词更新**（`research_agent_system.txt`）：
   - TODO 模板包含组件类型：`- [ ] 生成数字卡片（组件: StatisticCard，字段: metric_title/metric_value/...）`
   - 决策 JSON/工具说明增加 `target_component` 字段。
2. **工作记忆**：当 Planner 确定某子任务需要 `StatisticCard`，将契约写入 `working_memory["component_contracts"]`，供 data_operator/schema_coder 读取。
3. **ResearchAgent 输出**：在 `tool_call.description` 或 `args` 中附带 `component_contract_id`，让 data_operator 在 prompt 中引用。

### 13.4 data_operator/schema_coder 变更

1. **Prompt 注入契约**：
   - 在 `_build_schema_context` 时增加 `component_contract`，例如：
     ```jsonc
     {
       "target_component": "StatisticCard",
       "required_fields": ["metric_title", "metric_value", "description"],
       "sample_output": {"items":[{"metric_title":"播放量","metric_value":1234}]}
     }
     ```
   - SchemaCoder 必须按照契约生成 transform 函数；若缺字段，直接返回错误。
2. **输出元数据**：
   - `_normalize_transform_result()` 保留 `metadata["component_id"] = "StatisticCard"` 与 `metadata["contract_version"]`。
   - 如果 transform 返回的结构不符合契约，记录错误并触发 fallback（让 Planner 重新生成）。

### 13.5 panel_spec_builder & 面板渲染

1. **契约优先**：
   - 如果 dataset.metadata 中包含 `component_id`，`_build_display_schema()` 直接根据契约构建 DisplaySchema（例如 `kind="metric_set"`）。
   - `_should_build_metric_set()` 等 heuristics 降级为“无契约时才启用”，并写日志。
2. **panel_bundle**：
   - LangGraph Planner 在 `panel_bundle` 中包含 `component_id` / `props` / `panel_dsl` 基础结构。`emit_panel_preview` 直接返回该结构，允许前端 100% 复刻 Planner 的决策。
3. **渲染器**：PanelRuntime 不需要猜测组件，直接用 `component_id` 从 registry 里构造 ViewModel；任何缺失字段将在构造阶段抛错，ResearchAgent 需要重新生成数据。

### 13.6 前端联动

1. **面板契约显示**：在开发者模式 Inspector 中显示 `panel_spec.view_models[*].component_id` 与绑定的字段，提供调试信息。
2. **历史重放**：QueryCard/ResearchView 已经消费 `panel_spec`，只要 panel_spec 构造时带有正确 `component_id`，前端渲染就无需额外逻辑。

### 13.7 测试策略

1. **后端单测**：
   - `tests/panel/test_panel_spec_builder.py`: 新增“有 component_id=StatisticCard 时构建 metric_set”的测试。
   - `tests/langgraph_agents/tools/test_data_operator.py`: 加入“有契约时生成的 JSON 必须包含 metric_title/metric_value”的用例。
   - `tests/services/test_chat_service.py`: 模拟 Planner 返回 `panel_bundle`，确认 `metadata["panel_spec"].panel_dsl` 中的 `node` 等于契约组件。
2. **前端/手动测试**：请求“B 站热点数量并展示数字卡片”，确认 panel_spec 渲染的是 `StatisticCard`；历史卡片也能显示 mini 数字卡。

### 13.8 实施步骤

1. **阶段 1 - 契约定义 & Prompt 更新**：
   - 新建 `component_contracts.md`，定义每个组件的契约示例。
   - 更新 `research_agent_system.txt`，在 TODO/工作记忆中引入 `target_component`。
2. **阶段 2 - data_operator 契约注入**：
   - 在 `_build_schema_context()` 中读取 Planner 提供的契约，并传给 prompt。
   - `_normalize_transform_result()` 保存 `component_id`。
3. **阶段 3 - panel_spec_builder 契约消费**：
   - 增强 `_build_display_schema`；契约存在时不再执行 heuristics。
   - `PanelRuntime` 直接根据 `component_id` 构造 view model。
4. **阶段 4 - panel_bundle 全链路**：
   - LangGraph Planner 返回 `panel_bundle`，包含 DSL/view models。
   - ChatService/ResearchService 直接透传 `panel_bundle` 并在 metadata 中记录。
5. **阶段 5 - 清理 heuristics**：
   - 移除 `metadata.panel_hint`、`BANNED_PANEL_KEYS` 等补丁式逻辑；
   - 所有组件选择都依赖契约和 Planner 决策。

### 13.9 风险与对策

1. **LLM 不遵守契约**：通过 Prompt 强调“必须返回契约字段”；若失败，ResearchAgent 需要重试或提示用户。
2. **面板数量增加**：Planner 在 TODO 中控制“展示优先级”，防止反复生成相似面板。
3. **兼容旧日志**：在过渡期保留 heuristics 作为 fallback（但会记录 warning）。

### 13.10 预期成果

1. 用户在自然语言中描述任意 UI 需求，Planner 能选中合适组件并让 data_operator 输出匹配的数据；
2. `panel_spec` 中能直接反映 Planner 决策（component_id、props、DSL）；
3. ResearchView/QueryCard 历史面板与实时面板一致，前端无需额外适配；
4. 整个链路可追溯（组件契约 + pipeline 变更 +面板渲染），符合“AI 原生低代码平台”的目标。

---

此方案作为下一阶段（Phase 13）执行的详细设计，后续实际开发时可按“阶段 1~5”依次推进，完成后再更新文档与测试。届时 heuristics 将逐步下线，所有组件选择与数据加工都会由 Planner/data_operator 契约驱动，最终实现真正的 Schema-first/Panel-first 工作流。

## 14. Phase 13 执行蓝图（200+ 行详细方案）

> 目标：补齐“契约先行 → 数据加工 → 结构化渲染”的全链路执行细节，让任何“数字卡片/折线图/多列布局”需求都能从 Planner → data_operator → PanelRuntime → 前端保持严格一致，彻底满足“AI 原生低代码生成”的标准。

### 14.1 执行原则

1. 所有 UI 决策必须由 Planner 输出的 component contract 驱动，不允许在 data_operator、panel_spec_builder 或前端写死组件推断逻辑。
2. Schema、契约、DSL、ViewModel 四层都要记录 `component_id`、字段契约版本以及 source_refs，方便日志复现。
3. data_operator 负责让数据完全匹配契约，PanelRuntime 只负责渲染——不得再让前端去猜测字段含义。
4. 任何回退策略都必须“静默但可追踪”：失败节点降级为 ErrorCard，同时在 panel_spec.degraded_components 与日志中写清原因。
5. 测试与验证贯穿全程：Planner prompt diff、data_operator 校验、PanelRuntime 行为、ChatService/ResearchService 集成、前端回放都必须有自动化覆盖。

### 14.2 代码结构图（抽象层级）

```
LLMAgent (ResearchAgent)
├── PlannerContext
│   ├── TodoQueue
│   ├── ComponentContractsRegistry
│   └── WorkingMemory (component targets / schema plan / transformation hints)
├── ToolInvoker
│   ├── fetch_public_data
│   ├── data_operator (contract-aware)
│   └── emit_panel_preview
└── MemoryLogger

DataOperator Pipeline
├── ContractLoader (from Planner memory)
├── SchemaCoder Prompt Builder
├── SandboxExecutor (python inline / builtin pipeline)
└── ResultNormalizer (enforces contract, strips hints, attaches metadata)

Panel Spec Builder
├── EnvelopeBuilder
├── DisplaySchemaFactory (contract-first)
├── PanelRuntimeAdapter
│   ├── ViewModelAssembler
│   ├── PanelDSLGenerator
│   └── LayoutComposer
└── PanelBundleEmitter

Chat / Research Services
├── ChatService
│   ├── ResearchAgentRunner
│   ├── PanelBundleIntegrator
│   └── MetadataPropagator
├── ResearchService
│   ├── StreamingEmitter
│   └── panel_previews Replayer
└── Frontend Gateways (REST + WebSocket)

Frontend Runtime
├── QueryCard (mini preview from panel_spec)
├── ResearchView (full panel + progress)
└── DynamicBlockRenderer (component contracts manifest)
```

### 14.3 里程碑拆解

1. **Milestone A（基础契约 → Prompt/Memory）**：Planner 输出 component contract，working_memory 注入。
2. **Milestone B（data_operator 契约执行）**：SchemaCoder 与 Sandbox 根据契约生成结构；失败时列出缺失字段。
3. **Milestone C（panel_spec_builder 直接消费契约）**：DisplaySchema/ViewModel 不再猜测。
4. **Milestone D（PanelBundle 全链路）**：ChatService/ResearchService 直接透传 `panel_spec + panel_payload + component_id`，前端 zero-guess。
5. **Milestone E（验证/监控/文档）**：覆盖 200% 行动计划，包含测试、日志、观测、rollback 机制。

### 14.4 关键流程描述

1. Planner 在分析用户意图时，先根据组件 manifest 评估最合适的 component contract（例如 StatisticCard Contract v2）。
2. Planner 将目标 contract 写入 TODO（`component_id`, `data_contract`, `props_requirements`, `layout_hint`）以及 working_memory。
3. 当 Planner 决定调用 data_operator 时，Tool arguments 包含 `target_component_id` 与 `contract_id`；execution_wrapper 会把这些字段注入 prompt。
4. data_operator 运行完成后输出 `metadata.component_id`，并生成 envelope（summary 必为 string）。若 contract 字段缺失，会 raise contract violation。
5. emit_panel_preview / panel_spec_builder 读取 dataset.metadata.component_id，以 contract-first 模式生成 display schema、view model、panel DSL。无需 heuristics。
6. ChatService 将 panel_bundle 直接复制给 Response metadata；前端 QueryCard/ResearchView 只需渲染 `panel_spec.view_models[*].component_id`，不再 fallback 到列表。

### 14.5 阶段任务映射（高层）

| 阶段 | 内容 | 核心产出 |
| --- | --- | --- |
| A | Planner 契约输出 | system prompt 更新、TODO 模板、WorkingMemory schema |
| B | data_operator 契约执行 | prompt builder、contract validator、error taxonomy |
| C | panel_spec_builder 更新 | contract-aware display schema、component-first view model |
| D | PanelBundle 集成 | ChatService/ResearchService 注入 panel_spec/payload |
| E | 前端 + 测试 | QueryCard/ResearchView 读取 panel_spec、pytest 套件、端到端验证 |

### 14.6 详细任务分解（200+ 行核心内容）

#### Planner / ResearchAgent 任务清单

- (PL-01) 更新 `langgraph_agents/prompts/research_agent_system.txt`，在任务描述中明确“先确定组件契约再处理数据”。
- (PL-02) 在 TODO 渲染模板中加入 `组件` 栏位，格式为 `组件: StatisticCard（字段 metric_title/metric_value/metric_description）`。
- (PL-03) 扩展 ResearchAgent working_memory 数据结构，新增 `component_contracts: Dict[str, ComponentContract]`。
- (PL-04) 当 Planner 识别多个面板需求时，将 contract id 写到 TODO 条目的 metadata，供后续步骤引用。
- (PL-05) 在 `planner_context.py` 中提供 helper `remember_contract(contract: ComponentContract)`，用于缓存同一轮中的契约。
- (PL-06) 在 Tool selection 逻辑中增加校验：若 TODO 指定组件，但 data_operator 完成后 metadata 缺少 component_id，Planner 必须重新排程。
- (PL-07) 在研究模式日志中记录“组件契约决策”段落，包含组件、props、字段、候选理由。
- (PL-08) 在 Planner 输出 JSON schema 中新增 `target_component_id: Literal["StatisticCard","ListPanel",...]` 字段。
- (PL-09) 扩展 `planner_decision.py` 的 Pydantic 模型，确保 component id 被验证并转存至 LangGraph state。
- (PL-10) 针对“数字卡片”“图表”“表格”“图集”四类典型任务，在 prompt 中加入契约示例 JSON。
- (PL-11) 添加 heuristics 防护：提示词中强调“不得在后台添加规则引擎，必须依赖 manifest 中的契约”。
- (PL-12) 记录 Planner 失败重试原因：若 data_operator 返回 contract violation，Planner 需写入 working_memory `remediation` 字段。
- (PL-13) 研究模式 FINISH 消息中附带 `applied_component_contracts` 数组，便于后端/前端展示。
- (PL-14) 在 ResearchAgent 分析步骤写明“当前使用的 contract 版本”，以确保 prompt 可追踪。
- (PL-15) 将 component manifest 摘要通过 RAG 注入 Planner prompt，避免放入完整 manifest 而超过上下文。
- (PL-16) 为 Planner 添加“组件冲突检测”提示：当同一个数据集被要求同时输出 ListPanel 和 StatisticCard 时，需要拆分数据或复制 envelope。
- (PL-17) 更新测试 `tests/langgraph_agents/agents/test_research_agent_planner.py`，断言 Planner 输出 TODO 包含 component id。
- (PL-18) 添加 instrumentation，将 component contract 决策写入 telemetry（例如 `planner.contract.selected` 指标）。
- (PL-19) 建立 `ComponentContract` Pydantic 模型（id、version、required_fields、props_requirements、view_model_template）。
- (PL-20) 在 Planner 内部缓存 manifest 摘要的散列值，避免重复加载；出现变更时重建记忆。

#### data_operator / SchemaCoder 任务清单

- (DO-01) 在 `langgraph_agents/tools/data_operator.py` 中的 `_build_schema_context()` 注入 Planner 传入的 component contract。
- (DO-02) SchemaCoder prompt 中加入“输出字段必须覆盖 contract.required_fields”的声明。
- (DO-03) 若 contract 包含 props 需求（如 `value_field`），data_operator 需在 metadata 中回写 props 候选值，供 PanelRuntime 直接使用。
- (DO-04) 在 `_normalize_transform_result()` 里保留 `metadata.component_id` 与 `metadata.contract_version`。
- (DO-05) 若 transform 输出缺失字段，抛出 `ComponentContractViolation`，详细列出缺少字段、类型不匹配、值为空的原因。
- (DO-06) 扩展 `BANNED_PANEL_KEYS`，确认 metadata 不包含任何 `panel_hint`、`component_guess` 等。
- (DO-07) 在 transformation pipeline 中新增 `enforce_numeric_field` builtin，确保 contract 要求的 value 字段为 number。
- (DO-08) 在内置算子 `aggregate_numeric` 的返回结构中增加 `contract_field_map`，指示 sum/avg 对应 props 值。
- (DO-09) 若用户指令明确要求“仅统计数量”，SchemaCoder 需构建“count only”的输出结构，禁止悄悄附加列表。
- (DO-10) 在 `tests/langgraph_agents/tools/test_data_operator.py` 增加契约失败用例，断言工具会抛错且错误信息包含缺失字段。
- (DO-11) 在执行日志中输出 `component_contract_id`，方便排查 coder 行为。
- (DO-12) 新增 `contract_examples.json`，由 data_operator 在 prompt 中引用 sample output。
- (DO-13) 当 contract 要求 `items[0].value` 是整数时，内置 `coerce_number` 自动截断/四舍五入，并在 metadata 中注明转换策略。
- (DO-14) 对 pipeline transformation 增加 `validate_contract` 末尾步骤，统一校验 schema 与 data types。
- (DO-15) 加入统计指标 `contract_conformance_rate`，用于监控 coder 输出质量。
- (DO-16) 对 `inline_python` 增加安全提示：若 contract 指定 `numeric_only=true`，则 sandbox 拒绝返回非数值字段。
- (DO-17) SchemaCoder prompt 需描述“contract 字段命名必须与 manifest 一致，禁止自创 key”。
- (DO-18) 允许 contract 声明 `optional_fields`，data_operator 需在 metadata 中标注哪些 optional 字段已返回。
- (DO-19) 若 contract 要求 `items` 数量 <= 4，data_operator 在 pipeline 中必须执行 `head(4)` 并记录 `items_truncated=true`。
- (DO-20) 在 `langgraph_agents/tools/data_operator.py` 中注入新的 telemetry，记录每次 contract violate 的字段列表。

#### panel_spec_builder / PanelRuntime 任务清单

- (PB-01) 在 `_build_envelope()` 中将 `metadata.component_id` 透传到 `StructuredDataEnvelope.metadata`.
- (PB-02) `DisplaySchema` 构建流程改为：若 dataset.metadata.component_id 存在，则查找 `component_contracts` map 直接构建字段。
- (PB-03) `_should_build_metric_set()`、`_should_build_list_panel()` 仅在缺少 contract 时才执行，并记录 WARN。
- (PB-04) ViewModelAssembler 接收 contract，直接将数据映射到组件 props（例如 `value_field="metric_value"`）。
- (PB-05) PanelRuntime 渲染失败时，错误信息需要带上 `component_id`，方便定位 contract。
- (PB-06) PanelDSL generator 生成节点时强制 `node == component_id`，禁止 fallback 到 ListPanel。
- (PB-07) LayoutComposer 根据 contract.layout_hint（span/size）来布置 row/col。
- (PB-08) PanelBundle 中 `panel_payload.blocks[*].component` 直接使用 contract 组件 ID。
- (PB-09) `panel_spec.degraded_components` 需要包含 contract_id、component_id、failed_fields。
- (PB-10) 若 contract 声明 `requires_children=false`，Runtime 遇到 children 时直接 reject，避免 Planner 误拼嵌套。
- (PB-11) 在 `tests/panel/test_panel_spec_builder.py` 增加 contract-first 测试：StatisticCard contract 一定渲染出 `component="StatisticCard"`.
- (PB-12) PanelRuntime 对 `view_models` 的校验要确认 `component_id` 一致。
- (PB-13) Envelope summary 默认 `json.dumps` dictionary，禁止 dict 直接塞 summary。
- (PB-14) PanelRuntime 在 metadata 中记录 `contract_version`，便于前端显示。
- (PB-15) PanelBundle emitter 需要支持 `mode="replace"`/`"append"` 由 contract 提示 `layout_mode`。
- (PB-16) `panel_spec_builder` 添加 `ContractRegistry` 依赖，以便加载 `.agentdocs/component_contracts.md` 中的定义。
- (PB-17) 研究模式/普通模式共享 PanelRuntime 入口，完全复用 contract-first 逻辑。
- (PB-18) PanelRuntime 允许 contract 指定 `props_defaults`（如 `show_description=false`），渲染器自动注入。
- (PB-19) `panel_spec_builder` 记录 `panel_spec.metadata.contracts_applied` 数组，包含 data_id 与 contract。
- (PB-20) PanelPayload 产生 mini preview 时，也要把 contract 信息带到 `options.contract_label`，供开发者调试。

#### LangGraph / Runtime 集成任务

- (LG-01) LangGraph state 中新增 `component_contracts` 字段，存储 Planner 记忆。
- (LG-02) execution_wrapper 统一注入 `target_component_id` 到工具参数。
- (LG-03) 在 `emit_panel_preview` 调用链中校验 dataset.metadata 是否含契约，缺失则 warning。
- (LG-04) DataStasher 保存 panel_bundle 时将 contract 信息写入 `DataBlock.contract_id`。
- (LG-05) `services/chat_service.py` 在 `_handle_data_query` 中如果收到 panel_bundle，直接 bypass adapter。
- (LG-06) `services/chat/research_streaming.py` 推送消息时将 contract 信息放入 `panel_spec_metadata`.
- (LG-07) ResearchAgent 在 finish 阶段 summarizing steps 时引用 contract 名称，帮助用户理解 UI 决策。
- (LG-08) ChatService metadata 中新增 `component_contracts_summary`，列出所有 contract 及状态（success/fallback）。
- (LG-09) WebSocket 流消息 `panel_data_blocks` 中附带 contract id，前端 store 据此决定 component。
- (LG-10) LangGraph telemetry 上报 `panel.contract.success`, `panel.contract.violation`.
- (LG-11) 在 datastore 存储 envelope 时，以 contract id 为分区键的一部分，便于调试。
- (LG-12) 研究模式回放 logic 读取 metadata 中的 contract，展示“该面板由 StatisticCard Contract v2 生成”。
- (LG-13) 运行模式 CLI（如 send_test.py）更新示例 payload，展示 contract-first 输出。
- (LG-14) `langgraph_agents/sync_executor.py` 需要在同步执行模式下同样注入 contract。
- (LG-15) 当 Planner 取消某契约任务时，要清除 working_memory 中的 contract entry，避免污染下一步。

#### 前端联动任务

- (FE-01) `frontend/src/shared/types/panel.ts` 补充 `contract_id`、`component_id` 字段。
- (FE-02) `DynamicBlockRenderer` 渲染函数直接根据 `block.component` 渲染目标组件，不再 fallback。
- (FE-03) `QueryCard.vue` mini preview 使用 `panel_spec.view_models` 中的 `component_id` 和 props 渲染真实组件。
- (FE-04) `ResearchViewStore` 保存 `contract_id`，方便开发者模式展示。
- (FE-05) 新增“组件契约标签”UI（可选），在面板右上角显示 `StatisticCard v2`，帮助验证链路。
- (FE-06) 修改 `PanelBoard` 追加逻辑，确保 append/replace 时按 contract 提供的 layout_span 渲染。
- (FE-07) `ComponentManifest` 中每个组件新增 `contract_id` / `contract_version` 字段，与后端保持一致。
- (FE-08) `useResearchWebSocket` 解析消息时将 `panel_spec.degraded_components` 显示在 UI 中。
- (FE-09) `frontend/tests`（若有）补充 e2e：请求“B站热点数量”→渲染 StatisticCard。
- (FE-10) Query 输入 Form 中提供“渲染方式”QA 提示文案，引导用户描述 UI。
- (FE-11) `ResearchDataPanel` 允许用户点击“查看契约”，弹出 JSON 详情（component id、props、字段）。
- (FE-12) `devModeStore` Inspector 显示 `contract_id`/`component_id`/`view_model_schema`。
- (FE-13) `PanelLayoutEngine` 读取 `layout_size` contract hint，控制 `span` / `min_height`。
- (FE-14) 研究历史列表 `panel_previews` 解析 `component_id`，以卡片缩略形式展示。
- (FE-15) 增加前端 telemetry，记录 `panel_contract_render_success`。

#### 测试与验证任务

- (TS-01) `tests/langgraph_agents/tools/test_data_operator.py`：新增“契约满足”与“契约缺失”用例。
- (TS-02) `tests/panel/test_panel_spec_builder.py`：新增 contract-first StatisticCard/LineChart 测试。
- (TS-03) `tests/services/test_chat_service.py`：模拟 panel_bundle 返回 StatisticCard，断言 ChatService 不再退化。
- (TS-04) `tests/services/test_research_service.py`：验证 panel_previews 附带 contract 信息。
- (TS-05) `tests/frontend`（若存在）：snapshot 检查 QueryCard mini panel 渲染 StatisticCard。
- (TS-06) `tests/langgraph_agents/agents/test_research_agent_planner.py`：确保 TODO 包含 component id。
- (TS-07) `tests/langgraph_agents/tools/test_emit_panel_preview.py`：断言 summary 转 string，contract 透传。
- (TS-08) 集成测试 `test_research_flow.py`：新增 scenario “B站热点数量 → StatisticCard”。
- (TS-09) 新建 contract 验证脚本 `scripts/contract_validator.py`，跑通 manifest vs backend schema 一致性。
- (TS-10) 转测 Checklist：Planner prompt diff → data_operator contract log → panel_spec view models → 前端 snapshot。
- (TS-11) 性能测试：确保契约校验不会显著增加 ResearchAgent 延迟（目标 < +100ms）。
- (TS-12) 沙箱测试：验证 pipeline builtin 在 contract 下的数值精度。
- (TS-13) 失败回归：构造 invalid contract input，确认系统降级且日志清晰。
- (TS-14) 端到端 CLI 脚本 `python run_server.py --scenario contract_stat_card` 检查 outputs。
- (TS-15) 记录 `pytest -k contract` 执行指南，并指出需使用 `D:\\Anaconda\\envs\\torch-cuda\\python.exe`。
- (TS-16) 建立 nightly pipeline：自动跑契约相关的 30+ 测试，确保运维稳定。
- (TS-17) 研究模式 WebSocket 集成测试：mock contract panel 消息 → 前端 store 正确更新。
- (TS-18) 兼容性测试：旧日志（无 contract）仍可 fallback 渲染 ListPanel（记录 warning）。
- (TS-19) Telemetry 校验：contract success rate >= 95%。
- (TS-20) 文档验证：lint `.agentdocs/component_contracts.md` 结构正确。

#### 可观测性 / 运行监控任务

- (OB-01) 新增日志 `panel_contract.success/violation`，携带 contract id、component id、data_id。
- (OB-02) 把 contract 事件写入 OpenTelemetry span，方便链路追踪。
- (OB-03) 在监控面板上新增“契约成功率”“降级次数”“平均渲染时间”图表。
- (OB-04) 研究模式前端 console 在 dev 模式输出 contract 信息。
- (OB-05) 引入报警：contract violation 连续 5 次触发 Slack/Feishu 提醒。
- (OB-06) DataStasher 记录每个 data_id 的 contract history，允许追踪版本迁移。
- (OB-07) PanelRuntime 抛错时写入 `panel_runtime.log`，包含 DSL snippet、contract id、异常消息。
- (OB-08) ChatService metadata 加入 `panel_contract_status`，前端 UI 可用来提示“指标卡自动降级为列表”。
- (OB-09) 添加 `scripts/analyze_contract_failures.py`，按字段统计 violation。
- (OB-10) 监控 pipeline CPU/时间耗时，确保 contract 校验不会导致超时。

#### 文档 / 回放 / 培训任务

- (DC-01) 在 `.agentdocs/component_contracts.md` 中列出所有组件契约、字段说明、示例 JSON。
- (DC-02) 更新本方案文档（本文件）Phase 14 部分的 TODO 状态记录。
- (DC-03) 在 `.agentdocs/frontend/frontend-panel-components.md` 补充“contract-first 渲染流程”章节。
- (DC-04) 录制回放脚本：`B站热点数量 → StatisticCard` 全链路日志。
- (DC-05) 整理 FAQ：如果 Planner 没有选择组件怎么办？如何 debug contract violation？
- (DC-06) 准备训练数据：把成功的 contract 输出样本喂给 LLM（通过 few-shot JSON）。
- (DC-07) 更新团队 Onboarding 文档，强调“禁止规则引擎，必须契约驱动”。
- (DC-08) 在 `.agentdocs/index.md` 中加入本任务文档的最新状态与关键结论。
- (DC-09) 研究流 UI 中提供“查看契约文档”链接，跳转至 `.agentdocs` 说明。
- (DC-10) 按阶段记录完成度，确保 Phase 13 的每个子阶段都有文字描述。

### 14.7 交付节奏（时间线示例）

1. **Day 1**：完成 Planner prompt diff、working_memory schema、contract registry 数据结构。
2. **Day 2**：data_operator prompt 注入 + contract validator + pipeline builtin 对齐。
3. **Day 3**：panel_spec_builder/PanelRuntime contract-first 改造，emit_panel_preview 接入。
4. **Day 4**：ChatService/ResearchService/ResearchStore/QueryCard/ResearchView 全链路接入。
5. **Day 5**：测试完善（pytest + WebSocket + CLI），可观测性 + 文档更新。
6. **Day 6**：灰度验证 + 性能监控 + 回放案例整理。

### 14.8 主要风险与缓解策略

1. **LLM 仍输出错误结构**：通过契约验证 + 自动重试 + 少量可控示例（而非 heuristics）来提升稳定性。
2. **contract manifest/后端 schema 不一致**：引入 `contract_validator.py` 对比 TypeScript + Pydantic。
3. **前端渲染失败**：降级 UI + 明确告警 + Inspector 显示 contract id，辅助定位。
4. **性能影响**：监控 data_operator/PanelRuntime 延迟，必要时缓存 contract 描述或引入轻量 manifest。
5. **用户自定义需求过多**：Planner prompt 指导“任务拆分 + prioritization”，避免一次性生成 5 张大面板。
6. **旧面板兼容性**：保留 heuristics fallback，但 log warning，逐步淘汰。

### 14.9 完成标准

1. 任意“数字卡片”请求在后端/前端都渲染 `StatisticCard`，数据字段与 props 100% 契约一致。
2. Planner/TODO/working_memory/metadata 全部携带 component_id+contract_version。
3. data_operator 若无法满足契约会抛出明确错误，ResearchAgent 能读取并整改。
4. panel_spec / panel_payload / view_models / rendered_preview 的组件完全一致。
5. 前端 QueryCard/ResearchView 历史/实时面板展示效果一致，无列表 fallback。
6. 测试覆盖 Planner/data_operator/panel_spec_builder/ChatService/ResearchService/前端 store/渲染链路。
7. 日志、指标、文档、回放齐备，可支撑后续扩展至更多组件（LineChart/BarChart/TabGroup 等）。

---

> 此 14.x 章节作为 Phase 13 契约驱动实施的详细执行蓝图，合计超过 200 行内容，涵盖架构目标、代码结构、任务矩阵、风险缓解与完成标准。实施过程中需根据上述任务清单逐项打勾，并在本文档内持续更新进度。

## 15. data_operator 契约执行落地细化（Phase 13 · B 阶段）

> 针对前一阶段完成的 Planner 契约输出 + 工具透传基础，本节细化 data_operator/schema_coder 在契约驱动下的实现思路与验证方案，确保“组件契约 → 数据加工 → panel_spec”链路闭环。

### 15.1 目标与范围
- ✅（2025-11-30 实施）在 data_operator 调用时自动注入契约定义（component_contracts_for_call），LLM prompt 明确字段/类型/数量约束。
- ✅ transform 输出由统一契约校验器验证（缺字段/多字段直接抛出 `ComponentContractViolation`），Planner 根据错误重试或更换契约。
- ✅ metadata 写回 `component_id/contract_id/contract_version/component_props/layout_hint`，panel_spec_builder 直接消费。

### 15.2 架构调整
1. **ToolExecutor → data_operator**：已将契约经过 working_memory 透传，本节要求 data_operator 读取 `context.extras["component_contracts_for_call"]`，若存在多条契约：
   - 优先匹配 `status in {"planned","in_progress"}` 的项；
   - 若传入多个组件需求（多 TODO 并行），需在 prompt 中列出全部契约，指示 coder 逐一输出或拆分多次调用。
2. **SchemaCoder Prompt 更新**：
   - 在 `_build_prompt()` 追加 `## 组件契约` 区域，列出 `required_fields/optional_fields/props_mapping`；
   - 说明“禁止添加契约指定之外的字段；如需额外字段，必须更新契约定义再执行”。
3. **执行管线**：
   - transform 执行完成后，`_normalize_transform_result()` 新增 `_enforce_contract()` 步骤：
     ```python
     contract = active_contracts[0]
     enforce_items_schema(items, contract.required_fields, contract.optional_fields)
     ensure_max_items(items, contract.max_items or component_defaults)
     attach_metadata(metadata, component_id=contract.component_id, contract_id=contract.contract_id)
     ```
   - 若违反字段或类型，抛出 `ComponentContractViolation(details=...)`，ToolExecutionPayload.status = "error"，并记录在 raw_output 中；ResearchAgent 将根据错误重试或更换契约。

### 15.3 契约验证逻辑（伪代码）
```python
def enforce_items_schema(items, contract):
    for idx, item in enumerate(items):
        missing = [f for f in contract.required_fields if f not in item]
        if missing:
            raise ComponentContractViolation(f"record #{idx} missing {missing}")
        for key, value in item.items():
            if key not in contract.required_fields + contract.optional_fields:
                raise ComponentContractViolation(f"field {key} not allowed by {contract.contract_id}")
```
- `props_mapping` 也需验证：例如 `title_field` 指向的字段必须存在，且类型符合组件约定（string/number）。若 Planner 提供了 `value_field` 等 override，需要在 metadata 中记录并传递给 panel_spec_builder。

### 15.4 PanelSpec 适配预案（与 C 阶段联动）
- data_operator metadata → `metadata["component_id"]="StatisticCard"`。
- `panel_spec_builder._build_display_schema()` 先查 `metadata.component_id`，存在则直接加载契约 definition 构建 view_model，不再调用 `_should_build_metric_set()`.
- 兼容旧数据：当 metadata 未含契约时，保留 heuristics 但 emit warning（方便日志统计）。

### 15.5 可观测性
- `tool_executor` 日志已记录契约透传，本节新增：
  - data_operator 在处理契约时 log: `logger.info("data_operator.contract", extra={"contract_id": ..., "status": ...})`;
  - PanelRuntime 在渲染时记录 `panel_runtime.contract_applied=contract_id`，便于前端分析“成功率/降级率”。
- Telemetry 指标：
  - `contract_violation.count{component_id}`；
  - `contract_success.count{component_id}`；
  - `contract_latency_ms{component_id}`（观察引入契约后 LLm/执行耗时变化）。

### 15.6 测试计划补充
- **单测**：
  - `tests/langgraph_agents/tools/test_data_operator.py::test_contract_enforced`：mock 契约 + 生成输出，确保缺字段时报错。
  - `tests/langgraph_agents/tools/test_data_operator.py::test_contract_attaches_metadata`：验证 metadata 写入 component/contract。
- **集成**：
  - 扩展 `tests/langgraph_agents/test_research_agent.py` 场景：Planner 输出契约 → data_operator 成功 → panel_spec_builder 读取 metadata → 渲染 `StatisticCard`。
  - 添加 `tests/services/test_panel_spec_builder.py::test_component_contract_short_circuit`：有契约时不触发 heuristics。

### 15.7 风险与对策
- **LLM 忽略契约指令**：通过 `ComponentContractViolation` + 重试策略保证最终输出符合结构；必要时在 prompt 中加入 strong negative examples。
- **多契约并发**：如果 TODO 中出现多个组件绑定同一数据源，优先拆分 data_operator 调用；若必须一次完成，需在 prompt 中告知 coder 返回 `items_map` 或多数据块，并在 panel_spec 层拆分。
- **性能影响**：契约校验仅针对 preview items（默认 <=200），可接受；如需在大批量数据中执行，可将校验与采样结合，仅对 sample 校验。

---

> 下一阶段（Phase 13 · C）将围绕 panel_spec_builder/PanelRuntime 的契约消费与 `StatisticCard` 等组件的渲染路径展开，届时 `PanelBundle` 将携带完整 `component_contract` 元数据，确保前端无需猜测组件类型。

## 16. panel_spec_builder / PanelRuntime 契约消费（Phase 13 · C 阶段）

1. **DisplaySchema 扩展**：新增 `component_id` / `contract_id` / `contract_metadata` 字段；panel_spec_builder 在检测到 metadata 中的契约信息后，直接构建“合同版 schema”并跳过 `_should_build_metric_set()` 的 heuristics。`kind` 通过 `_infer_display_kind_for_contract()` 对齐已有枚举（StatisticCard → metric_set，ListPanel → record_set，其余默认 custom）。
2. **ViewModelBuilder 调整**：`GeneratedViewModel` 携带 `contract_id`；`build()` 在 `schema.component_id` 存在时调用 `validate_records()` 来执行组件契约校验，并按组件类型生成数据/props（Table 走 columns/rows，Chart 系列 + Media/List 统一输出 `{"items": ...}`）。
3. **Panel Spec 输出**：`panel_spec.view_models` 与 `panel_payload.blocks` 均包含 `contract_id`，并新增 `contracts_applied` 顶层列表（component_id/contract_id/view_model_id/title），便于 API/前端/日志直接追踪命中的契约。
4. **测试覆盖**：`tests/panel/test_panel_spec_builder.py` 新增契约用例，确保 `schema.component_id` 与 view_model component 精确对应；LangGraph 集成测试验证 ToolExecutor extras 中的契约信息贯穿至 panel spec，整体测试矩阵 now 包括 ResearchAgent（Planner/working_memory）、ToolExecutor（透传）、PanelSpecBuilder（契约消费）以及 component_contracts 解析。
5. **前端可视化**：DynamicBlockRenderer 在 header 部分渲染 `block.contract_id` 徽章，开发者模式无需查看 raw JSON 即能知道组件契约；后续可进一步扩展 QueryCard/ResearchView 的“面板列表”与“降级提示”以引用 `contracts_applied`。
