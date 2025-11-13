# LangGraph V4.4 架构实施任务

## 任务概述

**任务代号**: 251113-langgraph-v4.4-implementation
**创建时间**: 2025-01-13
**预计工作量**: 7.5 天
**状态**: 待开始（已通过设计评审）

**核心目标**：将 V4.4 架构改进与当前 V2 系统渐进式集成

**批准的实施范围**：
- ✅ V4.0: 显式依赖解析（StashReference + JSONPath）
- ✅ V4.1: 扇出并行执行（MappedExecutionReport）
- ✅ V4.2: RSSHub 路由发现（RAG 检索透明化）
- ✅ V4.4: 前置语义 + GraphRenderer（零溢出）
- ✅ 前端 RAG 图谱可视化

---

## 当前项目代码结构分析

### 现有 LangGraph Agents 架构

```
langgraph_agents/
├── __init__.py
├── state.py                    # ✅ GraphState, ToolCall, DataReference
├── graph_builder.py            # ✅ 图谱构建入口
├── runtime.py                  # ✅ LangGraphRuntime
├── config.py                   # ✅ 配置管理
├── agents/                     # ✅ 代理节点
│   ├── router.py              # ✅ RouterAgent
│   ├── planner.py             # ✅ PlannerAgent
│   ├── tool_executor.py       # ✅ ToolExecutor（需扩展为扇出）
│   ├── data_stasher.py        # ✅ DataStasher
│   ├── reflector.py           # ✅ ReflectorAgent
│   ├── synthesizer.py         # ✅ SynthesizerAgent
│   ├── simple_chat.py         # ✅ SimpleChatNode（P2 新增）
│   └── human.py               # ✅ wait_for_human
├── tools/
│   └── registry.py            # ✅ 工具注册表
├── storage/
│   └── research_data.py       # ✅ InMemoryResearchDataStore
├── utils/
│   ├── json_utils.py          # ✅ JSON 解析
│   ├── prompt_loader.py       # ✅ Prompt 加载
│   └── llm_retry.py           # ✅ LLM 重试装饰器
└── prompts/                   # ✅ Prompt 模板
    ├── router_system.txt
    ├── planner_system.txt
    ├── reflector_system.txt
    └── synthesizer_system.txt
```

### 现有 RAG 系统

```
rag_system/
├── retriever.py               # ✅ RAGRetriever（已实现）
├── indexer.py                 # ✅ RAG 索引构建
└── quick_start.py             # ✅ 初始化脚本
```

### 现有 Service 层

```
services/
├── chat_service.py            # ✅ ChatService（已与 LangGraph 集成）
├── data_query_service.py      # ✅ DataQueryService（RSSHub 调用）
└── panel/
    ├── panel_generator.py     # ✅ 面板生成器
    └── adapters/              # ✅ 路由适配器
```

### 前端结构

```
frontend/src/
├── features/
│   └── research/
│       └── components/        # ✅ 研究视图组件
│           ├── ResearchView.vue
│           └── ResearchContextPanel.vue
└── composables/
    └── useResearchWebSocket.ts # ✅ WebSocket 管理
```

---

## 实施阶段划分

### 阶段0: 设计评审与环境准备 ✅ 已完成

**状态**: ✅ 完成
**完成时间**: 2025-01-13

**完成项**:
- [x] V4.4 架构设计文档评审通过
- [x] 用户批准完整实施方案（包含 V4.2）
- [x] 明确工作量估算（7.5 天）
- [x] 明确前端可视化需求

---

## 阶段1: V4.0 显式依赖解析（1天）

**目标**: 支持 `StashReference` 和 JSONPath 精确数据提取

**状态**: ⏳ 待开始
**预计时间**: 1 天（2025-01-14）
**优先级**: P0（基础能力）

### 1.1 数据结构定义

#### 任务 1.1.1: 创建 `state_v4.py` 模块
- **文件**: `langgraph_agents/state_v4.py`（新建）
- **依赖**: 无
- **内容**:
  - `StaticValue` 类（包装静态值）
  - `StashReference` 类（data_id + json_path）
  - `ArgumentValue` 联合类型

**验收标准**:
```python
# 可以正常导入和使用
from langgraph_agents.state_v4 import StaticValue, StashReference, ArgumentValue

# 示例
static = StaticValue(value=3)
ref = StashReference(data_id="A", json_path="$.items[*].uid")
```

#### 任务 1.1.2: 扩展 `ToolCall` 为 `ToolCallV4`
- **文件**: `langgraph_agents/state.py`（修改）
- **依赖**: 任务 1.1.1
- **内容**:
  - 创建 `ToolCallV4` 类（继承 `ToolCall`）
  - 添加字段：`call_id`（替代 step_id）、`human_readable_label`、`map_over_arg`
  - `args` 类型支持 `Dict[str, ArgumentValue]`（向后兼容 V2）

**验收标准**:
```python
# V2 兼容（现有代码不受影响）
tool_call_v2 = ToolCall(
    plugin_id="fetch_data",
    args={"uid": "12345"},  # 直接传值
    step_id=1,
    description="获取数据"
)

# V4 新格式（可选使用）
tool_call_v4 = ToolCallV4(
    call_id="A",
    plugin_id="fetch_data",
    args={"uid": StaticValue(value="12345")},
    human_readable_label="获取数据"
)
```

### 1.2 参数解析器实现

#### 任务 1.2.1: 实现 `argument_resolver.py`
- **文件**: `langgraph_agents/utils/argument_resolver.py`（新建）
- **依赖**: 任务 1.1.1
- **内容**:
  - `resolve_arguments()` 函数
  - 处理 `StaticValue`（直接返回 value）
  - 处理 `StashReference`（从 data_stash 提取 + JSONPath）
  - V2 兼容（直接值原样返回）

**技术细节**:
- 使用 `jsonpath-ng` 库（需添加到 `requirements.txt`）
- 错误处理：`data_id` 不存在时抛出清晰错误

**验收标准**:
```python
# 测试用例
args = {
    "limit": StaticValue(value=3),
    "uid": StashReference(data_id="A", json_path="$.items[*].uid")
}
stash = {"A": {"items": [{"uid": "u1"}, {"uid": "u2"}]}}

resolved = resolve_arguments(args, stash)
# → {"limit": 3, "uid": ["u1", "u2"]}
```

### 1.3 测试用例编写

#### 任务 1.3.1: 编写单元测试
- **文件**: `tests/langgraph_agents/test_argument_resolver.py`（新建）
- **依赖**: 任务 1.2.1
- **测试场景**:
  1. 解析 `StaticValue`
  2. 解析 `StashReference`（JSONPath = "$"）
  3. 解析 `StashReference`（JSONPath = "$.items[*].uid"）
  4. V2 兼容（直接值）
  5. 错误处理（data_id 不存在）

**验收标准**:
```bash
pytest tests/langgraph_agents/test_argument_resolver.py -v
# → 5/5 测试通过
```

### 1.4 依赖安装

#### 任务 1.4.1: 更新 `requirements.txt`
- **文件**: `requirements.txt`（修改）
- **内容**: 添加 `jsonpath-ng==1.6.1`

**验收标准**:
```bash
pip install -r requirements.txt
# → jsonpath-ng 安装成功
```

### 阶段1 完成标准

- [ ] `state_v4.py` 创建完成，数据结构定义清晰
- [ ] `ToolCallV4` 扩展完成，向后兼容 V2
- [ ] `resolve_arguments()` 实现完成，支持 JSONPath
- [ ] 单元测试 100% 通过（5/5）
- [ ] 现有测试不受影响（V2 兼容）
- [ ] `jsonpath-ng` 添加到依赖

---

## 阶段2: V4.1 扇出并行执行（2天）

**目标**: 支持 `map_over_arg` 批量并行执行，防止部分失败污染结果

**状态**: ⏳ 待开始
**预计时间**: 2 天（2025-01-15 ~ 2025-01-16）
**优先级**: P0（核心功能）

### 2.1 扇出结果数据结构

#### 任务 2.1.1: 定义 `MappedTaskResult` 和 `MappedExecutionReport`
- **文件**: `langgraph_agents/state_v4.py`（修改）
- **依赖**: 阶段1 完成
- **内容**:
  - `MappedTaskResult` 类（单项结果：status + input_item + output/error）
  - `MappedExecutionReport` 类（批处理报告：overall_status + results）
  - 添加 `successful_outputs` 和 `failed_items` 属性方法

**验收标准**:
```python
report = MappedExecutionReport(
    overall_status="PARTIAL_SUCCESS",
    results=[
        MappedTaskResult(status="success", input_item="u1", output={...}),
        MappedTaskResult(status="error", input_item="u2", error="Timeout"),
        MappedTaskResult(status="success", input_item="u3", output={...})
    ]
)

# 轻松获取成功数据
success_data = report.successful_outputs  # → 2 个
failed_items = report.failed_items  # → ["u2"]
```

### 2.2 扇出执行器实现

#### 任务 2.2.1: 创建 `fanout_executor.py`
- **文件**: `langgraph_agents/utils/fanout_executor.py`（新建）
- **依赖**: 任务 2.1.1、阶段1 完成
- **内容**:
  - `execute_fanout()` 异步函数
  - 并行执行（使用 `asyncio.gather`）
  - 并发限制（`asyncio.Semaphore(10)`）
  - 错误隔离（单项失败不影响其他）

**技术细节**:
- 每个子任务独立捕获异常
- 使用 `Semaphore` 控制最大并发数（默认 10）
- 返回 `MappedExecutionReport`（结构化）

**验收标准**:
```python
# 并行执行 100 个任务
report = await execute_fanout(
    plugin_id="fetch_videos",
    items=["uid1", "uid2", ..., "uid100"],
    param_name="uid",
    base_args={"limit": 3},
    runtime=runtime
)

# 即使部分失败，也能获取成功结果
assert len(report.successful_outputs) >= 90
assert report.overall_status == "PARTIAL_SUCCESS"
```

### 2.3 改造 ToolExecutor 节点

#### 任务 2.3.1: 修改 `tool_executor.py` 支持扇出
- **文件**: `langgraph_agents/agents/tool_executor.py`（修改）
- **依赖**: 任务 2.2.1
- **内容**:
  - 检查 `ToolCallV4.map_over_arg`
  - 如果设置，调用 `execute_fanout()`
  - 否则，保持原 V2 逻辑不变

**伪代码**:
```python
async def execute_tool(call: ToolCallV4, runtime):
    # 1. 解析参数（阶段1 的能力）
    resolved_args = resolve_arguments(call.args, runtime.get_stash_dict())

    # 2. 检查是否为扇出任务
    if call.map_over_arg:
        list_arg = resolved_args.get(call.map_over_arg)
        if not isinstance(list_arg, list):
            return error_result("map_over_arg 必须是列表")

        # 3. 扇出并行执行
        report = await execute_fanout(
            plugin_id=call.plugin_id,
            items=list_arg,
            param_name=call.map_over_arg,
            base_args={k: v for k, v in resolved_args.items() if k != call.map_over_arg},
            runtime=runtime
        )

        return ToolExecutionPayload(
            call=call,
            raw_output=report,  # MappedExecutionReport
            status="success"
        )
    else:
        # 4. 普通执行（V2 逻辑）
        ...
```

**验收标准**:
- [ ] 扇出任务正确执行（并行调用）
- [ ] 普通任务不受影响（V2 兼容）
- [ ] 部分失败时返回结构化报告

### 2.4 改造 DataStasher 节点

#### 任务 2.4.1: 修改 `data_stasher.py` 支持扇出结果
- **文件**: `langgraph_agents/agents/data_stasher.py`（修改）
- **依赖**: 任务 2.1.1
- **内容**:
  - 检测 `raw_output` 是否为 `MappedExecutionReport`
  - 如果是，生成特殊的摘要（包含成功率统计）
  - 存储到 `InMemoryResearchDataStore`

**伪代码**:
```python
def store_result(result: ToolExecutionPayload, runtime):
    if isinstance(result.raw_output, MappedExecutionReport):
        # 扇出结果
        report = result.raw_output

        # 存储到外部存储
        data_id = runtime.data_store.store(result.call.call_id, report)

        # 生成摘要（关键：包含成功率）
        summary = (
            f"{result.call.human_readable_label}: "
            f"{len(report.successful_outputs)}/{len(report.results)} 成功"
        )

        return DataReference(
            step_id=result.call.step_id or 0,
            tool_name=result.call.plugin_id,
            data_id=data_id,
            summary=summary,
            status="success" if report.overall_status != "ALL_FAILURE" else "error"
        )
    else:
        # 普通结果（V2 逻辑）
        ...
```

**验收标准**:
- [ ] 扇出结果正确存储
- [ ] 摘要包含成功率统计（如"2/3 成功"）
- [ ] 普通结果不受影响

### 2.5 测试用例编写

#### 任务 2.5.1: 编写扇出执行器单元测试
- **文件**: `tests/langgraph_agents/test_fanout_executor.py`（新建）
- **测试场景**:
  1. 全部成功（100 个任务）
  2. 部分失败（3 个任务，1 个失败）
  3. 全部失败
  4. 并发限制（验证 Semaphore）

**验收标准**:
```bash
pytest tests/langgraph_agents/test_fanout_executor.py -v
# → 4/4 测试通过
```

#### 任务 2.5.2: 编写集成测试
- **文件**: `tests/langgraph_agents/test_integration_fanout.py`（新建）
- **测试场景**:
  - 端到端测试：用户查询 → Discovery → Planning → Fanout Execution → Synthesis

**验收标准**:
```bash
pytest tests/langgraph_agents/test_integration_fanout.py -v
# → 集成测试通过
```

### 阶段2 完成标准

- [ ] `MappedExecutionReport` 数据结构定义完成
- [ ] `execute_fanout()` 实现完成，支持并发限制
- [ ] `tool_executor.py` 改造完成，支持扇出
- [ ] `data_stasher.py` 改造完成，支持扇出结果
- [ ] 单元测试 100% 通过（4/4）
- [ ] 集成测试通过（端到端）
- [ ] 性能测试验证（并发执行比顺序快 5 倍+）

---

## 阶段3: V4.4 前置语义 + GraphRenderer（1天）

**目标**: 添加人类可读标签，实现程序化 RAG 图生成（零上下文溢出）

**状态**: ⏳ 待开始
**预计时间**: 1 天（2025-01-17）
**优先级**: P1（用户体验）

### 3.1 修改 Planner Prompt

#### 任务 3.1.1: 更新 `planner_system.txt`
- **文件**: `langgraph_agents/prompts/planner_system.txt`（修改）
- **依赖**: 阶段1、阶段2 完成
- **内容**:
  - 要求 Planner 输出 `call_id`（任务唯一标识）
  - 要求 Planner 输出 `human_readable_label`（人类可读描述）
  - 示例：`"call_id": "A", "human_readable_label": "获取科技美学的 UID"`

**验收标准**:
```python
# Planner 输出示例（JSON）
{
    "call_id": "A",
    "plugin_id": "resolve_entity",
    "args": {"name": {"value": "科技美学"}},
    "human_readable_label": "解析'科技美学'的 UID"
}
```

### 3.2 实现 GraphRenderer

#### 任务 3.2.1: 创建 `graph_renderer.py`
- **文件**: `langgraph_agents/utils/graph_renderer.py`（新建）
- **依赖**: 阶段1、阶段2 完成
- **内容**:
  - `render_rag_graph()` 函数（100% 纯代码，无 LLM）
  - 从 `execution_graph` 提取节点（id + label + status）
  - 从 `execution_graph` 的 `args` 提取边（依赖关系）

**技术细节**:
- 节点状态：从 `data_stash` 获取（PENDING / SUCCESS / PARTIAL_SUCCESS / ERROR）
- 边：解析 `StashReference` 自动生成依赖边
- 返回标准 JSON 格式（便于前端渲染）

**伪代码**:
```python
def render_rag_graph(state: GraphStateV4) -> Dict[str, Any]:
    execution_graph = state.get("execution_graph", [])
    data_stash_dict = _build_stash_dict(state.get("data_stash", []))

    nodes = []
    edges = []

    for task in execution_graph:
        # 节点
        call_id = task.call_id
        label = task.human_readable_label

        # 从 data_stash 获取状态
        ref = data_stash_dict.get(call_id)
        status = ref.status.upper() if ref else "PENDING"
        summary = ref.summary if ref else ""

        nodes.append({
            "id": call_id,
            "label": label,
            "status": status,
            "summary": summary
        })

        # 边（从 args 中提取 StashReference）
        for arg_name, arg_value in task.args.items():
            if isinstance(arg_value, StashReference):
                edges.append({
                    "from": arg_value.data_id,
                    "to": call_id,
                    "label": f"提供 {arg_name}"
                })

    return {"nodes": nodes, "edges": edges}
```

**验收标准**:
```python
graph = render_rag_graph(state)
# 返回:
{
    "nodes": [
        {"id": "A", "label": "获取关注列表", "status": "SUCCESS", "summary": "..."},
        {"id": "B", "label": "批量获取视频", "status": "PARTIAL_SUCCESS", "summary": "2/3 成功"}
    ],
    "edges": [
        {"from": "A", "to": "B", "label": "提供 uid"}
    ]
}
```

### 3.3 后端 API 端点

#### 任务 3.3.1: 创建 `research_graph.py` 控制器
- **文件**: `api/controllers/research_graph.py`（新建）
- **依赖**: 任务 3.2.1
- **内容**:
  - `GET /research/{task_id}/graph` 端点
  - 从 TaskHub 获取任务状态
  - 调用 `render_rag_graph()`
  - 返回 JSON

**技术细节**:
- 与现有 `/research/stream` 端点配合使用
- 支持轮询（前端每 5 秒刷新一次）

**验收标准**:
```bash
curl http://localhost:8000/api/research/task_123/graph
# 返回:
{
    "nodes": [...],
    "edges": [...]
}
```

#### 任务 3.3.2: 注册路由到 FastAPI
- **文件**: `api/main.py`（修改）
- **内容**: 添加 `research_graph` router

### 3.4 测试用例编写

#### 任务 3.4.1: 编写 GraphRenderer 单元测试
- **文件**: `tests/langgraph_agents/test_graph_renderer.py`（新建）
- **测试场景**:
  1. 空图谱（无节点）
  2. 单节点（无依赖）
  3. 两节点依赖（A → B）
  4. 扇出节点状态（PARTIAL_SUCCESS）

**验收标准**:
```bash
pytest tests/langgraph_agents/test_graph_renderer.py -v
# → 4/4 测试通过
```

### 阶段3 完成标准

- [ ] Planner Prompt 更新完成，输出 `human_readable_label`
- [ ] `render_rag_graph()` 实现完成（纯代码，无 LLM）
- [ ] API 端点 `/research/{task_id}/graph` 创建完成
- [ ] 单元测试 100% 通过（4/4）
- [ ] API 端点可正常访问

---

## 阶段4: V4.2 RSSHub 路由发现（2天）

**目标**: 让 RAG 检索成为显式步骤，支持多候选路由智能选择

**状态**: ⏳ 待开始
**预计时间**: 2 天（2025-01-18 ~ 2025-01-19）
**优先级**: P0（核心价值）

### 4.1 注册路由检索工具

#### 任务 4.1.1: 创建 `route_discovery.py`
- **文件**: `langgraph_agents/tools/route_discovery.py`（新建）
- **依赖**: 现有 `rag_system/retriever.py`
- **内容**:
  - `search_rsshub_routes()` 函数
  - 调用现有 `RAGRetriever`
  - 返回候选路由列表（route_id + path_template + score + description）

**技术细节**:
- 复用现有 RAG 系统（`rag_system/retriever.py`）
- 格式化输出（统一数据结构）
- 默认返回 top_k=5 个候选

**伪代码**:
```python
from rag_system.retriever import RAGRetriever

@register_tool("search_rsshub_routes")
def search_rsshub_routes(query: str, top_k: int = 5) -> Dict[str, Any]:
    """
    通过 RAG 检索 RSSHub 路由库

    Args:
        query: 自然语言查询（如"B站用户视频"）
        top_k: 返回候选数量

    Returns:
        候选路由列表
    """
    retriever = RAGRetriever()
    results = retriever.retrieve(query, top_k=top_k)

    candidates = []
    for result in results:
        candidates.append({
            "route_id": result.route_id,
            "path_template": result.path,
            "description": result.description,
            "score": result.score,
            "required_params": result.params  # 如 ["uid"]
        })

    return {
        "query": query,
        "candidates": candidates,
        "total": len(candidates)
    }
```

**验收标准**:
```python
result = search_rsshub_routes("B站用户视频")
# 返回:
{
    "query": "B站用户视频",
    "candidates": [
        {"route_id": "bilibili_user_video", "score": 0.95, ...},
        {"route_id": "bilibili_followings_video", "score": 0.87, ...},
        {"route_id": "bilibili_user_dynamic", "score": 0.75, ...}
    ],
    "total": 3
}
```

#### 任务 4.1.2: 注册工具到 ToolRegistry
- **文件**: `langgraph_agents/tools/registry.py`（修改）
- **内容**: 添加 `search_rsshub_routes` 到工具注册表

### 4.2 修改 Planner 支持 Discovery

#### 任务 4.2.1: 实现 Discovery 逻辑
- **文件**: `langgraph_agents/agents/planner.py`（修改）
- **依赖**: 任务 4.1.1
- **内容**:
  - `_should_discover_routes()` 函数（判断是否需要 Discovery）
  - `_extract_rag_query()` 函数（从用户查询提取 RAG 关键词）
  - 首次规划时自动生成 Discovery 任务

**技术细节**:
- 启发式判断：查询包含"B站/知乎/GitHub"等关键词 → 需要 Discovery
- 如果 `data_stash` 中已有 `search_rsshub_routes` 结果 → 跳过 Discovery

**伪代码**:
```python
def create_planner_node_v4_2(runtime):
    def node(state: GraphStateV4):
        # 1. 检查是否需要 Discovery
        if _should_discover_routes(state):
            query = _extract_rag_query(state["original_query"])

            discovery = ToolCallV4(
                call_id="DISCOVER_ROUTES",
                plugin_id="search_rsshub_routes",
                args={"query": StaticValue(value=query)},
                human_readable_label=f"侦察 RSSHub 路由: {query}"
            )

            return {"execution_graph": [discovery]}

        # 2. 如果已有候选路由，进行智能选择
        route_discovery = _get_route_discovery(state)
        if route_discovery:
            candidates = runtime.data_store.get(route_discovery.data_id)

            # LLM 智能选择最合适的路由
            selected = _select_best_route(
                candidates["candidates"],
                state["original_query"]
            )

            # 生成执行计划
            execution_graph = _build_execution_graph(selected, state)
            return {"execution_graph": execution_graph}

        # 3. 正常规划逻辑（V2）
        ...

    return node
```

**验收标准**:
- [ ] 首次规划自动生成 Discovery 任务
- [ ] Discovery 完成后，Planner 看到候选路由列表

### 4.3 实现多候选智能选择

#### 任务 4.3.1: 创建 `route_selector.py`
- **文件**: `langgraph_agents/utils/route_selector.py`（新建）
- **依赖**: 任务 4.2.1
- **内容**:
  - `_select_best_route()` 函数
  - 策略1：只有一个候选 → 直接返回
  - 策略2：高分候选（score > 0.9）→ 直接返回
  - 策略3：让 LLM 从多个候选中选择

**技术细节**:
- 使用现有 LLM Client（`runtime.llm_client`）
- Prompt 设计：展示所有候选，要求返回 JSON（selected_index + reasoning）

**伪代码**:
```python
def _select_best_route(candidates: List[Dict], query: str):
    # 策略1
    if len(candidates) == 1:
        return candidates[0]

    # 策略2
    if candidates[0]["score"] > 0.9:
        return candidates[0]

    # 策略3: LLM 决策
    prompt = f"""
    用户查询: {query}

    RAG 检索到以下候选路由:
    {json.dumps(candidates, indent=2, ensure_ascii=False)}

    请选择最合适的路由，返回 JSON:
    {{
        "selected_index": 0,
        "reasoning": "..."
    }}
    """

    response = llm_client.chat([{"role": "user", "content": prompt}])
    decision = json.loads(response)

    return candidates[decision["selected_index"]]
```

**验收标准**:
```python
candidates = [
    {"route_id": "bilibili_user_video", "score": 0.85, ...},
    {"route_id": "bilibili_followings_video", "score": 0.82, ...}
]

selected = _select_best_route(candidates, "获取科技美学的最新视频")
# → LLM 选择 bilibili_user_video
```

### 4.4 实现 Reflector 备选重试

#### 任务 4.4.1: 修改 `reflector.py` 支持备选路由
- **文件**: `langgraph_agents/agents/reflector.py`（修改）
- **依赖**: 任务 4.3.1
- **内容**:
  - `_should_retry_with_alternative()` 函数
  - 检查是否有备选路由
  - 生成重试任务（使用第 2 个候选路由）

**技术细节**:
- 只在执行失败 + 还有备选路由时触发
- 重试任务的 `call_id` 应与原任务不同（如 `B_RETRY`）

**伪代码**:
```python
def _should_retry_with_alternative(state: GraphStateV4):
    # 1. 获取路由发现结果
    route_discovery = _get_route_discovery(state)
    if not route_discovery:
        return False

    candidates = route_discovery["candidates"]
    if len(candidates) <= 1:
        return False

    # 2. 检查上次执行是否失败
    last_execution = state["data_stash"][-1]
    if last_execution.status == "success":
        return False

    return True

# 在 Reflector 中使用
if _should_retry_with_alternative(state):
    # 生成重试任务（使用第 2 个候选路由）
    retry_task = _build_retry_task(state, alternative_index=1)
    return {
        "reflection": Reflection(decision="CONTINUE", reasoning="尝试备选路由"),
        "execution_graph": [retry_task]
    }
```

**验收标准**:
- [ ] 第一个路由失败时，自动尝试第二个
- [ ] 备选路由用完后，返回 FINISH

### 4.5 测试用例编写

#### 任务 4.5.1: 编写路由发现单元测试
- **文件**: `tests/langgraph_agents/test_route_discovery.py`（新建）
- **测试场景**:
  1. RAG 检索返回多个候选
  2. 智能选择（高分直接返回）
  3. 智能选择（LLM 决策）
  4. 备选路由重试

**验收标准**:
```bash
pytest tests/langgraph_agents/test_route_discovery.py -v
# → 4/4 测试通过
```

#### 任务 4.5.2: 编写端到端集成测试
- **文件**: `tests/langgraph_agents/test_e2e_discovery.py`（新建）
- **测试场景**:
  - 用户查询 → Discovery → Planning（选择路由）→ Execution → Synthesis

**验收标准**:
```bash
pytest tests/langgraph_agents/test_e2e_discovery.py -v
# → 端到端测试通过
```

### 阶段4 完成标准

- [ ] `search_rsshub_routes` 工具注册完成
- [ ] Planner 支持 Discovery 阶段
- [ ] 多候选路由智能选择实现
- [ ] Reflector 支持备选路由重试
- [ ] 单元测试 100% 通过（4/4）
- [ ] 端到端测试通过

---

## 阶段5: 前端可视化 + 测试优化（1天）

**目标**: 前端 RAG 图谱可视化，全面测试验证

**状态**: ⏳ 待开始
**预计时间**: 1 天（2025-01-20）
**优先级**: P1（用户体验 + 质量保证）

### 5.1 前端 RAG 图谱可视化

#### 任务 5.1.1: 创建 `ResearchGraphPanel.vue`
- **文件**: `frontend/src/features/research/components/ResearchGraphPanel.vue`（新建）
- **依赖**: 阶段3 完成（API 端点已就绪）
- **内容**:
  - 使用 D3.js 或 Cytoscape.js 渲染图谱
  - 支持节点状态可视化（PENDING/SUCCESS/ERROR）
  - 支持依赖边展示
  - 自动刷新（每 5 秒轮询一次）

**技术细节**:
- 与现有 `ResearchView.vue` 集成
- 使用 shadcn-vue 组件（Card 容器）
- 响应式布局（适配不同屏幕）

**验收标准**:
```vue
<!-- 在 ResearchView.vue 中使用 -->
<template>
  <div class="research-view">
    <ResearchContextPanel />
    <ResearchGraphPanel :taskId="taskId" />  <!-- 新增 -->
    <ResearchDataPanel />
  </div>
</template>
```

#### 任务 5.1.2: 集成到研究视图
- **文件**: `frontend/src/views/ResearchView.vue`（修改）
- **内容**: 添加 `ResearchGraphPanel` 组件

### 5.2 全面测试验证

#### 任务 5.2.1: 运行完整测试套件
- **命令**: `pytest tests/langgraph_agents/ -v --cov=langgraph_agents`
- **目标**: 覆盖率 ≥ 80%

**验收标准**:
```bash
# 预期结果
tests/langgraph_agents/test_argument_resolver.py ........  5 passed
tests/langgraph_agents/test_fanout_executor.py .........  4 passed
tests/langgraph_agents/test_graph_renderer.py ..........  4 passed
tests/langgraph_agents/test_route_discovery.py .........  4 passed
tests/langgraph_agents/test_integration_fanout.py ......  1 passed
tests/langgraph_agents/test_e2e_discovery.py ...........  1 passed
-----------------------------------------------------------
Total: 19 passed

Coverage: 82%
```

#### 任务 5.2.2: 性能测试
- **文件**: `tests/langgraph_agents/test_performance.py`（新建）
- **测试场景**:
  1. 扇出并发性能（100 个任务）
  2. GraphRenderer 性能（无 LLM 调用）

**验收标准**:
- [ ] 扇出并发比顺序快 5 倍以上
- [ ] GraphRenderer 执行时间 < 100ms

#### 任务 5.2.3: 端到端手动测试
- **测试场景**:
  1. 简单查询："我想看看 GitHub 今日热门项目"
  2. 复杂查询："获取我所有关注的 B 站 UP 主的最新视频"
  3. 部分失败："获取 3 个 UP 主的视频（其中 1 个失败）"

**验收标准**:
- [ ] 所有场景正常工作
- [ ] RAG 图谱正确展示
- [ ] 部分失败不影响成功项

### 5.3 文档更新

#### 任务 5.3.1: 更新 `.agentdocs/index.md`
- **文件**: `.agentdocs/index.md`（修改）
- **内容**:
  - 将 `langgraph-v4.4-architecture-design.md` 状态改为"已实施"
  - 添加 V4.4 架构关键记忆

#### 任务 5.3.2: 归档任务文档
- **操作**:
  - 更新本文档的完成状态
  - 移动到 `.agentdocs/workflow/done/`（如果全部完成）

### 阶段5 完成标准

- [ ] 前端 RAG 图谱可视化完成
- [ ] 完整测试套件通过（19/19）
- [ ] 覆盖率 ≥ 80%
- [ ] 性能测试验证通过
- [ ] 端到端手动测试通过
- [ ] 文档更新完成

---

## 进度跟踪

### 总体进度

```
阶段0: 设计评审        ✅ 完成 (2025-01-13)
阶段1: 显式依赖解析    ⏳ 待开始 (预计 2025-01-14)
阶段2: 扇出并行执行    ⏳ 待开始 (预计 2025-01-15 ~ 2025-01-16)
阶段3: 前置语义+图谱   ⏳ 待开始 (预计 2025-01-17)
阶段4: 路由发现        ⏳ 待开始 (预计 2025-01-18 ~ 2025-01-19)
阶段5: 可视化+测试     ⏳ 待开始 (预计 2025-01-20)
------------------------------------------------
总体进度: 0/5 阶段完成 (0%)
预计完成: 2025-01-20
```

### 详细任务清单

#### 阶段1 任务（0/6 完成）
- [ ] 1.1.1: 创建 `state_v4.py`（StaticValue + StashReference）
- [ ] 1.1.2: 扩展 `ToolCall` 为 `ToolCallV4`
- [ ] 1.2.1: 实现 `argument_resolver.py`
- [ ] 1.3.1: 编写单元测试（5 个测试用例）
- [ ] 1.4.1: 更新 `requirements.txt`（添加 jsonpath-ng）
- [ ] 阶段1 验收：所有测试通过，现有功能不受影响

#### 阶段2 任务（0/8 完成）
- [ ] 2.1.1: 定义 `MappedTaskResult` 和 `MappedExecutionReport`
- [ ] 2.2.1: 创建 `fanout_executor.py`
- [ ] 2.3.1: 修改 `tool_executor.py` 支持扇出
- [ ] 2.4.1: 修改 `data_stasher.py` 支持扇出结果
- [ ] 2.5.1: 编写扇出单元测试（4 个测试用例）
- [ ] 2.5.2: 编写集成测试
- [ ] 性能测试：验证并发效果（快 5 倍+）
- [ ] 阶段2 验收：扇出功能完整可用

#### 阶段3 任务（0/5 完成）
- [ ] 3.1.1: 更新 `planner_system.txt`（要求输出 human_readable_label）
- [ ] 3.2.1: 创建 `graph_renderer.py`
- [ ] 3.3.1: 创建 `research_graph.py` API 端点
- [ ] 3.3.2: 注册路由到 FastAPI
- [ ] 3.4.1: 编写 GraphRenderer 单元测试（4 个测试用例）
- [ ] 阶段3 验收：API 端点可正常访问，返回正确 JSON

#### 阶段4 任务（0/8 完成）
- [ ] 4.1.1: 创建 `route_discovery.py`（search_rsshub_routes 工具）
- [ ] 4.1.2: 注册工具到 ToolRegistry
- [ ] 4.2.1: 修改 `planner.py` 支持 Discovery
- [ ] 4.3.1: 创建 `route_selector.py`（智能选择）
- [ ] 4.4.1: 修改 `reflector.py` 支持备选重试
- [ ] 4.5.1: 编写路由发现单元测试（4 个测试用例）
- [ ] 4.5.2: 编写端到端集成测试
- [ ] 阶段4 验收：Discovery → Planning → Execution 全流程通过

#### 阶段5 任务（0/7 完成）
- [ ] 5.1.1: 创建 `ResearchGraphPanel.vue`
- [ ] 5.1.2: 集成到 `ResearchView.vue`
- [ ] 5.2.1: 运行完整测试套件（覆盖率 ≥ 80%）
- [ ] 5.2.2: 性能测试
- [ ] 5.2.3: 端到端手动测试（3 个场景）
- [ ] 5.3.1: 更新 `.agentdocs/index.md`
- [ ] 5.3.2: 归档任务文档

---

## 风险管理

### 已识别风险

| 风险 | 影响 | 概率 | 缓解措施 | 状态 |
|------|------|------|---------|------|
| **JSONPath 库不兼容** | 中 | 低 | 充分测试，准备替代方案 | ⏳ 待验证 |
| **扇出并发性能不达标** | 高 | 低 | 使用 Semaphore 限流，性能测试验证 | ⏳ 待验证 |
| **RAG 检索不准确** | 中 | 中 | 让 LLM 智能选择，支持备选重试 | ⏳ 待验证 |
| **前端图谱渲染性能** | 低 | 低 | 限制节点数量，使用轻量级库 | ⏳ 待验证 |
| **工作量超预期** | 中 | 中 | 按阶段交付，可灵活调整范围 | ⏳ 持续监控 |

### 应急预案

**如果阶段2扇出功能遇到技术难题**：
- 备选方案：先实施阶段3、阶段4，回头再优化扇出
- 影响：V4.1 功能延后，不影响其他阶段

**如果前端可视化时间不足**：
- 备选方案：先提供 API 端点，前端可视化作为可选项
- 影响：用户体验下降，但核心功能不受影响

---

## 质量标准

### 代码质量

- [ ] 所有新增代码符合 CLAUDE.md 规范
- [ ] 单个文件不超过 1000 行
- [ ] 所有公共函数有文档字符串（中文）
- [ ] 类型注解覆盖率 ≥ 90%

### 测试覆盖

- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 所有新功能有对应测试用例
- [ ] 集成测试覆盖核心流程
- [ ] 性能测试验证关键指标

### 向后兼容

- [ ] 现有 V2 测试 100% 通过
- [ ] 现有 API 不受影响
- [ ] 提供兼容模式（V2 和 V4 可共存）

---

## 完成标准

### 功能完整性

- [ ] V4.0 显式依赖解析完整可用
- [ ] V4.1 扇出并行执行完整可用
- [ ] V4.2 RSSHub 路由发现完整可用
- [ ] V4.4 GraphRenderer 完整可用
- [ ] 前端 RAG 图谱可视化完整可用

### 性能指标

- [ ] 扇出并发比顺序执行快 5 倍以上
- [ ] GraphRenderer 执行时间 < 100ms（零 LLM 调用）
- [ ] RAG 检索响应时间 < 2 秒

### 用户体验

- [ ] 用户可以看到清晰的 RAG 执行图谱
- [ ] 部分失败不影响成功项
- [ ] 失败时自动尝试备选路由

---

## 关键决策记录

### 决策1: 采用渐进式集成策略
- **时间**: 2025-01-13
- **决策**: 保持 V2 和 V4 兼容模式，逐步迁移
- **理由**: 降低风险，确保现有功能不受影响

### 决策2: 实施完整 V4.4（包含 V4.2）
- **时间**: 2025-01-13
- **决策**: 实施所有 5 个阶段，包括路由发现
- **理由**: V4.2 是核心价值，用户批准完整方案

### 决策3: 前端可视化使用 D3.js
- **时间**: 待定（阶段5）
- **决策**: 待评估（D3.js vs Cytoscape.js）
- **理由**: 需要验证性能和易用性

---

## 参考资料

### 设计文档
- `.agentdocs/langgraph-v4.4-architecture-design.md` - 完整架构设计
- `docs/langgraph-agents-design.md` - V2 架构参考

### 现有代码
- `langgraph_agents/` - 现有代理实现
- `rag_system/` - RAG 检索系统
- `services/` - 服务层架构

### 测试参考
- `tests/langgraph_agents/` - 现有测试用例
- `.agentdocs/workflow/251111-langgraph-agents-refactor.md` - 测试策略参考

---

## 下一步行动

### 立即开始（阶段1）

1. **创建 `state_v4.py`**
   ```bash
   touch langgraph_agents/state_v4.py
   ```

2. **安装依赖**
   ```bash
   echo "jsonpath-ng==1.6.1" >> requirements.txt
   pip install -r requirements.txt
   ```

3. **开始编写代码**
   - 按照任务 1.1.1 的验收标准实施

---

**文档版本**: V1.0
**创建时间**: 2025-01-13
**最后更新**: 2025-01-13
**维护者**: AI Agent
**状态**: ✅ 已批准，待开始实施
