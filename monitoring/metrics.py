"""
运维监控模块
提供统一的日志格式和统计指标收集
"""

import logging
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock


logger = logging.getLogger(__name__)


@dataclass
class MetricsCollector:
    """
    指标收集器

    收集关键运维指标：
    - 缓存命中率（RAG/RSS）
    - RSSHub降级次数
    - API响应耗时
    - 错误统计
    """

    # RAG缓存统计
    rag_cache_hits: int = 0
    rag_cache_misses: int = 0

    # RSS缓存统计
    rss_cache_hits: int = 0
    rss_cache_misses: int = 0

    # RSSHub统计
    rsshub_local_success: int = 0
    rsshub_local_failure: int = 0
    rsshub_fallback_success: int = 0
    rsshub_fallback_failure: int = 0

    # API统计
    api_requests: int = 0
    api_success: int = 0
    api_errors: int = 0

    # WebSocket统计
    ws_connections: int = 0
    ws_messages_sent: int = 0
    ws_errors: int = 0

    # 响应耗时统计（秒）
    response_times: list = field(default_factory=list)

    # 线程安全锁
    _lock: Lock = field(default_factory=Lock, repr=False)

    # 开始时间
    start_time: float = field(default_factory=time.time)

    def record_rag_cache_hit(self):
        """记录RAG缓存命中"""
        with self._lock:
            self.rag_cache_hits += 1

    def record_rag_cache_miss(self):
        """记录RAG缓存未命中"""
        with self._lock:
            self.rag_cache_misses += 1

    def record_rss_cache_hit(self):
        """记录RSS缓存命中"""
        with self._lock:
            self.rss_cache_hits += 1

    def record_rss_cache_miss(self):
        """记录RSS缓存未命中"""
        with self._lock:
            self.rss_cache_misses += 1

    def record_rsshub_local_success(self):
        """记录本地RSSHub成功"""
        with self._lock:
            self.rsshub_local_success += 1

    def record_rsshub_local_failure(self):
        """记录本地RSSHub失败"""
        with self._lock:
            self.rsshub_local_failure += 1

    def record_rsshub_fallback_success(self):
        """记录降级RSSHub成功"""
        with self._lock:
            self.rsshub_fallback_success += 1

    def record_rsshub_fallback_failure(self):
        """记录降级RSSHub失败"""
        with self._lock:
            self.rsshub_fallback_failure += 1

    def record_api_request(self, success: bool = True):
        """记录API请求"""
        with self._lock:
            self.api_requests += 1
            if success:
                self.api_success += 1
            else:
                self.api_errors += 1

    def record_ws_connection(self):
        """记录WebSocket连接"""
        with self._lock:
            self.ws_connections += 1

    def record_ws_message(self):
        """记录WebSocket消息"""
        with self._lock:
            self.ws_messages_sent += 1

    def record_ws_error(self):
        """记录WebSocket错误"""
        with self._lock:
            self.ws_errors += 1

    def record_response_time(self, duration: float):
        """
        记录响应时间

        Args:
            duration: 响应耗时（秒）
        """
        with self._lock:
            self.response_times.append(duration)
            # 保留最近1000条记录
            if len(self.response_times) > 1000:
                self.response_times = self.response_times[-1000:]

    @property
    def rag_cache_hit_rate(self) -> float:
        """RAG缓存命中率"""
        total = self.rag_cache_hits + self.rag_cache_misses
        return self.rag_cache_hits / total if total > 0 else 0.0

    @property
    def rss_cache_hit_rate(self) -> float:
        """RSS缓存命中率"""
        total = self.rss_cache_hits + self.rss_cache_misses
        return self.rss_cache_hits / total if total > 0 else 0.0

    @property
    def rsshub_fallback_rate(self) -> float:
        """RSSHub降级率"""
        total_success = self.rsshub_local_success + self.rsshub_fallback_success
        return self.rsshub_fallback_success / total_success if total_success > 0 else 0.0

    @property
    def api_success_rate(self) -> float:
        """API成功率"""
        return self.api_success / self.api_requests if self.api_requests > 0 else 0.0

    @property
    def avg_response_time(self) -> float:
        """平均响应时间（秒）"""
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0

    @property
    def p95_response_time(self) -> float:
        """P95响应时间（秒）"""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx] if idx < len(sorted_times) else sorted_times[-1]

    @property
    def uptime_seconds(self) -> float:
        """运行时长（秒）"""
        return time.time() - self.start_time

    def get_summary(self) -> Dict[str, Any]:
        """
        获取统计摘要

        Returns:
            统计摘要字典
        """
        with self._lock:
            return {
                "uptime_seconds": self.uptime_seconds,
                "uptime_hours": self.uptime_seconds / 3600,
                "cache": {
                    "rag_hit_rate": f"{self.rag_cache_hit_rate:.2%}",
                    "rag_hits": self.rag_cache_hits,
                    "rag_misses": self.rag_cache_misses,
                    "rss_hit_rate": f"{self.rss_cache_hit_rate:.2%}",
                    "rss_hits": self.rss_cache_hits,
                    "rss_misses": self.rss_cache_misses,
                },
                "rsshub": {
                    "fallback_rate": f"{self.rsshub_fallback_rate:.2%}",
                    "local_success": self.rsshub_local_success,
                    "local_failure": self.rsshub_local_failure,
                    "fallback_success": self.rsshub_fallback_success,
                    "fallback_failure": self.rsshub_fallback_failure,
                },
                "api": {
                    "total_requests": self.api_requests,
                    "success_rate": f"{self.api_success_rate:.2%}",
                    "success_count": self.api_success,
                    "error_count": self.api_errors,
                },
                "websocket": {
                    "connections": self.ws_connections,
                    "messages_sent": self.ws_messages_sent,
                    "errors": self.ws_errors,
                },
                "performance": {
                    "avg_response_time": f"{self.avg_response_time:.3f}s",
                    "p95_response_time": f"{self.p95_response_time:.3f}s",
                    "sample_count": len(self.response_times),
                }
            }

    def reset(self):
        """重置所有统计"""
        with self._lock:
            self.rag_cache_hits = 0
            self.rag_cache_misses = 0
            self.rss_cache_hits = 0
            self.rss_cache_misses = 0
            self.rsshub_local_success = 0
            self.rsshub_local_failure = 0
            self.rsshub_fallback_success = 0
            self.rsshub_fallback_failure = 0
            self.api_requests = 0
            self.api_success = 0
            self.api_errors = 0
            self.ws_connections = 0
            self.ws_messages_sent = 0
            self.ws_errors = 0
            self.response_times.clear()
            self.start_time = time.time()


# 全局指标收集器实例
_global_metrics: Optional[MetricsCollector] = None
_metrics_lock = Lock()


def get_metrics_collector() -> MetricsCollector:
    """
    获取全局指标收集器实例（单例模式）

    Returns:
        MetricsCollector实例
    """
    global _global_metrics
    if _global_metrics is None:
        with _metrics_lock:
            if _global_metrics is None:
                _global_metrics = MetricsCollector()
                logger.info("✓ MetricsCollector初始化完成")
    return _global_metrics


def log_rsshub_switch(
    from_source: str,
    to_source: str,
    reason: str,
    path: Optional[str] = None
):
    """
    记录RSSHub源切换日志（统一格式）

    Args:
        from_source: 原来源（local/fallback）
        to_source: 目标来源（local/fallback）
        reason: 切换原因
        path: RSS路径（可选）
    """
    logger.warning(
        f"[RSSHub切换] {from_source} → {to_source} | 原因: {reason}" +
        (f" | 路径: {path}" if path else "")
    )


def log_rsshub_error(
    source: str,
    error_type: str,
    error_message: str,
    path: Optional[str] = None,
    status_code: Optional[int] = None
):
    """
    记录RSSHub错误日志（统一格式）

    Args:
        source: 来源（local/fallback）
        error_type: 错误类型（http_error/request_error/parse_error等）
        error_message: 错误描述
        path: RSS路径（可选）
        status_code: HTTP状态码（可选）
    """
    logger.error(
        f"[RSSHub错误] 来源: {source} | 类型: {error_type} | " +
        f"错误: {error_message}" +
        (f" | HTTP: {status_code}" if status_code else "") +
        (f" | 路径: {path}" if path else "")
    )


def log_cache_event(
    cache_type: str,
    event_type: str,
    key: str,
    hit: bool = False,
    ttl: Optional[int] = None
):
    """
    记录缓存事件日志（统一格式）

    Args:
        cache_type: 缓存类型（rag/rss/llm）
        event_type: 事件类型（hit/miss/set/expire/clear）
        key: 缓存键
        hit: 是否命中（可选）
        ttl: TTL时间（秒，可选）
    """
    level = logging.DEBUG if event_type in ["hit", "miss"] else logging.INFO
    logger.log(
        level,
        f"[缓存事件] 类型: {cache_type} | 事件: {event_type} | " +
        f"键: {key[:50]}..." if len(key) > 50 else key +
        (f" | 命中: {hit}" if event_type in ["hit", "miss"] else "") +
        (f" | TTL: {ttl}s" if ttl else "")
    )


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    duration: float,
    user_agent: Optional[str] = None,
    error: Optional[str] = None
):
    """
    记录API请求日志（统一格式）

    Args:
        method: HTTP方法
        path: 请求路径
        status_code: 响应状态码
        duration: 处理耗时（秒）
        user_agent: 用户代理（可选）
        error: 错误信息（可选）
    """
    level = logging.ERROR if status_code >= 500 else (
        logging.WARNING if status_code >= 400 else logging.INFO
    )
    logger.log(
        level,
        f"[API请求] {method} {path} | " +
        f"状态: {status_code} | 耗时: {duration:.3f}s" +
        (f" | 错误: {error}" if error else "") +
        (f" | UA: {user_agent[:50]}" if user_agent else "")
    )


def log_websocket_event(
    stream_id: str,
    event_type: str,
    message: str,
    error: Optional[str] = None
):
    """
    记录WebSocket事件日志（统一格式）

    Args:
        stream_id: 流ID
        event_type: 事件类型（connect/disconnect/message/error）
        message: 事件描述
        error: 错误信息（可选）
    """
    level = logging.ERROR if event_type == "error" else logging.INFO
    logger.log(
        level,
        f"[WebSocket] [{stream_id}] {event_type} | {message}" +
        (f" | 错误: {error}" if error else "")
    )
