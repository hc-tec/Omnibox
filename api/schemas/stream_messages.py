"""
WebSocket流式消息Schema定义
按阶段推送处理进度：intent → rag → fetch → summary
"""

from typing import Optional, Literal, Any
from pydantic import BaseModel, Field
from datetime import datetime


class StreamMessage(BaseModel):
    """
    WebSocket流式消息基类

    所有流式消息的统一格式
    """
    type: Literal["stage", "data", "error", "complete"] = Field(
        ...,
        description="消息类型：stage=阶段更新, data=数据推送, error=错误, complete=完成"
    )
    stream_id: str = Field(..., description="流ID，用于关联日志和追踪")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="消息时间戳（ISO格式）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "stage",
                "stream_id": "stream-1234567890",
                "timestamp": "2025-10-31T12:00:00.000000"
            }
        }


class StageMessage(StreamMessage):
    """
    阶段更新消息

    标识处理进入新阶段
    """
    type: Literal["stage"] = "stage"
    stage: Literal["intent", "rag", "fetch", "summary"] = Field(
        ...,
        description="处理阶段：intent=意图识别, rag=RAG检索, fetch=数据获取, summary=结果总结"
    )
    message: str = Field(..., description="阶段描述")
    progress: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="进度（0.0-1.0），可选"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "stage",
                "stream_id": "stream-1234567890",
                "timestamp": "2025-10-31T12:00:00.000000",
                "stage": "intent",
                "message": "正在识别意图...",
                "progress": 0.25
            }
        }


class DataMessage(StreamMessage):
    """
    数据推送消息

    推送实际业务数据
    """
    type: Literal["data"] = "data"
    stage: Literal["intent", "rag", "fetch", "summary"] = Field(
        ...,
        description="数据所属阶段"
    )
    data: Any = Field(..., description="阶段数据（dict/list/str等）")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "data",
                "stream_id": "stream-1234567890",
                "timestamp": "2025-10-31T12:00:01.000000",
                "stage": "intent",
                "data": {
                    "intent_type": "data_query",
                    "confidence": 0.95,
                    "reasoning": "包含数据源关键词"
                }
            }
        }


class ErrorMessage(StreamMessage):
    """
    错误消息

    推送处理过程中的错误
    """
    type: Literal["error"] = "error"
    error_code: str = Field(..., description="错误代码")
    error_message: str = Field(..., description="错误描述")
    stage: Optional[Literal["intent", "rag", "fetch", "summary"]] = Field(
        None,
        description="错误发生的阶段（如果已知）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "error",
                "stream_id": "stream-1234567890",
                "timestamp": "2025-10-31T12:00:02.000000",
                "error_code": "RAG_ERROR",
                "error_message": "RAG检索失败: 向量索引不可用",
                "stage": "rag"
            }
        }


class CompleteMessage(StreamMessage):
    """
    完成消息

    标识流式处理完成
    """
    type: Literal["complete"] = "complete"
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="完成描述")
    total_time: Optional[float] = Field(None, description="总耗时（秒）")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "complete",
                "stream_id": "stream-1234567890",
                "timestamp": "2025-10-31T12:00:05.000000",
                "success": True,
                "message": "查询完成，共返回10条数据",
                "total_time": 5.2
            }
        }


# 流式处理阶段定义
class StreamStage:
    """流式处理阶段常量"""
    INTENT = "intent"       # 意图识别
    RAG = "rag"             # RAG检索
    FETCH = "fetch"         # 数据获取
    SUMMARY = "summary"     # 结果总结


# 阶段描述映射
STAGE_DESCRIPTIONS = {
    StreamStage.INTENT: "正在识别意图...",
    StreamStage.RAG: "正在检索知识库...",
    StreamStage.FETCH: "正在获取数据...",
    StreamStage.SUMMARY: "正在总结结果...",
}


# 阶段进度映射（用于progress计算）
STAGE_PROGRESS = {
    StreamStage.INTENT: 0.25,
    StreamStage.RAG: 0.50,
    StreamStage.FETCH: 0.75,
    StreamStage.SUMMARY: 1.0,
}


# ============================================================
# 研究模式专用消息类型
# ============================================================


class ResearchStartMessage(BaseModel):
    """
    研究开始消息

    标识研究任务启动，包含任务元信息和执行计划
    """
    type: Literal["research_start"] = "research_start"
    stream_id: str = Field(..., description="流ID，用于关联日志和追踪")
    task_id: str = Field(..., description="研究任务ID")
    query: str = Field(..., description="原始查询")
    plan: dict[str, Any] = Field(..., description="执行计划（LLM生成的子查询列表）")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="消息时间戳（ISO格式）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "research_start",
                "stream_id": "stream-1234567890",
                "task_id": "task-abc123",
                "query": "查看 up主15616847 的视频并分析方向",
                "plan": {
                    "sub_queries": [
                        {
                            "query": "查看 up主15616847 的视频",
                            "task_type": "data_fetch",
                            "datasource": None
                        },
                        {
                            "query": "分析 up主15616847 的内容方向",
                            "task_type": "analysis",
                            "datasource": None
                        }
                    ]
                },
                "timestamp": "2025-11-13T12:00:00.000000"
            }
        }


class ResearchStepMessage(BaseModel):
    """
    研究步骤更新消息

    实时推送研究过程中的每个步骤状态
    """
    type: Literal["research_step"] = "research_step"
    stream_id: str = Field(..., description="流ID")
    task_id: str = Field(..., description="研究任务ID")
    step_id: str = Field(..., description="步骤ID（如 sub_query_0）")
    step_type: Literal["planning", "data_fetch", "analysis"] = Field(
        ...,
        description="步骤类型：planning=规划, data_fetch=数据获取, analysis=分析"
    )
    action: str = Field(..., description="步骤描述（如：正在获取 up主15616847 的视频）")
    status: Literal["processing", "success", "error"] = Field(
        ...,
        description="步骤状态"
    )
    details: Optional[dict[str, Any]] = Field(
        None,
        description="步骤详情（如：查询耗时、数据条数等）"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="消息时间戳（ISO格式）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "research_step",
                "stream_id": "stream-1234567890",
                "task_id": "task-abc123",
                "step_id": "sub_query_0",
                "step_type": "data_fetch",
                "action": "正在获取 up主15616847 的视频",
                "status": "processing",
                "details": None,
                "timestamp": "2025-11-13T12:00:01.000000"
            }
        }


class ResearchPanelMessage(BaseModel):
    """
    面板数据推送消息

    推送数据面板给前端渲染（包含布局和数据）
    """
    type: Literal["research_panel"] = "research_panel"
    stream_id: str = Field(..., description="流ID")
    task_id: str = Field(..., description="研究任务ID")
    step_id: str = Field(..., description="关联的步骤ID")
    panel_payload: dict[str, Any] = Field(
        ...,
        description="面板数据 payload（PanelResult.payload）"
    )
    source_query: str = Field(..., description="数据来源查询")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="消息时间戳（ISO格式）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "research_panel",
                "stream_id": "stream-1234567890",
                "task_id": "task-abc123",
                "step_id": "sub_query_0",
                "panel_payload": {
                    "layout": [...],
                    "components": {...}
                },
                "source_query": "查看 up主15616847 的视频",
                "timestamp": "2025-11-13T12:00:03.000000"
            }
        }


class ResearchAnalysisMessage(BaseModel):
    """
    分析结果推送消息

    推送 LLM 分析结果（流式文本 或 完整 Markdown）
    """
    type: Literal["research_analysis"] = "research_analysis"
    stream_id: str = Field(..., description="流ID")
    task_id: str = Field(..., description="研究任务ID")
    step_id: str = Field(..., description="关联的步骤ID")
    analysis_text: str = Field(..., description="分析文本（支持增量推送）")
    is_complete: bool = Field(
        default=False,
        description="是否为该步骤的最终分析（True=完整文本，False=增量片段）"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="消息时间戳（ISO格式）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "research_analysis",
                "stream_id": "stream-1234567890",
                "task_id": "task-abc123",
                "step_id": "sub_query_1",
                "analysis_text": "该 up主 主要专注于技术教程...",
                "is_complete": True,
                "timestamp": "2025-11-13T12:00:05.000000"
            }
        }


class ResearchCompleteMessage(BaseModel):
    """
    研究完成消息

    标识研究任务全部完成
    """
    type: Literal["research_complete"] = "research_complete"
    stream_id: str = Field(..., description="流ID")
    task_id: str = Field(..., description="研究任务ID")
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="完成描述")
    total_time: Optional[float] = Field(None, description="总耗时（秒）")
    summary: Optional[str] = Field(None, description="研究总结（可选）")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="消息时间戳（ISO格式）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "research_complete",
                "stream_id": "stream-1234567890",
                "task_id": "task-abc123",
                "success": True,
                "message": "研究完成，共执行 2 个子任务",
                "total_time": 12.5,
                "summary": "该 up主 主要制作技术教程，涵盖编程、AI 等领域...",
                "timestamp": "2025-11-13T12:00:15.000000"
            }
        }


class ResearchErrorMessage(BaseModel):
    """
    研究错误消息

    推送研究过程中的错误
    """
    type: Literal["research_error"] = "research_error"
    stream_id: str = Field(..., description="流ID")
    task_id: str = Field(..., description="研究任务ID")
    step_id: Optional[str] = Field(None, description="错误发生的步骤ID（如果已知）")
    error_code: str = Field(..., description="错误代码")
    error_message: str = Field(..., description="错误描述")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="消息时间戳（ISO格式）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "research_error",
                "stream_id": "stream-1234567890",
                "task_id": "task-abc123",
                "step_id": "sub_query_0",
                "error_code": "DATA_FETCH_ERROR",
                "error_message": "数据获取失败: RSSHub 服务不可用",
                "timestamp": "2025-11-13T12:00:02.000000"
            }
        }


# 研究步骤类型常量
class ResearchStepType:
    """研究步骤类型常量"""
    PLANNING = "planning"          # LLM 规划
    DATA_FETCH = "data_fetch"      # 数据获取
    ANALYSIS = "analysis"          # 数据分析


# 研究步骤状态常量
class ResearchStepStatus:
    """研究步骤状态常量"""
    PROCESSING = "processing"      # 处理中
    SUCCESS = "success"            # 成功
    ERROR = "error"                # 失败
