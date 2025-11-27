# V5.0 Agent 重构方案：Task Graph 智能执行

## 背景与问题
- 现状：LLM 意图分类 simple/simple_query 直接走单次 RAG → QueryParser → PathBuilder，复杂语义完全被“简单查询”吞没。
- 结果：Planner/Research 层根本没机会介入，多工具、多步骤能力形同虚设，订阅解析与关键词增强只能“打补丁”。
- 目标：像 AI 编程模型一样，把自然语言理解为“多步骤任务图”，由统一执行框架调度工具，保持上下文与可扩展性。

## 核心设计
### 1. Task Graph（任务图）
- **结构**：节点（Node）+ 边（依赖），相当于“伪代码 AST”。
- **节点类型**：
  - `fetch_data`：调用数据源工具（如 `bilibili_user_video`、`fetch_private_data`）。
  - `transform`：对已有数据执行过滤/聚合/比较（`filter_data`、`compare_data`、`aggregate_data`）。
  - `analysis`：调用 LLM 对结果进行总结/推理。
  - `interaction`：需要用户澄清的节点。
  - `output`：最终汇报/面板构建。
- **节点描述**：`id`、`type`、`input_refs`、`tool_spec`、`expected_output`、`on_fail` 等元数据。

### 2. Planner（Graph Planner）
- 输入：自然语言请求、会话上下文、可用工具 Schema、历史执行记录。
- 输出：Task Graph（JSON 中严格定义 Node/Edge），可多轮增量更新。
- 约束：
  - Planner 必须显式列出“需要的数据源 + 后续处理”。
  - 如用户指定“UP投稿 + 条件过滤”，Planner 需拆成 `fetch_user_video` → `filter_data` → `analysis`。
  - 允许 Planner 根据已有结果动态插入/删除节点（类似代码迭代）。

### 3. Graph Executor
- 负责读取 Task Graph、调度节点执行、缓存中间结果、处理错误。
- 执行步骤：
  1. **拓扑调度**：按依赖拓扑顺序执行，支持并行节点。
  2. **工具调用**：通过统一 Tool API（Service 层已有）执行，写入 `execution_state`。
  3. **记忆写入**：每个节点输出包含 `result`, `metadata`, `confidence`，写进共享记忆（可用于 Planner 增量规划）。
  4. **错误回路**：节点失败可触发 `on_fail` 策略（重试/换工具/请求澄清）。
  5. **Streaming**：执行过程实时推送给前端（WebSocket），用户可看到 Node 状态/产出。

### 4. 统一记忆层
- 数据结构：`WorkingMemory`（短期，存 Task Graph & 中间结果）+ `LongTermMemory`（订阅、私有数据、历史任务）。
- 每个节点读写通过标准接口完成（避免临时变量）。
- Planner/Executor 都能访问记忆（Planner 可根据现有结果决定后续步骤）。

### 5. 工具 Registry
- 保持已有 Tool 元数据（schema、参数、能力），Planner 通过这些 schema 组装 Task Graph。
- 新工具只需注册 Manifest + 测试；Planner 通过描述即可使用，无需修改核心代码。

## 执行流程（示例）
1. **用户输入**：“B站影视飓风投稿视频中，标题包含‘英雄联盟’的视频”。
2. **Planner 输出任务图**：
   ```json
   {
     "nodes": [
       { "id": "fetch_up", "type": "fetch_data", "tool": "bilibili_user_video", "params": {"uid": "影视飓风"} },
       { "id": "filter", "type": "transform", "tool": "filter_data", "params": {"keyword": "英雄联盟"}, "inputs": ["fetch_up"] },
       { "id": "analysis", "type": "analysis", "tool": "generate_summary", "inputs": ["filter"] }
     ]
   }
   ```
3. **Executor**：
   - `fetch_up` 调订阅解析 → 取数据 → 写入记忆。
   - `filter` 从 `fetch_up` 读取结果 → 运行过滤 → 写入记忆。
   - `analysis` 调 LLM 对过滤结果生成解释 → 写入记忆。
4. **输出**：最终节点 `analysis` + 面板数据聚合成响应，前端展示一步步的 Node 状态。

## 与现有系统的集成
1. **RAG / 订阅 / 数据服务**：不改现有 Service，转为通过 Tool Interface 被 Graph 节点消费。
2. **ChatService**：收到请求后直接触发 Planner → Graph Executor → Streaming，simple 模式仅在 Planner 输出单节点且无需研究时才 fallback。
3. **前端**：沿用研究模式的 WebSocket，展示 Task Graph + 节点日志，Panel 渲染仍复用 Panel Generator。

## 开发计划（建议）
1. **文档阶段**（当前）：整理架构、节点协议、Planner Prompt 规范、测试矩阵。
2. **实现阶段**：
   - Task Graph 数据结构 & Schema。
   - Planner Prompt + 评估（可先用 “半结构化 → 调试 Prompt”）。
   - Graph Executor（含 Memory、工具调用、Streaming）。
   - 测试：单元（节点执行）、集成（Graph + Tool）、端到端（WebSocket + Panel）。
3. **迁移阶段**：将旧的 simple/comple 模式逐步切换至 Graph，使 RAGInAction 仅负责 Tool 调度，不再做业务补丁。

## 追踪 & TODO
- [x] 定义 Task Graph JSON Schema 与 Node/Edge 类型。（`services/agent_graph/schema.py`）
- [x] 设计 Planner Prompt（涵盖 fetch/filter/analysis/interaction）。`TaskGraphPlanner.SYSTEM_PROMPT` 已落地，默认降级规则覆盖 fetch→filter。
- [x] 实现 Graph Executor（含拓扑调度、记忆、错误处理）。`services/agent_graph/executor.py`
- [x] WebSocket message schema 扩展（Node 状态、结果引用）。新增 `GraphNodeMessage` 并在 `chat_stream` 中推送节点状态。
- [x] 回归测试：确保“UP 投稿 + 条件过滤”自动生成 2+ 节点图。（`tests/services/test_chat_service.py::test_chat_service_task_graph_filters_items`）

> 本方案旨在恢复 V5.0 的“智能代理”定位：用 Task Graph 驱动规划 → 执行 → 反馈的完整闭环，避免通过特例补丁实现功能。
