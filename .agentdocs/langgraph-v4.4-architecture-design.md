# LangGraph V4.4 架构设计方案

## 文档概述

**版本**: V4.4
**创建时间**: 2025-01-13
**状态**: 设计方案
**目标**: 将外部 AI 提出的 V4.4 架构改进与当前 V2 系统集成

---

## 1. 背景与动机

### 1.1 当前架构（V2 动态自适应方案）

项目目前实现了基于 **ReAct 风格**的 V2 动态自适应架构：

**核心思想**：规划一小步 → 执行 → 观察与反思 → 再规划下一步

**代理团队**：
```
RouterAgent → PlannerAgent → ToolExecutor → DataStasher → ReflectorAgent → SynthesizerAgent
```

**关键数据结构**：
- `GraphState`: 轻量级状态容器（只存元数据）
- `ToolCall`: 单步工具调用计划
- `DataReference`: 指向外部存储的数据引用
- `Reflection`: 反思决策结果

**已完成修复**（2025-01-11）：
- ✅ P0: 工具注册、类型安全、测试覆盖
- ✅ P1: LLM重试、JSON解析、异常处理
- ✅ P2: 快速路由、配置管理、内存清理

### 1.2 V4.4 架构的核心改进

V4.4 方案提出了四个关键创新：

| 版本 | 核心特性 | 解决的问题 |
|------|---------|-----------|
| **V4.0** | 显式依赖解析（StashReference + JSONPath） | 隐式依赖导致的调试困难 |
| **V4.1** | 扇出防爆（MappedExecutionReport） | 批处理中部分失败污染整体结果 |
| **V4.2** | 迭代式图景拼合（Discovery → Planning） | "战争迷雾"问题（工具 Schema 未知） |
| **V4.4** | 前置语义 + 零溢出（GraphRenderer） | 上下文溢出、可视化不透明 |

**架构理念**：
- **规划域（LLM驱动）** 和 **执行域（Code驱动）** 完全分离
- **认知飞轮**：Planner ↔ Graph Engine ↔ DataStasher ↔ Reflector

---

## 2. V2 vs V4.4 架构对比

### 2.1 核心差异对照表

| 维度 | V2 当前方案 | V4.4 提议方案 | 集成策略 |
|------|------------|--------------|---------|
| **依赖管理** | 隐式（args 中传 data_id） | 显式（StashReference + json_path） | ✅ **增量集成** |
| **扇出处理** | ❌ 未实现 | ✅ map_over_arg + 并行执行 | ✅ **全新功能** |
| **错误处理** | 简单 success/error | 结构化 MappedExecutionReport | ✅ **增量集成** |
| **工具发现** | 直接调用 | Discovery → Planning → Refinement | ⚠️ **需评估** |
| **图谱生成** | 可能有 LLM 参与 | 纯代码 GraphRenderer | ✅ **全新功能** |
| **语义标签** | ❌ 缺少 | human_readable_label | ✅ **轻松添加** |
| **上下文管理** | 已优化（DataReference） | 进一步强化（摘要 + GraphRenderer） | ✅ **增量改进** |

### 2.2 架构兼容性分析

**高度兼容的部分**（可直接集成）：
1. ✅ **显式依赖解析**：V2 的 `args: Dict[str, Any]` 完全可以扩展为 `ArgumentValue`
2. ✅ **扇出机制**：V2 的 `ToolCall` 添加 `map_over_arg` 字段即可
3. ✅ **语义标签**：V2 的 `ToolCall.description` 重命名为 `human_readable_label`
4. ✅ **GraphRenderer**：与现有架构正交，可独立添加

**需要评估的部分**（可能冲突）：
1. ⚠️ **工具发现机制**：V2 已有工具注册表，V4.4 的 Discovery 阶段是否必要？
2. ⚠️ **执行引擎**：V2 的 `ToolExecutor` 是否需要重构为 `Graph Engine`？

---

## 3. V4.4 核心数据结构设计

### 3.1 参数源（Argument Source）

```python
# file: langgraph_agents/state_v4.py

from pydantic import BaseModel, Field
from typing import Any, Union

class StaticValue(BaseModel):
    """静态值（硬编码）"""
    value: Any

class StashReference(BaseModel):
    """动态引用（指向 DataStash 中的某个结果）"""
    data_id: str  # 引用的任务 ID（如 "A"）
    json_path: str = Field(
        default="$",
        description="JSONPath 表达式，从结果中提取特定部分"
    )
    # 示例：
    # {"data_id": "A", "json_path": "$.items[*].uid"}
    # 从任务 A 的结果中提取所有 uid 字段

ArgumentValue = Union[StaticValue, StashReference]
```

**关键优势**：
- 显式依赖关系，易于调试
- 支持 JSONPath 精确提取数据
- 与 V2 的 `args: Dict[str, Any]` 兼容（逐步迁移）

### 3.2 工具调用（V4.4 版本）

```python
class ToolCallV4_4(BaseModel):
    """V4.4 工具调用计划（扩展自 V2 的 ToolCall）"""

    call_id: str = Field(..., description="任务唯一标识（如 'A', 'B'）")
    plugin_id: str = Field(..., description="注册的工具 ID")

    # V4.0: 显式依赖
    args: Dict[str, ArgumentValue] = Field(
        default_factory=dict,
        description="参数可以是静态值或动态引用"
    )

    # V4.1: 扇出支持
    map_over_arg: Optional[str] = Field(
        default=None,
        description="如果设置，将对该参数的列表项并行执行"
    )

    # V4.4: 前置语义
    human_readable_label: str = Field(
        ...,
        description="人类可读的任务描述（用于 RAG 图展示）"
    )

    # 兼容 V2（保留原字段）
    step_id: Optional[int] = Field(
        default=None,
        description="V2 兼容：步骤编号"
    )
```

**迁移路径**：
1. **阶段1**：保持 V2 的 `ToolCall` 不变，添加 `ToolCallV4_4` 作为可选替代
2. **阶段2**：在 Planner 中逐步生成 `ToolCallV4_4`
3. **阶段3**：统一为 `ToolCallV4_4`，移除 `ToolCall`

### 3.3 扇出执行结果（V4.1 防爆）

```python
class MappedTaskResult(BaseModel):
    """扇出任务中单个项的执行结果"""

    status: Literal["success", "error"]
    input_item: Any = Field(
        ...,
        description="映射的输入项（如 uid_B）"
    )
    output: Optional[Any] = None  # 成功时的结果
    error: Optional[str] = None  # 失败时的错误信息

class MappedExecutionReport(BaseModel):
    """扇出任务的结构化批处理报告"""

    overall_status: Literal["ALL_SUCCESS", "PARTIAL_SUCCESS", "ALL_FAILURE"]
    results: List[MappedTaskResult]

    @property
    def successful_outputs(self) -> List[Any]:
        """供 Synthesizer 轻松获取所有成功数据"""
        return [r.output for r in self.results if r.status == "success"]

    @property
    def failed_items(self) -> List[Any]:
        """供 Reflector 决策是否重试"""
        return [r.input_item for r in self.results if r.status == "error"]
```

**关键价值**：
- **防止部分失败污染整体结果**：不再返回 `[result_A, Exception_B, result_C]`
- **结构化错误信息**：Reflector 可以智能决策（重试失败项 vs 忽略）
- **向后兼容**：普通任务仍返回 `Any`，只有扇出任务返回 `MappedExecutionReport`

### 3.4 图状态（V4.4 扩展）

```python
class GraphStateV4(TypedDict, total=False):
    """V4.4 图状态（扩展自 V2 的 GraphState）"""

    # === V2 现有字段（保持不变） ===
    original_query: Required[str]
    chat_history: List[str]
    data_stash: List[DataReference]  # V2: 元数据引用
    reflection: Optional[Reflection]
    final_report: Optional[str]
    human_in_loop_request: Optional[str]
    router_decision: Optional[RouterDecision]

    # === V4.4 新增字段 ===
    execution_graph: List[ToolCallV4_4]  # V4.4: 执行图（替代 next_tool_call）

    # V4.2: 工具发现（可选）
    discovered_tools: Optional[Dict[str, Any]]  # 工具 Schema 缓存
```

**迁移策略**：
- **阶段1**：保留 `next_tool_call`，添加 `execution_graph` 作为可选字段
- **阶段2**：Planner 同时填充两个字段（兼容模式）
- **阶段3**：移除 `next_tool_call`，只使用 `execution_graph`

---

## 4. V4.4 核心组件设计

### 4.1 Planner（规划器 - LLM）

**V2 现状**：
- 每次输出一个 `ToolCall`
- 直接调用已知工具
- 不支持依赖解析

**V4.4 改进**：
```python
def create_planner_node_v4(runtime: LangGraphRuntime):
    """V4.4 Planner 节点"""

    def node(state: GraphStateV4) -> GraphStateV4:
        # V4.2: 如果是首次规划且工具未发现，进行 Discovery
        if not state.get("discovered_tools") and not state.get("execution_graph"):
            # 生成 Discovery 任务
            discovery_call = ToolCallV4_4(
                call_id="SCHEMA_DISCOVERY",
                plugin_id="rss",  # 假设我们要发现 RSSHub 工具
                args={"action": StaticValue(value="get_schema")},
                human_readable_label="侦察 RSS 工具接口"
            )
            return {
                "execution_graph": [discovery_call]
            }

        # V4.4: 正常规划（基于已发现的工具 Schema）
        discovered = state.get("discovered_tools", {})
        data_stash = state.get("data_stash", [])

        # 构建 Prompt（包含工具 Schema 和已有数据摘要）
        prompt = _build_planner_prompt_v4(
            query=state["original_query"],
            discovered_tools=discovered,
            data_stash=data_stash,
            reflection=state.get("reflection")
        )

        # 调用 LLM
        response = runtime.llm_client.chat([{"role": "user", "content": prompt}])

        # 解析为 List[ToolCallV4_4]
        execution_graph = _parse_execution_graph(response)

        return {
            "execution_graph": execution_graph
        }

    return node
```

**关键改进**：
1. **V4.2 工具发现**：首次规划时自动侦察工具 Schema
2. **V4.0 依赖解析**：生成的 `args` 使用 `StashReference`
3. **V4.1 扇出标记**：为需要批处理的任务设置 `map_over_arg`

### 4.2 Graph Engine（执行引擎 - Code）

**V2 现状**：
- `ToolExecutor` 节点：顺序执行单个工具
- 不支持并行扇出

**V4.4 改进**：
```python
import asyncio
from typing import List, Any

def create_graph_engine_node_v4(runtime: LangGraphRuntime):
    """V4.4 Graph Engine（替代 V2 的 ToolExecutor）"""

    async def node(state: GraphStateV4) -> GraphStateV4:
        execution_graph = state.get("execution_graph", [])
        data_stash_dict = _build_stash_dict(state.get("data_stash", []))

        # 找到所有"就绪"的任务（依赖已满足）
        ready_tasks = _find_ready_tasks(execution_graph, data_stash_dict)

        if not ready_tasks:
            # 没有就绪任务，可能需要 Planner 重新规划
            return {"last_error": "No ready tasks found"}

        # 并行执行所有就绪任务
        results = await asyncio.gather(
            *[_execute_single_task(task, data_stash_dict, runtime) for task in ready_tasks],
            return_exceptions=True
        )

        # 将结果存入 DataStash（通过 DataStasher）
        # 注意：这里返回的是临时结果，DataStasher 节点会处理存储
        return {
            "pending_tool_results": results
        }

    async def _execute_single_task(
        task: ToolCallV4_4,
        stash: Dict[str, Any],
        runtime: LangGraphRuntime
    ) -> ToolExecutionPayload:
        """执行单个任务（支持扇出）"""

        # 1. 解析参数（将 StashReference 替换为实际值）
        resolved_args = _resolve_arguments(task.args, stash)

        # 2. 检查是否为扇出任务
        if task.map_over_arg:
            # V4.1: 扇出执行
            list_arg = resolved_args.get(task.map_over_arg)
            if not isinstance(list_arg, list):
                return ToolExecutionPayload(
                    call=task,
                    status="error",
                    error_message=f"map_over_arg '{task.map_over_arg}' is not a list"
                )

            # 并行执行列表中的每一项
            mapped_results = await _execute_mapped_task(
                task, list_arg, resolved_args, runtime
            )

            # 返回 MappedExecutionReport
            return ToolExecutionPayload(
                call=task,
                raw_output=mapped_results,
                status="success"
            )
        else:
            # V2: 普通执行
            result = await runtime.tool_registry.execute_async(
                task.plugin_id, resolved_args
            )
            return ToolExecutionPayload(
                call=task,
                raw_output=result,
                status="success"
            )

    async def _execute_mapped_task(
        task: ToolCallV4_4,
        items: List[Any],
        base_args: Dict[str, Any],
        runtime: LangGraphRuntime
    ) -> MappedExecutionReport:
        """V4.1: 扇出并行执行"""

        async def _run_single_item(item: Any) -> MappedTaskResult:
            try:
                # 替换扇出参数
                args = {**base_args, task.map_over_arg: item}
                output = await runtime.tool_registry.execute_async(
                    task.plugin_id, args
                )
                return MappedTaskResult(
                    status="success",
                    input_item=item,
                    output=output
                )
            except Exception as e:
                return MappedTaskResult(
                    status="error",
                    input_item=item,
                    error=str(e)
                )

        # 并行执行所有项
        results = await asyncio.gather(
            *[_run_single_item(item) for item in items]
        )

        # 统计状态
        success_count = sum(1 for r in results if r.status == "success")
        if success_count == len(results):
            overall = "ALL_SUCCESS"
        elif success_count == 0:
            overall = "ALL_FAILURE"
        else:
            overall = "PARTIAL_SUCCESS"

        return MappedExecutionReport(
            overall_status=overall,
            results=results
        )

    return node
```

**关键改进**：
1. **依赖解析**：`_resolve_arguments` 将 `StashReference` 替换为实际值
2. **扇出并行**：`map_over_arg` 触发并行执行
3. **结构化错误**：返回 `MappedExecutionReport` 而非混合列表

### 4.3 DataStasher（数据暂存 - Code）

**V2 现状**：
- 存储原始数据到外部存储
- 生成摘要（使用廉价模型）

**V4.4 改进**：
```python
def create_data_stasher_node_v4(runtime: LangGraphRuntime):
    """V4.4 DataStasher（支持 MappedExecutionReport）"""

    def node(state: GraphStateV4) -> GraphStateV4:
        results = state.get("pending_tool_results", [])
        data_stash = state.get("data_stash", [])

        for result in results:
            if isinstance(result.raw_output, MappedExecutionReport):
                # V4.1: 存储扇出结果
                data_ref = _store_mapped_result(result, runtime)
            else:
                # V2: 存储普通结果
                data_ref = _store_normal_result(result, runtime)

            data_stash.append(data_ref)

        return {
            "data_stash": data_stash,
            "pending_tool_results": []  # 清空临时结果
        }

    def _store_mapped_result(
        result: ToolExecutionPayload,
        runtime: LangGraphRuntime
    ) -> DataReference:
        """存储扇出结果（带结构化报告）"""

        report: MappedExecutionReport = result.raw_output

        # 1. 存储到外部存储
        data_id = runtime.data_store.store(result.call.call_id, report)

        # 2. 生成摘要（关键：包含成功/失败统计）
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

    return node
```

**关键改进**：
- 区分普通结果和扇出结果
- 摘要包含成功率统计（供 Reflector 决策）

### 4.4 Reflector（反思器 - LLM）

**V2 现状**：
- 决策 `CONTINUE / FINISH / REQUEST_HUMAN`
- 基于 `data_stash` 的摘要

**V4.4 改进**：
```python
def create_reflector_node_v4(runtime: LangGraphRuntime):
    """V4.4 Reflector（支持部分失败决策）"""

    def node(state: GraphStateV4) -> GraphStateV4:
        data_stash = state.get("data_stash", [])

        # 检查是否有部分失败
        partial_failures = [
            ref for ref in data_stash
            if "PARTIAL_SUCCESS" in ref.summary
        ]

        # 构建 Prompt
        prompt = _build_reflector_prompt_v4(
            query=state["original_query"],
            data_stash=data_stash,
            partial_failures=partial_failures
        )

        # 调用 LLM
        response = runtime.llm_client.chat([{"role": "user", "content": prompt}])
        reflection = _parse_reflection(response)

        # V4.4: 如果决定重试，修改 execution_graph
        if reflection.decision == "CONTINUE" and partial_failures:
            # 提取失败项，生成重试任务
            retry_tasks = _build_retry_tasks(partial_failures, runtime)
            return {
                "reflection": reflection,
                "execution_graph": retry_tasks  # 替换为重试图
            }

        return {
            "reflection": reflection
        }

    def _build_retry_tasks(
        failures: List[DataReference],
        runtime: LangGraphRuntime
    ) -> List[ToolCallV4_4]:
        """V4.1: 为失败项构建重试任务"""

        retry_tasks = []
        for ref in failures:
            # 从存储中获取 MappedExecutionReport
            report: MappedExecutionReport = runtime.data_store.get(ref.data_id)

            # 提取失败的输入项
            failed_items = report.failed_items

            # 生成新的任务（只处理失败项）
            retry_task = ToolCallV4_4(
                call_id=f"{ref.data_id}_RETRY",
                plugin_id=ref.tool_name,
                args={"items": StaticValue(value=failed_items)},
                map_over_arg="items",
                human_readable_label=f"重试失败项: {ref.tool_name}"
            )
            retry_tasks.append(retry_task)

        return retry_tasks

    return node
```

**关键改进**：
- 检测部分失败并决策是否重试
- 自动生成重试任务（只处理失败项）

### 4.5 GraphRenderer（RAG图渲染器 - Code）

**V4.4 新增组件**（100% 纯代码，无 LLM）：
```python
def render_rag_graph(state: GraphStateV4) -> Dict[str, Any]:
    """
    V4.4: 程序化生成用户 RAG 图（零上下文溢出）

    返回格式：
    {
        "nodes": [
            {"id": "A", "label": "获取关注列表", "status": "SUCCESS"},
            {"id": "B", "label": "批量获取视频", "status": "PARTIAL_SUCCESS", "summary": "2/3 成功"}
        ],
        "edges": [
            {"from": "A", "to": "B", "label": "提供 UID 列表"}
        ]
    }
    """

    execution_graph = state.get("execution_graph", [])
    data_stash_dict = _build_stash_dict(state.get("data_stash", []))

    nodes = []
    edges = []

    for task in execution_graph:
        # 1. 提取节点信息（程序化，无 LLM）
        call_id = task.call_id
        label = task.human_readable_label  # V4.4: 前置语义

        # 2. 从 data_stash 获取状态
        data_ref = data_stash_dict.get(call_id)
        if data_ref:
            status = data_ref.status.upper()
            summary = data_ref.summary
        else:
            status = "PENDING"
            summary = ""

        nodes.append({
            "id": call_id,
            "label": label,
            "status": status,
            "summary": summary
        })

        # 3. 解析依赖边（程序化）
        for arg_name, arg_value in task.args.items():
            if isinstance(arg_value, StashReference):
                edges.append({
                    "from": arg_value.data_id,
                    "to": call_id,
                    "label": f"提供 {arg_name}"
                })

    return {
        "nodes": nodes,
        "edges": edges
    }
```

**关键价值**：
- **零上下文溢出**：不调用 LLM，不消耗 Token
- **实时更新**：每次 Reflector 后都可以调用，无性能问题
- **精确可靠**：基于 `execution_graph` 和 `data_stash`，不会幻觉

---

## 5. 渐进式集成方案

### 5.1 阶段划分

| 阶段 | 目标 | 工作量 | 风险 |
|------|------|--------|------|
| **阶段0** | 设计评审与技术验证 | 0.5天 | 低 |
| **阶段1** | V4.0 显式依赖解析 | 1天 | 低 |
| **阶段2** | V4.1 扇出并行执行 | 2天 | 中 |
| **阶段3** | V4.4 前置语义 + GraphRenderer | 1天 | 低 |
| **阶段4** | V4.2 工具发现（可选） | 2天 | 高 |
| **阶段5** | 测试与优化 | 1天 | 低 |

**总工作量**：7.5 天（不含阶段4）

### 5.2 阶段0：设计评审（0.5天）

**目标**：确认 V4.4 架构是否适合当前项目

**关键问题**：
1. ❓ **工具发现（V4.2）是否必要**？
   - 当前项目已有完善的工具注册表（`ToolRegistry`）
   - RSSHub 工具 Schema 可以静态定义
   - **建议**：暂缓实施，先完成 V4.0/4.1/4.4

2. ❓ **Graph Engine 是否需要重构**？
   - 当前 `ToolExecutor` 节点已工作良好
   - Graph Engine 主要是添加并行扇出逻辑
   - **建议**：渐进式改造，不做全量重构

3. ❓ **向后兼容性如何保证**？
   - 新增 `ToolCallV4_4` 但保留 `ToolCall`
   - 新增 `GraphStateV4` 但保留 `GraphState`
   - **建议**：兼容模式运行 1-2 个版本，再统一

**输出**：
- [ ] 评审会议纪要
- [ ] 确定实施的阶段范围（是否包含阶段4）
- [ ] 更新本文档的"实施计划"部分

### 5.3 阶段1：V4.0 显式依赖解析（1天）

**目标**：支持 `StashReference` 和 JSONPath 提取

**实施步骤**：

#### 1.1 定义新数据结构
```bash
# 创建 langgraph_agents/state_v4.py
touch langgraph_agents/state_v4.py
```

```python
# file: langgraph_agents/state_v4.py
from pydantic import BaseModel, Field
from typing import Any, Union

class StaticValue(BaseModel):
    value: Any

class StashReference(BaseModel):
    data_id: str
    json_path: str = "$"

ArgumentValue = Union[StaticValue, StashReference]
```

#### 1.2 扩展 ToolCall
```python
# file: langgraph_agents/state.py（修改现有文件）

from typing import Union, Dict
from .state_v4 import ArgumentValue

class ToolCallV4(ToolCall):
    """V4.0 工具调用（兼容 V2）"""

    # 覆盖 args 类型
    args: Union[
        Dict[str, Any],  # V2 兼容
        Dict[str, ArgumentValue]  # V4.0 新格式
    ] = Field(default_factory=dict)

    # 新增字段
    call_id: Optional[str] = None  # V4.4
    human_readable_label: Optional[str] = None  # V4.4
    map_over_arg: Optional[str] = None  # V4.1
```

#### 1.3 实现参数解析器
```python
# file: langgraph_agents/utils/argument_resolver.py（新文件）

import jsonpath_ng
from typing import Any, Dict
from ..state_v4 import ArgumentValue, StaticValue, StashReference

def resolve_arguments(
    args: Dict[str, ArgumentValue],
    data_stash: Dict[str, Any]
) -> Dict[str, Any]:
    """
    解析参数（将 StashReference 替换为实际值）

    Args:
        args: 参数字典（可能包含 StashReference）
        data_stash: 数据仓库（call_id -> 数据）

    Returns:
        解析后的参数字典（只含实际值）
    """
    resolved = {}

    for key, value in args.items():
        if isinstance(value, StaticValue):
            resolved[key] = value.value
        elif isinstance(value, StashReference):
            # 从 data_stash 获取数据
            data = data_stash.get(value.data_id)
            if data is None:
                raise ValueError(f"StashReference refers to unknown data_id: {value.data_id}")

            # 使用 JSONPath 提取
            if value.json_path != "$":
                parser = jsonpath_ng.parse(value.json_path)
                matches = parser.find(data)
                resolved[key] = [m.value for m in matches]
            else:
                resolved[key] = data
        else:
            # V2 兼容：直接使用原始值
            resolved[key] = value

    return resolved
```

#### 1.4 测试用例
```python
# file: tests/langgraph_agents/test_argument_resolver.py

def test_resolve_static_value():
    args = {"limit": StaticValue(value=3)}
    resolved = resolve_arguments(args, {})
    assert resolved == {"limit": 3}

def test_resolve_stash_reference():
    args = {"uid": StashReference(data_id="A", json_path="$")}
    stash = {"A": ["uid1", "uid2"]}
    resolved = resolve_arguments(args, stash)
    assert resolved == {"uid": ["uid1", "uid2"]}

def test_resolve_jsonpath():
    args = {"uid": StashReference(data_id="A", json_path="$.items[*].uid")}
    stash = {"A": {"items": [{"uid": "u1"}, {"uid": "u2"}]}}
    resolved = resolve_arguments(args, stash)
    assert resolved == {"uid": ["u1", "u2"]}
```

**验收标准**：
- [ ] `ArgumentValue` 数据结构定义完成
- [ ] `resolve_arguments` 函数实现并测试通过
- [ ] 现有测试不受影响（V2 兼容）

### 5.4 阶段2：V4.1 扇出并行执行（2天）

**目标**：支持 `map_over_arg` 批量并行执行

**实施步骤**：

#### 2.1 定义扇出结果结构
```python
# file: langgraph_agents/state_v4.py（追加）

class MappedTaskResult(BaseModel):
    status: Literal["success", "error"]
    input_item: Any
    output: Optional[Any] = None
    error: Optional[str] = None

class MappedExecutionReport(BaseModel):
    overall_status: Literal["ALL_SUCCESS", "PARTIAL_SUCCESS", "ALL_FAILURE"]
    results: List[MappedTaskResult]

    @property
    def successful_outputs(self) -> List[Any]:
        return [r.output for r in self.results if r.status == "success"]
```

#### 2.2 改造 ToolExecutor 节点
```python
# file: langgraph_agents/agents/tool_executor.py（修改）

async def _execute_with_fanout(
    call: ToolCallV4,
    runtime: LangGraphRuntime
) -> ToolExecutionPayload:
    """执行工具（支持扇出）"""

    # 1. 解析参数
    resolved_args = resolve_arguments(call.args, runtime.get_stash_dict())

    # 2. 检查是否为扇出任务
    if call.map_over_arg:
        list_arg = resolved_args.get(call.map_over_arg)
        if not isinstance(list_arg, list):
            return ToolExecutionPayload(
                call=call,
                status="error",
                error_message=f"{call.map_over_arg} is not a list"
            )

        # 3. 并行执行
        results = await _fanout_execute(
            call.plugin_id,
            list_arg,
            call.map_over_arg,
            {k: v for k, v in resolved_args.items() if k != call.map_over_arg},
            runtime
        )

        return ToolExecutionPayload(
            call=call,
            raw_output=results,  # MappedExecutionReport
            status="success"
        )
    else:
        # 普通执行（V2 逻辑不变）
        ...
```

#### 2.3 实现扇出执行器
```python
# file: langgraph_agents/utils/fanout_executor.py（新文件）

async def _fanout_execute(
    plugin_id: str,
    items: List[Any],
    param_name: str,
    base_args: Dict[str, Any],
    runtime: LangGraphRuntime
) -> MappedExecutionReport:
    """并行执行扇出任务"""

    async def _run_single(item: Any) -> MappedTaskResult:
        try:
            args = {**base_args, param_name: item}
            output = await runtime.tool_registry.execute_async(plugin_id, args)
            return MappedTaskResult(
                status="success",
                input_item=item,
                output=output
            )
        except Exception as e:
            return MappedTaskResult(
                status="error",
                input_item=item,
                error=str(e)
            )

    # 并行执行（最大并发数：10）
    semaphore = asyncio.Semaphore(10)

    async def _run_with_limit(item):
        async with semaphore:
            return await _run_single(item)

    results = await asyncio.gather(*[_run_with_limit(item) for item in items])

    # 统计状态
    success_count = sum(1 for r in results if r.status == "success")
    if success_count == len(results):
        overall = "ALL_SUCCESS"
    elif success_count == 0:
        overall = "ALL_FAILURE"
    else:
        overall = "PARTIAL_SUCCESS"

    return MappedExecutionReport(
        overall_status=overall,
        results=results
    )
```

#### 2.4 测试用例
```python
# file: tests/langgraph_agents/test_fanout.py

@pytest.mark.asyncio
async def test_fanout_all_success():
    """测试扇出执行（全部成功）"""

    # Mock 工具
    async def mock_tool(uid):
        return {"uid": uid, "videos": [1, 2, 3]}

    report = await _fanout_execute(
        plugin_id="mock",
        items=["uid1", "uid2"],
        param_name="uid",
        base_args={"limit": 3},
        runtime=mock_runtime({"mock": mock_tool})
    )

    assert report.overall_status == "ALL_SUCCESS"
    assert len(report.successful_outputs) == 2

@pytest.mark.asyncio
async def test_fanout_partial_failure():
    """测试扇出执行（部分失败）"""

    async def mock_tool(uid):
        if uid == "uid2":
            raise Exception("Network error")
        return {"uid": uid, "videos": [1, 2, 3]}

    report = await _fanout_execute(
        plugin_id="mock",
        items=["uid1", "uid2", "uid3"],
        param_name="uid",
        base_args={},
        runtime=mock_runtime({"mock": mock_tool})
    )

    assert report.overall_status == "PARTIAL_SUCCESS"
    assert len(report.successful_outputs) == 2
    assert len(report.failed_items) == 1
```

**验收标准**：
- [ ] `MappedExecutionReport` 数据结构定义完成
- [ ] `_fanout_execute` 函数实现并测试通过
- [ ] 支持并发限制（Semaphore）
- [ ] 部分失败不影响成功项

### 5.5 阶段3：V4.4 前置语义 + GraphRenderer（1天）

**目标**：添加人类可读标签，实现程序化 RAG 图生成

**实施步骤**：

#### 3.1 修改 Planner Prompt
```python
# file: langgraph_agents/prompts/planner_system.txt（修改）

你是一个智能规划器。根据用户查询和已有数据，制定下一步行动。

输出格式（JSON）：
{
  "call_id": "A",  // 任务唯一标识
  "plugin_id": "fetch_public_data",
  "args": {
    "query": {"value": "B站科技美学的最新视频"}
  },
  "human_readable_label": "获取科技美学的最新视频",  // 关键：前置语义
  "map_over_arg": null
}

如果需要并行处理多个项，使用 map_over_arg：
{
  "call_id": "B",
  "plugin_id": "fetch_public_data",
  "args": {
    "uid": {"data_id": "A", "json_path": "$.items[*].uid"}  // 引用任务 A 的结果
  },
  "map_over_arg": "uid",  // 并行处理每个 uid
  "human_readable_label": "批量获取 UP 主视频"
}
```

#### 3.2 实现 GraphRenderer
```python
# file: langgraph_agents/utils/graph_renderer.py（新文件）

def render_rag_graph(state: GraphStateV4) -> Dict[str, Any]:
    """
    程序化生成 RAG 图（零上下文溢出）

    返回格式：
    {
        "nodes": [...],
        "edges": [...]
    }
    """

    execution_graph = state.get("execution_graph", [])
    data_stash = state.get("data_stash", [])

    # 构建 call_id -> DataReference 映射
    stash_map = {ref.data_id: ref for ref in data_stash if hasattr(ref, 'data_id')}

    nodes = []
    edges = []

    for task in execution_graph:
        # 节点
        call_id = task.call_id or f"step_{task.step_id}"
        label = task.human_readable_label or task.description

        # 从 stash 获取状态
        ref = stash_map.get(call_id)
        if ref:
            status = ref.status.upper()
            summary = ref.summary
        else:
            status = "PENDING"
            summary = ""

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

    return {
        "nodes": nodes,
        "edges": edges
    }
```

#### 3.3 添加 API 端点
```python
# file: api/controllers/research_graph.py（新文件）

from fastapi import APIRouter, HTTPException
from langgraph_agents.utils.graph_renderer import render_rag_graph

router = APIRouter(prefix="/research", tags=["research"])

@router.get("/{task_id}/graph")
def get_research_graph(task_id: str):
    """
    获取研究任务的 RAG 图

    返回格式：
    {
        "nodes": [
            {"id": "A", "label": "获取关注列表", "status": "SUCCESS"},
            {"id": "B", "label": "批量获取视频", "status": "PARTIAL_SUCCESS", "summary": "2/3 成功"}
        ],
        "edges": [
            {"from": "A", "to": "B", "label": "提供 uid"}
        ]
    }
    """

    # 从 TaskHub 获取任务状态
    state = task_hub.get_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")

    # 渲染 RAG 图（纯代码，无 LLM）
    graph = render_rag_graph(state)

    return graph
```

#### 3.4 前端集成（可选）
```vue
<!-- file: frontend/src/features/research/components/ResearchGraphPanel.vue -->

<template>
  <div class="research-graph">
    <h3>研究执行图谱</h3>
    <div ref="graphContainer" class="graph-container"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import * as d3 from 'd3'

const props = defineProps<{
  taskId: string
}>()

const graphContainer = ref<HTMLDivElement | null>(null)

async function fetchGraph() {
  const res = await fetch(`/api/research/${props.taskId}/graph`)
  const graph = await res.json()
  renderGraph(graph)
}

function renderGraph(graph: { nodes: any[], edges: any[] }) {
  // 使用 D3.js 或 Cytoscape.js 渲染图谱
  // （这里省略具体实现）
}

onMounted(() => {
  fetchGraph()
  // 可选：每 5 秒刷新一次
  setInterval(fetchGraph, 5000)
})
</script>
```

**验收标准**：
- [ ] Planner 输出包含 `human_readable_label`
- [ ] `render_rag_graph` 函数实现并测试通过
- [ ] API 端点返回正确的图谱数据
- [ ] 前端可视化渲染（可选）

### 5.6 阶段4：V4.2 RSSHub 路由发现（推荐，2天）

**目标**：让 RAG 检索成为显式步骤，支持多候选路由智能选择

**核心价值**：
1. **透明度**：Planner 可以看到 RAG 检索到的候选路由列表
2. **智能选择**：LLM 从多个候选路由中选择最合适的
3. **鲁棒性**：第一个路由失败时，可以尝试备选路由
4. **可视化**：在 RAG 图中展示"发现了 3 个候选路由"

**⚠️ 重要澄清**：
- 这**不是**发现工具的 Schema（工具注册表已有）
- **而是**：通过 RAG 检索 RSSHub 路由库，发现有哪些相关接口

**实施步骤**：

#### 4.1 注册 RSSHub 路由检索工具
```python
# file: langgraph_agents/tools/route_discovery.py（新文件）

from rag_system.retriever import RAGRetriever

@register_tool("search_rsshub_routes")
def search_rsshub_routes(query: str, top_k: int = 5) -> Dict[str, Any]:
    """
    通过 RAG 检索 RSSHub 路由库，发现相关接口

    Args:
        query: 自然语言查询（如"B站用户视频"）
        top_k: 返回候选路由数量（默认 5）

    Returns:
        候选路由列表，按相似度排序
    """

    # 使用现有的 RAG 系统检索 RSSHub 路由
    retriever = RAGRetriever()
    results = retriever.retrieve(query, top_k=top_k)

    # 格式化为候选路由列表
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

#### 4.2 修改 Planner（支持 Discovery 阶段）
```python
# file: langgraph_agents/agents/planner.py（修改）

def create_planner_node_v4_2(runtime: LangGraphRuntime):
    def node(state: GraphStateV4) -> GraphStateV4:
        # 检查是否需要 Discovery
        if _should_discover_routes(state):
            # 生成 Discovery 任务
            query = _extract_rag_query(state["original_query"])

            discovery = ToolCallV4_4(
                call_id="DISCOVER_ROUTES",
                plugin_id="search_rsshub_routes",
                args={"query": StaticValue(value=query)},
                human_readable_label=f"侦察 RSSHub 路由: {query}"
            )
            return {"execution_graph": [discovery]}

        # 如果已有候选路由，进行正常规划
        discovered = state.get("data_stash", [])
        route_discovery = next(
            (ref for ref in discovered if ref.tool_name == "search_rsshub_routes"),
            None
        )

        if route_discovery:
            # 从 data_stash 获取候选路由
            candidates = runtime.data_store.get(route_discovery.data_id)

            # LLM 决策：从候选路由中选择最合适的
            selected_route = _select_best_route(
                candidates=candidates["candidates"],
                query=state["original_query"]
            )

            # 生成执行计划
            execution_graph = _build_execution_graph(
                selected_route,
                state
            )

            return {"execution_graph": execution_graph}

        # ... 正常规划逻辑 ...

    return node

def _should_discover_routes(state: GraphStateV4) -> bool:
    """判断是否需要进行路由发现"""
    # 如果是首次规划，且查询涉及公共数据，则需要 Discovery
    if not state.get("execution_graph"):
        query = state["original_query"]
        # 简单启发式：包含 B站/知乎/GitHub 等关键词
        public_keywords = ["B站", "知乎", "GitHub", "微博", "豆瓣"]
        return any(kw in query for kw in public_keywords)
    return False
```

#### 4.3 实现多候选路由智能选择
```python
# file: langgraph_agents/utils/route_selector.py（新文件）

def _select_best_route(
    candidates: List[Dict],
    query: str,
    context: Optional[Dict] = None
) -> Dict:
    """
    从候选路由中智能选择最合适的

    Args:
        candidates: RAG 检索到的候选路由列表
        query: 用户查询
        context: 可选的上下文信息

    Returns:
        选中的路由
    """

    # 策略1: 如果只有一个候选，直接返回
    if len(candidates) == 1:
        return candidates[0]

    # 策略2: 如果有高分候选（score > 0.9），直接返回
    if candidates[0]["score"] > 0.9:
        return candidates[0]

    # 策略3: 让 LLM 从多个候选中选择
    prompt = f"""
    用户查询: {query}

    RAG 检索到以下候选 RSSHub 路由:
    {json.dumps(candidates, indent=2, ensure_ascii=False)}

    请选择最合适的路由，返回 JSON:
    {{
        "selected_index": 0,  // 选中的候选索引
        "reasoning": "..."    // 选择理由
    }}
    """

    response = llm_client.chat([{"role": "user", "content": prompt}])
    decision = json.loads(response)

    return candidates[decision["selected_index"]]
```

#### 4.4 实现 Reflector 的备选路由重试逻辑
```python
# file: langgraph_agents/agents/reflector.py（修改）

def _should_retry_with_alternative_route(state: GraphStateV4) -> bool:
    """检查是否应该尝试备选路由"""

    # 获取路由发现结果
    route_discovery = _get_route_discovery(state)
    if not route_discovery:
        return False

    candidates = route_discovery["candidates"]
    if len(candidates) <= 1:
        return False  # 没有备选路由

    # 获取当前执行结果
    last_execution = state.get("data_stash", [])[-1]
    if last_execution.status == "success":
        return False  # 执行成功，无需重试

    # 失败了，且还有备选路由，返回 True
    return True
```

**验收标准**：
- [ ] `search_rsshub_routes` 工具注册并测试通过
- [ ] Planner 支持 Discovery 阶段（生成 DISCOVER_ROUTES 任务）
- [ ] 多候选路由智能选择（LLM 决策）实现
- [ ] Reflector 支持备选路由重试
- [ ] 端到端流程测试（Discovery → Planning → Execution → Refinement）

### 5.7 阶段5：测试与优化（1天）

**目标**：确保所有新功能稳定可靠

**测试清单**：

#### 5.1 单元测试
```bash
pytest tests/langgraph_agents/test_argument_resolver.py -v
pytest tests/langgraph_agents/test_fanout.py -v
pytest tests/langgraph_agents/test_graph_renderer.py -v
```

#### 5.2 集成测试
```python
# file: tests/langgraph_agents/test_integration_v4.py

@pytest.mark.asyncio
async def test_v4_dependency_resolution():
    """测试 V4.0 依赖解析"""

    # 模拟查询："获取我所有关注的 UP 主的最新视频"
    state = {
        "original_query": "获取我所有关注的 UP 主的最新视频"
    }

    # 执行 LangGraph
    result = await runtime.run(state)

    # 验证：应生成 A -> B 依赖图
    graph = result["execution_graph"]
    assert len(graph) == 2
    assert graph[1].args["uid"].data_id == graph[0].call_id

@pytest.mark.asyncio
async def test_v4_fanout_execution():
    """测试 V4.1 扇出执行"""

    # 执行包含扇出任务的查询
    result = await runtime.run({
        "original_query": "获取 3 个 UP 主的视频"
    })

    # 验证：应有 MappedExecutionReport
    data_stash = result["data_stash"]
    fanout_result = [r for r in data_stash if "批量" in r.summary][0]

    # 从存储中获取完整报告
    report = runtime.data_store.get(fanout_result.data_id)
    assert isinstance(report, MappedExecutionReport)
    assert len(report.results) == 3
```

#### 5.3 端到端测试
```python
# file: tests/langgraph_agents/test_e2e_v4.py

@pytest.mark.e2e
async def test_complex_research_with_partial_failure():
    """
    端到端测试：复杂研究 + 部分失败

    场景：
    1. 获取 B 站关注列表（3 个 UP 主）
    2. 批量获取视频（1 个失败）
    3. Reflector 决定继续（不重试）
    4. Synthesizer 生成报告（包含失败说明）
    """

    # 执行查询
    result = await runtime.run({
        "original_query": "获取我所有关注的 UP 主的最新视频"
    })

    # 验证最终报告
    assert "2/3 成功" in result["final_report"]
    assert "uid_B 获取失败" in result["final_report"]

    # 验证 RAG 图
    graph = render_rag_graph(result)
    assert len(graph["nodes"]) == 2
    assert graph["nodes"][1]["status"] == "PARTIAL_SUCCESS"
```

#### 5.4 性能测试
```python
# file: tests/langgraph_agents/test_performance_v4.py

@pytest.mark.performance
async def test_fanout_concurrency():
    """测试扇出并发性能"""

    # 模拟 100 个 UP 主
    items = [f"uid_{i}" for i in range(100)]

    # 记录执行时间
    start = time.time()
    report = await _fanout_execute(
        plugin_id="fetch_videos",
        items=items,
        param_name="uid",
        base_args={"limit": 3},
        runtime=runtime
    )
    duration = time.time() - start

    # 验证：并发执行应远快于顺序执行
    # 假设单个请求需要 1 秒，顺序执行需要 100 秒
    # 并发执行（10 个并发）应在 10-15 秒内完成
    assert duration < 20
    assert len(report.successful_outputs) > 90  # 允许少量失败
```

**验收标准**：
- [ ] 所有单元测试通过
- [ ] 集成测试覆盖核心流程
- [ ] 端到端测试验证完整场景
- [ ] 性能测试确认并发效果

---

## 6. 风险评估与缓解

### 6.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **V4.0 依赖解析失败** | 高 | 低 | 充分的单元测试 + JSONPath 库成熟 |
| **V4.1 扇出并发问题** | 中 | 中 | 使用 Semaphore 限流 + 异常隔离 |
| **V4.2 工具发现复杂度** | 高 | 高 | **暂缓实施**，优先完成 V4.0/4.1/4.4 |
| **与现有系统不兼容** | 高 | 低 | 保持向后兼容 + 兼容模式运行 |

### 6.2 时间风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **工作量估算不足** | 中 | 中 | 按阶段交付，可灵活调整范围 |
| **测试耗时超预期** | 低 | 中 | 优先覆盖核心流程，非核心延后 |

### 6.3 业务风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **用户感知不到改进** | 低 | 低 | V4.4 GraphRenderer 提供直观可视化 |
| **破坏现有功能** | 高 | 低 | 保持向后兼容 + 完整测试覆盖 |

---

## 7. 关键决策点

### 决策1：是否实施 V4.2 路由发现（RSSHub RAG 检索）？

**⚠️ 重要澄清**：
- V4.2 的"工具发现"**不是**发现工具的 Schema
- **而是**：通过 RAG 检索 RSSHub 路由库，发现有哪些相关接口可用
- 这是 V4.4 架构的**核心价值**之一！

**选项A**：实施路由发现（完整 V4.4）
- ✅ 优势：
  - RAG 检索结果对 Planner 可见（透明度）
  - 支持多候选路由智能选择（LLM 决策）
  - 失败时可以尝试备选路由（鲁棒性）
  - 可视化"发现了哪些路由"（用户体验）
- ❌ 劣势：复杂度中等、工作量增加 2 天

**选项B**：保持现状（RAG 在 fetch_public_data 内部）
- ✅ 优势：简单、无需改动
- ❌ 劣势：
  - RAG 检索是黑盒，Planner 无法调整
  - 只能使用第一个候选路由，无法智能选择
  - 无法展示"发现过程"

**建议**：选择 **选项A**，理由：
1. **这是 V4.4 的核心价值**：让 RAG 检索成为可见、可调试的步骤
2. 当前项目已有 RAG 系统，只需要将其暴露为显式工具
3. 对复杂查询（如"对比多个 UP 主"）价值巨大
4. 工作量可控（2 天），风险中等

### 决策2：V4.0 依赖解析是否强制要求 JSONPath？

**选项A**：强制使用 JSONPath（严格模式）
- ✅ 优势：统一标准、可读性高
- ❌ 劣势：学习成本、可能过度设计

**选项B**：JSONPath 可选（兼容模式）
- ✅ 优势：灵活、易于迁移
- ❌ 劣势：可能出现两种风格混用

**建议**：选择 **选项B**，理由：
1. 简单引用（`$.`）可以省略 JSONPath
2. 复杂提取（`$.items[*].uid`）使用 JSONPath
3. 逐步迁移，降低风险

### 决策3：是否重构 ToolExecutor 为 Graph Engine？

**选项A**：全量重构（符合 V4.4 命名）
- ✅ 优势：架构清晰、概念一致
- ❌ 劣势：改动大、风险高

**选项B**：渐进式改造（保留 ToolExecutor 名称）
- ✅ 优势：降低风险、小步迭代
- ❌ 劣势：概念不统一

**建议**：选择 **选项B**，理由：
1. ToolExecutor 只是名称，核心逻辑可以升级
2. 避免大规模重构带来的风险
3. 可以在未来统一重命名

---

## 8. 实施时间表

### 8.1 推荐路径（完整 V4.4 - 包含路由发现）

**⭐ 推荐此方案**，因为 V4.2 路由发现是核心价值之一。

```
阶段0: 设计评审                  [0.5天]  2025-01-13
阶段1: V4.0 显式依赖解析          [1天]    2025-01-14
阶段2: V4.1 扇出并行执行          [2天]    2025-01-15 ~ 2025-01-16
阶段3: V4.4 前置语义 + 图谱       [1天]    2025-01-17
阶段4: V4.2 RSSHub 路由发现       [2天]    2025-01-18 ~ 2025-01-19
阶段5: 测试与优化                [1天]    2025-01-20
---------------------------------------------------
总计: 7.5 天                               预计完成: 2025-01-20
```

**核心价值**：
- ✅ RAG 检索结果对 Planner 可见（透明度）
- ✅ 多候选路由智能选择（LLM 决策）
- ✅ 备选路由重试（鲁棒性）
- ✅ 可视化"发现了哪些路由"（用户体验）

### 8.2 简化路径（不含 V4.2 - 不推荐）

如果时间紧张，可以暂时跳过 V4.2，但会损失核心价值。

```
阶段0: 设计评审              [0.5天]  2025-01-13
阶段1: V4.0 显式依赖解析      [1天]    2025-01-14
阶段2: V4.1 扇出并行执行      [2天]    2025-01-15 ~ 2025-01-16
阶段3: V4.4 前置语义 + 图谱   [1天]    2025-01-17
阶段5: 测试与优化            [1天]    2025-01-18
---------------------------------------------------
总计: 5.5 天                           预计完成: 2025-01-18
```

**⚠️ 缺失**：
- ❌ RAG 检索仍是黑盒，Planner 无法调整
- ❌ 只能使用第一个候选路由
- ❌ 无法展示"发现过程"

---

## 9. 成功指标

### 9.1 技术指标

- [ ] **测试覆盖率**：新增代码覆盖率 ≥ 80%
- [ ] **向后兼容性**：现有测试 100% 通过
- [ ] **性能提升**：扇出并行执行比顺序执行快 5 倍以上
- [ ] **错误隔离**：部分失败不影响成功项

### 9.2 业务指标

- [ ] **可视化透明度**：用户可以看到清晰的 RAG 执行图谱
- [ ] **调试效率**：通过 GraphRenderer 快速定位问题
- [ ] **扩展性**：支持批量并行查询（如"对比 10 个 UP 主的视频"）

### 9.3 架构指标

- [ ] **代码质量**：符合 CLAUDE.md 规范（文件 < 1000 行）
- [ ] **依赖管理**：显式依赖关系，易于理解和维护
- [ ] **错误处理**：结构化错误报告，支持智能重试

---

## 10. 附录

### 10.1 关键文件清单

**新增文件**：
```
langgraph_agents/
├── state_v4.py                    # V4.4 数据结构
├── utils/
│   ├── argument_resolver.py      # V4.0 参数解析
│   ├── fanout_executor.py        # V4.1 扇出执行
│   └── graph_renderer.py         # V4.4 图谱渲染
└── tools/
    └── schema_discovery.py        # V4.2 工具发现（可选）

tests/langgraph_agents/
├── test_argument_resolver.py
├── test_fanout.py
├── test_graph_renderer.py
├── test_integration_v4.py
└── test_e2e_v4.py

api/controllers/
└── research_graph.py              # V4.4 图谱 API

frontend/src/features/research/components/
└── ResearchGraphPanel.vue         # V4.4 前端可视化（可选）
```

**修改文件**：
```
langgraph_agents/
├── state.py                       # 添加 ToolCallV4
├── agents/
│   ├── planner.py                 # 支持 V4.4 输出
│   ├── tool_executor.py           # 支持扇出执行
│   └── reflector.py               # 支持部分失败决策
└── graph_builder.py               # 可能需要调整边逻辑
```

### 10.2 依赖库

**新增依赖**：
```
jsonpath-ng==1.6.1      # V4.0 JSONPath 解析
```

**无需新增依赖**：
- V4.1 扇出：使用内置 `asyncio`
- V4.4 图谱：纯 Python 数据结构

### 10.3 参考资料

- **V4.4 原始方案**：用户提供的 AI 生成文档
- **当前 V2 架构**：`docs/langgraph-agents-design.md`
- **代码审查报告**：`.agentdocs/workflow/251111-langgraph-agents-refactor.md`
- **JSONPath 语法**：https://goessner.net/articles/JsonPath/

---

## 11. 下一步行动

### 11.1 立即行动（评审后）

1. [ ] 召开设计评审会议（30分钟）
   - 确认是否实施 V4.2 工具发现
   - 确定实施时间表
   - 分配开发任务

2. [ ] 更新 `.agentdocs/index.md`
   - 添加本文档的索引条目
   - 标记为"设计方案"状态

3. [ ] 创建任务文档（如果批准实施）
   - `.agentdocs/workflow/251113-langgraph-v4.4-implementation.md`
   - 详细的 TODO 清单和进度跟踪

### 11.2 评审问题清单

请在评审会议中回答以下问题：

1. ❓ **是否实施 V4.2 路由发现**？（建议：暂缓）
   是
2. ❓ **是否接受 7.5 天的工作量估算**？
   是
3. ❓ **是否优先实施 V4.1 扇出功能**？（建议：是）
4. ❓ **前端 RAG 图谱可视化是否必需**？（建议：可选）
   是
5. ❓ **是否需要调整实施优先级**？
   否
---

**文档版本**: V1.0
**最后更新**: 2025-01-13
**维护者**: AI Agent
**审核状态**: 待评审
