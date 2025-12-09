from __future__ import annotations

"""简单的 Prompt 文件加载器，避免在代码中硬编码大段字符串。

模块重载时自动清除缓存，确保 WatchFiles 触发重载后能读取最新的 prompt 文件。
"""

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"


@lru_cache(maxsize=16)
def load_prompt(filename: str) -> str:
    path = PROMPT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"未找到 Prompt 文件: {path}")
    content = path.read_text(encoding="utf-8").strip()
    logger.debug("加载 prompt 文件: %s (%d 字符)", filename, len(content))
    return content


def clear_prompt_cache() -> None:
    """清除 prompt 缓存，强制重新加载所有 prompt 文件。"""
    load_prompt.cache_clear()
    logger.info("Prompt 缓存已清除")


# 模块加载时清除缓存，确保 WatchFiles 重载后能读取最新文件
clear_prompt_cache()

