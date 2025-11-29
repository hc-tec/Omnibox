"""
Panel specification models.

该模块定义 StructuredEnvelope / DisplaySchema / PanelDSL 等结构化模型，
用于约束 AI 生成 UI 时的数据输入、转换与渲染契约。
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict, ValidationError


class EnvelopeCursor(BaseModel):
    """用于描述在预览之外的原始数据分页信息。"""

    next_token: Optional[str] = Field(
        default=None,
        description="可选分页 token，供后续请求追加更多 preview",
    )
    total: Optional[int] = Field(
        default=None, ge=0, description="底层数据总条数（如果可计算）"
    )
    sampled: Optional[int] = Field(
        default=None, ge=0, description="本次 preview 包含的条数"
    )


class StructuredDataSchema(BaseModel):
    """Envelope 使用的 schema 模型，允许额外字段以兼容不同数据结构。"""

    model_config = ConfigDict(extra="allow")

    type: Literal[
        "table",
        "record",
        "graph",
        "geojson",
        "metric_set",
        "custom",
    ] = Field(..., description="数据类型，用于指示 preview 的结构")
    description: Optional[str] = Field(
        default=None,
        description="Schema 描述，帮助 Planner 选择合适的组件",
    )


class StructuredDataEnvelope(BaseModel):
    """
    Structured Envelope.

    - data_id：用于在数据仓库中定位原始数据
    - preview：供 LLM 使用的精简样本
    """

    model_config = ConfigDict(populate_by_name=True)

    data_id: str = Field(..., description="唯一数据标识符")
    data_schema: StructuredDataSchema = Field(..., alias="schema", description="结构化 schema 描述")
    summary: Optional[str] = Field(
        default=None,
        max_length=600,
        description="不超过 600 字符的描述/摘要，供 LLM 阅读",
    )
    preview: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="安全可展示的数据样本（自动裁剪字段）",
    )
    cursor: Optional[EnvelopeCursor] = Field(
        default=None,
        description="预览的分页信息，供 Planner 请求更多样本",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="来源、时间、可见性等额外元信息",
    )


class DisplaySchema(BaseModel):
    """分析节点输出的洞察结构，描述“要展示什么样的洞察”。"""

    kind: Literal[
        "metric_set",
        "comparison",
        "cluster",
        "timeline",
        "story_graph",
        "playbook",
        "alert",
        "record_set",
        "custom",
    ] = Field(..., description="洞察种类")
    title: Optional[str] = Field(default=None, description="标题/名称")
    summary: Optional[str] = Field(default=None, description="简要说明")
    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="不同 kind 对应的 payload",
    )
    source_refs: List[str] = Field(
        default_factory=list,
        description="关联的 envelope data_id，便于溯源",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="计算过程中的警告（如部分来源失败）",
    )


class TransformationSpec(BaseModel):
    """数据绑定中的转换指令，由 Sandbox 执行。"""

    type: Literal["inline_python", "code_ref", "builtin"] = Field(
        ...,
        description="转换类型：内联 Python、引用预置代码或使用内置函数",
    )
    code: Optional[str] = Field(
        default=None,
        description="内联代码或代码引用的唯一名称",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="传递给转换函数的参数",
    )


class EventHandlerSpec(BaseModel):
    """组件交互事件定义。"""

    action: Literal["refresh_panel", "emit_event", "server_action"] = Field(
        ...,
        description="事件类型：刷新 Panel / 回传事件 / 调用服务器动作",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="事件参数，可引用 `$event.xxx`",
    )


class DataBinding(BaseModel):
    """Panel 节点与数据 envelope 的绑定描述。"""

    data_id: Optional[str] = Field(
        default=None, description="绑定的数据源 envelope id"
    )
    view_model_id: Optional[str] = Field(
        default=None,
        description="引用现有 ViewModel（当 Sandbox 已输出时使用）",
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict, description="简单过滤条件（等值/范围）"
    )
    transformation: Optional[TransformationSpec] = Field(
        default=None,
        description="可选转换管线，由 Sandbox 执行后生成 ViewModel 数据",
    )
    cursor: Optional[EnvelopeCursor] = Field(
        default=None,
        description="可覆盖的分页设置，用于局部取数",
    )


class PanelNode(BaseModel):
    """Panel DSL 的节点模型（树形结构）。"""

    node: str = Field(..., description="组件名称/标识，必须存在于 manifest")
    props: Dict[str, Any] = Field(
        default_factory=dict,
        description="组件属性，将直接传给前端",
    )
    data_binding: Optional[DataBinding] = Field(
        default=None, description="可选数据绑定描述"
    )
    events: Dict[str, EventHandlerSpec] = Field(
        default_factory=dict,
        description="交互事件定义（如 on_change/on_click）",
    )
    children: List["PanelNode"] = Field(
        default_factory=list, description="子节点，支持嵌套布局"
    )


PanelNode.model_rebuild()


class PanelDSL(BaseModel):
    """整体 Panel 描述，由多个根节点组成。"""

    version: str = Field(
        default="1.0",
        description="DSL 版本号，便于向后兼容",
    )
    layout: List[PanelNode] = Field(
        default_factory=list,
        description="根节点列表，每个节点代表一个顶层组件/容器",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="额外声明，如 skeleton、主题等"
    )

    def iter_nodes(self) -> List[PanelNode]:
        """展开 DSL 树，方便校验/遍历。"""

        stack: List[PanelNode] = list(self.layout)
        nodes: List[PanelNode] = []
        while stack:
            node = stack.pop()
            nodes.append(node)
            stack.extend(node.children)
        return nodes


class PanelSpecError(RuntimeError):
    """Panel 规范相关错误。"""

    def __init__(self, message: str, data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.data = data or {}


def validate_panel_dsl(payload: Dict[str, Any]) -> PanelDSL:
    """解析并校验 DSL 结构。"""

    try:
        return PanelDSL.model_validate(payload)
    except ValidationError as exc:
        raise PanelSpecError("Invalid panel DSL payload", {"error": exc.errors()}) from exc


def validate_envelope(payload: Dict[str, Any]) -> StructuredDataEnvelope:
    """解析并校验 Structured Envelope。"""

    try:
        return StructuredDataEnvelope.model_validate(payload)
    except ValidationError as exc:
        raise PanelSpecError("Invalid structured envelope", {"error": exc.errors()}) from exc
