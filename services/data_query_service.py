"""
数据查询服务
职责：整合 RAG 检索、路径生成、RSS 数据获取与缓存，向上层提供结构化数据结果。
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field

from orchestrator.rag_in_action import RAGInAction
from integration.data_executor import DataExecutor, FetchResult
from integration.cache_service import CacheService, get_cache_service

logger = logging.getLogger(__name__)


@dataclass
class QueryDataset:
    """
    单份数据集结果（用于前端生成多张卡片）。

    用于支持一次查询返回多个数据源的数据（如"B站热搜 + 指定UP投稿"）。
    每个 QueryDataset 会在前端渲染为独立的面板卡片。

    Attributes:
        route_id: RSSHub 路由 ID（如 "bilibili/hot-search"）
        provider: 数据提供商（如 "bilibili"）
        name: 数据集名称（如 "B站热搜"）
        generated_path: 生成的完整路径（如 "/bilibili/hot-search"）
        items: 数据项列表（字典格式）
        feed_title: Feed 标题
        source: 数据来源（local/fallback）
        cache_hit: 缓存命中状态（none/rag_cache/rss_cache）
        reasoning: 推理过程或错误信息
        payload: RSSHub 原始返回（字典格式）
    """

    route_id: Optional[str]
    provider: Optional[str]
    name: Optional[str]
    generated_path: Optional[str]
    items: List[Dict[str, Any]]
    feed_title: Optional[str] = None
    source: Optional[str] = None
    cache_hit: str = "none"
    reasoning: str = ""
    payload: Optional[Dict[str, Any]] = None


@dataclass
class DataQueryResult:
    """数据查询结果（兼容旧字段，同时携带多路数据集）。"""

    status: str
    items: List[Dict[str, Any]]
    feed_title: Optional[str] = None
    generated_path: Optional[str] = None
    source: Optional[str] = None
    cache_hit: str = "none"
    reasoning: str = ""
    clarification_question: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    datasets: List[QueryDataset] = field(default_factory=list)
    retrieved_tools: List[Dict[str, Any]] = field(default_factory=list)  # RAG 检索到的候选工具列表
    rag_trace: Dict[str, Any] = field(default_factory=dict)


class DataQueryService:
    """数据查询服务（生产实现）。"""

    # 最多尝试 3 条候选路由，避免过多请求延长响应时间
    MULTI_ROUTE_LIMIT = 3

    def __init__(
        self,
        rag_in_action: RAGInAction,
        data_executor: Optional[DataExecutor] = None,
        cache_service: Optional[CacheService] = None,
    ):
        self.rag_in_action = rag_in_action
        self.data_executor = data_executor or DataExecutor()
        self.cache = cache_service or get_cache_service()
        self._own_executor = data_executor is None

        logger.info("DataQueryService 初始化完成")

    def query(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        use_cache: bool = True,
    ) -> DataQueryResult:
        logger.info("开始数据查询: %s", user_query)

        retrieved_tools: List[Dict[str, Any]] = []
        rag_trace: Dict[str, Any] = {}

        try:
            rag_cache_key = user_query if not filter_datasource else f"{user_query}||{filter_datasource}"
            rag_result, rag_cache_hit = self._resolve_rag_result(
                user_query=user_query,
                filter_datasource=filter_datasource,
                cache_key=rag_cache_key,
                use_cache=use_cache,
            )
            retrieved_tools = rag_result.get("retrieved_tools") or []
            rag_trace = self._build_rag_trace(rag_result)

            status = rag_result.get("status")
            if status == "needs_clarification":
                return DataQueryResult(
                    status="needs_clarification",
                    items=[],
                    reasoning=rag_result.get("reasoning", ""),
                    clarification_question=rag_result.get("clarification_question"),
                    cache_hit=rag_cache_hit,
                    retrieved_tools=retrieved_tools,
                    rag_trace=rag_trace,
                )
            if status == "not_found":
                return DataQueryResult(
                    status="not_found",
                    items=[],
                    reasoning=rag_result.get("reasoning", "未找到匹配的工具"),
                    clarification_question=rag_result.get("clarification_question"),
                    cache_hit=rag_cache_hit,
                    retrieved_tools=retrieved_tools,
                    rag_trace=rag_trace,
                )
            if status != "success":
                return DataQueryResult(
                    status="error",
                    items=[],
                    reasoning=rag_result.get("reasoning", "RAG 处理失败"),
                    cache_hit=rag_cache_hit,
                    retrieved_tools=retrieved_tools,
                    rag_trace=rag_trace,
                )

            datasets, failures = self._collect_datasets(
                user_query=user_query,
                rag_result=rag_result,
                cache_hint=rag_cache_hit,
                use_cache=use_cache,
            )

            if datasets:
                primary = datasets[0]
                reasoning_notes = [rag_result.get("reasoning", "成功获取数据")]
                if len(datasets) > 1:
                    reasoning_notes.append(f"共生成 {len(datasets)} 组数据")
                if failures:
                    reasoning_notes.append(f"{len(failures)} 组候选拉取失败: {', '.join(failures)}")
                return DataQueryResult(
                    status="success",
                    items=primary.items,
                    feed_title=primary.feed_title,
                    generated_path=primary.generated_path,
                    source=primary.source,
                    cache_hit=primary.cache_hit,
                    reasoning="；".join(reasoning_notes),
                    payload=primary.payload,
                    datasets=datasets,
                    retrieved_tools=retrieved_tools,
                    rag_trace=rag_trace,
                )

            failure_reason = failures[0] if failures else rag_result.get("reasoning", "未能获取可用数据")
            return DataQueryResult(
                status="error",
                items=[],
                reasoning=failure_reason,
                cache_hit=rag_cache_hit,
                retrieved_tools=retrieved_tools,
                rag_trace=rag_trace,
            )

        except Exception as exc:
            logger.error("数据查询失败: %s", exc, exc_info=True)
            return DataQueryResult(
                status="error",
                items=[],
                reasoning=f"查询过程中发生异常: {exc}",
                retrieved_tools=retrieved_tools,
                rag_trace=rag_trace,
            )

    def close(self):
        if self._own_executor and self.data_executor:
            self.data_executor.close()
            logger.info("DataQueryService 已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ===== 内部方法 =====

    def _resolve_rag_result(
        self,
        user_query: str,
        filter_datasource: Optional[str],
        cache_key: str,
        use_cache: bool,
    ) -> Tuple[Dict[str, Any], str]:
        cache_hit_type = "none"
        cached_rag_result = None

        if use_cache:
            cached_rag_result = self.cache.get_rag_cache(
                cache_key,
                filter_datasource=filter_datasource or "",
            )

        if cached_rag_result:
            logger.debug("RAG 缓存命中")
            return cached_rag_result, "rag_cache"

        rag_result = self.rag_in_action.process(
            user_query=user_query,
            filter_datasource=filter_datasource,
            verbose=False,
        )
        if use_cache:
            self.cache.set_rag_cache(
                cache_key,
                rag_result,
                filter_datasource=filter_datasource or "",
            )
        return rag_result, cache_hit_type

    def _collect_datasets(
        self,
        user_query: str,
        rag_result: Dict[str, Any],
        cache_hint: str,
        use_cache: bool,
    ) -> Tuple[List[QueryDataset], List[str]]:
        datasets: List[QueryDataset] = []
        failures: List[str] = []

        for task in self._plan_tasks(user_query, rag_result, cache_hint):
            dataset = self._fetch_dataset(task, use_cache)
            if dataset:
                datasets.append(dataset)
            else:
                failures.append(task.get("name") or task.get("route_id") or "unknown_route")

        return datasets, failures

    @staticmethod
    def _build_rag_trace(rag_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not rag_result:
            return {}

        trace: Dict[str, Any] = {
            "status": rag_result.get("status"),
            "reasoning": rag_result.get("reasoning"),
            "generated_path": rag_result.get("generated_path"),
        }

        selected_tool = rag_result.get("selected_tool") or {}
        if selected_tool:
            trace["selected_tool"] = {
                "route_id": selected_tool.get("route_id"),
                "name": selected_tool.get("name"),
                "provider": selected_tool.get("provider"),
            }

        if rag_result.get("parameters_filled"):
            trace["parameters_filled"] = rag_result.get("parameters_filled")
        if rag_result.get("clarification_question"):
            trace["clarification_question"] = rag_result.get("clarification_question")

        retrieved = rag_result.get("retrieved_tools") or []
        if retrieved:
            trace["retrieved_tools_preview"] = [
                {
                    "route_id": tool.get("route_id"),
                    "name": tool.get("name"),
                    "score": tool.get("score"),
                }
                for tool in retrieved[:5]
            ]

        return trace

    def _plan_tasks(
        self,
        user_query: str,
        rag_result: Dict[str, Any],
        cache_hint: str,
    ) -> List[Dict[str, Any]]:
        tasks: List[Dict[str, Any]] = []

        primary_tool = rag_result.get("selected_tool") or {}
        primary_path = rag_result.get("generated_path")
        if primary_path:
            tasks.append(
                {
                    "route_id": primary_tool.get("route_id"),
                    "provider": primary_tool.get("provider"),
                    "name": primary_tool.get("name"),
                    "generated_path": primary_path,
                    "reasoning": rag_result.get("reasoning", ""),
                    "cache_hint": cache_hint,
                }
            )

        retrieved_tools = rag_result.get("retrieved_tools") or []
        for tool_def in retrieved_tools:
            if len(tasks) >= self.MULTI_ROUTE_LIMIT:
                break
            route_id = tool_def.get("route_id")
            if not route_id or any(task.get("route_id") == route_id for task in tasks):
                continue

            try:
                plan = self.rag_in_action.plan_with_tool(user_query, tool_def)
            except Exception as exc:
                logger.warning(
                    "附加路由 %s (%s) 解析失败: %s",
                    route_id,
                    tool_def.get("name", "unknown"),
                    exc,
                    exc_info=True,
                )
                continue

            if plan.get("status") != "success":
                continue
            generated_path = plan.get("generated_path")
            if not generated_path:
                continue

            tasks.append(
                {
                    "route_id": route_id,
                    "provider": tool_def.get("datasource") or tool_def.get("provider_id"),
                    "name": tool_def.get("name"),
                    "generated_path": generated_path,
                    "reasoning": plan.get("reasoning", ""),
                    "cache_hint": "none",
                }
            )

        return tasks[: self.MULTI_ROUTE_LIMIT]

    def _fetch_dataset(self, task: Dict[str, Any], use_cache: bool) -> Optional[QueryDataset]:
        generated_path = task.get("generated_path")
        if not generated_path:
            logger.warning("数据集任务缺少 generated_path: %s", task.get("name", "unknown"))
            return None

        fetch_result, cache_state = self._fetch_rss_payload(
            generated_path,
            task.get("cache_hint", "none"),
            use_cache,
        )

        if fetch_result.status != "success":
            logger.warning(
                "数据集拉取失败: %s (%s) - %s",
                task.get("name", "unknown"),
                generated_path,
                fetch_result.error_message or "未知错误",
            )
            return None

        return QueryDataset(
            route_id=task.get("route_id"),
            provider=task.get("provider"),
            name=task.get("name"),
            generated_path=generated_path,
            items=fetch_result.items,
            feed_title=fetch_result.feed_title,
            source=fetch_result.source,
            cache_hit=cache_state,
            reasoning=task.get("reasoning", "成功获取数据"),
            payload=fetch_result.payload,
        )

    def _fetch_rss_payload(
        self,
        generated_path: str,
        cache_hint: str,
        use_cache: bool,
    ) -> Tuple[FetchResult, str]:
        cached_rss_data: Optional[FetchResult] = None
        if use_cache:
            cached_rss_data = self.cache.get_rss_cache(generated_path)

        if cached_rss_data:
            logger.debug("RSS 缓存命中: %s", generated_path)
            return cached_rss_data, "rss_cache"

        fetch_result = self.data_executor.fetch_rss(generated_path)
        if use_cache and fetch_result.status == "success":
            self.cache.set_rss_cache(generated_path, fetch_result)

        return fetch_result, cache_hint
