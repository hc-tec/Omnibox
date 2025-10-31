"""
Integration层 - 数据访问层
职责：处理所有外部I/O操作（RSSHub调用、缓存、会话存储等）
"""

from .data_executor import DataExecutor, FeedItem, FetchResult

__all__ = ["DataExecutor", "FeedItem", "FetchResult"]
