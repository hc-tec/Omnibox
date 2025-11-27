# V5.0 Task Graph 统一架构重构

## 背景

当前后端存在三套并行的复杂任务处理系统：

1. **Task Graph (V5.0)** - 仅在 simple_query 中使用
2. **LLMQueryPlanner + ParallelQueryExecutor** - 用于 complex_research 流式
3. **ResearchService + LangGraph** - 用于 langgraph 模式

这导致 V5.0 设计的 Task Graph 架构未被充分利用，用户的复杂查询（如"获取+过滤"）无法正确处理。

## 目标

将 Task Graph 作为**统一的数据查询编排层**，废弃冗余组件。

## 重构方案

### Phase 1: 统一所有数据查询到 Task Graph

**修改文件**: `services/chat_service.py`

1. 移除 `complex_research` 意图的特殊处理（不再返回"需要流式接口"）
2. 将 `_handle_simple_query` 重命名为 `_handle_data_query`
3. 所有数据查询（simple/complex）统一使用 Task Graph

**修改前**:
```
complex_research → 返回"需要流式接口" → 流式接口用 LLMQueryPlanner
```

**修改后**:
```
所有 data_query → Task Graph Planner → Graph Executor → 返回结果
```

### Phase 2: 重构流式接口

**修改文件**: `api/controllers/chat_stream.py`

1. 流式接口直接调用 Task Graph
2. 按节点推送执行进度
3. 移除对 `_handle_complex_research_streaming` 的依赖

### Phase 3: 废弃旧组件

**删除/废弃**:
- `services/llm_query_planner.py` - 功能由 Task Graph Planner 替代
- `services/parallel_query_executor.py` - 功能由 Graph Executor 替代
- `services/chat/research_streaming.py` - 功能由流式 Task Graph 替代
- `ChatService` 中的 `query_planner` 和 `parallel_executor` 属性

### Phase 4: LangGraph 作为高级扩展（可选）

保留 `ResearchService` 作为需要多轮反思的深度研究模式，但基础数据查询统一走 Task Graph。

## TODO

- [x] Phase 1: 统一数据查询到 Task Graph
- [x] Phase 2: 重构流式接口
- [x] Phase 3: 废弃旧组件
- [x] Phase 4: 测试验证 (412 passed)

## 问题修复记录

### 2024-11-27 修复：Task Graph 执行问题

**问题1：重复数据获取**
- 症状：fetch_data 节点获取数据后，data_query_service 又通过 vsearch 重复获取
- 原因：`prefer_single_route=False` 导致 data_query_service 内部做多路由规划
- 修复：`executor.py` 中 fetch_data 节点强制 `prefer_single_route=True`

**问题2：filter 节点未被规划**
- 症状：LLM 只规划了 fetch 节点，没有规划 filter 节点
- 原因：System Prompt 不够明确
- 修复：优化 `planner.py` 的 System Prompt，增加明确的规划原则和示例

**问题3：缺少规划日志**
- 修复：添加 Task Graph 规划结果日志，便于调试

**问题4：工具定义硬编码在 System Prompt**
- 症状：工具定义直接写在 planner.py 中，不符合最佳实践
- 原因：未遵循项目现有的 ToolRegistry 架构
- 修复：
  - `planner.py` 添加 `tool_registry` 参数，动态从 ToolRegistry 构建工具定义
  - `chat_service.py` 初始化时创建 ToolRegistry 并注册默认工具
  - 修正工具 ID：`data_compare` → `compare_data`，`data_aggregator` → `aggregate_data`
  - 工具定义（含 JSON Schema）自动注入到 System Prompt

**问题5：filter 节点参数格式不匹配**
- 症状：LLM 规划了 filter 节点，但执行时没有过滤效果
- 原因：ToolRegistry 的 schema 使用 `conditions` 格式，但 executor 只支持 `keywords` 格式
- 修复：
  - 重写 `executor.py` 的 `_apply_filter` 方法
  - 支持 `conditions` 格式：`{"title": {"$contains": "英雄联盟"}}`
  - 保持 `keywords` 向后兼容
  - 支持 10 种操作符：$eq, $ne, $gt, $gte, $lt, $lte, $contains, $in, $between, $regex

**问题6：复杂任务未使用流式接口**
- 症状：前端调用非流式接口，复杂任务执行期间无任何反馈
- 原因：V5.0 重构后 `complex_research` 直接执行 Task Graph，没有返回流式提示
- 修复：
  - 后端 `chat_service.py` 添加 `force_execute` 参数
  - 非流式接口：复杂任务返回 `requires_streaming=True`，让前端切换到 WebSocket
  - 流式接口：设置 `force_execute=True`，直接执行 Task Graph 并按节点推送进度
  - 前端 `panelStore.ts` 的 `fetchPanel()` 方法自动检测 `requires_streaming`
  - 检测到复杂任务时，自动切换到 `connectStreamWithCallback()` 流式模式
