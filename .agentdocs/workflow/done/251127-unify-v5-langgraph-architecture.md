# V5.0 架构统一：废弃 services/agent_graph，使用完整 LangGraph 状态机

## 状态：已完成 ✅

## 背景与问题

### 问题发现
用户提出疑问："V5.0 的 agent 不是已经包含了从规范到执行各方面的内容嘛？目前的 taskgraph 是从哪里来的？"

### 架构分裂现状（已解决）

项目中曾存在**两套并行的任务执行系统**：

| 特性 | V5.0 设计 (`langgraph_agents/`) | Task Graph (`services/agent_graph/`) |
|------|--------------------------------|------------------------------------|
| 文件数 | **35+ 个文件** | **4 个文件** |
| 规划模式 | **单步迭代规划**（有上下文） | 多步一次性规划（无上下文） |
| filter_data | 408 行完整实现 | ~150 行简化版 |
| 执行引擎 | ExecutionEngine 385 行 | GraphExecutor 简化版 |
| data_store | 完整集成 | **无** |
| 容量保护 | MAX_ROWS_LIMIT + 自动采样 | **无** |

### 根本问题

1. **`services/agent_graph/` 采用多步一次性规划**：LLM 在没有任何上下文的情况下规划完整 DAG
   - 问题：规划时不知道有哪些数据源、数据结构是什么
   - 结果：无法做出正确的规划决策

2. **V5.0 采用单步迭代规划**（类似 Claude Code 自身的工作方式）：
   - Router → 判断意图
   - Planner → 规划下一步（比如先调用 search_data_sources）
   - ToolExecutor → 执行工具
   - Reflector → 根据结果决定是否继续
   - 循环直到完成

## 解决方案

**方案 B 修正版：使用 V5.0 完整 LangGraph 状态机**

核心原则：
1. ChatService 直接接入 V5.0 的 `create_langgraph_app()`
2. 使用迭代式规划（每步都有充足上下文）
3. 复用完整的 Router → Planner → ToolExecutor → DataStasher → Reflector 流程

## 实施计划

### Phase 1: 创建同步执行适配层 ✅

- [x] 1.1 修复 `filter_data` 工具支持直接数据对象传入
- [x] 1.2 创建 `langgraph_agents/sync_executor.py`
  - 提供 `SyncLangGraphExecutor` 类和 `create_sync_executor()` 工厂函数
  - 封装 `create_langgraph_app().invoke()` 为同步调用
- [x] 1.3 单元测试 - 5 个测试全部通过

### Phase 2: ChatService 迁移 ✅

- [x] 2.1 修改 `services/chat_service.py`
  - 移除 `from services.agent_graph import ...`
  - 使用 `langgraph_agents.sync_executor` 替代
  - 新增 `self.langgraph_executor` 属性
  - 新增 `_build_langgraph_metadata()` 方法
- [x] 2.2 删除 `services/chat/task_graph_handler.py`（不再需要）
- [x] 2.3 更新测试用例
  - 将 `test_chat_service_task_graph_filters_items` 重写为 `test_chat_service_langgraph_integration`

### Phase 3: 废弃旧代码 ✅

- [x] 3.1 删除 `services/agent_graph/` 目录
- [x] 3.2 删除 `services/chat/task_graph_handler.py`
- [x] 3.3 删除 `tests/services/test_agent_graph.py`

### Phase 4: 验证 ✅

- [x] 4.1 ChatService 测试：10 个测试全部通过
- [x] 4.2 LangGraph 测试：190 个测试通过，1 个跳过
- [x] 4.3 导入验证：ChatService 和 SyncLangGraphExecutor 导入正常

## 关键设计决策

### Q1: 为什么必须使用单步迭代规划？
**答案**：上下文至关重要！
- 多步一次性规划时，LLM 不知道有哪些数据源
- 单步迭代规划时，每一步都有前序步骤的执行结果作为上下文
- 类比：Claude Code 也是先读文件了解情况，再决定下一步

### Q2: 是否需要完整的 LangGraph 状态机？
**答案**：**是的**。需要完整的 Router → Planner → ToolExecutor → Reflector 循环：
- Router：判断简单查询还是复杂研究
- Planner：规划下一步（有上下文）
- ToolExecutor：执行工具
- Reflector：决定是否继续

### Q3: 如何处理同步 vs 异步？
**答案**：创建 `sync_executor.py` 适配层，内部调用 `app.invoke()`

## 新增文件

- `langgraph_agents/sync_executor.py` - 同步执行适配层（227 行）
- `tests/langgraph_agents/test_sync_executor.py` - 单元测试（146 行）

## 删除的文件

- `services/agent_graph/` - 整个目录（4 个文件）
- `services/chat/task_graph_handler.py`
- `tests/services/test_agent_graph.py`

## 相关文档

- `.agentdocs/langgraph-v5.0-flexible-agent-architecture.md` - V5.0 原始设计
