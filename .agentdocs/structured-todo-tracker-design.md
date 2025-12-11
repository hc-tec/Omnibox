# 任务状态追踪优化方案 - 架构设计 v2.0

## 文档版本
- **版本**：v2.0（重新设计）
- **日期**：2025-12-11
- **状态**：✅ 已完成（所有阶段验证通过）

---

## 1. 原方案问题分析

### 1.1 原方案回顾

原方案（v1.0）提出新增 `TODOTracker` 数据结构：
- 在 `working_memory` 中新增 `todo_tracker` 字段
- 每个 `component_contract` 登记时同步创建结构化 TODO
- `DataStasher` 监听工具结果并自动标记 TODO 完成

### 1.2 原方案的根本问题

**问题 1：造成三套并行状态追踪系统**

```
┌─────────────────────────────────────────────────────────────────┐
│                   当前架构（已有两套）                            │
├──────────────────────────┬──────────────────────────────────────┤
│  data_stash              │  working_memory.component_contracts   │
│  ├─ step_id              │  ├─ contracts[contract_id]           │
│  ├─ tool_name            │  │   ├─ component_id                 │
│  ├─ status               │  │   ├─ status (planned/applied)     │
│  ├─ summary              │  │   ├─ targets                      │
│  └─ data_id              │  │   └─ last_updated_step            │
├──────────────────────────┴──────────────────────────────────────┤
│                   原方案（新增第三套）                           │
│  working_memory.todo_tracker                                    │
│  ├─ todos[todo_id]                                              │
│  │   ├─ status (pending/in_progress/completed)                  │
│  │   ├─ contract_id                                             │
│  │   ├─ completed_at_step                                       │
│  │   └─ ...                                                     │
└─────────────────────────────────────────────────────────────────┘
```

**这违反了 CLAUDE.md 的铁律**：
> "基于现有项目进行改进，绝对禁止另起炉灶重新实现已有功能"

**问题 2：错误诊断了问题根源**

原方案认为：
> "TODO 只存在于文本中，无法编程查询"

但实际情况是：
- `component_contracts` **已经是结构化的**（`status: "applied"` 表示完成）
- `data_stash` **已经记录了完整的执行历史**
- `DataStasher` **已经在自动更新 contract status**（见 `data_stasher.py:171-211`）

**真正的问题是**：LLM 在决策时**没有正确理解**这些已有信息。

**问题 3：与 Claude Code 设计哲学相悖**

Claude Code 的核心设计：
1. **依赖对话历史本身**：不维护单独的 TODO 追踪
2. **工具执行后直接反馈**：结果追加到对话上下文
3. **长对话累积上下文**：LLM 自然"记住"做过什么

当前项目架构与此类似：
- `data_stash` = 工具执行历史
- `component_contracts` = 任务状态
- 每轮将这些信息格式化后放入提示词

**问题不在于缺少追踪机制，而在于信息的可理解性不足**。

---

## 2. 问题根源再诊断

### 2.1 从实际失败案例分析

**场景**：第一轮 "B站热搜前三条" → 第二轮 "用表格形式呈现数据"

**Agent 实际看到的信息**（在 step 5 决策时）：

```
## 已获取的数据（data_stash）
[Step 1] fetch_public_data (✓): B站热搜获取10条数据。最新: ...
  → data_id: lg-abc123
[Step 2] data_operator (✓): 从10条中筛选出3条，返回3条
  → data_id: lg-def456
[Step 3] emit_panel_preview (✓): 已生成并推送 ListPanel 面板（ListPanel-contract-v3），展示 3 条数据
  → data_id: lg-ghi789
[Step 4] emit_panel_preview (✓): 已生成并推送 Table 面板（Table-contract-v1），展示 3 条数据
  → data_id: lg-jkl012

## 已登记的组件契约
- Table (Table-contract-v1) [applied] 目标: lg-jkl012 面板已生成并推送
```

**Agent 的决策**（错误）：
```json
{
  "decision": "CONTINUE",
  "reasoning": "用户可能没有看到或希望重新确认/刷新，为确保满足用户需求，再次推送表格面板",
  "tool_call": { "plugin_id": "emit_panel_preview", ... }
}
```

### 2.2 真正的问题

**不是信息缺失，而是 LLM 决策逻辑问题**：

1. **提示词规则过强**：`research_agent_system.txt` 中 "展示不可省略" 规则让 Agent 倾向于多次推送
2. **缺少明确的"已完成"判断规则**：虽然信息都在，但没有告诉 LLM "当 status=applied 且 data_stash 有成功记录时，任务已完成"
3. **缺少程序化保护**：即使 LLM 判断错误，也没有代码级别的拦截

---

## 3. 新方案：增强现有状态的可理解性

### 3.1 核心理念

**不新增任何数据结构，而是：**
1. 优化状态格式化函数，让 LLM 更容易理解"已完成"
2. 优化提示词，添加明确的完成判断规则
3. 增加程序化保护，在代码层面阻止重复调用

### 3.2 架构对比

```
┌─────────────────────────────────────────────────────────────────┐
│  原方案：新增 TODOTracker                                        │
│  ┌──────────────┐   ┌──────────────────────┐   ┌──────────────┐ │
│  │  data_stash  │ + │ component_contracts  │ + │ todo_tracker │ │
│  │  (执行历史)  │   │   (契约状态)         │   │  (TODO状态)  │ │
│  └──────────────┘   └──────────────────────┘   └──────────────┘ │
│         ↓                    ↓                       ↓          │
│    三套状态需要同步，复杂度高，容易不一致                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  新方案：增强现有状态可理解性                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  data_stash + component_contracts（已有，无需新增）        │   │
│  │  + 优化格式化输出（让 LLM 更容易理解）                     │   │
│  │  + 程序化完成检查（代码级阻止重复调用）                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│         ↓                                                       │
│    单一真实来源，简单可靠                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 详细设计

#### 改进 1：优化 `_format_data_stash()` 输出

**当前输出**：
```
[Step 4] emit_panel_preview (✓): 已生成并推送 Table 面板（Table-contract-v1），展示 3 条数据
  → data_id: lg-jkl012
```

**优化后输出**：
```
## 工具执行历史 & 任务完成状态

### 任务完成度摘要
✅ 展示面板: 2/2 已完成（ListPanel, Table）
✅ 数据获取: 1/1 已完成
✅ 数据加工: 1/1 已完成

### 详细执行记录
[Step 1] fetch_public_data (✓): B站热搜获取10条数据
[Step 2] data_operator (✓): 从10条中筛选出3条
[Step 3] emit_panel_preview (✓): ListPanel 面板已推送 ← 契约 ListPanel-contract-v3 已完成
[Step 4] emit_panel_preview (✓): Table 面板已推送 ← 契约 Table-contract-v1 已完成

⚠️ 所有面板契约都已 applied，无需重复调用 emit_panel_preview
```

**实现**：修改 `research_agent.py:_format_data_stash()`

```python
def _format_data_stash(data_stash: List[DataReference], working_memory: Dict) -> str:
    """格式化已获取的数据摘要，包含任务完成度分析。"""
    if not data_stash:
        return "暂无数据"

    # 统计任务完成度
    panel_tools = {"emit_panel_preview"}
    fetch_tools = {"fetch_public_data", "fetch_private_data"}
    process_tools = {"data_operator", "filter_data"}

    panel_count = sum(1 for ref in data_stash if ref.tool_name in panel_tools and ref.status == "success")
    fetch_count = sum(1 for ref in data_stash if ref.tool_name in fetch_tools and ref.status == "success")
    process_count = sum(1 for ref in data_stash if ref.tool_name in process_tools and ref.status == "success")

    # 获取已完成的契约
    contracts_entry = working_memory.get("component_contracts", {})
    contracts = contracts_entry.get("contracts", {})
    applied_contracts = [c for c in contracts.values() if c.get("status") == "applied"]
    applied_components = [c.get("component_id") for c in applied_contracts]

    lines = ["## 工具执行历史 & 任务完成状态\n"]

    # 任务完成度摘要
    lines.append("### 任务完成度摘要")
    if applied_contracts:
        lines.append(f"✅ 展示面板: {len(applied_contracts)} 个已完成（{', '.join(applied_components)}）")
    if fetch_count > 0:
        lines.append(f"✅ 数据获取: {fetch_count} 个已完成")
    if process_count > 0:
        lines.append(f"✅ 数据加工: {process_count} 个已完成")
    lines.append("")

    # 详细执行记录
    lines.append("### 详细执行记录")
    for item in data_stash:
        status_icon = "✓" if item.status == "success" else "✗" if item.status == "error" else "?"
        line = f"[Step {item.step_id}] {item.tool_name} ({status_icon}): {item.summary}"

        # 如果是面板工具，检查契约状态
        if item.tool_name == "emit_panel_preview" and item.status == "success":
            # 从契约中查找对应的 contract_id
            for contract_id, contract in contracts.items():
                if contract.get("status") == "applied":
                    targets = contract.get("targets", [])
                    if item.data_id in targets or f"$step.{item.step_id}" in targets:
                        line += f" ← 契约 {contract_id} 已完成"
                        break

        lines.append(line)
        if item.data_id:
            lines.append(f"  → data_id: {item.data_id}")

    # 警告提示
    if applied_contracts:
        lines.append("")
        lines.append("⚠️ 所有面板契约都已 applied，无需重复调用 emit_panel_preview")

    return "\n".join(lines)
```

#### 改进 2：优化 `_format_component_contract_registry()` 输出

**当前输出**：
```
## 已登记的组件契约
- Table (Table-contract-v1) [applied] 目标: lg-jkl012 面板已生成并推送
```

**优化后输出**：
```
## 组件契约状态

### ✅ 已完成（无需重复调用）
- Table (Table-contract-v1): 已在 Step 4 推送完成，展示 3 条数据
- ListPanel (ListPanel-contract-v3): 已在 Step 3 推送完成，展示 3 条数据

### ⏳ 待执行（需要调用 emit_panel_preview）
（无）

⚠️ 决策规则：当契约 status=applied 时，该面板已成功推送，禁止重复调用
```

**实现**：修改 `research_agent.py:_format_component_contract_registry()`

```python
def _format_component_contract_registry(working_memory: Dict[str, Any]) -> str:
    """格式化组件契约信息，明确区分已完成和待执行。"""
    if not isinstance(working_memory, dict):
        return "暂无"
    contracts_entry = working_memory.get("component_contracts")
    if not isinstance(contracts_entry, dict):
        return "暂无"
    contracts = contracts_entry.get("contracts") or {}
    if not contracts:
        return "暂无"

    completed = []
    pending = []

    for contract_id, entry in contracts.items():
        component_id = entry.get("component_id", "未知组件")
        status = entry.get("status", "pending")
        description = entry.get("description", "")
        step = entry.get("last_updated_step", "?")

        if status == "applied":
            completed.append(f"- {component_id} ({contract_id}): 已在 Step {step} 推送完成 {description}")
        else:
            targets = entry.get("targets", [])
            target_str = ", ".join(targets) if targets else "未绑定数据"
            pending.append(f"- {component_id} ({contract_id}): 目标数据 {target_str}")

    lines = ["## 组件契约状态\n"]

    lines.append("### ✅ 已完成（无需重复调用）")
    if completed:
        lines.extend(completed)
    else:
        lines.append("（无）")
    lines.append("")

    lines.append("### ⏳ 待执行（需要调用 emit_panel_preview）")
    if pending:
        lines.extend(pending)
    else:
        lines.append("（无）")

    if completed:
        lines.append("")
        lines.append("⚠️ 决策规则：当契约 status=applied 时，该面板已成功推送，禁止重复调用")

    return "\n".join(lines)
```

#### 改进 3：优化提示词 `research_agent_system.txt`

**新增规则**：

```
## 任务完成判断（必读！）

在做出 CONTINUE/FINISH 决策前，必须执行以下检查：

### 完成判断清单
1. **检查组件契约状态**：
   - 如果"组件契约状态"部分显示某个契约在"✅ 已完成"列表中
   - 说明该面板已成功推送，**绝对禁止**再次调用 emit_panel_preview

2. **检查 data_stash**：
   - 如果 data_stash 显示 emit_panel_preview (✓) 且有 data_id
   - 说明面板已生成并推送成功

3. **改呈现方式的特殊规则**：
   - 用户要求"用表格呈现"/"换个展示方式"时
   - 只需调用**一次** emit_panel_preview(contract_id=目标组件)
   - 成功后立即 FINISH，**不要因为"确保用户看到"而重复推送**

### 禁止的行为
- ❌ 对已 applied 的契约重复调用 emit_panel_preview
- ❌ 以"确保用户看到"、"刷新"、"确认"等理由重复推送
- ❌ 在 reasoning 中写 `- [ ] 生成/推送展示面板` 但实际上契约已完成

### 正确的决策示例
```json
// 当 Table-contract-v1 状态为 applied 时
{
  "decision": "FINISH",
  "reasoning": "检查组件契约状态：Table-contract-v1 已在 Step 4 成功推送（status=applied）。所有任务已完成，无需重复调用。",
  "final_report": { ... }
}
```
```

#### 改进 4：程序化保护（代码级阻止重复调用）

**在 `_process_agent_decision()` 中增加硬性检查**：

```python
def _process_agent_decision(
    data: Dict[str, Any],
    next_step: int,
    state: GraphState,
    runtime: LangGraphRuntime,
) -> Dict[str, Any]:
    """处理 Agent 的决策结果，包含重复调用保护。"""

    # ... 现有逻辑 ...

    if decision == "CONTINUE":
        tool_call_data = data.get("tool_call", {})
        plugin_id = tool_call_data.get("plugin_id")

        # 🆕 重复调用保护：检查 emit_panel_preview 是否针对已完成的契约
        if plugin_id == "emit_panel_preview":
            args = tool_call_data.get("args", {})
            contract_id = args.get("contract_id")

            if contract_id and _is_contract_already_applied(state, contract_id):
                logger.warning(
                    "阻止重复调用：契约 %s 已 applied，跳过 emit_panel_preview",
                    contract_id
                )
                return {
                    "final_report": json.dumps({
                        "summary": f"任务已完成：{contract_id} 面板已成功推送，无需重复调用",
                        "evidence": [],
                        "next_actions": [],
                    }, ensure_ascii=False, indent=2),
                    "next_tool_call": None,
                    "agent_decision": "FINISH",
                    "agent_reasoning": f"程序保护：检测到 {contract_id} 已 applied，阻止重复调用",
                }

        # ... 现有逻辑 ...


def _is_contract_already_applied(state: GraphState, contract_id: str) -> bool:
    """检查某个契约是否已完成（status=applied）。"""
    working_memory = state.get("working_memory", {})
    contracts_entry = working_memory.get("component_contracts", {})
    contracts = contracts_entry.get("contracts", {})

    contract = contracts.get(contract_id, {})
    return contract.get("status") == "applied"
```

---

## 4. 实施计划

### Phase 1：优化状态格式化 ✅ 已完成

**修改文件**：
- `langgraph_agents/agents/research_agent.py`
  - ✅ 修改 `_format_data_stash()`：添加任务完成度摘要，新增 `working_memory` 参数
  - ✅ 修改 `_format_component_contract_registry()`：区分已完成/待执行
  - ✅ 新增 `_is_contract_already_applied()` 辅助函数（支持 contract_id 和 component_id 双重匹配）

### Phase 2：优化提示词 ✅ 已完成

**修改文件**：
- `langgraph_agents/prompts/research_agent_system.txt`
  - ✅ 新增"任务完成判断（必读！）"章节
  - ✅ 添加完成判断清单、禁止行为列表、正确决策示例

### Phase 3：程序化保护 ✅ 已完成

**修改文件**：
- `langgraph_agents/agents/research_agent.py`
  - ✅ 在 `_process_agent_decision()` 的 CONTINUE 分支添加重复调用检查
  - ✅ 支持从 contract_id 推断 component_id（如 "Table-contract-v1" -> "Table"）
  - ✅ 对已 applied 的契约，直接返回 FINISH

### Phase 4：端到端验证 ✅ 已完成

**测试场景与结果**：

| 测试场景 | 预期 | 实际结果 | 状态 |
|---------|------|---------|------|
| "B站热搜前三条" | emit_panel_preview 调用 1 次 | ListPanel 生成 1 次，展示 3 条 | ✅ 通过 |
| "用表格呈现B站热搜前五条数据" | emit_panel_preview 调用 1 次 | Table 生成 1 次，展示 5 条 | ✅ 通过 |

**关键日志验证**：

**第一轮查询**：
```
ResearchAgent 选择工具: fetch_public_data (step 1)
ResearchAgent 选择工具: data_operator (step 2)
ResearchAgent 选择工具: emit_panel_preview (step 3)
panel_spec_builder: record_count=3, components=['ListPanel']
ResearchAgent 决策: FINISH
```

**第二轮查询**：
```
ToolExecutor 契约透传: contracts=['Table-contract-v1']
ResearchAgent 选择工具: fetch_public_data (step 1)
ResearchAgent 选择工具: data_operator (step 2)
ResearchAgent 选择工具: data_operator (step 3)
ResearchAgent 选择工具: emit_panel_preview (step 4)
panel_spec_builder: record_count=5, components=['Table']
ResearchAgent 决策: FINISH
```

**核心问题已解决**：`emit_panel_preview` 从之前的 3 次调用减少为 1 次。

**验证日期**：2025-12-11

---

## 5. 与原方案对比

| 维度 | 原方案（TODOTracker） | 新方案（增强可理解性） |
|------|----------------------|----------------------|
| **数据结构** | 新增 todo_tracker | 无新增 |
| **状态源数量** | 3 套（data_stash + contracts + todos） | 2 套（现有） |
| **同步复杂度** | 高（需保持三套状态一致） | 低（单一真实来源） |
| **代码改动量** | ~500+ 行新增 | ~100 行修改 |
| **测试复杂度** | 高（新数据结构需全面测试） | 低（修改现有逻辑） |
| **与 Claude Code 设计一致性** | ❌ 违背（新增独立追踪） | ✅ 一致（依赖历史本身） |
| **解决问题的层次** | 表层（新增追踪） | 根源（增强理解） |

---

## 6. 风险评估

### 风险 1：LLM 仍可能忽视提示词规则

**对策**：Phase 3 的程序化保护作为最后一道防线，即使 LLM 决策错误，代码也会阻止重复调用。

### 风险 2：格式化输出过长

**对策**：
- 任务完成度摘要控制在 5 行以内
- 详细记录保持原有长度
- 必要时可根据 step 数量动态调整

### 风险 3：程序化保护可能误拦截

**对策**：
- 只对 `status=applied` 的契约阻止
- 用户明确要求"重新生成"时，应先重置契约状态
- 添加详细日志，便于调试

---

## 7. 总结

### 核心发现

原方案错误地将问题诊断为"TODO 状态追踪不足"，实际上：
- **现有架构已有完善的状态追踪**：`data_stash` + `component_contracts`
- **真正的问题是信息可理解性不足**：LLM 无法正确判断"已完成"
- **新增 TODOTracker 会造成三套并行系统**，违反项目原则

### 新方案优势

1. **零新增数据结构**：复用现有 `data_stash` + `component_contracts`
2. **符合 Claude Code 设计哲学**：依赖历史本身，不维护独立追踪
3. **从根源解决问题**：增强信息可理解性 + 程序化保护
4. **实施成本低**：约 100 行代码修改，2-3 天完成

### 决策建议

**推荐采用新方案（v2.0）**，原因：
1. 符合项目"基于现有架构改进"的原则
2. 避免三套并行状态追踪的复杂度
3. 从根源解决问题，而非打补丁
4. 实施风险低，可快速验证

---

## 附录：Claude Code 设计参考

### Claude Code 的上下文管理

Claude Code 采用**长对话模式**：
1. 所有工具执行结果直接追加到对话历史
2. LLM 通过对话历史"记住"做过什么
3. 不维护单独的 TODO 追踪数据结构

### 当前项目的类似设计

当前项目虽然每轮是新 LLM 调用，但：
1. `data_stash` = 工具执行历史（类似对话追加）
2. `component_contracts` = 任务状态（类似"已完成"标记）
3. 每轮将这些信息格式化后放入提示词

**问题在于**：格式化输出不够"一目了然"，LLM 需要额外推理才能判断"已完成"。

**新方案**：让格式化输出**直接告诉** LLM "这个任务已完成，不要重复执行"。
