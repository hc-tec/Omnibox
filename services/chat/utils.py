"""
Chat 服务工具函数模块

提供 ChatService 使用的静态工具函数。
"""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def merge_planner_engines(engines: List[str]) -> str:
    """
    合并多个 planner 引擎标识为单个标识。

    Args:
        engines: 引擎标识列表

    Returns:
        合并后的引擎标识
    """
    if not engines:
        return "rule"
    if len(set(engines)) == 1:
        return engines[0]
    if "llm" in engines:
        return "llm"
    if "error" in engines and "rule" in engines:
        return "mixed"
    return engines[0]


def clone_llm_logs(llm_logs: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    克隆 LLM 日志列表。

    Args:
        llm_logs: LLM 日志列表

    Returns:
        克隆后的日志列表
    """
    if not llm_logs:
        return []
    return [dict(entry) for entry in llm_logs]


def compose_debug_payload(
    panel_debug: Optional[Dict[str, Any]] = None,
    llm_logs: Optional[List[Dict[str, Any]]] = None,
    rag_trace: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    组合调试信息载荷。

    Args:
        panel_debug: 面板调试信息
        llm_logs: LLM 调用日志
        rag_trace: RAG 检索追踪

    Returns:
        合并后的调试信息
    """
    debug_info: Dict[str, Any] = {}
    if panel_debug:
        debug_info.update(panel_debug)
    if llm_logs:
        debug_info.setdefault("llm_calls", []).extend([
            dict(entry) for entry in llm_logs
        ])
    if rag_trace:
        debug_info["rag"] = rag_trace
    return debug_info


def guess_datasource(generated_path: Optional[str]) -> str:
    """
    通过生成的路径推测数据源标识。

    Args:
        generated_path: 生成的路径（如 "/bilibili/user/video/123"）

    Returns:
        数据源标识（如 "bilibili"）
    """
    if not generated_path:
        return "unknown"
    stripped = generated_path.strip("/")
    if not stripped:
        return "unknown"
    return stripped.split("/")[0]


def format_source_hint(source: Optional[str]) -> str:
    """
    格式化数据源提示文本。

    Args:
        source: 数据源类型（local/fallback/其他）

    Returns:
        格式化后的提示文本
    """
    if source == "local":
        return "本地"
    if source == "fallback":
        return "公共"
    return "远程"


def format_retrieved_tools(retrieved_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    格式化 RAG 检索到的候选工具列表，用于前端展示。

    Args:
        retrieved_tools: RAG 检索返回的工具列表

    Returns:
        格式化后的工具列表，包含关键信息
    """
    if not retrieved_tools:
        return []

    formatted = []
    for tool in retrieved_tools:
        formatted.append({
            "route_id": tool.get("route_id"),
            "name": tool.get("name"),
            "provider": tool.get("datasource") or tool.get("provider_id"),
            "description": (tool.get("description") or "")[:120],
            "score": tool.get("score"),
            "route": resolve_tool_route(tool),
            "example_path": tool.get("example_path"),
        })
    return formatted


def resolve_tool_route(tool: Dict[str, Any]) -> Optional[str]:
    """
    从工具定义中解析路由路径。

    Args:
        tool: 工具定义字典

    Returns:
        路由路径，如果无法解析则返回 None
    """
    if tool.get("route"):
        return tool["route"]

    path_template = tool.get("path_template")
    if isinstance(path_template, list) and path_template:
        return path_template[0]
    if isinstance(path_template, str):
        return path_template

    if tool.get("generated_path"):
        return tool.get("generated_path")

    if tool.get("example_path"):
        return tool.get("example_path")

    return None
