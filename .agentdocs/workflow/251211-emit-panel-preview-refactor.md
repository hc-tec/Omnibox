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
- ✅ data_operator：所有失败态返回标准 `error_code`；"多余字段"契约违规不再报错，改为裁剪并写入 `metadata.trimmed_fields`。
- ✅ ResearchAgent：统一提取错误码计数，同工具同错误 ≥3 次直接 FINISH；同一工具连续成功 ≥3 次也终止以防无进展循环。
- ✅ 单测：`test_data_operator.py`、`test_panel_stream_tool.py` 全部通过。
- ✅ **根本原因诊断（2025-12-11 晚）**：通过端到端代码分析+Playwright实测发现了**两个关键 bug**

  **Bug 1: Summary 质量不足** (`data_stasher.py`)
  - **问题根源**: `_smart_default_summary` 函数缺少对 `panel_preview` 类型的处理
  - **导致现象**: Summary 是截断的 JSON 字符串，LLM 无法理解"面板已推送"的语义
  - **修复方案**: 在 `_smart_default_summary` 中添加专门处理，生成人类可读的摘要：
    ```python
    if data_type == "panel_preview":
        component_id = payload.get("component_id") or "未知组件"
        contract_id = payload.get("contract_id") or ""
        count = payload.get("count", 0)
        return f"已生成并推送 {component_id} 面板（{contract_id}），展示 {count} 条数据"
    ```
  - **实施位置**: `langgraph_agents/agents/data_stasher.py:82-89`
  - **验证**: ✅ 端到端测试通过，summary 清晰可读

  **Bug 2: Count 计算错误** (`panel_stream.py`)
  - **问题根源**: `count = len(preview_payload.get("previews", []))` 计算的是 previews 数组长度（固定为1），而非实际数据条数
  - **数据结构**:
    ```python
    preview_payload = {
        "previews": [  # 固定只有 1 个元素
            {
                "items": [...]  # 这里才是实际的 3 条数据
            }
        ]
    }
    ```
  - **导致现象**: Summary 显示"展示 1 条数据"，Agent 误以为数据不完整，重复推送
  - **修复方案**: 从 `previews[0].items` 计算实际数据条数
    ```python
    actual_count = 0
    previews = preview_payload.get("previews", [])
    if previews and isinstance(previews[0], dict):
        items = previews[0].get("items", [])
        actual_count = len(items) if isinstance(items, list) else 0
    ```
  - **实施位置**: `langgraph_agents/tools/panel_stream.py:125-143`
  - **ListPanel 验证**: ✅ 正确显示"展示 3 条数据"
  - **Table 组件验证**: ⚠️ **仍显示 1 条数据**（数据结构不同）

- ⚠️ **剩余问题（Table 组件的 count 计算）**：
  - **现象**: Table 组件生成时 `count calculation: previews=1, actual_count=1`（应该是 3）
  - **原因**: Table 组件的 `preview_payload` 结构可能不同，`previews[0].items` 可能不包含所有行数据
  - **影响**: 第二轮"用表格呈现"查询时，Agent 看到"展示 1 条数据"，重复调用 3 次后触发保护机制
  - **解决方向**:
    1. 检查 Table 组件的 `preview_payload` 实际结构
    2. 从 `panel_spec` 或 `panel_payload` 中提取正确的行数
    3. 优化 count 计算逻辑，支持不同组件类型

- 🔜 **下一步行动**：
  1. 深入分析 Table 组件的数据结构，找到正确的行数来源
  2. 优化 `panel_stream.py` 中的 count 计算，支持 Table/ListPanel/MediaCard 等不同组件
  3. 重新测试"表格呈现"场景，验证不再重复调用

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
