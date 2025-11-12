from __future__ import annotations

"""
外部数据存储抽象。

LangGraph 状态机不再直接持久化原始数据，而是写入一个轻量存储并只保留引用。
此处默认提供线程安全的内存实现，支持 LRU 淘汰和 TTL 过期。
"""

from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, Dict, Optional
from uuid import uuid4
import threading
import time


class ResearchDataStore(ABC):
    """抽象数据存储接口。"""

    @abstractmethod
    def save(self, payload: Any) -> str:
        """写入原始数据，返回 data_id。"""

    @abstractmethod
    def load(self, data_id: str) -> Optional[Any]:
        """根据 data_id 读取原始数据。"""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """返回调试友好的统计信息。"""

    def clear(self) -> None:
        """清空所有数据（可选实现）"""
        pass


class InMemoryResearchDataStore(ResearchDataStore):
    """
    线程安全的内存实现，支持 LRU 淘汰和 TTL 过期。

    特性：
    - LRU (Least Recently Used): 达到容量上限时淘汰最少使用的数据
    - TTL (Time To Live): 数据自动过期
    - 线程安全: 使用 RLock 保护
    - 适合本地开发/单进程测试

    可通过实现 ResearchDataStore 接口平滑迁移至 Redis/S3。
    """

    def __init__(self, max_items: int = 1000, ttl_seconds: int = 3600):
        """
        初始化内存存储。

        Args:
            max_items: 最大存储项目数，超过后使用 LRU 淘汰
            ttl_seconds: 数据存活时间（秒），0 表示永不过期
        """
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._lock = threading.RLock()
        self._max_items = max_items
        self._ttl_seconds = ttl_seconds

    def save(self, payload: Any) -> str:
        """
        保存数据，自动处理 LRU 淘汰。

        Args:
            payload: 要保存的数据

        Returns:
            data_id: 数据唯一标识
        """
        data_id = f"lg-{uuid4().hex}"
        with self._lock:
            # 检查是否需要淘汰
            if len(self._store) >= self._max_items:
                # 淘汰最旧的项（OrderedDict 保持插入顺序）
                oldest_id, _ = self._store.popitem(last=False)
                self._timestamps.pop(oldest_id, None)

            # 保存新数据
            self._store[data_id] = payload
            if self._ttl_seconds > 0:
                self._timestamps[data_id] = time.time()

        return data_id

    def load(self, data_id: str) -> Optional[Any]:
        """
        加载数据，自动检查 TTL 过期。

        Args:
            data_id: 数据标识

        Returns:
            数据内容，如果不存在或已过期返回 None
        """
        with self._lock:
            # 检查是否存在
            if data_id not in self._store:
                return None

            # 检查是否过期
            if self._ttl_seconds > 0:
                timestamp = self._timestamps.get(data_id)
                if timestamp and (time.time() - timestamp > self._ttl_seconds):
                    # 已过期，删除
                    self._store.pop(data_id, None)
                    self._timestamps.pop(data_id, None)
                    return None

            # 更新访问顺序（LRU）
            self._store.move_to_end(data_id)
            return self._store[data_id]

    def stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息。

        Returns:
            包含项目数、配置等信息的字典
        """
        with self._lock:
            return {
                "items": len(self._store),
                "max_items": self._max_items,
                "ttl_seconds": self._ttl_seconds,
                "lru_enabled": self._max_items > 0,
                "ttl_enabled": self._ttl_seconds > 0,
            }

    def clear(self) -> None:
        """清空所有数据"""
        with self._lock:
            self._store.clear()
            self._timestamps.clear()

    def cleanup_expired(self) -> int:
        """
        主动清理过期数据（可选调用）。

        Returns:
            清理的项目数
        """
        if self._ttl_seconds <= 0:
            return 0

        with self._lock:
            now = time.time()
            expired_ids = [
                data_id
                for data_id, timestamp in self._timestamps.items()
                if now - timestamp > self._ttl_seconds
            ]

            for data_id in expired_ids:
                self._store.pop(data_id, None)
                self._timestamps.pop(data_id, None)

            return len(expired_ids)

