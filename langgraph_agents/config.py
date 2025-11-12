"""LangGraph Agents 配置管理

集中管理所有配置项，避免硬编码 magic numbers。
支持环境变量覆盖。
"""
import os
from dataclasses import dataclass


@dataclass
class LLMRetryConfig:
    """LLM 重试配置"""

    max_retries: int = 3
    """最大重试次数"""

    initial_delay: float = 1.0
    """首次重试延迟（秒）"""

    backoff_factor: float = 2.0
    """退避因子（每次重试延迟翻倍）"""

    max_delay: float = 10.0
    """最大延迟时间（秒）"""

    @classmethod
    def from_env(cls) -> "LLMRetryConfig":
        """从环境变量加载配置"""
        return cls(
            max_retries=int(os.getenv("LANGGRAPH_RETRY_MAX", "3")),
            initial_delay=float(os.getenv("LANGGRAPH_RETRY_INITIAL_DELAY", "1.0")),
            backoff_factor=float(os.getenv("LANGGRAPH_RETRY_BACKOFF", "2.0")),
            max_delay=float(os.getenv("LANGGRAPH_RETRY_MAX_DELAY", "10.0")),
        )


@dataclass
class DataStoreConfig:
    """数据存储配置"""

    max_items: int = 1000
    """内存存储最大项目数（LRU淘汰）"""

    ttl_seconds: int = 3600
    """数据存活时间（秒），0表示永不过期"""

    summary_max_chars: int = 320
    """摘要最大字符数"""

    @classmethod
    def from_env(cls) -> "DataStoreConfig":
        """从环境变量加载配置"""
        return cls(
            max_items=int(os.getenv("LANGGRAPH_STORE_MAX_ITEMS", "1000")),
            ttl_seconds=int(os.getenv("LANGGRAPH_STORE_TTL", "3600")),
            summary_max_chars=int(os.getenv("LANGGRAPH_SUMMARY_MAX_CHARS", "320")),
        )


@dataclass
class NoteSearchConfig:
    """笔记搜索配置"""

    snippet_radius: int = 120
    """摘要半径（字符数）"""

    default_top_k: int = 5
    """默认返回结果数"""

    encoding: str = "utf-8"
    """文件编码"""

    @classmethod
    def from_env(cls) -> "NoteSearchConfig":
        """从环境变量加载配置"""
        return cls(
            snippet_radius=int(os.getenv("LANGGRAPH_SNIPPET_RADIUS", "120")),
            default_top_k=int(os.getenv("LANGGRAPH_NOTE_TOP_K", "5")),
            encoding=os.getenv("LANGGRAPH_NOTE_ENCODING", "utf-8"),
        )


@dataclass
class LangGraphConfig:
    """LangGraph Agents 全局配置"""

    llm_retry: LLMRetryConfig
    data_store: DataStoreConfig
    note_search: NoteSearchConfig

    @classmethod
    def default(cls) -> "LangGraphConfig":
        """获取默认配置"""
        return cls(
            llm_retry=LLMRetryConfig(),
            data_store=DataStoreConfig(),
            note_search=NoteSearchConfig(),
        )

    @classmethod
    def from_env(cls) -> "LangGraphConfig":
        """从环境变量加载配置"""
        return cls(
            llm_retry=LLMRetryConfig.from_env(),
            data_store=DataStoreConfig.from_env(),
            note_search=NoteSearchConfig.from_env(),
        )


# 全局默认配置实例
default_config = LangGraphConfig.default()
