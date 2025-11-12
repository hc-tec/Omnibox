from __future__ import annotations

"""LangGraph 运行时依赖与工具上下文定义。"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, TYPE_CHECKING

from query_processor.llm_client import LLMClient
from services.data_query_service import DataQueryService

from .storage import ResearchDataStore

if TYPE_CHECKING:  # 避免循环引用
    from .tools.registry import ToolRegistry


class NoteSearchBackend(Protocol):
    """私有笔记检索后端接口。"""

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        ...


@dataclass
class ToolExecutionContext:
    """
    工具执行上下文。

    LangGraph 的 ToolExecutor 会把该上下文注入给每个工具，实现对现有 Service 的复用。
    """

    data_query_service: Optional[DataQueryService] = None
    note_backend: Optional[NoteSearchBackend] = None
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LangGraphRuntime:
    """LangGraph App 构建所需的运行时依赖。"""

    router_llm: LLMClient
    planner_llm: LLMClient
    reflector_llm: LLMClient
    synthesizer_llm: LLMClient
    tool_registry: "ToolRegistry"
    data_store: ResearchDataStore
    tool_context: ToolExecutionContext
    summarizer_llm: Optional[LLMClient] = None
    cheap_summary_max_chars: int = 320

