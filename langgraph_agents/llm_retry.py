"""LLM 调用重试机制

提供装饰器和工具函数，用于处理 LLM 调用失败的情况。
支持指数退避重试策略。
"""
import logging
import time
from functools import wraps
from typing import Callable, Optional, Type, Tuple

logger = logging.getLogger(__name__)


# 可重试的异常类型
RETRIABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,  # 包括网络相关错误
)


class LLMRetryError(Exception):
    """LLM 重试失败后的最终异常"""

    def __init__(self, message: str, last_exception: Exception, attempts: int):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


def is_retriable_error(exc: Exception) -> bool:
    """
    判断异常是否可重试。

    可重试错误：
    - 网络错误（ConnectionError, TimeoutError）
    - 限流错误（通过异常消息判断）
    - 临时服务错误（5xx）

    不可重试错误：
    - 认证错误（401, 403）
    - 格式错误（400）
    - JSON 解析错误
    """
    if isinstance(exc, RETRIABLE_EXCEPTIONS):
        return True

    # 检查异常消息中的关键词
    exc_msg = str(exc).lower()
    retriable_keywords = [
        "timeout",
        "rate limit",
        "too many requests",
        "503",
        "504",
        "502",
        "connection",
        "network",
    ]

    return any(keyword in exc_msg for keyword in retriable_keywords)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 10.0,
    retriable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
):
    """
    LLM 调用重试装饰器，使用指数退避策略。

    Args:
        max_retries: 最大重试次数（不包括首次调用）
        initial_delay: 首次重试延迟（秒）
        backoff_factor: 退避因子（每次重试延迟翻倍）
        max_delay: 最大延迟时间（秒）
        retriable_exceptions: 自定义可重试异常类型

    Example:
        @retry_with_backoff(max_retries=3)
        def call_llm(prompt):
            return llm_client.generate(prompt)
    """
    if retriable_exceptions is None:
        retriable_exceptions = RETRIABLE_EXCEPTIONS

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = initial_delay

            # 首次调用 + max_retries 次重试
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except Exception as exc:
                    last_exception = exc

                    # 最后一次尝试，不再重试
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} 失败，已达最大重试次数 {max_retries}",
                            exc_info=True,
                        )
                        raise LLMRetryError(
                            f"LLM 调用在 {max_retries + 1} 次尝试后仍然失败",
                            last_exception,
                            attempt + 1,
                        ) from exc

                    # 判断是否可重试
                    if not is_retriable_error(exc):
                        logger.warning(
                            f"{func.__name__} 遇到不可重试错误: {type(exc).__name__}: {exc}"
                        )
                        raise

                    # 记录重试信息
                    logger.warning(
                        f"{func.__name__} 调用失败（尝试 {attempt + 1}/{max_retries + 1}），"
                        f"{delay:.1f}秒后重试。错误: {type(exc).__name__}: {exc}"
                    )

                    # 等待后重试
                    time.sleep(delay)

                    # 计算下次延迟（指数退避）
                    delay = min(delay * backoff_factor, max_delay)

            # 理论上不会到这里，但为了类型检查
            raise LLMRetryError(
                "意外的重试失败",
                last_exception or Exception("Unknown error"),
                max_retries + 1,
            )

        return wrapper

    return decorator


def call_llm_with_retry(
    llm_callable: Callable,
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    **kwargs,
):
    """
    调用 LLM 函数并自动重试。

    这是一个非装饰器版本，适合在运行时动态调用。

    Args:
        llm_callable: 要调用的 LLM 函数
        *args: 位置参数
        max_retries: 最大重试次数
        initial_delay: 首次重试延迟
        **kwargs: 关键字参数

    Returns:
        LLM 函数的返回值

    Example:
        result = call_llm_with_retry(
            llm_client.generate,
            prompt="Hello",
            temperature=0.7,
            max_retries=3
        )
    """
    decorated_func = retry_with_backoff(
        max_retries=max_retries, initial_delay=initial_delay
    )(llm_callable)

    return decorated_func(*args, **kwargs)
