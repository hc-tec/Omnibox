from __future__ import annotations

"""
LangGraph V2 状态与数据结构定义。

该模块复用了《docs/langgrapg-agents-design.md》给出的约束：
1. Planner 每次只输出一个 ToolCall；
2. LangGraph 状态机仅存储“元数据”（引用、摘要），原始数据放入外部存储；
3. Reflector 负责决定流程是否继续/结束/请求人工协助。
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict

try:
    from typing import Required
except ImportError:
    from typing_extensions import Required

from pydantic import BaseModel, Field


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
    last_error: Optional[str]

