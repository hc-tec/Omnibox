"""
服务层配置

统一管理 ChatService 和 DataQueryService 的配置项，避免环境变量硬编码分散在多处。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class DataQueryConfig(BaseSettings):
    """
    数据查询服务配置

    控制 DataQueryService 和 ChatService 的查询行为。
    """

    # 单路模式：当用户已指定数据源时只执行 primary route
    single_route_default: bool = Field(
        default=False,
        alias="DATA_QUERY_SINGLE_ROUTE",
        description="默认是否启用单路查询模式（1=是，0=否）",
    )

    # 多路查询限制
    multi_route_limit: int = Field(
        default=3,
        alias="DATA_QUERY_MULTI_ROUTE_LIMIT",
        description="多路查询时的最大路由数量",
    )

    # 数据预览配置（用于分析总结）
    analysis_preview_max_items: int = Field(
        default=20,
        alias="DATA_QUERY_ANALYSIS_PREVIEW_MAX_ITEMS",
        description="分析总结时的最大数据采样数",
    )

    description_max_length: int = Field(
        default=120,
        alias="DATA_QUERY_DESCRIPTION_MAX_LENGTH",
        description="描述文本的最大长度",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略不属于此配置的环境变量
    )


# 全局单例
_config_instance = None


def get_data_query_config() -> DataQueryConfig:
    """
    获取数据查询配置单例

    Returns:
        DataQueryConfig 实例
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = DataQueryConfig()
    return _config_instance


def reset_data_query_config():
    """
    重置配置单例（主要用于测试）
    """
    global _config_instance
    _config_instance = None
