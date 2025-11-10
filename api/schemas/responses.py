"""
API 响应 Schema 定义�?"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from api.schemas.panel import PanelPayload, DataBlock


class ResponseMetadata(BaseModel):
    """响应元数据�?""

    intent_type: Optional[str] = Field(None, description="识别的意图类型（data_query/chitchat�?)
    intent_confidence: Optional[float] = Field(None, description="意图识别置信�?)
    generated_path: Optional[str] = Field(None, description="生成的RSS路径")
    source: Optional[str] = Field(None, description="数据来源（local/fallback/mock�?)
    cache_hit: Optional[str] = Field(None, description="缓存命中情况（rag_cache/rss_cache/mock/none�?)
    feed_title: Optional[str] = Field(None, description="Feed标题")
    status: Optional[str] = Field(None, description="处理状态（success/needs_clarification/not_found/error�?)
    reasoning: Optional[str] = Field(None, description="推理过程或错误原�?)
    component_confidence: Optional[Dict[str, float]] = Field(
        None,
        description="组件置信度映射（UIBlock ID -> score�?,
    )
    debug: Optional[Dict[str, Any]] = Field(
        None,
        description="调试信息（耗时、降级情况等�?,
    )



class LayoutSnapshotItem(BaseModel):
    """ǰ�˵�ǰ���ֿ��գ�Ϊ Planner �ṩ�ο�"""

    block_id: str = Field(..., description="UIBlock ID")
    component: str = Field(..., description="��� ID")
    x: int = Field(..., ge=0, description="���� X ����")
    y: int = Field(..., ge=0, description="���� Y ����")
    w: int = Field(..., ge=1, description="ռ������")
    h: int = Field(..., ge=1, description="ռ������")
class ChatRequest(BaseModel):
    """对话请求体�?""

    query: str = Field(..., description="用户查询", min_length=1, max_length=500)
    filter_datasource: Optional[str] = Field(None, description="过滤特定数据�?)
    use_cache: bool = Field(True, description="�Ƿ�ʹ�û���")
    layout_snapshot: Optional[List[LayoutSnapshotItem]] = Field(
        default=None,
        description="ǰ�˵�ǰ���ֿ��գ���ѡ��",
    )

class ChatResponse(BaseModel):
    """对话响应�?""

    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[PanelPayload] = Field(None, description="智能数据面板载荷")
    data_blocks: Dict[str, DataBlock] = Field(
        default_factory=dict,
        description="数据块字典，供前端按需引用",
    )
    metadata: Optional[ResponseMetadata] = Field(None, description="元数�?)


class ErrorResponse(BaseModel):
    """错误响应�?""

    success: bool = Field(False, description="恒为False表示请求失败")
    message: str = Field(..., description="错误消息")
    error_code: Optional[str] = Field(None, description="错误代码")
    detail: Optional[str] = Field(None, description="详细错误信息")


class HealthCheckResponse(BaseModel):
    """健康检查响应�?""

    status: str = Field(..., description="服务状态（healthy/unhealthy�?)
    version: str = Field(..., description="版本�?)
    services: Dict[str, str] = Field(..., description="各子服务状�?)







