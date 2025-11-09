"""
Bilibili-specific route adapters.

Import submodules to ensure route adapters are registered on package import.
"""

from . import feed  # noqa: F401
from . import followings  # noqa: F401
from . import hot_search  # noqa: F401
from . import user_video  # noqa: F401

__all__ = ["feed", "followings", "hot_search", "user_video"]
