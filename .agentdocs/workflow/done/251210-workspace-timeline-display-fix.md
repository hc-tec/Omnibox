# 工作台时间线显示问题修复

## 问题描述

用户反馈工作台存在三个严重的显示问题：

### 问题1：重复的"思考中"条目
- **现象**：多次出现"思考中 - 分析查询并规划执行步骤..."
- **影响**：界面混乱，用户无法判断执行进度

### 问题2：面板生成重复
- **现象**：同一个面板被展示多次
- **影响**：界面冗余，数据重复

### 问题3：关键思考内容缺失
- **现象**：Agent 的重要决策（如"发现已有B站热搜数据，不用重复获取"）未展示
- **影响**：用户无法理解 AI 的推理过程，丧失透明度和信任感

## 现状分析

### 后端数据流
```
session_controller.py._stream_session_execution()
  ├─ StageMessage("分析查询...")          → 推送给前端
  ├─ runtime_manager.execute_in_session() → 执行 LangGraph
  │     └─ panel_callback()               → 每个面板触发
  │           ├─ ResearchStepMessage      → 推送给前端
  │           └─ DataMessage(panel_preview) → 推送给前端
  └─ StageMessage("生成执行摘要...")      → 推送给前端
  └─ DataMessage(summary)                 → 推送 data_stash
```

### 前端处理流
```
useSessionWebSocket.ts.handleMessage()
  ├─ stage    → handleStageMessage() → addThinkingEntry()  ← 每次都添加新条目
  ├─ data     → handleDataMessage()
  │     ├─ panel_preview → handlePanelPreview() → addPanelEntry() + addPanelPreview()
  │     └─ summary       → handleSummaryData()  → addToolCallEntry() ← 重复处理 data_stash
  └─ research_step → handleStepMessage() → addToolCallEntry()
```

### 问题根源

#### 根源1：Stage 消息无去重
- 后端每个阶段发送 StageMessage
- 前端 `addThinkingEntry()` 无条件添加新条目
- 没有检查是否已存在相同内容的思考条目

#### 根源2：面板数据双重处理
- `panel_callback` 触发时推送 `panel_preview` 数据 → 前端添加面板
- `summary` 阶段也包含 `panel_previews` → 前端再次添加面板
- 虽然 `handleSummaryData` 有去重检查，但 `alreadyAdded` 判断可能失效

#### 根源3：Agent Reasoning 未传递
- `research_agent.py` 返回 `agent_reasoning`
- `sync_executor.py._extract_result()` 只提取 `execution_steps`，不含 reasoning
- `session_controller.py` 不推送 Agent 决策过程
- **关键缺失**：LangGraph 执行是同步的，中间状态未实时推送

## 改造方案

### Phase 1: Agent Reasoning 实时推送（核心改造）

**目标**：让 Agent 的每一步决策实时推送给前端

**方案**：在 `runtime_manager.execute_in_session()` 中注入 reasoning 回调

1. **扩展 SyncLangGraphExecutor**
   - 添加 `reasoning_callback` 参数
   - 在 LangGraph 执行过程中触发回调

2. **修改 session_controller.py**
   - 定义 `reasoning_callback` 函数
   - 在回调中推送 `ResearchStepMessage`

3. **前端显示 reasoning**
   - 扩展 `handleStepMessage` 处理 reasoning 字段
   - 在时间线中显示 Agent 的思考过程

**涉及文件**：
- `langgraph_agents/sync_executor.py`
- `services/session/runtime_manager.py`
- `api/controllers/session_controller.py`
- `frontend/src/features/workspace/composables/useSessionWebSocket.ts`

### Phase 2: 去重机制

**目标**：消除重复的思考条目和面板

1. **Stage 消息去重**
   - 前端 `addThinkingEntry` 检查最后一条是否相同
   - 或后端只在真正的阶段切换时发送 stage 消息

2. **面板去重**
   - 后端：在 summary 中不再包含 panel_previews（已通过回调实时推送）
   - 前端：基于 data_id 或面板内容 hash 去重

**涉及文件**：
- `api/controllers/session_controller.py`
- `frontend/src/features/workspace/stores/workspaceStore.ts`
- `frontend/src/features/workspace/composables/useSessionWebSocket.ts`

### Phase 3: 时间线显示优化

**目标**：更清晰地展示执行流程

1. **合并连续思考条目**
   - 如果多个 stage 消息内容相同，只保留一条

2. **工具调用条目增强**
   - 显示工具描述（summary）
   - 显示执行耗时
   - 显示 reasoning（Agent 为什么选择这个工具）

3. **面板条目增强**
   - 显示数据来源
   - 显示数据条数
   - 关联到对应的工具调用

## TODO 清单

### Phase 1: Agent Reasoning 实时推送
- [x] 1.1 扩展 LangGraph 回调机制，支持 reasoning 推送
- [x] 1.2 修改 session_controller 注入 reasoning_callback
- [x] 1.3 定义 reasoning 消息类型（ResearchStepMessage 扩展）
- [x] 1.4 前端 handleStepMessage 处理 reasoning 字段
- [x] 1.5 时间线显示 Agent 思考内容

### Phase 2: 去重机制
- [x] 2.1 后端 summary 移除 panel_previews 重复数据
- [x] 2.2 前端 addThinkingEntry 去重逻辑
- [x] 2.3 前端面板去重（基于 title + source_query）

### Phase 3: 时间线优化
- [x] 3.1 合并连续相同的思考条目（通过 2.2 去重实现）
- [~] 3.2 工具调用条目显示 reasoning（当前架构不适用，跳过）
- [~] 3.3 工具调用条目显示执行耗时（需要后端时间追踪支持，未来优化）

### Phase 4: 工具调用步骤实时推送（测试发现的新问题）
- [x] 4.1 在 data_stasher.py 添加 emit_tool_result 回调触发
- [x] 4.2 在 runtime_manager.py 添加 tool_callback 参数和注册
- [x] 4.3 在 session_controller.py 定义 tool_callback 并处理 tool_result 事件
- [x] 4.4 推送 ResearchStepMessage with step_type="tool_call"

## 测试过程中发现的新问题

### 问题4：工具调用步骤姗姗来迟

**现象**：
- 时间线中工具调用步骤（fetch_public_data、data_operator）不是在执行时实时显示
- 而是在最后 summary 阶段才从 `execution_steps` 中提取显示
- 导致时间线顺序混乱：先显示"完成任务"，然后才显示"获取数据"和"数据处理"

**问题根源**：
当前实现中，只有两种情况推送 `ResearchStepMessage`：
1. `agent_reasoning` 回调 → `step_type: planning`（Agent 推理）
2. `panel_preview` 回调 → `step_type: data_fetch`（面板预览）

但**工具调用本身**没有推送为独立的时间线条目！

**解决方案**：
添加工具调用完成回调（tool_callback），在工具执行完成时实时推送：

1. **DataStasher 触发回调**（`langgraph_agents/agents/data_stasher.py`）
   - 在记录工具执行结果后，触发 `emit_tool_result` 回调
   - 传递 step_id、tool_name、description、status、summary

2. **RuntimeManager 注册回调**（`services/session/runtime_manager.py`）
   - 添加 `tool_callback` 参数
   - 注册到 `extras["emit_tool_result"]`

3. **SessionController 处理事件**（`api/controllers/session_controller.py`）
   - 定义 `tool_callback` 函数，推送到事件队列
   - 处理 `tool_result` 事件，推送 `ResearchStepMessage` with `step_type: tool_call`

**修改的文件**：
- `langgraph_agents/agents/data_stasher.py`
- `services/session/runtime_manager.py`
- `api/controllers/session_controller.py`

## 实施总结

所有核心问题已修复：
1. ✅ 重复的"思考中"条目 → addThinkingEntry 去重逻辑
2. ✅ 缺失的 Agent reasoning → 完整的 reasoning 推送链路（research_agent → sync_executor → runtime_manager → session_controller → WebSocket → frontend）
3. ✅ 重复的面板生成 → addPanelPreview 去重 + 后端 summary 移除 panel_previews
4. ✅ 工具调用步骤延迟显示 → 添加 tool_callback 实时推送工具调用完成消息

**测试验证通过**（2025-12-10 15:23）：
- Agent 推理内容实时显示，带 Lightbulb 图标和"详细推理"标签
- 工具调用步骤实时显示（fetch_public_data、data_operator、emit_panel_preview）
- Agent 正确识别已有数据："之前已成功获取并清洗了B站热榜数据（Step 2，data_id: lg-xxx）"
- 时间线顺序正确：推理 → 工具调用 → 推理 → 工具调用...

**测试中发现的其他问题**（非本次任务范围）：
- ListPanel 组件契约的 link 字段应该设为可选（require: false），而非必填

ThinkingEntry.vue 现在会展示：
- 主要内容（content）
- 详细推理（reasoning），带 Lightbulb 图标和"详细推理"标签

时间线现在会实时显示：
- Agent 推理步骤（planning）
- 工具调用步骤（tool_call）- 新增
- 面板预览步骤（data_fetch）

## 技术细节

### ResearchStepMessage 扩展
```python
class ResearchStepMessage(BaseStreamMessage):
    type: Literal["research_step"] = "research_step"
    task_id: str
    step_id: str
    step_type: str  # "thinking" | "tool_call" | "panel_preview"
    action: str
    status: str
    details: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None  # 新增：Agent 的思考内容
```

### 前端时间线条目类型扩展
```typescript
interface TimelineEntry {
  type: 'thinking' | 'tool_call' | 'panel' | ...
  thinking?: {
    content: string
    reasoning?: string  // 新增：Agent 的推理过程
  }
  toolCall?: {
    tool_name: string
    reasoning?: string  // 新增：为什么选择这个工具
    duration_ms?: number  // 新增：执行耗时
  }
}
```

## 预期效果

修复后的时间线应该展示：

```
[用户查询] 查看B站热榜
[思考中] 用户要求查看B站热榜，这是首次查询，需要获取原始数据...
[工具调用] fetch_public_data - B站热榜
[工具调用] data_operator - 清洗并格式化数据
[面板] B站热搜榜单 (10条记录)
[完成] 已成功获取并展示B站热榜数据

[用户查询] 分析一下前三个热搜的内容是什么
[思考中] 根据对话历史，之前已获取并清洗了B站热榜数据。现在需要从已有数据中筛选前三条进行分析...  ← 关键！
[工具调用] data_operator - 筛选前三条记录
[工具调用] data_operator - 生成内容摘要
[面板] B站热搜内容摘要 (3条记录)
[完成] 已成功分析前三个热搜的内容
```

## 相关文件清单

### 后端
- `api/controllers/session_controller.py` - WebSocket 消息推送
- `api/schemas/stream_messages.py` - 消息类型定义
- `services/session/runtime_manager.py` - Session 执行管理
- `langgraph_agents/sync_executor.py` - LangGraph 同步执行
- `langgraph_agents/agents/research_agent.py` - Agent 决策（已有 reasoning）

### 前端
- `frontend/src/features/workspace/composables/useSessionWebSocket.ts` - WebSocket 消息处理
- `frontend/src/features/workspace/stores/workspaceStore.ts` - 时间线状态管理
- `frontend/src/features/workspace/components/canvas/MainCanvas.vue` - 时间线渲染

## 创建日期
2025-12-10
