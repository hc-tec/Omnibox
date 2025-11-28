from __future__ import annotations

"""
LangGraph V2 状态与数据结构定义。

该模块复用了《docs/langgrapg-agents-design.md》给出的约束：
1. Planner 每次只输出一个 ToolCall；
2. LangGraph 状态机仅存储"元数据"（引用、摘要），原始数据放入外部存储；
3. Reflector 负责决定流程是否继续/结束/请求人工协助。
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict, TYPE_CHECKING

try:
    from typing import Required
except ImportError:
    from typing_extensions import Required

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .knowledge_graph import KnowledgeGraph


class ToolCall(BaseModel):
    """Planner 输出的单步工具调用计划。"""

    plugin_id: str = Field(..., description="注册的工具 ID")
    args: Dict[str, Any] = Field(default_factory=dict, description="调用参数")
    step_id: int = Field(..., description="连续步骤编号，Reflector 用于追踪进展")
    description: str = Field(..., description="人类可读的操作说明")


class ToolExecutionPayload(BaseModel):
    """
    工具执行后的基础结果。
    DataStasher 负责将 raw_output 写入外部存储、生成摘要。

    V5.0 P0: 新增 needs_user_input 状态，用于请求用户澄清。
    """

    call: ToolCall
    raw_output: Any = None
    status: Literal["success", "error", "needs_user_input"] = "success"
    error_message: Optional[str] = None


class DataReference(BaseModel):
    """
    指向外部存储中原始数据的元数据。

    V5.0 P0: 新增 needs_user_input 状态，用于请求用户澄清。
    当 status="needs_user_input" 时，data_id 为 None（不存储到 data_store）。
    """

    step_id: int
    tool_name: str
    data_id: Optional[str] = Field(None, description="外部存储主键（needs_user_input 时为 None）")
    summary: str = Field(..., description="廉价模型生成的摘要")
    status: Literal["success", "error", "needs_user_input"] = "success"
    error_message: Optional[str] = None


class EnhancedDataReference(DataReference):
    """
    增强的数据引用（V5.0 Phase 5）。

    在 DataReference 基础上添加结构化元数据和质量评分。
    """

    schema_info: Optional[Dict[str, str]] = Field(
        None,
        description="数据 Schema 信息：{field_name: field_type}"
    )
    statistics: Optional[Dict[str, Any]] = Field(
        None,
        description="数据统计信息：{record_count, field_stats, etc.}"
    )
    sample_items: Optional[List[Dict]] = Field(
        None,
        description="样本数据（前 3-5 条记录）"
    )
    quality_score: Optional[float] = Field(
        None,
        description="数据质量评分 (0-1)：完整性、一致性、准确性"
    )


class Reflection(BaseModel):
    """
    Reflector 决策结果。

    V5.0 P0: 新增 REQUEST_HUMAN_CLARIFICATION 决策类型。
    """

    decision: Literal["CONTINUE", "FINISH", "REQUEST_HUMAN_CLARIFICATION"]
    reasoning: str = Field(..., description="推理过程，Planner/Synthesizer 会引用")


class RouterDecision(BaseModel):
    """RouterAgent 输出，驱动入口分支。"""

    route: Literal["simple_tool_call", "complex_research", "clarify_with_human", "end"]
    reasoning: str = Field(..., description="用于 UI 展示的解释")


class StashReference(BaseModel):
    """
    指向 data_stash 中某个步骤结果的引用（V5.0 Phase 4）。

    用于依赖解析，支持从前序步骤提取数据作为当前步骤的参数。
    """

    step_id: int = Field(..., description="引用的步骤 ID")
    json_path: Optional[str] = Field(None, description="JSONPath 表达式，提取特定字段")

    def resolve(self, data_stash: List[DataReference], data_store) -> Any:
        """
        解析引用，从 data_stash 和 data_store 中提取实际值。

        Args:
            data_stash: 当前的 data_stash
            data_store: 外部数据存储

        Returns:
            解析后的值
        """
        # 查找对应的 DataReference
        ref = next((r for r in data_stash if r.step_id == self.step_id), None)
        if not ref:
            raise ValueError(f"未找到 step_id={self.step_id} 的数据引用")

        if ref.status != "success":
            raise ValueError(f"step_id={self.step_id} 的执行失败，无法引用")

        # 加载数据
        data = data_store.load(ref.data_id)

        # 如果指定了 JSONPath，提取字段
        if self.json_path:
            # 简化实现：支持基础的点号路径（如 "data.id"）
            parts = self.json_path.split(".")
            for part in parts:
                if isinstance(data, dict):
                    data = data.get(part)
                elif isinstance(data, list) and part.isdigit():
                    data = data[int(part)]
                else:
                    data = getattr(data, part, None)

                if data is None:
                    break

        return data


class ExecutionPlan(BaseModel):
    """
    多步执行计划（V5.0 Phase 4）。

    PlannerAgent 输出的完整执行计划，包含多个步骤和依赖关系。
    """

    steps: List[ToolCall] = Field(..., description="有序的工具调用列表")
    dependencies: Dict[int, List[int]] = Field(
        default_factory=dict,
        description="依赖关系：{step_id: [依赖的 step_id 列表]}"
    )
    reasoning: str = Field(..., description="规划推理过程")

    def get_ready_steps(self, completed_step_ids: List[int]) -> List[ToolCall]:
        """
        获取所有依赖已满足、可以执行的步骤。

        Args:
            completed_step_ids: 已完成的步骤 ID 列表

        Returns:
            可执行的 ToolCall 列表
        """
        ready = []
        completed_set = set(completed_step_ids)

        for step in self.steps:
            # 跳过已完成的步骤
            if step.step_id in completed_set:
                continue

            # 检查依赖是否满足
            deps = self.dependencies.get(step.step_id, [])
            if all(dep_id in completed_set for dep_id in deps):
                ready.append(step)

        return ready

    def is_complete(self, completed_step_ids: List[int]) -> bool:
        """检查计划是否全部完成。"""
        return len(completed_step_ids) == len(self.steps)


class GraphState(TypedDict, total=False):
    """
    LangGraph 核心状态。
    TypedDict 便于 LangGraph StateGraph 做键级 merge，值则继续使用 Pydantic 模型。

    注意：original_query 是必需字段，其他字段可选。
    """

    original_query: Required[str]  # 必需字段
    chat_history: List[str]
    next_tool_call: Optional[ToolCall]
    data_stash: List[DataReference]
    reflection: Optional[Reflection]
    final_report: Optional[str]
    human_in_loop_request: Optional[str]
    router_decision: Optional[RouterDecision]
    pending_tool_result: Optional[ToolExecutionPayload]
    last_tool_result: Optional[ToolExecutionPayload]  # V5.0 P0: Reflector 用于检查工具状态
    working_memory: Dict[str, Any]  # V5.0 Phase 2: 轻量工具结果（不持久化）
    last_error: Optional[str]
    execution_plan: Optional[ExecutionPlan]  # V5.0 Phase 4: 多步执行计划
    completed_step_ids: List[int]  # V5.0 Phase 4: 已完成的步骤 ID
    knowledge_graph: Optional[Any]  # V5.0 Phase 5: 知识图谱（Any 避免循环引用）
    # V6.0 单Agent架构新增
    agent_decision: Optional[Literal["CONTINUE", "FINISH", "REQUEST_CLARIFICATION"]]
    agent_reasoning: Optional[str]

