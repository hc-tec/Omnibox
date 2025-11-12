from __future__ import annotations

"""运行时构建辅助函数。"""

from pathlib import Path
from typing import Dict, Optional

from query_processor.llm_client import LLMClient
from services.data_query_service import DataQueryService

from .runtime import LangGraphRuntime, ToolExecutionContext
from .storage import InMemoryResearchDataStore, ResearchDataStore
from .tools.bootstrap import register_default_tools
from .tools.private_notes import MarkdownNoteStore
from .tools.registry import ToolRegistry


def _require_llm(llms: Dict[str, LLMClient], role: str) -> LLMClient:
    if role in llms:
        return llms[role]
    if "default" in llms:
        return llms["default"]
    raise ValueError(f"缺少 {role} LLM 客户端")


def build_runtime(
    *,
    llms: Dict[str, LLMClient],
    data_query_service: DataQueryService,
    notes_path: Optional[Path] = None,
    data_store: Optional[ResearchDataStore] = None,
    summarizer_llm: Optional[LLMClient] = None,
) -> LangGraphRuntime:
    """
    构建 LangGraphRuntime。

    Args:
        llms: 角色 -> LLMClient 映射；若缺少某角色将回退到 "default"
        data_query_service: 复用现有 DataQueryService
        notes_path: 私有笔记目录（默认 docs/）
        data_store: 自定义数据存储
        summarizer_llm: DataStasher 可选摘要模型
    """

    registry = ToolRegistry()
    register_default_tools(registry)

    note_backend = None
    if notes_path:
        note_backend = MarkdownNoteStore(notes_path)

    context = ToolExecutionContext(
        data_query_service=data_query_service,
        note_backend=note_backend,
    )

    runtime = LangGraphRuntime(
        router_llm=_require_llm(llms, "router"),
        planner_llm=_require_llm(llms, "planner"),
        reflector_llm=_require_llm(llms, "reflector"),
        synthesizer_llm=_require_llm(llms, "synthesizer"),
        tool_registry=registry,
        data_store=data_store or InMemoryResearchDataStore(),
        tool_context=context,
        summarizer_llm=summarizer_llm,
    )
    return runtime

