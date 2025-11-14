"""
Chat 服务子模块

将 ChatService 的功能拆分为多个子模块，符合 CLAUDE.md 单文件不超过 1000 行的要求。
"""

from .utils import (
    merge_planner_engines,
    clone_llm_logs,
    compose_debug_payload,
    guess_datasource,
    format_source_hint,
    format_retrieved_tools,
    resolve_tool_route,
)

from .dataset_utils import (
    dataset_from_result,
    dataset_records,
    infer_dataset_item_count,
    build_dataset_preview,
    summarize_datasets,
    format_success_message,
    build_analysis_prompt,
)

__all__ = [
    # utils
    "merge_planner_engines",
    "clone_llm_logs",
    "compose_debug_payload",
    "guess_datasource",
    "format_source_hint",
    "format_retrieved_tools",
    "resolve_tool_route",
    # dataset_utils
    "dataset_from_result",
    "dataset_records",
    "infer_dataset_item_count",
    "build_dataset_preview",
    "summarize_datasets",
    "format_success_message",
    "build_analysis_prompt",
]
