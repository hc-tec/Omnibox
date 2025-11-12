"""API 响应 Schema 定义"""

from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field

from api.schemas.panel import PanelPayload, DataBlock


class ResponseMetadata(BaseModel):
    """响应元数据，记录意图、缓存命中与调试信息。"""

    intent_type: Optional[str] = Field(
        None,
        description="识别的意图类型（data_query/chitchat）",
    )
    intent_confidence: Optional[float] = Field(
        None,
        description="意图识别置信度",
    )
    generated_path: Optional[str] = Field(
        None,
        description="生成的 RSS 路径",
    )
    source: Optional[str] = Field(
        None,
        description="数据来源（local/fallback/mock）",
    )
    cache_hit: Optional[str] = Field(
        None,
        description="缓存命中情况（rag_cache/rss_cache/mock/none）",
    )
    feed_title: Optional[str] = Field(
        None,
        description="Feed 标题",
    )
    status: Optional[str] = Field(
        None,
        description="处理状态（success/needs_clarification/not_found/error）",
    )
    reasoning: Optional[str] = Field(
        None,
        description="推理过程或错误原因",
    )
    component_confidence: Optional[Dict[str, float]] = Field(
        None,
        description="组件置信度映射（UIBlock ID -> score）",
    )
    debug: Optional[Dict[str, Any]] = Field(
        None,
        description="调试信息（耗时、降级情况等）",
    )
    mode: Optional[str] = Field(None, description="查询模式")
    task_id: Optional[str] = Field(None, description="研究任务ID")
    thread_id: Optional[str] = Field(None, description="LangGraph 线程 ID")
    total_steps: Optional[int] = Field(None, description="研究步骤总数")
    execution_steps: Optional[List[Dict[str, Any]]] = Field(
        None, description="研究步骤明细（仅研究模式返回）"
    )
    data_stash_count: Optional[int] = Field(None, description="数据仓条目数量")
    warnings: Optional[List[Dict[str, Any]]] = Field(
        None, description="面板生成过程中的警告列表"
    )
    retrieved_tools: Optional[List[Dict[str, Any]]] = Field(
        None, description="RAG 检索到的候选工具列表"
    )


class LayoutSnapshotItem(BaseModel):
    """前端当前面板布局的快照，供 Planner 参考。"""

    block_id: str = Field(..., description="UIBlock ID")
    component: str = Field(..., description="组件 ID")
    x: int = Field(..., ge=0, description="栅格 X 坐标")
    y: int = Field(..., ge=0, description="栅格 Y 坐标")
    w: int = Field(..., ge=1, description="栅格宽度")
    h: int = Field(..., ge=1, description="栅格高度")


class ChatRequest(BaseModel):
    """对话请求体。"""

    query: str = Field(..., description="用户查询", min_length=1, max_length=500)
    filter_datasource: Optional[str] = Field(
        None,
        description="过滤特定数据源",
    )
    use_cache: bool = Field(True, description="是否使用缓存")
    layout_snapshot: Optional[List[LayoutSnapshotItem]] = Field(
        default=None,
        description="前端上报的布局快照（可选）",
    )
    mode: str = Field(
        "auto",
        description="查询模式：auto(自动识别)/simple(简单查询)/research(复杂研究)",
        pattern="^(auto|simple|research)$",
    )
    client_task_id: Optional[str] = Field(
        default=None,
        description="客户端生成的研究任务ID（研究实时流使用，可选）",
        max_length=128,
    )


class ChatResponse(BaseModel):
    """对话响应。"""

    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[PanelPayload] = Field(None, description="智能数据面板载荷")
    data_blocks: Dict[str, DataBlock] = Field(
        default_factory=dict,
        description="数据块字典，供前端按需引用",
    )
    metadata: Optional[ResponseMetadata] = Field(None, description="元数据")


class ErrorResponse(BaseModel):
    """错误响应。"""

    success: bool = Field(False, description="恒为 False 表示请求失败")
    message: str = Field(..., description="错误消息")
    error_code: Optional[str] = Field(None, description="错误代码")
    detail: Optional[str] = Field(None, description="详细错误信息")


class HealthCheckResponse(BaseModel):
    """健康检查响应。"""

    status: str = Field(..., description="服务状态（healthy/unhealthy）")
    version: str = Field(..., description="版本号")
    services: Dict[str, str] = Field(..., description="各子服务状态")
