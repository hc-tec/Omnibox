"""Session 配置

可配置参数，支持环境变量覆盖。
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SessionConfig:
    """Session 配置类

    所有参数都支持环境变量覆盖：
    - SESSION_TIMEOUT_MINUTES: Session 超时时间（分钟）
    - SESSION_DATA_STASH_LIMIT: data_stash 上限
    - SESSION_CHAT_HISTORY_LIMIT: chat_history 滑动窗口大小
    - SESSION_CLEANUP_INTERVAL_MINUTES: 清理检查间隔（分钟）
    """

    # Session 超时时间（分钟）
    timeout_minutes: int = 60

    # data_stash 上限（0 表示无限制）
    data_stash_limit: int = 100

    # chat_history 滑动窗口大小（0 表示保留全部）
    chat_history_limit: int = 20

    # 自动保存：每次执行后自动持久化
    auto_persist: bool = True

    # 清理检查间隔（分钟）
    cleanup_interval_minutes: int = 30

    @classmethod
    def from_env(cls) -> "SessionConfig":
        """从环境变量创建配置"""
        return cls(
            timeout_minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "60")),
            data_stash_limit=int(os.getenv("SESSION_DATA_STASH_LIMIT", "100")),
            chat_history_limit=int(os.getenv("SESSION_CHAT_HISTORY_LIMIT", "20")),
            auto_persist=os.getenv("SESSION_AUTO_PERSIST", "true").lower() == "true",
            cleanup_interval_minutes=int(os.getenv("SESSION_CLEANUP_INTERVAL_MINUTES", "30")),
        )


# 全局配置实例
_config: Optional[SessionConfig] = None


def get_session_config() -> SessionConfig:
    """获取 Session 配置（单例）"""
    global _config
    if _config is None:
        _config = SessionConfig.from_env()
    return _config


def reset_session_config():
    """重置配置（测试用）"""
    global _config
    _config = None
