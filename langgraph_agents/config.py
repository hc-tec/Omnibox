"""LangGraph Agents 配置管理

集中管理所有配置项，统一使用 Pydantic Settings 读取 `.env`/环境变量。
"""
from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _alias(field_name: str, env_name: str) -> AliasChoices:
    """生成兼容字段名和环境变量名的别名定义。"""
    return AliasChoices(field_name, env_name)


class _BaseLangGraphSettings(BaseSettings):
    """所有 LangGraph Setting 的公共配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class LLMRetryConfig(_BaseLangGraphSettings):
    """LLM 重试配置"""

    max_retries: int = Field(
        default=3,
        validation_alias=_alias("max_retries", "LANGGRAPH_RETRY_MAX"),
        description="最大重试次数",
    )
    initial_delay: float = Field(
        default=1.0,
        validation_alias=_alias("initial_delay", "LANGGRAPH_RETRY_INITIAL_DELAY"),
        description="首次重试延迟（秒）",
    )
    backoff_factor: float = Field(
        default=2.0,
        validation_alias=_alias("backoff_factor", "LANGGRAPH_RETRY_BACKOFF"),
        description="退避因子（每次重试延迟翻倍）",
    )
    max_delay: float = Field(
        default=10.0,
        validation_alias=_alias("max_delay", "LANGGRAPH_RETRY_MAX_DELAY"),
        description="最大延迟时间（秒）",
    )


class DataStoreConfig(_BaseLangGraphSettings):
    """数据存储配置"""

    max_items: int = Field(
        default=1000,
        validation_alias=_alias("max_items", "LANGGRAPH_STORE_MAX_ITEMS"),
        description="内存存储最大项目数（LRU 淘汰）",
    )
    ttl_seconds: int = Field(
        default=3600,
        validation_alias=_alias("ttl_seconds", "LANGGRAPH_STORE_TTL"),
        description="数据存活时间（秒），0 表示永不过期",
    )
    summary_max_chars: int = Field(
        default=320,
        validation_alias=_alias("summary_max_chars", "LANGGRAPH_SUMMARY_MAX_CHARS"),
        description="摘要最大字符数",
    )


class NoteSearchConfig(_BaseLangGraphSettings):
    """笔记搜索配置"""

    snippet_radius: int = Field(
        default=120,
        validation_alias=_alias("snippet_radius", "LANGGRAPH_SNIPPET_RADIUS"),
        description="摘要半径（字符数）",
    )
    default_top_k: int = Field(
        default=5,
        validation_alias=_alias("default_top_k", "LANGGRAPH_NOTE_TOP_K"),
        description="默认返回结果数",
    )
    encoding: str = Field(
        default="utf-8",
        validation_alias=_alias("encoding", "LANGGRAPH_NOTE_ENCODING"),
        description="文件编码",
    )


class ExecutionConfig(_BaseLangGraphSettings):
    """运行时执行配置"""

    recursion_limit: int = Field(
        default=60,
        validation_alias=_alias("recursion_limit", "LANGGRAPH_RECURSION_LIMIT"),
        description="LangGraph 单次执行允许的最大步骤数",
    )


class LangGraphConfig(BaseModel):
    """LangGraph Agents 全局配置"""

    llm_retry: LLMRetryConfig = Field(default_factory=LLMRetryConfig)
    data_store: DataStoreConfig = Field(default_factory=DataStoreConfig)
    note_search: NoteSearchConfig = Field(default_factory=NoteSearchConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)

    @classmethod
    def default(cls) -> "LangGraphConfig":
        """获取默认配置（自动读取 .env/环境变量）。"""
        return cls()

    @classmethod
    def from_env(cls) -> "LangGraphConfig":
        """兼容旧 API，等价于 default()。"""
        return cls()
