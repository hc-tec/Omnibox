"""
数据查询服务
职责：整合RAG检索、路径生成、RSS数据获取和缓存
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from orchestrator.rag_in_action import RAGInAction
from integration.data_executor import DataExecutor, FetchResult
from integration.cache_service import CacheService, get_cache_service

logger = logging.getLogger(__name__)


@dataclass
class DataQueryResult:
    """
    数据查询结果

    Attributes:
        status: 状态（success/needs_clarification/not_found/error）
        items: 数据项列表（原始字典）
        feed_title: Feed标题
        generated_path: 生成的RSS路径
        source: 数据来源（local/fallback）
        cache_hit: 是否命中缓存（rag_cache/rss_cache/none）
        reasoning: 推理过程或错误信息
        clarification_question: 需要澄清的问题（可选）
        payload: RSSHub 原始返回（字典格式）
    """
    status: str
    items: List[Dict[str, Any]]
    feed_title: Optional[str] = None
    generated_path: Optional[str] = None
    source: Optional[str] = None  # local/fallback
    cache_hit: str = "none"  # rag_cache/rss_cache/none
    reasoning: str = ""
    clarification_question: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class DataQueryService:
    """
    数据查询服务（同步实现）

    整合RAG检索、DataExecutor和缓存，提供完整的数据查询功能。

    流程：
    1. 检查RAG缓存（相同查询避免重复RAG）
    2. 如果未命中，调用RAGInAction进行路径生成
    3. 缓存RAG结果
    4. 检查RSS数据缓存（相同路径避免重复请求）
    5. 如果未命中，调用DataExecutor获取数据
    6. 缓存RSS数据
    7. 返回结果

    使用示例：
        service = DataQueryService(rag_in_action, data_executor)
        result = service.query("虎扑步行街最新帖子")
        if result.status == "success":
            for item in result.items:
                print(item.title)
    """

    def __init__(
        self,
        rag_in_action: RAGInAction,
        data_executor: Optional[DataExecutor] = None,
        cache_service: Optional[CacheService] = None,
    ):
        """
        初始化数据查询服务

        Args:
            rag_in_action: RAG-in-Action实例
            data_executor: DataExecutor实例（可选，None则自动创建）
            cache_service: CacheService实例（可选，None则使用全局单例）
        """
        self.rag_in_action = rag_in_action
        self.data_executor = data_executor or DataExecutor()
        self.cache = cache_service or get_cache_service()
        self._own_executor = data_executor is None  # 标记是否自己创建的executor

        logger.info("DataQueryService初始化完成")

    def query(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        use_cache: bool = True,
    ) -> DataQueryResult:
        """
        查询数据

        Args:
            user_query: 用户查询
            filter_datasource: 过滤特定数据源（可选）
            use_cache: 是否使用缓存（默认True）

        Returns:
            DataQueryResult: 查询结果
        """
        logger.info(f"开始数据查询: {user_query}")

        try:
            # ========== 阶段1: 检查RAG缓存 ==========
            rag_cache_key = user_query
            if filter_datasource:
                rag_cache_key = f"{user_query}||{filter_datasource}"

            cached_rag_result = None
            if use_cache:
                cached_rag_result = self.cache.get_rag_cache(
                    rag_cache_key,
                    filter_datasource=filter_datasource or ""
                )

            if cached_rag_result:
                logger.debug("RAG缓存命中")
                rag_result = cached_rag_result
                cache_hit_type = "rag_cache"
            else:
                # ========== 阶段2: RAG检索和路径生成 ==========
                logger.debug("RAG缓存未命中，调用RAGInAction")
                rag_result = self.rag_in_action.process(
                    user_query=user_query,
                    filter_datasource=filter_datasource,
                    verbose=False,
                )

                # 缓存RAG结果
                if use_cache:
                    self.cache.set_rag_cache(
                        rag_cache_key,
                        rag_result,
                        filter_datasource=filter_datasource or ""
                    )
                cache_hit_type = "none"

            # ========== 阶段3: 处理RAG结果 ==========
            status = rag_result.get("status")

            # 如果需要澄清或未找到，直接返回
            if status == "needs_clarification":
                return DataQueryResult(
                    status="needs_clarification",
                    items=[],
                    reasoning=rag_result.get("reasoning", ""),
                    clarification_question=rag_result.get("clarification_question"),
                    cache_hit=cache_hit_type,
                )

            if status == "not_found":
                return DataQueryResult(
                    status="not_found",
                    items=[],
                    reasoning=rag_result.get("reasoning", "未找到匹配的工具"),
                    clarification_question=rag_result.get("clarification_question"),
                    cache_hit=cache_hit_type,
                )

            if status != "success":
                return DataQueryResult(
                    status="error",
                    items=[],
                    reasoning=rag_result.get("reasoning", "RAG处理失败"),
                    cache_hit=cache_hit_type,
                )

            # 提取生成的路径
            generated_path = rag_result.get("generated_path")
            if not generated_path:
                return DataQueryResult(
                    status="error",
                    items=[],
                    reasoning="路径生成失败",
                    cache_hit=cache_hit_type,
                )

            # ========== 阶段4: 检查RSS数据缓存 ==========
            cached_rss_data = None
            if use_cache:
                cached_rss_data = self.cache.get_rss_cache(generated_path)

            if cached_rss_data:
                logger.debug(f"RSS缓存命中: {generated_path}")
                fetch_result = cached_rss_data
                final_cache_hit = "rss_cache"
            else:
                # ========== 阶段5: 获取RSS数据 ==========
                logger.debug(f"RSS缓存未命中，调用DataExecutor: {generated_path}")
                fetch_result = self.data_executor.fetch_rss(generated_path)

                # 缓存RSS数据（仅当成功时）
                if use_cache and fetch_result.status == "success":
                    self.cache.set_rss_cache(generated_path, fetch_result)

                final_cache_hit = cache_hit_type

            # ========== 阶段6: 返回结果 ==========
            if fetch_result.status == "success":
                return DataQueryResult(
                    status="success",
                    items=fetch_result.items,
                    feed_title=fetch_result.feed_title,
                    generated_path=generated_path,
                    source=fetch_result.source,
                    cache_hit=final_cache_hit,
                    reasoning="成功获取数据",
                    payload=fetch_result.payload,
                )
            else:
                return DataQueryResult(
                    status="error",
                    items=[],
                    generated_path=generated_path,
                    reasoning=fetch_result.error_message or "数据获取失败",
                    cache_hit=final_cache_hit,
                )

        except Exception as e:
            logger.error(f"数据查询失败: {e}", exc_info=True)
            return DataQueryResult(
                status="error",
                items=[],
                reasoning=f"查询过程发生异常: {str(e)}",
            )

    def close(self):
        """关闭服务，释放资源"""
        if self._own_executor and self.data_executor:
            self.data_executor.close()
            logger.info("DataQueryService已关闭")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
