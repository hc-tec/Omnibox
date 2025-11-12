from __future__ import annotations

"""简单的 Prompt 文件加载器，避免在代码中硬编码大段字符串。"""

from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"


@lru_cache(maxsize=16)
def load_prompt(filename: str) -> str:
    path = PROMPT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"未找到 Prompt 文件: {path}")
    return path.read_text(encoding="utf-8").strip()

