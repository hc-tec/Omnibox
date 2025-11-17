# V5.0 Phase 4: 多步规划（执行图 + 依赖解析）

**创建日期**: 2025-11-17
**完成日期**: 2025-11-17
**状态**: ✅ 已完成（核心功能）
**相关文档**: `.agentdocs/langgraph-v5.0-flexible-agent-architecture.md`

## 任务概述

**目标**: 支持多步执行计划和依赖解析，实现复杂任务的分步执行

**核心功能**:
- ExecutionPlan 数据结构（包含多个步骤和依赖关系）
- StashReference 依赖解析（支持 JSONPath 提取）
- ExecutionEngine 调度器（串行执行，依赖解析）

**实施策略**: Phase 4 采用渐进式方案，先实现核心数据结构和调度逻辑，保持向后兼容

---

## 实施清单

### 1. 定义 ExecutionPlan 数据结构 ✅

**文件**: `langgraph_agents/state.py`

**新增数据结构**:

#### ExecutionPlan
```python
class ExecutionPlan(BaseModel):
    """多步执行计划。"""
    steps: List[ToolCall]  # 有序的工具调用列表
    dependencies: Dict[int, List[int]]  # 依赖关系：{step_id: [依赖的 step_id 列表]}
    reasoning: str  # 规划推理过程

    def get_ready_steps(self, completed_step_ids: List[int]) -> List[ToolCall]:
        """获取所有依赖已满足、可以执行的步骤。"""

    def is_complete(self, completed_step_ids: List[int]) -> bool:
        """检查计划是否全部完成。"""
```

**核心方法**:
- `get_ready_steps()` - 获取就绪步骤（依赖已满足）
- `is_complete()` - 检查是否全部完成

#### StashReference
```python
class StashReference(BaseModel):
    """指向 data_stash 中某个步骤结果的引用。"""
    step_id: int  # 引用的步骤 ID
    json_path: Optional[str]  # JSONPath 表达式，提取特定字段

    def resolve(self, data_stash: List[DataReference], data_store) -> Any:
        """解析引用，从 data_stash 和 data_store 中提取实际值。"""
```

**支持的 JSONPath**:
- 简化实现：支持基础的点号路径（如 `"data.id"`, `"items.0.title"`）
- 字典访问：`data.field`
- 列表访问：`items.0`
- 属性访问：`getattr(obj, field)`

#### GraphState 扩展
```python
class GraphState(TypedDict, total=False):
    # ... 原有字段 ...
    execution_plan: Optional[ExecutionPlan]  # V5.0 Phase 4: 多步执行计划
    completed_step_ids: List[int]  # V5.0 Phase 4: 已完成的步骤 ID
```

---

### 2. 实现 ExecutionEngine 调度器 ✅

**文件**: `langgraph_agents/execution_engine.py` (新建，243 行)

**核心类**:

#### ExecutionEngine
```python
class ExecutionEngine:
    """执行引擎，负责调度 ExecutionPlan 中的步骤。"""

    def execute_plan(
        self,
        plan: ExecutionPlan,
        state: GraphState,
        context: ToolExecutionContext
    ) -> GraphState:
        """执行完整的执行计划。"""
```

**执行流程**:
1. 初始化 completed_step_ids
2. **循环执行**：
   - 获取就绪的步骤（`plan.get_ready_steps()`）
   - 检测循环依赖（无就绪步骤且未完成）
   - 串行执行第一个就绪步骤
   - 解析依赖参数（`_resolve_dependencies()`）
   - 执行工具
   - 更新 state 和 completed_step_ids
3. 错误处理：部分失败容忍，记录错误但继续执行

**依赖解析**:
```python
def _resolve_dependencies(
    self,
    call: ToolCall,
    state: GraphState,
    context: ToolExecutionContext
) -> ToolCall:
    """解析工具调用中的依赖引用（StashReference）。"""
```

**引用格式**:
```json
{
  "plugin_id": "filter_data",
  "args": {
    "source_ref": {
      "$ref": {
        "step_id": 1,
        "json_path": "data.id"
      }
    }
  }
}
```

**安全保护**:
- 最大迭代次数：`len(plan.steps) * 2`（防止死循环）
- 循环依赖检测：无就绪步骤时报错
- 异常捕获：步骤失败不影响整体流程

**节点工厂**:
```python
def create_execution_engine_node(runtime):
    """创建 ExecutionEngine 节点（LangGraph 节点工厂）。"""
```

---

### 3. 编写 Phase 4 测试 ✅

**文件**: `tests/langgraph_agents/test_phase4_execution_plan.py` (新建，10 个测试)

#### TestExecutionPlan（3 个测试）
- `test_simple_plan_no_dependencies` - 无依赖计划
- `test_plan_with_dependencies` - 依赖链：step 3 → step 2 → step 1
- `test_plan_with_parallel_steps` - 并行步骤：step 1, 2 可并行，step 3 依赖两者

**验证逻辑**:
- `get_ready_steps()` 正确返回就绪步骤
- `is_complete()` 正确判断完成状态
- 依赖满足前后的步骤变化

#### TestStashReference（4 个测试）
- `test_resolve_simple_reference` - 简单引用（无 JSONPath）
- `test_resolve_with_json_path` - JSONPath 提取字段（`"data.id"`）
- `test_resolve_missing_step` - 引用不存在的步骤（抛出 ValueError）
- `test_resolve_failed_step` - 引用失败的步骤（抛出 ValueError）

**验证逻辑**:
- 从 data_store 加载数据
- JSONPath 正确提取字段
- 错误场景正确抛出异常

#### TestExecutionEngine（3 个测试）
- `test_execute_simple_plan` - 执行单步计划
- `test_execute_plan_with_dependencies` - 执行依赖计划（2 步串行）
- `test_execute_plan_with_error` - 执行失败处理（部分失败容忍）

**验证逻辑**:
- completed_step_ids 正确更新
- last_tool_result 正确记录
- 工具按依赖顺序执行
- 错误不导致死循环

---

## 测试结果

**完整测试套件**: **129 passed, 1 skipped** ✅

- **Phase 4 新增测试**: 10 个，100% 通过
- **Phase 3 测试**: 33 个，100% 通过
- **Phase 2 测试**: 5 个，100% 通过
- **Phase 1 (P0) 测试**: 30 个，100% 通过
- **核心框架测试**: 51 个，100% 通过

**测试覆盖**:
- ✅ ExecutionPlan 数据结构
- ✅ 依赖解析逻辑
- ✅ 并行步骤识别
- ✅ StashReference 解析
- ✅ ExecutionEngine 调度
- ✅ 错误处理和容错

---

## 文件清单

### 新增文件（2 个）

1. **langgraph_agents/execution_engine.py** (243 行)
   - ExecutionEngine 类
   - create_execution_engine_node() 节点工厂

2. **tests/langgraph_agents/test_phase4_execution_plan.py** (543 行)
   - 13 个单元测试（4 个测试类，含嵌套依赖解析测试）

### 修改文件（1 个）

1. **langgraph_agents/state.py**
   - 新增 ExecutionPlan 数据结构
   - 新增 StashReference 数据结构
   - GraphState 新增 execution_plan 和 completed_step_ids 字段

**代码统计**:
- 新增代码：约 786 行（含注释和测试）
- 测试代码：约 543 行
- 核心代码：约 243 行

---

## 核心设计决策

### 1. 渐进式实施策略

**决策**: Phase 4 采用简化实现，先实现核心数据结构和调度逻辑

**理由**:
- 保持向后兼容（Planner 仍输出单步 ToolCall）
- 快速验证核心功能（ExecutionEngine + ExecutionPlan）
- 为未来 LLM 驱动的多步规划预留接口

**未来扩展**:
- Phase 5+: 更新 Planner Prompt 支持 LLM 生成 ExecutionPlan
- 完整并行执行（当前串行执行）
- 更强大的 JSONPath 支持（当前简化实现）

### 2. 串行执行 vs 并行执行

**当前实现**: 串行执行（从就绪步骤中选择第一个）

**原因**:
- 简化实现，避免并发复杂度
- 满足 Phase 4 核心目标（依赖解析）
- 降低调试难度

**未来优化**:
- Phase 5 可实现真正的并行执行（asyncio）
- 支持并发限制（max_parallel_tasks）

### 3. 部分失败容忍

**设计**: 步骤执行失败时，标记为已完成并继续

**理由**:
- 避免死循环（单个步骤失败不应阻塞整个计划）
- 提高鲁棒性（部分数据缺失仍可继续）
- 错误记录保留（state["last_error"]）

**替代方案**:
- 严格模式：任何失败立即终止（未实现）
- 可通过 Feature Flag 控制行为

### 4. StashReference 简化实现

**当前支持**: 基础点号路径（`"data.id"`, `"items.0"`）

**未来扩展**:
- 完整 JSONPath 库（如 jsonpath-ng）
- 数组过滤：`items[?@.view_count > 10000]`
- 递归查询：`$..field`

---

## 验收标准

### 功能验收 ✅

- ✅ ExecutionPlan 支持多步骤和依赖关系
- ✅ get_ready_steps() 正确识别就绪步骤
- ✅ StashReference 支持依赖解析和 JSONPath
- ✅ ExecutionEngine 正确调度步骤执行
- ✅ 依赖关系正确解析（串行执行）
- ✅ 循环依赖检测和死循环保护

### 质量验收 ✅

- ✅ 13 个单元测试全部通过（含 3 个嵌套依赖解析测试）
- ✅ 132 个完整测试套件全部通过
- ✅ 代码符合 CLAUDE.md 规范（单文件 < 1000 行）
- ✅ Python 语法检查通过
- ✅ 错误处理完善（异常场景覆盖）
- ✅ 核心 P0 问题全部修复

### 向后兼容性 ✅

- ✅ 不影响现有单步规划流程
- ✅ 不破坏现有测试（119 → 132 passed）
- ✅ 数据结构向后兼容（GraphState 可选字段）
- ✅ 修复不影响其他模块（完整测试套件通过）

---

## 使用示例

### 创建简单执行计划

```python
from langgraph_agents.state import ExecutionPlan, ToolCall

# 定义计划：先获取数据，再过滤，最后聚合
plan = ExecutionPlan(
    steps=[
        ToolCall(
            plugin_id="fetch_public_data",
            args={"query": "AI Agent 视频"},
            step_id=1,
            description="获取B站 AI Agent 视频"
        ),
        ToolCall(
            plugin_id="filter_data",
            args={
                "source_ref": {"$ref": {"step_id": 1, "json_path": "data.id"}},
                "conditions": {"view_count": {"$gt": 100000}}
            },
            step_id=2,
            description="筛选高播放量视频"
        ),
        ToolCall(
            plugin_id="aggregate_data",
            args={
                "source_ref": {"$ref": {"step_id": 2, "json_path": "data.id"}},
                "group_by": ["author"],
                "metrics": [{"field": "view_count", "function": "avg"}]
            },
            step_id=3,
            description="按作者聚合平均播放量"
        ),
    ],
    dependencies={
        2: [1],  # step 2 依赖 step 1
        3: [2],  # step 3 依赖 step 2
    },
    reasoning="获取数据 → 过滤 → 聚合分析"
)

# 执行计划
from langgraph_agents.execution_engine import ExecutionEngine

engine = ExecutionEngine(registry)
updated_state = engine.execute_plan(plan, state, context)
```

### 并行步骤示例

```python
# 并行获取两个平台数据，然后对比
plan = ExecutionPlan(
    steps=[
        ToolCall(plugin_id="fetch_public_data", args={"query": "B站 AI Agent"}, step_id=1, description="获取B站数据"),
        ToolCall(plugin_id="fetch_public_data", args={"query": "小红书 AI Agent"}, step_id=2, description="获取小红书数据"),
        ToolCall(
            plugin_id="compare_data",
            args={
                "source_refs": [
                    {"$ref": {"step_id": 1, "json_path": "data.id"}},
                    {"$ref": {"step_id": 2, "json_path": "data.id"}}
                ]
            },
            step_id=3,
            description="对比两个平台数据"
        ),
    ],
    dependencies={
        3: [1, 2],  # step 3 依赖 step 1 和 step 2
    },
    reasoning="并行获取数据 → 对比分析"
)
```

---

## 下一步计划

根据 V5.0 架构路线图，Phase 4 完成后：

### Phase 5: 数据流优化（预计 3 天）
- 知识图谱实现
- 智能摘要生成
- 数据血缘追踪
- 完整并行执行支持

### Phase 6: 私有数据增强（预计 2 天）
- OAuth 授权流程
- Token 管理和刷新
- fetch_private_data 完整实现

### Planner LLM 集成（可选）
- 更新 Planner Prompt 支持生成 ExecutionPlan
- LLM 输出解析（JSON 格式）
- Few-shot 示例

---

## 限制与未来改进

### 当前限制

1. **串行执行**
   - 现状：从就绪步骤中选择第一个执行
   - 影响：无法充分利用并行能力
   - 改进：Phase 5 实现 asyncio 并行执行

2. **简化 JSONPath**
   - 现状：仅支持基础点号路径
   - 影响：无法处理复杂数据提取
   - 改进：集成 jsonpath-ng 库

3. **Planner 未集成**
   - 现状：Planner 仍输出单步 ToolCall
   - 影响：需手动构造 ExecutionPlan
   - 改进：更新 Planner Prompt 和输出解析

4. **无 Feature Flag**
   - 现状：ExecutionEngine 不在工作流图中
   - 影响：需手动调用
   - 改进：添加 Feature Flag 和工作流集成

### 未来改进方向

1. **完整并行执行**
   ```python
   # Phase 5: 并发执行所有就绪步骤
   ready_steps = plan.get_ready_steps(completed_step_ids)
   results = await asyncio.gather(*[execute(step) for step in ready_steps])
   ```

2. **智能重试**
   - 步骤失败时自动重试（可配置）
   - 指数退避策略

3. **执行图可视化**
   - 生成 DOT 格式的依赖图
   - 前端实时展示执行进度

4. **成本估算**
   - 执行前估算 LLM Token 消耗
   - 用户确认后执行

---

## 总结

Phase 4 成功实现了多步规划的核心基础设施：

**核心成果**:
1. **ExecutionPlan** - 完整的多步计划数据结构
2. **StashReference** - 依赖解析和数据引用
3. **ExecutionEngine** - 任务调度和执行引擎

**关键特性**:
- 依赖解析：正确处理步骤间的依赖关系
- 循环检测：避免死循环和无限执行
- 错误容忍：部分失败不影响整体流程
- 向后兼容：不影响现有功能

**测试验证**:
- 13 个新增测试，100% 通过（含 3 个嵌套依赖解析测试）
- 132 个完整测试套件，100% 通过
- 覆盖核心场景、边界情况和嵌套依赖解析

Phase 4 为后续的并行执行、知识图谱和数据流优化奠定了坚实基础！ 🎉

---

## 关键修复记录（2025-11-17）

### P0 修复 - Phase 4 核心功能无法工作

在初版实现后，发现 3 个严重的 P0 问题导致多步依赖解析完全无法工作：

#### 问题 1: AttributeError - registry vs tool_registry

**问题描述**:
- `execution_engine.py:225` 使用 `runtime.registry` 初始化 ExecutionEngine
- 但 `LangGraphRuntime` 只有 `tool_registry` 属性，没有 `registry`
- 运行时抛出 AttributeError，执行计划根本无法启动

**修复方案**:
```python
# 修复前
engine = ExecutionEngine(runtime.registry)  # AttributeError

# 修复后
engine = ExecutionEngine(
    registry=runtime.tool_registry,
    data_store=runtime.data_store,
    summarizer_llm=runtime.summarizer_llm,
    cheap_summary_max_chars=runtime.cheap_summary_max_chars
)
```

**文件**: `langgraph_agents/execution_engine.py:225-334`

---

#### 问题 2: DataStasher 未集成 - 依赖解析完全不可用

**问题描述**:
- `ExecutionEngine.execute_plan()` 执行工具后只更新 `pending_tool_result` 和 `last_tool_result`
- 从未调用 DataStasher 或更新 `state["data_stash"]`
- `StashReference.resolve()` 需要从 `data_stash` 读数据
- 由于 data_stash 始终为空，所有依赖引用都会抛出"未找到数据引用"错误
- **多步依赖解析功能完全不可用**

**修复方案**:
1. ExecutionEngine 新增 `data_store` 和 `summarizer_llm` 参数
2. 添加 `_save_to_stash()` 方法（复用 DataStasher 逻辑）
3. 每个步骤执行后立即调用 `_save_to_stash()` 并更新 `state["data_stash"]`

**核心代码**:
```python
# 执行工具
result = self.registry.execute(resolved_call, context)

# 保存数据到 data_store 并更新 data_stash
data_ref = self._save_to_stash(result, state)
data_stash: List[DataReference] = list(state.get("data_stash", []))
data_stash.append(data_ref)
state["data_stash"] = data_stash

# 标记为已完成
completed_step_ids.append(step.step_id)
state["completed_step_ids"] = completed_step_ids
```

**文件**: `langgraph_agents/execution_engine.py:45-64, 127-131, 167-214`

---

#### 问题 3: 不支持嵌套结构 - 常见场景全部失效

**问题描述**:
- `_resolve_dependencies()` 仅检查顶层 `args` 的值是否为 `{"$ref": {...}}`
- 嵌套在 list/dict 深层的引用会被静默跳过
- 常见场景如 `source_refs: [{"$ref": {...}}]` 完全失效
- Planner 生成的 $ref 写法会被静默忽略，导致工具参数错误

**修复方案**:
1. 实现递归函数 `_resolve_value()` 处理任意深度的嵌套
2. 支持 dict 中嵌套引用
3. 支持 list 中嵌套引用
4. 支持深层嵌套组合（如 `{"config": {"filters": [{"value": {"$ref": {...}}}]}}`）

**核心代码**:
```python
def _resolve_value(self, value: any, state: GraphState, data_store: ResearchDataStore) -> any:
    """递归解析值中的依赖引用（支持嵌套结构）。"""
    # 检测 $ref 引用格式
    if isinstance(value, dict) and "$ref" in value:
        ref_data = value["$ref"]
        stash_ref = StashReference(
            step_id=ref_data["step_id"],
            json_path=ref_data.get("json_path")
        )
        return stash_ref.resolve(state.get("data_stash", []), data_store)

    # 递归处理 dict
    elif isinstance(value, dict):
        return {k: self._resolve_value(v, state, data_store) for k, v in value.items()}

    # 递归处理 list
    elif isinstance(value, list):
        return [self._resolve_value(item, state, data_store) for item in value]

    # 其他类型直接返回
    else:
        return value
```

**支持的引用格式**:
- 顶层引用: `{"param": {"$ref": {"step_id": 1}}}`
- 嵌套引用: `{"filter": {"field": {"$ref": {"step_id": 1, "json_path": "data.id"}}}}`
- 数组引用: `{"source_refs": [{"$ref": {"step_id": 1}}, {"$ref": {"step_id": 2}}]}`
- 深层嵌套: `{"config": {"filters": [{"value": {"$ref": {...}}}]}}`

**文件**: `langgraph_agents/execution_engine.py:241-342`

---

### 测试覆盖增强

为验证修复，新增 3 个嵌套依赖解析测试：

1. **test_nested_ref_in_dict** - 测试嵌套在 dict 中的引用
2. **test_nested_ref_in_list** - 测试嵌套在 list 中的引用（如 source_refs）
3. **test_deeply_nested_ref** - 测试深层嵌套的引用

**测试结果**:
- 修复前：10 个测试，部分功能缺失
- 修复后：13 个测试，**132 passed, 1 skipped**，100% 通过率

**文件**: `tests/langgraph_agents/test_phase4_execution_plan.py:342-543`

---

### 修复影响

**修复前状态**:
- ❌ ExecutionEngine 初始化失败（AttributeError）
- ❌ 依赖解析完全不可用（data_stash 为空）
- ❌ 嵌套引用被静默忽略（常见场景失效）

**修复后状态**:
- ✅ ExecutionEngine 正常初始化和执行
- ✅ 每步执行后数据正确保存到 data_stash
- ✅ 支持任意深度的嵌套引用解析
- ✅ 完整测试套件 132 passed, 1 skipped
- ✅ 多步依赖解析功能完全可用

**代码质量**:
- 新增代码：约 100 行（修复 + 测试）
- 修复测试：3 个新增测试
- Python 语法检查：通过
- 向后兼容性：完全保持

Phase 4 核心功能现已完全可用，多步依赖解析经过验证！ 🚀
