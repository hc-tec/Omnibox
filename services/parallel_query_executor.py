"""
并行查询执行器
并行执行多个 RAG 查询，提高复杂研究的效率
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from services.llm_query_planner import SubQuery
from services.data_query_service import DataQueryService, DataQueryResult

logger = logging.getLogger(__name__)


@dataclass
class SubQueryResult:
    """子查询执行结果"""
    sub_query: SubQuery
    result: Optional[DataQueryResult]  # 成功时的结果
    error: Optional[str] = None  # 失败时的错误信息
    execution_time: float = 0.0  # 执行耗时（秒）


class ParallelQueryExecutor:
    """
    并行查询执行器

    功能：
    1. 并行执行多个 RAG 查询
    2. 超时控制
    3. 错误处理和降级
    """

    def __init__(
        self,
        data_query_service: DataQueryService,
        max_workers: int = 3,
        timeout_per_query: int = 30,
    ):
        """
        初始化并行查询执行器

        Args:
            data_query_service: 数据查询服务实例
            max_workers: 最大并行数（默认 3）
            timeout_per_query: 每个查询的超时时间（秒，默认 30）
        """
        self.data_query_service = data_query_service
        self.max_workers = max_workers
        self.timeout_per_query = timeout_per_query
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="parallel-query"
        )
        logger.info(
            "ParallelQueryExecutor 初始化完成 (max_workers=%d, timeout=%ds)",
            max_workers,
            timeout_per_query
        )

    def execute_parallel(
        self,
        sub_queries: List[SubQuery],
        use_cache: bool = True,
        prefer_single_route: bool = False,
    ) -> List[SubQueryResult]:
        """
        并行执行多个子查询

        Args:
            sub_queries: 子查询列表
            use_cache: 是否使用缓存
            prefer_single_route: 是否优先使用单路模式（仅执行primary route，忽略RAG候选路由）

        Returns:
            List[SubQueryResult]: 所有子查询的执行结果
        """
        if not sub_queries:
            logger.warning("子查询列表为空，无需执行")
            return []

        logger.info(f"开始并行执行 {len(sub_queries)} 个子查询")

        # 提交所有任务
        futures = {}
        for idx, sub_query in enumerate(sub_queries):
            future = self.executor.submit(
                self._execute_single_query,
                sub_query,
                use_cache,
                idx,
                prefer_single_route,
            )
            futures[future] = sub_query

        # 收集结果
        results = []
        for future in as_completed(futures, timeout=self.timeout_per_query * 2):
            sub_query = futures[future]
            try:
                result = future.result(timeout=self.timeout_per_query)
                results.append(result)

                if result.error:
                    logger.warning(
                        "子查询失败: %s - %s",
                        result.sub_query.query,
                        result.error
                    )
                else:
                    logger.info(
                        "子查询成功: %s (耗时 %.2fs, %d 条数据)",
                        result.sub_query.query,
                        result.execution_time,
                        len(result.result.items) if result.result else 0
                    )

            except TimeoutError:
                logger.error(f"子查询超时: {sub_query.query}")
                results.append(SubQueryResult(
                    sub_query=sub_query,
                    result=None,
                    error=f"查询超时（>{self.timeout_per_query}秒）"
                ))

            except Exception as exc:
                logger.error(f"子查询异常: {sub_query.query} - {exc}", exc_info=True)
                results.append(SubQueryResult(
                    sub_query=sub_query,
                    result=None,
                    error=str(exc)
                ))

        # 按原始顺序排序结果
        results_map = {r.sub_query.query: r for r in results}
        sorted_results = [
            results_map.get(sq.query, SubQueryResult(
                sub_query=sq,
                result=None,
                error="未执行"
            ))
            for sq in sub_queries
        ]

        # 统计
        success_count = sum(1 for r in sorted_results if r.result and r.result.status == "success")
        failure_count = len(sorted_results) - success_count

        logger.info(
            "并行执行完成: 成功 %d 个，失败 %d 个",
            success_count,
            failure_count
        )

        return sorted_results

    def _execute_single_query(
        self,
        sub_query: SubQuery,
        use_cache: bool,
        index: int,
        prefer_single_route: bool,
    ) -> SubQueryResult:
        """
        执行单个子查询

        Args:
            sub_query: 子查询
            use_cache: 是否使用缓存
            index: 查询索引

        Returns:
            SubQueryResult: 执行结果
        """
        import time
        start_time = time.time()

        try:
            logger.debug(f"[子查询 {index+1}] 开始执行: {sub_query.query}")

            # 调用 DataQueryService
            result = self.data_query_service.query(
                user_query=sub_query.query,
                filter_datasource=sub_query.datasource,
                use_cache=use_cache,
                prefer_single_route=prefer_single_route,
            )

            execution_time = time.time() - start_time

            # 检查结果状态
            if result.status == "success":
                return SubQueryResult(
                    sub_query=sub_query,
                    result=result,
                    error=None,
                    execution_time=execution_time
                )
            else:
                # RAG 返回了错误状态
                return SubQueryResult(
                    sub_query=sub_query,
                    result=result,
                    error=result.reasoning or f"查询失败：status={result.status}",
                    execution_time=execution_time
                )

        except Exception as exc:
            execution_time = time.time() - start_time
            logger.error(
                f"[子查询 {index+1}] 执行异常: {sub_query.query} - {exc}",
                exc_info=True
            )
            return SubQueryResult(
                sub_query=sub_query,
                result=None,
                error=str(exc),
                execution_time=execution_time
            )

    def shutdown(self):
        """关闭执行器"""
        logger.info("关闭 ParallelQueryExecutor")
        self.executor.shutdown(wait=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
