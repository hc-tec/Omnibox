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
