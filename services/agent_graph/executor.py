"""
Task Graph Executor

负责读取 Task Graph 并调度各节点执行，支持将 DataQueryService 的结果
作为输入，额外提供关键词过滤等 transform 能力。
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from services.data_query_service import DataQueryService, DataQueryResult, QueryDataset

from .schema import (
    GraphExecutionResult,
    GraphNode,
    GraphNodeStatus,
    NodeExecutionRecord,
    TaskGraph,
)

logger = logging.getLogger(__name__)


@dataclass
class TaskGraphExecutionContext:
    """执行 Task Graph 所需的环境信息。"""

    user_query: str
    filter_datasource: Optional[str]
    use_cache: bool = True
    prefer_single_route: Optional[bool] = None
    user_id: Optional[int] = None


class NodeExecutionError(RuntimeError):
    """节点执行失败时抛出的异常。"""

    def __init__(self, message: str, payload: Any = None):
        super().__init__(message)
        self.payload = payload


class GraphExecutor:
    """Task Graph 执行器。"""

    def __init__(self, data_query_service: DataQueryService):
        self.data_query_service = data_query_service

    def execute(self, graph: TaskGraph, context: TaskGraphExecutionContext) -> GraphExecutionResult:
        """执行任务图，并返回结果。"""
        node_records: List[NodeExecutionRecord] = []
        memory: Dict[str, Any] = {}
        final_output: Any = None
        graph_error: Optional[str] = None

        try:
            ordered_nodes = graph.topological_order()
        except ValueError as exc:
            logger.error("TaskGraph 拓扑排序失败: %s", exc)
            return GraphExecutionResult(
                success=False,
                final_output=None,
                node_results=[],
                graph_metadata=graph.metadata,
                error=str(exc),
            )

        for node in ordered_nodes:
            start = datetime.now()
            status: GraphNodeStatus = "running"
            summary: Dict[str, Any] = {}
            error_message: Optional[str] = None
            result_payload: Any = None

            try:
                if node.type == "fetch_data":
                    result_payload = self._execute_fetch_node(node, context)
                elif node.type == "transform":
                    result_payload = self._execute_transform_node(node, memory)
                elif node.type == "analysis":
                    result_payload = self._execute_analysis_node(node, memory)
                else:
                    result_payload = self._passthrough_node(node, memory)

                status = "success"
                summary = self._build_summary(result_payload)
                memory[node.id] = result_payload
            except NodeExecutionError as exc:
                status = "error"
                error_message = str(exc)
                summary = self._build_summary(exc.payload)
                memory[node.id] = exc.payload
                graph_error = error_message
                final_output = exc.payload
                logger.warning("Task Graph 节点执行失败 (%s): %s", node.id, exc)
                node_records.append(
                    NodeExecutionRecord(
                        node_id=node.id,
                        node_type=node.type,
                        status=status,
                        started_at=start,
                        finished_at=datetime.now(),
                        summary=summary,
                        error=error_message,
                    )
                )
                break
            except Exception as exc:  # noqa: BLE001
                status = "error"
                error_message = str(exc)
                graph_error = error_message
                logger.exception("Task Graph 节点执行异常 (%s)", node.id)
                node_records.append(
                    NodeExecutionRecord(
                        node_id=node.id,
                        node_type=node.type,
                        status=status,
                        started_at=start,
                        finished_at=datetime.now(),
                        summary=summary,
                        error=error_message,
                    )
                )
                break

            node_records.append(
                NodeExecutionRecord(
                    node_id=node.id,
                    node_type=node.type,
                    status=status,
                    started_at=start,
                    finished_at=datetime.now(),
                    summary=summary,
                    error=error_message,
                )
            )
            final_output = result_payload

        final_node_id = graph.output_node_id()
        metadata = dict(graph.metadata)
        if final_node_id:
            metadata.setdefault("output_node", final_node_id)

        success = graph_error is None and final_output is not None
        return GraphExecutionResult(
            success=success,
            final_output=final_output,
            node_results=node_records,
            graph_metadata=metadata,
            error=graph_error,
        )

    def _execute_fetch_node(
        self,
        node: GraphNode,
        context: TaskGraphExecutionContext,
    ) -> DataQueryResult:
        query_text = node.params.get("query") or context.user_query
        datasource = node.params.get("filter_datasource", context.filter_datasource)
        use_cache = node.params.get("use_cache", context.use_cache)

        # Task Graph 节点执行时强制单路由模式
        # 原因：Task Graph Planner 已经规划了完整的多节点策略（fetch + filter 等）
        # 不需要 DataQueryService 内部再做多路由规划，避免重复请求
        prefer_single_route = True

        logger.info("Task Graph 节点(%s) 拉取数据: %s (单路由模式)", node.id, query_text)
        result = self.data_query_service.query(
            user_query=query_text,
            filter_datasource=datasource,
            use_cache=use_cache,
            prefer_single_route=prefer_single_route,
            user_id=context.user_id,
        )

        if result.status != "success":
            raise NodeExecutionError(f"数据获取失败: {result.reasoning}", payload=result)
        return result

    def _execute_transform_node(self, node: GraphNode, memory: Dict[str, Any]) -> Any:
        if not node.input_refs:
            raise NodeExecutionError("transform 节点缺少输入引用")

        input_ref = node.input_refs[0]
        parent = memory.get(input_ref)
        if parent is None:
            raise NodeExecutionError(f"transform 节点未找到输入 {input_ref}")

        if node.tool == "filter_data":
            return self._apply_filter(node, parent)

        raise NodeExecutionError(f"未知的 transform 工具: {node.tool}")

    def _execute_analysis_node(self, node: GraphNode, memory: Dict[str, Any]) -> Any:
        """当前暂用传递策略，后续可接入 LLM 分析。"""
        if not node.input_refs:
            raise NodeExecutionError("analysis 节点缺少输入引用")
        input_ref = node.input_refs[0]
        return memory.get(input_ref)

    @staticmethod
    def _passthrough_node(node: GraphNode, memory: Dict[str, Any]) -> Any:
        if node.input_refs:
            for ref in reversed(node.input_refs):
                if ref in memory:
                    return memory[ref]
        return None

    def _apply_filter(self, node: GraphNode, payload: Any) -> DataQueryResult:
        """基于关键词对 DataQueryResult 进行过滤。"""
        if not isinstance(payload, DataQueryResult):
            raise NodeExecutionError("filter_data 输入必须是 DataQueryResult")

        keywords = node.params.get("keywords") or []
        if not keywords:
            return payload

        target_field = node.params.get("target_field", "title")
        filtered_datasets: List[QueryDataset] = []

        datasets = payload.datasets or []
        if datasets:
            for dataset in datasets:
                filtered_items = self._filter_items(dataset.items, keywords, target_field)
                filtered_dataset = QueryDataset(
                    route_id=dataset.route_id,
                    provider=dataset.provider,
                    name=dataset.name,
                    generated_path=dataset.generated_path,
                    items=filtered_items,
                    feed_title=dataset.feed_title,
                    source=dataset.source,
                    cache_hit=dataset.cache_hit,
                    reasoning=self._merge_reasoning(dataset.reasoning, keywords),
                    payload=dataset.payload,
                )
                filtered_datasets.append(filtered_dataset)
        else:
            filtered_items = self._filter_items(payload.items, keywords, target_field)
            filtered_datasets.append(
                QueryDataset(
                    route_id=None,
                    provider=None,
                    name=payload.feed_title,
                    generated_path=payload.generated_path,
                    items=filtered_items,
                    feed_title=payload.feed_title,
                    source=payload.source,
                    cache_hit=payload.cache_hit,
                    reasoning=self._merge_reasoning(payload.reasoning, keywords),
                    payload=payload.payload,
                )
            )

        filtered_result = DataQueryResult(
            status=payload.status,
            items=filtered_datasets[0].items if filtered_datasets else [],
            feed_title=payload.feed_title,
            generated_path=payload.generated_path,
            source=payload.source,
            cache_hit=payload.cache_hit,
            reasoning=self._merge_reasoning(payload.reasoning, keywords),
            payload=copy.deepcopy(payload.payload),
            datasets=filtered_datasets,
            retrieved_tools=copy.deepcopy(payload.retrieved_tools),
            rag_trace=copy.deepcopy(payload.rag_trace),
        )
        return filtered_result

    @staticmethod
    def _filter_items(items: List[Dict[str, Any]], keywords: List[str], target_field: str) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        for item in items:
            field_value = str(item.get(target_field) or "")
            lowered = field_value.lower()
            if all(keyword.lower() in lowered for keyword in keywords):
                filtered.append(item)
        return filtered

    @staticmethod
    def _merge_reasoning(reasoning: Optional[str], keywords: List[str]) -> str:
        keyword_text = "、".join(keywords)
        parts = [text for text in [reasoning, f"过滤关键词：{keyword_text}"] if text]
        return "；".join(parts) if parts else f"过滤关键词：{keyword_text}"

    @staticmethod
    def _build_summary(payload: Any) -> Dict[str, Any]:
        if isinstance(payload, DataQueryResult):
            datasets = payload.datasets or []
            item_count = sum(len(dataset.items) for dataset in datasets) if datasets else len(payload.items)
            return {
                "status": payload.status,
                "dataset_count": len(datasets) or 1,
                "item_count": item_count,
            }
        if isinstance(payload, QueryDataset):
            return {
                "dataset": payload.route_id,
                "item_count": len(payload.items),
            }
        return {}

