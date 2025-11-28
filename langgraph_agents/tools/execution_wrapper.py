"""
工具执行包装器 - 提供超时和容错机制。

V6.0 Phase 2.3: 为工具执行添加：
1. 超时控制
2. 重试机制（指数退避）
3. 优雅的错误处理
"""

from __future__ import annotations

import logging
import signal
import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from functools import wraps
from typing import Callable, Optional, Tuple, Type, TypeVar, Any

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext

logger = logging.getLogger(__name__)

T = TypeVar("T")


# 可重试的异常类型
TOOL_RETRIABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


class ToolExecutionError(Exception):
    """工具执行错误基类。"""
    pass


class ToolTimeoutError(ToolExecutionError):
    """工具执行超时错误。"""

    def __init__(self, plugin_id: str, timeout: float):
        super().__init__(f"工具 {plugin_id} 执行超时（超过 {timeout} 秒）")
        self.plugin_id = plugin_id
        self.timeout = timeout


class ToolRetryExhaustedError(ToolExecutionError):
    """工具重试耗尽错误。"""

    def __init__(self, plugin_id: str, attempts: int, last_exception: Exception):
        super().__init__(
            f"工具 {plugin_id} 在 {attempts} 次尝试后仍然失败"
        )
        self.plugin_id = plugin_id
        self.attempts = attempts
        self.last_exception = last_exception


def is_tool_retriable_error(exc: Exception) -> bool:
    """
    判断工具执行异常是否可重试。

    可重试错误：
    - 网络错误（ConnectionError, TimeoutError）
    - 临时服务错误
    - 超时错误

    不可重试错误：
    - 参数验证错误
    - 权限错误
    - 数据格式错误
    """
    if isinstance(exc, TOOL_RETRIABLE_EXCEPTIONS):
        return True

    if isinstance(exc, ToolTimeoutError):
        return True

    # 检查异常消息中的关键词
    exc_msg = str(exc).lower()
    retriable_keywords = [
        "timeout",
        "connection",
        "network",
        "temporary",
        "unavailable",
        "503",
        "504",
        "502",
    ]

    return any(keyword in exc_msg for keyword in retriable_keywords)


def with_timeout(
    timeout_seconds: float,
    plugin_id: str = "unknown",
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    工具执行超时装饰器。

    使用线程池实现超时控制（Windows 兼容）。

    Args:
        timeout_seconds: 超时时间（秒）
        plugin_id: 工具ID（用于错误消息）

    Example:
        @with_timeout(30.0, "fetch_public_data")
        def fetch_data(call, context):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # 使用线程池执行，支持超时
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout_seconds)
                except FuturesTimeoutError:
                    logger.error(
                        "工具 %s 执行超时（%s 秒）",
                        plugin_id, timeout_seconds
                    )
                    raise ToolTimeoutError(plugin_id, timeout_seconds)

        return wrapper

    return decorator


def with_retry(
    max_retries: int = 2,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    max_delay: float = 5.0,
    plugin_id: str = "unknown",
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    工具执行重试装饰器，使用指数退避策略。

    Args:
        max_retries: 最大重试次数（不包括首次调用）
        initial_delay: 首次重试延迟（秒）
        backoff_factor: 退避因子
        max_delay: 最大延迟时间（秒）
        plugin_id: 工具ID（用于日志）

    Example:
        @with_retry(max_retries=2, plugin_id="fetch_public_data")
        def fetch_data(call, context):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # 如果不重试，直接执行
            if max_retries <= 0:
                return func(*args, **kwargs)

            last_exception: Optional[Exception] = None
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except Exception as exc:
                    last_exception = exc

                    # 最后一次尝试，不再重试
                    if attempt == max_retries:
                        logger.error(
                            "工具 %s 失败，已达最大重试次数 %d",
                            plugin_id, max_retries
                        )
                        raise ToolRetryExhaustedError(
                            plugin_id, attempt + 1, exc
                        ) from exc

                    # 判断是否可重试
                    if not is_tool_retriable_error(exc):
                        logger.warning(
                            "工具 %s 遇到不可重试错误: %s: %s",
                            plugin_id, type(exc).__name__, exc
                        )
                        raise

                    # 记录重试信息
                    logger.warning(
                        "工具 %s 调用失败（尝试 %d/%d），%.1f秒后重试。错误: %s: %s",
                        plugin_id,
                        attempt + 1,
                        max_retries + 1,
                        delay,
                        type(exc).__name__,
                        exc
                    )

                    # 等待后重试
                    time.sleep(delay)

                    # 计算下次延迟（指数退避）
                    delay = min(delay * backoff_factor, max_delay)

            # 理论上不会到这里
            raise ToolRetryExhaustedError(
                plugin_id,
                max_retries + 1,
                last_exception or Exception("Unknown error"),
            )

        return wrapper

    return decorator


class ToolExecutionWrapper:
    """
    工具执行包装器类。

    提供统一的执行接口，集成超时和重试机制。

    Example:
        wrapper = ToolExecutionWrapper(
            default_timeout=30.0,
            default_retries=2,
        )
        payload = wrapper.execute(handler, call, context)
    """

    # 工具特定的超时配置
    TOOL_TIMEOUTS = {
        "fetch_public_data": 60.0,  # 网络请求可能较慢
        "search_private_notes": 30.0,
        "filter_data": 30.0,
        "aggregate_data": 30.0,
        "compare_data": 45.0,  # 可能涉及 LLM 调用
        "extract_insights": 60.0,  # LLM 调用
        "ask_user_clarification": 5.0,  # 快速返回
        "discover_sources": 30.0,
    }

    # 工具特定的重试配置
    TOOL_RETRIES = {
        "fetch_public_data": 3,  # 网络请求多重试
        "search_private_notes": 1,
        "filter_data": 0,  # 纯计算，不重试
        "aggregate_data": 0,
        "compare_data": 1,
        "extract_insights": 2,
        "ask_user_clarification": 0,
        "discover_sources": 2,
    }

    def __init__(
        self,
        default_timeout: float = 30.0,
        default_retries: int = 1,
    ):
        """
        初始化包装器。

        Args:
            default_timeout: 默认超时时间（秒）
            default_retries: 默认重试次数
        """
        self.default_timeout = default_timeout
        self.default_retries = default_retries

    def get_timeout(self, plugin_id: str) -> float:
        """获取工具的超时配置。"""
        return self.TOOL_TIMEOUTS.get(plugin_id, self.default_timeout)

    def get_retries(self, plugin_id: str) -> int:
        """获取工具的重试配置。"""
        return self.TOOL_RETRIES.get(plugin_id, self.default_retries)

    def execute(
        self,
        handler: Callable[[ToolCall, ToolExecutionContext], ToolExecutionPayload],
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        """
        执行工具，带超时和重试。

        Args:
            handler: 工具处理函数
            call: 工具调用
            context: 执行上下文

        Returns:
            ToolExecutionPayload
        """
        plugin_id = call.plugin_id
        timeout = self.get_timeout(plugin_id)
        max_retries = self.get_retries(plugin_id)

        logger.info(
            "执行工具: %s (timeout=%.1fs, retries=%d)",
            plugin_id, timeout, max_retries
        )

        # 包装处理函数
        @with_retry(max_retries=max_retries, plugin_id=plugin_id)
        @with_timeout(timeout, plugin_id)
        def wrapped_handler() -> ToolExecutionPayload:
            return handler(call, context)

        try:
            start_time = time.time()
            result = wrapped_handler()
            elapsed = time.time() - start_time

            logger.info(
                "工具 %s 执行成功 (耗时 %.2fs)",
                plugin_id, elapsed
            )

            return result

        except ToolTimeoutError as e:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "error",
                    "error_code": "E601",
                    "error_type": "timeout",
                },
                status="error",
                error_message=str(e),
            )

        except ToolRetryExhaustedError as e:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "error",
                    "error_code": "E602",
                    "error_type": "retry_exhausted",
                    "attempts": e.attempts,
                },
                status="error",
                error_message=str(e),
            )

        except Exception as e:
            logger.exception("工具 %s 执行失败: %s", plugin_id, e)
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "error",
                    "error_code": "E699",
                    "error_type": "unknown",
                },
                status="error",
                error_message=f"未预期的错误: {type(e).__name__}: {e}",
            )


# 全局包装器实例
default_wrapper = ToolExecutionWrapper()


def execute_with_protection(
    handler: Callable[[ToolCall, ToolExecutionContext], ToolExecutionPayload],
    call: ToolCall,
    context: ToolExecutionContext,
) -> ToolExecutionPayload:
    """
    使用默认包装器执行工具。

    这是一个便捷函数，使用全局默认配置。

    Args:
        handler: 工具处理函数
        call: 工具调用
        context: 执行上下文

    Returns:
        ToolExecutionPayload
    """
    return default_wrapper.execute(handler, call, context)
