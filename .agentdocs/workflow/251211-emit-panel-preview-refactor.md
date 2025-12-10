## 任务：emit_panel_preview 契约化改造（视图适配 + 推送一体化）

### 背景 / 痛点
- 现状：emit_panel_preview 被理解为“纯展示”，Planner 认为需要先用 data_operator 把数据加工成表格再推送。实际实现中隐含了适配能力，但契约未说明，导致误导。
- 结果：二次请求“用表格展示数据”时，Agent反复调用 data_operator，出现 `records_not_available` 仍继续重试，无法产出表格面板。
- 问题点：
  - 工具职责不清：展示适配能力被埋在工具内部/提示词，元数据未暴露。
  - 错误状态不可见：data_operator 失败未写入 data_stash/working_memory，Agent决策看不到“失败态”，陷入循环。
  - 渲染链路不确定：缺少“直接用现有 data_id 生成视图”的标准路径，Planner默认再加工。

### 目标
1. 将 emit_panel_preview 明确为“契约化视图适配 + 推送”单一工具（无 LLM 推理），输入 data_id + contract + 可选字段映射，输出 panel_spec 并推送。
2. data_operator 仅负责数据处理/变换；展示适配走 emit_panel_preview，除非确实缺字段时再调用 data_operator。
3. 统一错误回传：所有工具失败态写入 data_stash/working_memory，Agent/Planner 可见并停止重复调用。
4. 保证泛化：同一机制适用于表格/列表/图表等组件契约，不引入特例/规则引擎。

### 最新问题 & 对策（2025-12-11）
- 现象：Playwright `/workspace` 双轮查询仍触发递归深度超限。第一轮 data_operator 因契约校验出现 `contract_violation`（多余字段 url/content_html），但 raw_output 没有标准 `error_code`，ResearchAgent 无法累计错误计数，继续重复调用。
- 现象：emit_panel_preview 已契约化，但 Planner/Agent 仍可能在展示场景先调 data_operator，再触发同样的错误循环。
- 对策：
  - data_operator 标准化错误码：所有错误态填充 `error_code`（如 `contract_violation`/`missing_fields`/`execution_failed` 等），并在 raw_output 中显式携带，供 error_counter 使用。
  - 契约容错：对“多余字段”类违规（disallowed fields）改为裁剪+记录 metadata，而非直接抛错；仍对缺失必填字段保持严格报错。
- Agent 侧错误感知：ResearchAgent 读取 `error_code` 或 `error` 字段统一计数，连续同工具同错误 ≥3 次即停止；prompt 依赖 data_stash 的摘要看到错误态，避免盲重试。
- 展示契约兜底：展示需求仍默认 `emit_panel_preview(contract_id=? , source_ref=recent success)`，只有缺字段时再单次调用 data_operator 做补齐。

### 进展与下一步（2025-12-11）
- ✅ data_operator：所有失败态返回标准 `error_code`；“多余字段”契约违规不再报错，改为裁剪并写入 `metadata.trimmed_fields`。
- ✅ ResearchAgent：统一提取错误码计数，同工具同错误 ≥3 次直接 FINISH；同一工具连续成功 ≥3 次也终止以防无进展循环。
- ✅ 单测：`test_data_operator.py`、`test_panel_stream_tool.py` 全部通过。
- 🔜 待做：重跑 /workspace Playwright 双轮查询（查看热搜→表格展示），确认不再触发 recursion limit；如仍循环，需要检查决策 JSON 是否携带 contract_id/source_ref 并是否触发 stop 逻辑。

### 方案概述
- emit_panel_preview 强化为“视图适配器 + 推送器”：
  - 输入：`data_id`（或 `$step.N`）、`contract_id`（如 Table-contract-v1）、可选 `field_mapping`/`options`。
  - 阶段 A（适配）：基于组件契约 + schema_registry + 数据示例，生成 panel_spec 或 table-ready dataset（headers/rows），自动做必要的采样/截断。
  - 阶段 B（推送）：将生成的 panel_spec 通过 WS 推送前端。
  - 输出：写入 data_stash 的 DataReference，`status`=success/error，携带 `panel_spec` 摘要/错误码。
- data_operator 保持纯数据加工角色，不负责视图适配。
- 决策策略（通用）：当需求是“展示/改呈现”，优先尝试 emit_panel_preview 直接适配已有成功数据；若缺字段/格式再调用 data_operator 做补齐，然后再次 emit_panel_preview。

### 工具契约调整（emit_panel_preview）
- Schema（示意）：
  - `data_ref`: string（data_id 或 `$step.N`），required
  - `contract_id`: string（组件契约 ID），required
  - `field_mapping`: object（可选，列名/字段映射）
  - `options`: object（可选，max_items、layout_size、sorting 等）
- 行为：
  1. 解析 data_ref → 加载数据/metadata/schema；空/不可用→ error_code=`data_load_failed`。
  2. 校验契约所需字段/shape；缺失→ error_code=`missing_fields`，列出缺失列表。
  3. 执行契约驱动的适配：生成 headers/rows 或 panel_spec（纯程序化，无 LLM）。
  4. 采样/截断保护：超长数据自动限额，标记 metadata。
  5. 推送 panel_spec；写入 data_stash：status、summary、panel_meta（component_id、record_count）、error_code/message。
- 错误范式：
  - `data_load_failed`（data_id 不存在/加载失败）
  - `missing_fields`（列出缺字段）
  - `records_not_available`（空数据）
  - `invalid_contract`（未知契约/不支持的 shape）

### Agent/Planner 协作策略（契约化，而非规则化）
- 读取 data_stash/working_memory 中的 error/success，避免重复调用同一失败工具。
- 渲染需求路径：`emit_panel_preview(contract=目标组件, data_ref=最新成功 data_id)` → 若返回 missing_fields/records_not_available，再选择 data_operator 补齐 → 再次 emit_panel_preview。
- 对话改呈现（如“用表格展示”）默认复用已有分析 data_id，不重复 fetch/analysis。

### 任务拆解 / TODO
- [x] 设计 & 更新 emit_panel_preview 工具 schema 与契约描述（暴露适配能力与错误码）。
- [x] 改造 emit_panel_preview 实现：契约驱动适配 + 推送，写入 data_stash（含错误态）。
- [x] data_operator 输出补全：统一 status/error_code/error_message，写入 data_stash；“多余字段”容错。
- [x] ResearchAgent 决策调整：读取 last_tool_result/error，避免无限重试；展示需求优先 emit_panel_preview，缺字段时再 data_operator；同一工具连续成功/失败达阈值时终止。
- [ ] 测试：
  - [x] 单元：emit_panel_preview 契约校验/缺字段/空数据/error_code 断言。
  - [ ] 集成：fetch → analyze_content → emit_panel_preview(Table) 成功；data_operator 失败后不循环。
  - [ ] Playwright：同 Session 下“查看B站热搜并分析前三条”后再“用表格展示数据”，一次生成表格面板，无重复 data_operator。

### 风险与对策
- 风险：契约/字段推断不足导致适配失败 → 对策：明确缺失字段清单 + error_code 反馈，Agent 可澄清或调用 data_operator。
- 风险：数据量大导致面板 payload 过大 → 对策：适配阶段强制采样/截断 + metadata 标记。
- 风险：现有前端消费 panel_spec 变更 → 对策：保持输出结构兼容（仅增强 error/status/metadata），先跑回归。
