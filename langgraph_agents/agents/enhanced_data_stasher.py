"""
EnhancedDataStasher - 增强的数据存储节点（V5.0 Phase 5）。

在原有 DataStasher 基础上添加：
1. 结构化元数据提取
2. 知识图谱更新
3. 智能摘要生成
"""

import json
import logging
from typing import Dict

from ..prompt_loader import load_prompt
from ..runtime import LangGraphRuntime
from ..state import EnhancedDataReference, GraphState, ToolExecutionPayload
from ..metadata_extractor import (
    extract_schema_info,
    extract_statistics,
    extract_sample_items,
    calculate_quality_score
)
from ..knowledge_graph import (
    KnowledgeGraph,
    GraphNode,
    GraphEdge,
    NodeType,
    EdgeType
)

logger = logging.getLogger(__name__)


def _ensure_serializable(payload) -> str:
    """确保数据可序列化。"""
    try:
        return json.dumps(payload, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(payload), ensure_ascii=False)


def _default_summary(payload, max_chars: int) -> str:
    """生成兜底摘要。"""
    text = _ensure_serializable(payload)
    return (text[: max_chars - 3] + "...") if len(text) > max_chars else text


def _update_knowledge_graph(
    graph: KnowledgeGraph,
    step_id: int,
    tool_name: str,
    data_id: str,
    schema_info: Dict[str, str],
    statistics: Dict[str, any],
    state: GraphState
) -> None:
    """
    更新知识图谱。

    Args:
        graph: 知识图谱
        step_id: 步骤 ID
        tool_name: 工具名称
        data_id: 数据 ID
        schema_info: Schema 信息
        statistics: 统计信息
        state: 当前状态
    """
    # 创建数据集节点
    node_id = f"dataset-{step_id}"
    node = GraphNode(
        node_id=node_id,
        node_type=NodeType.DATASET,
        step_id=step_id,
        data_id=data_id,
        metadata={"tool_name": tool_name},
        record_count=statistics.get("record_count") if statistics else None,
        schema_info=schema_info
    )
    graph.add_node(node)

    # 创建衍生关系边
    # 如果工具是 filter_data、aggregate_data 等，需要查找 source_ref
    last_tool_result = state.get("last_tool_result")
    if last_tool_result and last_tool_result.call.args:
        source_ref_arg = last_tool_result.call.args.get("source_ref")

        # 如果有引用，创建衍生边
        if source_ref_arg:
            # 查找源节点
            # 简化实现：假设 source_ref 是前一个步骤
            if isinstance(source_ref_arg, dict) and "$ref" in source_ref_arg:
                source_step_id = source_ref_arg["$ref"].get("step_id")
                if source_step_id:
                    source_node_id = f"dataset-{source_step_id}"
                    if graph.get_node(source_node_id):
                        edge = GraphEdge(
                            edge_id=f"edge-derived-{source_step_id}-{step_id}",
                            edge_type=EdgeType.DERIVED_FROM,
                            source_node_id=source_node_id,
                            target_node_id=node_id,
                            metadata={"operation": tool_name}
                        )
                        graph.add_edge(edge)
                        logger.debug(
                            f"创建衍生边: {source_node_id} -> {node_id} ({tool_name})"
                        )

    # 创建对比关系边（如果工具是 compare_data）
    if tool_name == "compare_data":
        source_refs_arg = last_tool_result.call.args.get("source_refs", [])
        for i, ref in enumerate(source_refs_arg):
            if isinstance(ref, dict) and "$ref" in ref:
                source_step_id = ref["$ref"].get("step_id")
                if source_step_id:
                    source_node_id = f"dataset-{source_step_id}"
                    if graph.get_node(source_node_id):
                        edge = GraphEdge(
                            edge_id=f"edge-compare-{source_step_id}-{step_id}-{i}",
                            edge_type=EdgeType.COMPARED_WITH,
                            source_node_id=source_node_id,
                            target_node_id=node_id,
                            metadata={"position": i}
                        )
                        graph.add_edge(edge)


def create_enhanced_data_stasher_node(runtime: LangGraphRuntime):
    """
    创建增强的 DataStasher 节点。

    Args:
        runtime: LangGraphRuntime 实例

    Returns:
        LangGraph 节点函数
    """
    summarizer_prompt = load_prompt("summarizer_system.txt")

    def summarize(raw_output: object, state: GraphState) -> str:
        """生成智能摘要（支持 LLM）。"""
        if runtime.summarizer_llm is None:
            return _default_summary(raw_output, runtime.cheap_summary_max_chars)

        prompt = (
            f"{summarizer_prompt}\n\n"
            f"original_query: {state.get('original_query', '')}\n"
            f"raw_data:\n{_ensure_serializable(raw_output)}"
        )
        try:
            text = runtime.summarizer_llm.generate(prompt, temperature=0.2)
            text = text.strip()
            if not text:
                raise ValueError("empty summary")
            return text[: runtime.cheap_summary_max_chars]
        except Exception as exc:
            logger.warning("摘要 LLM 失败，使用兜底摘要: %s", exc)
            return _default_summary(raw_output, runtime.cheap_summary_max_chars)

    def node(state: GraphState) -> Dict[str, object]:
        """增强的 DataStasher 节点函数。"""
        pending: ToolExecutionPayload | None = state.get("pending_tool_result")
        if pending is None:
            return {}

        raw_output = pending.raw_output

        # needs_user_input 状态不存储到 data_store
        if pending.status == "needs_user_input":
            data_id = None
            summary = f"等待用户澄清: {raw_output.get('question', '未知问题')}"
            schema_info = None
            statistics = None
            sample_items = None
            quality_score = None

            logger.info(
                "EnhancedDataStasher: 跳过存储 needs_user_input 状态 (step=%s)",
                pending.call.step_id
            )
        else:
            # 正常数据：保存到 data_store
            data_id = runtime.data_store.save(raw_output)
            summary = summarize(raw_output, state)

            # Phase 5: 提取元数据
            schema_info = extract_schema_info(raw_output)
            statistics = extract_statistics(raw_output)
            sample_items = extract_sample_items(raw_output)
            quality_score = calculate_quality_score(schema_info, statistics)

            logger.info(
                "EnhancedDataStasher 完成: step=%s tool=%s data_id=%s quality=%.2f",
                pending.call.step_id,
                pending.call.plugin_id,
                data_id,
                quality_score if quality_score else 0.0
            )

        # 创建增强的 DataReference
        data_ref = EnhancedDataReference(
            step_id=pending.call.step_id,
            tool_name=pending.call.plugin_id,
            data_id=data_id,
            summary=summary,
            status=pending.status,
            error_message=pending.error_message,
            schema_info=schema_info,
            statistics=statistics,
            sample_items=sample_items,
            quality_score=quality_score
        )

        data_stash = list(state.get("data_stash", []))
        data_stash.append(data_ref)

        # Phase 5: 更新知识图谱
        knowledge_graph = state.get("knowledge_graph")
        if knowledge_graph is None:
            from ..knowledge_graph import KnowledgeGraph
            knowledge_graph = KnowledgeGraph()

        if data_id and schema_info:  # 只为成功的数据创建图节点
            _update_knowledge_graph(
                knowledge_graph,
                pending.call.step_id,
                pending.call.plugin_id,
                data_id,
                schema_info,
                statistics,
                state
            )

        return {
            "data_stash": data_stash,
            "pending_tool_result": None,
            "last_tool_result": pending,
            "knowledge_graph": knowledge_graph
        }

    return node
