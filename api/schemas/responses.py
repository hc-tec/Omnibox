"""
API响应Schema定义
所有API响应使用统一的格式，包含元数据和数据
"""

from typing import Optional, List, Dict, Any, Generic, TypeVar
from pydantic import BaseModel, Field

# 泛型数据类型
T = TypeVar('T')


class FeedItemSchema(BaseModel):
    """RSS Feed数据项Schema"""
    title: str = Field(..., description="标题")
    link: str = Field(..., description="链接")
    description: str = Field(..., description="描述/摘要")
    pub_date: Optional[str] = Field(None, description="发布时间")
    author: Optional[str] = Field(None, description="作者/发布者")
    guid: Optional[str] = Field(None, description="唯一标识")
    category: Optional[List[str]] = Field(None, description="分类/标签")
    media_url: Optional[str] = Field(None, description="媒体URL")
    media_type: Optional[str] = Field(None, description="媒体类型（image/video/audio）")

    class Config:
        schema_extra = {
            "example": {
                "title": "虎扑步行街热帖",
                "link": "https://bbs.hupu.com/12345",
                "description": "今天的热门话题...",
                "pub_date": "2025-10-31T10:00:00Z",
                "author": "虎扑用户",
                "guid": "hupu-12345",
                "category": ["体育", "讨论"],
                "media_url": None,
                "media_type": None,
            }
        }


class ResponseMetadata(BaseModel):
    """响应元数据"""
    intent_type: Optional[str] = Field(None, description="识别的意图类型（data_query/chitchat）")
    intent_confidence: Optional[float] = Field(None, description="意图识别置信度")
    generated_path: Optional[str] = Field(None, description="生成的RSS路径")
    source: Optional[str] = Field(None, description="数据来源（local/fallback）")
    cache_hit: Optional[str] = Field(None, description="缓存命中情况（rag_cache/rss_cache/none）")
    feed_title: Optional[str] = Field(None, description="Feed标题")
    status: Optional[str] = Field(None, description="处理状态（success/needs_clarification/not_found/error）")
    reasoning: Optional[str] = Field(None, description="推理过程或错误原因")

    class Config:
        schema_extra = {
            "example": {
                "intent_type": "data_query",
                "intent_confidence": 0.95,
                "generated_path": "/hupu/bbs/bxj/1",
                "source": "local",
                "cache_hit": "rss_cache",
                "feed_title": "虎扑步行街",
                "status": "success",
                "reasoning": "成功获取20条数据",
            }
        }


class ApiResponse(BaseModel, Generic[T]):
    """统一API响应格式"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")
    metadata: Optional[ResponseMetadata] = Field(None, description="元数据")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "已获取「虎扑步行街」共20条（本地服务）",
                "data": [
                    {
                        "title": "示例标题",
                        "link": "https://example.com",
                        "description": "示例描述",
                    }
                ],
                "metadata": {
                    "intent_type": "data_query",
                    "source": "local",
                    "cache_hit": "none",
                },
            }
        }


class ChatRequest(BaseModel):
    """对话请求"""
    query: str = Field(..., description="用户查询", min_length=1, max_length=500)
    filter_datasource: Optional[str] = Field(None, description="过滤特定数据源")
    use_cache: bool = Field(True, description="是否使用缓存")

    class Config:
        schema_extra = {
            "example": {
                "query": "虎扑步行街最新帖子",
                "filter_datasource": None,
                "use_cache": True,
            }
        }


class ChatResponse(ApiResponse[List[FeedItemSchema]]):
    """对话响应（继承统一响应格式）"""
    pass


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = Field(False, description="请求失败")
    message: str = Field(..., description="错误消息")
    error_code: Optional[str] = Field(None, description="错误代码")
    detail: Optional[str] = Field(None, description="详细错误信息")

    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "message": "请求处理失败",
                "error_code": "INTERNAL_ERROR",
                "detail": "数据获取超时",
            }
        }


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态（healthy/unhealthy）")
    version: str = Field(..., description="API版本")
    services: Dict[str, str] = Field(..., description="各服务状态")

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "services": {
                    "rsshub": "local",
                    "rag": "ready",
                    "cache": "ready",
                },
            }
        }
