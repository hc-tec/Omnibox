"""
服务层配置

统一管理 ChatService、DataQueryService 和 DatabaseConnection 的配置项，
避免环境变量硬编码分散在多处。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os
from pathlib import Path


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


class DatabaseConfig(BaseSettings):
    """
    数据库配置

    管理 SQLite 数据库的位置、文件名等配置。
    遵循 runtime-persistence-plan.md 的设计原则。
    """

    # 数据库目录（默认为项目根目录下的 runtime）
    database_dir: str = Field(
        default="runtime",
        alias="DATABASE_DIR",
        description="数据库文件存放目录（相对于项目根目录）",
    )

    # 数据库文件名
    database_name: str = Field(
        default="omni.db",
        alias="DATABASE_NAME",
        description="数据库文件名",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_database_url(self) -> str:
        """
        获取完整的数据库 URL

        Returns:
            SQLite 数据库 URL，格式: sqlite:///runtime/omni.db
        """
        # 获取项目根目录（假设 config.py 在 services/ 目录下）
        project_root = Path(__file__).parent.parent
        db_dir = project_root / self.database_dir

        # 确保目录存在
        db_dir.mkdir(parents=True, exist_ok=True)

        db_path = db_dir / self.database_name
        return f"sqlite:///{db_path}"


# 数据库配置全局单例
_db_config_instance = None


def get_database_config() -> DatabaseConfig:
    """
    获取数据库配置单例

    Returns:
        DatabaseConfig 实例
    """
    global _db_config_instance
    if _db_config_instance is None:
        _db_config_instance = DatabaseConfig()
    return _db_config_instance


def reset_database_config():
    """
    重置数据库配置单例（主要用于测试）
    """
    global _db_config_instance
    _db_config_instance = None
