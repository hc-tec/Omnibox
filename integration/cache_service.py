"""
缓存服务 - TTL缓存管理
职责：
1. 提供线程安全的TTL缓存
2. 支持不同类型的缓存（RSS数据、RAG结果、LLM解析结果）
3. 提供缓存统计和管理功能
"""

import threading
import logging
from typing import Any, Optional, Dict, List
from cachetools import TTLCache
import hashlib
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class CacheService:
    """
    TTL缓存服务（线程安全）

    支持不同类型的缓存，每种缓存有独立的TTL：
    - RSS数据缓存：TTL 10分钟（避免频繁请求RSSHub）
    - RAG检索结果缓存：TTL 1小时（相同查询不重复计算）
    - LLM解析结果缓存：TTL 1小时（避免重复LLM调用）

    使用示例：
        cache = CacheService()

        # RSS缓存
        cache.set_rss_cache("/hupu/bbs/bxj/1", data)
        data = cache.get_rss_cache("/hupu/bbs/bxj/1")

        # RAG缓存
        cache.set_rag_cache("虎扑步行街", rag_result)
        result = cache.get_rag_cache("虎扑步行街")

        # 统计信息
        stats = cache.get_stats()
    """

    def __init__(
        self,
        rss_cache_maxsize: int = 100,
        rss_cache_ttl: int = 600,  # 10分钟
        rag_cache_maxsize: int = 500,
        rag_cache_ttl: int = 3600,  # 1小时
        llm_cache_maxsize: int = 500,
        llm_cache_ttl: int = 3600,  # 1小时
    ):
        """
        初始化缓存服务

        Args:
            rss_cache_maxsize: RSS缓存最大条目数
            rss_cache_ttl: RSS缓存TTL（秒）
            rag_cache_maxsize: RAG缓存最大条目数
            rag_cache_ttl: RAG缓存TTL（秒）
            llm_cache_maxsize: LLM缓存最大条目数
            llm_cache_ttl: LLM缓存TTL（秒）
        """
        # RSS数据缓存 - TTL 10分钟
        self.rss_cache = TTLCache(maxsize=rss_cache_maxsize, ttl=rss_cache_ttl)
        self.rss_lock = threading.RLock()
        self._rss_hits = 0
        self._rss_misses = 0

        # RAG检索结果缓存 - TTL 1小时
        self.rag_cache = TTLCache(maxsize=rag_cache_maxsize, ttl=rag_cache_ttl)
        self.rag_lock = threading.RLock()
        self._rag_hits = 0
        self._rag_misses = 0

        # LLM解析结果缓存 - TTL 1小时
        self.llm_cache = TTLCache(maxsize=llm_cache_maxsize, ttl=llm_cache_ttl)
        self.llm_lock = threading.RLock()
        self._llm_hits = 0
        self._llm_misses = 0

        logger.info(
            f"缓存服务初始化完成: "
            f"RSS={rss_cache_maxsize}条/{rss_cache_ttl}s, "
            f"RAG={rag_cache_maxsize}条/{rag_cache_ttl}s, "
            f"LLM={llm_cache_maxsize}条/{llm_cache_ttl}s"
        )

    def _generate_key(self, *args, **kwargs) -> str:
        """
        生成缓存键（基于参数哈希）

        确保相同参数总是生成相同的key，不同参数生成不同key
        """
        try:
            # 对参数进行JSON序列化，确保一致性
            key_data = json.dumps(
                [args, sorted(kwargs.items())],
                sort_keys=True,
                ensure_ascii=True
            )
            return hashlib.md5(key_data.encode('utf-8')).hexdigest()
        except (TypeError, ValueError) as e:
            # 如果参数不可序列化，使用字符串表示
            logger.warning(f"缓存键生成失败，使用备用方案: {e}")
            key_str = f"{args}_{sorted(kwargs.items())}"
            return hashlib.md5(key_str.encode('utf-8')).hexdigest()

    # ==================== RSS缓存方法 ====================

    def get_rss_cache(self, path: str) -> Optional[Any]:
        """
        获取RSS缓存

        Args:
            path: RSSHub路径

        Returns:
            缓存的数据，如果不存在返回None
        """
        with self.rss_lock:
            key = path
            value = self.rss_cache.get(key)

            if value is not None:
                self._rss_hits += 1
                logger.debug(f"RSS缓存命中: {path}")
            else:
                self._rss_misses += 1
                logger.debug(f"RSS缓存未命中: {path}")

            return value

    def set_rss_cache(self, path: str, value: Any) -> None:
        """
        设置RSS缓存

        Args:
            path: RSSHub路径
            value: 要缓存的数据
        """
        with self.rss_lock:
            key = path
            self.rss_cache[key] = value
            logger.debug(f"RSS缓存写入: {path}")

    def invalidate_rss_cache(self, path: str) -> bool:
        """
        使指定RSS缓存失效

        Args:
            path: RSSHub路径

        Returns:
            是否成功删除缓存
        """
        with self.rss_lock:
            key = path
            if key in self.rss_cache:
                del self.rss_cache[key]
                logger.debug(f"RSS缓存失效: {path}")
                return True
            return False

    # ==================== RAG缓存方法 ====================

    def get_rag_cache(self, query: str, **kwargs) -> Optional[Any]:
        """
        获取RAG检索结果缓存

        Args:
            query: 用户查询
            **kwargs: 额外的查询参数（如top_k、filter等）

        Returns:
            缓存的RAG结果，如果不存在返回None
        """
        with self.rag_lock:
            key = self._generate_key("rag", query, **kwargs)
            value = self.rag_cache.get(key)

            if value is not None:
                self._rag_hits += 1
                logger.debug(f"RAG缓存命中: {query[:50]}...")
            else:
                self._rag_misses += 1
                logger.debug(f"RAG缓存未命中: {query[:50]}...")

            return value

    def set_rag_cache(self, query: str, value: Any, **kwargs) -> None:
        """
        设置RAG检索结果缓存

        Args:
            query: 用户查询
            value: RAG检索结果
            **kwargs: 额外的查询参数
        """
        with self.rag_lock:
            key = self._generate_key("rag", query, **kwargs)
            self.rag_cache[key] = value
            logger.debug(f"RAG缓存写入: {query[:50]}...")

    # ==================== LLM缓存方法 ====================

    def get_llm_cache(self, prompt: str, **kwargs) -> Optional[Any]:
        """
        获取LLM解析结果缓存

        Args:
            prompt: LLM的prompt
            **kwargs: LLM参数（如temperature、model等）

        Returns:
            缓存的LLM结果，如果不存在返回None
        """
        with self.llm_lock:
            key = self._generate_key("llm", prompt, **kwargs)
            value = self.llm_cache.get(key)

            if value is not None:
                self._llm_hits += 1
                logger.debug(f"LLM缓存命中: {prompt[:50]}...")
            else:
                self._llm_misses += 1
                logger.debug(f"LLM缓存未命中: {prompt[:50]}...")

            return value

    def set_llm_cache(self, prompt: str, value: Any, **kwargs) -> None:
        """
        设置LLM解析结果缓存

        Args:
            prompt: LLM的prompt
            value: LLM生成结果
            **kwargs: LLM参数
        """
        with self.llm_lock:
            key = self._generate_key("llm", prompt, **kwargs)
            self.llm_cache[key] = value
            logger.debug(f"LLM缓存写入: {prompt[:50]}...")

    # ==================== 管理方法 ====================

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存���计信息

        Returns:
            包含缓存大小、命中率等统计信息的字典
        """
        # 计算命中率
        rss_total = self._rss_hits + self._rss_misses
        rag_total = self._rag_hits + self._rag_misses
        llm_total = self._llm_hits + self._llm_misses

        stats = {
            # 当前缓存大小
            "rss_cache_size": len(self.rss_cache),
            "rag_cache_size": len(self.rag_cache),
            "llm_cache_size": len(self.llm_cache),
            "total_cache_size": len(self.rss_cache) + len(self.rag_cache) + len(self.llm_cache),

            # 命中统计
            "rss_hits": self._rss_hits,
            "rss_misses": self._rss_misses,
            "rag_hits": self._rag_hits,
            "rag_misses": self._rag_misses,
            "llm_hits": self._llm_hits,
            "llm_misses": self._llm_misses,

            # 命中率
            "rss_hit_rate": self._rss_hits / rss_total if rss_total > 0 else 0.0,
            "rag_hit_rate": self._rag_hits / rag_total if rag_total > 0 else 0.0,
            "llm_hit_rate": self._llm_hits / llm_total if llm_total > 0 else 0.0,
            "overall_hit_rate": (
                (self._rss_hits + self._rag_hits + self._llm_hits) /
                (rss_total + rag_total + llm_total)
                if (rss_total + rag_total + llm_total) > 0 else 0.0
            ),
        }

        return stats

    def clear_all(self) -> None:
        """清空所有缓存"""
        with self.rss_lock, self.rag_lock, self.llm_lock:
            total_before = len(self.rss_cache) + len(self.rag_cache) + len(self.llm_cache)

            self.rss_cache.clear()
            self.rag_cache.clear()
            self.llm_cache.clear()

            # 重置统计
            self._rss_hits = self._rss_misses = 0
            self._rag_hits = self._rag_misses = 0
            self._llm_hits = self._llm_misses = 0

            logger.info(f"所有缓存已清空，共清除 {total_before} 条记录")

    def clear_expired(self) -> int:
        """
        清理过期缓存项

        TTLCache会自动清理过期项，但这里提供手动清理接口
        """
        cleaned_total = 0

        with self.rss_lock:
            before = len(self.rss_cache)
            self.rss_cache.expire()
            after = len(self.rss_cache)
            cleaned_total += before - after

        with self.rag_lock:
            before = len(self.rag_cache)
            self.rag_cache.expire()
            after = len(self.rag_cache)
            cleaned_total += before - after

        with self.llm_lock:
            before = len(self.llm_cache)
            self.llm_cache.expire()
            after = len(self.llm_cache)
            cleaned_total += before - after

        if cleaned_total > 0:
            logger.debug(f"清理了 {cleaned_total} 条过期缓存")

        return cleaned_total


# 全局单例
_cache_service: Optional[CacheService] = None
_cache_lock = threading.Lock()


def get_cache_service() -> CacheService:
    """
    获取缓存服务单例

    Returns:
        全局唯一的CacheService实例
    """
    global _cache_service
    if _cache_service is None:
        with _cache_lock:
            if _cache_service is None:
                _cache_service = CacheService()
                logger.info("创建全局缓存服务实例")
    return _cache_service


def reset_cache_service() -> None:
    """
    重置全局缓存服务实例（主要用于测试）
    """
    global _cache_service
    with _cache_lock:
        if _cache_service is not None:
            _cache_service.clear_all()
            _cache_service = None
            logger.info("重置全局缓存服务实例")
