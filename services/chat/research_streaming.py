"""
流式研究处理模块

从 ChatService 拆分出来，负责处理复杂研究任务的流式响应生成。
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple
from uuid import uuid4

from services.data_query_service import DataQueryResult, QueryDataset
from services.llm_query_planner import QueryPlan, SubQuery
from services.chat.dataset_utils import (
    dataset_from_result,
    build_dataset_preview,
    build_analysis_prompt,
)

logger = logging.getLogger(__name__)


def handle_complex_research_streaming(
    task_id: str,
    user_query: str,
    query_planner,
    data_query_service,
    llm_client,
    build_panel_func,
    should_force_single_route_func,
    filter_datasource: Optional[str] = None,
    use_cache: bool = True,
    intent_confidence: float = 0.95,
    layout_snapshot: Optional[List[Dict[str, Any]]] = None,
    user_id: Optional[int] = None,
) -> Generator[Dict[str, Any], None, None]:
    """
    处理复杂研究意图（流式版本）。

    通过 Generator 逐步 yield 研究进度消息，支持 WebSocket 实时推送。

    流程：
    1. LLM 查询规划 → yield ResearchStartMessage
    2. 并行执行数据子查询 → 每个子查询 yield step/panel 消息
    3. 执行分析子查询 → 每个分析 yield analysis 消息
    4. 完成 → yield ResearchCompleteMessage

    Args:
        task_id: 研究任务 ID
        user_query: 用户查询
        query_planner: LLM 查询规划器
        data_query_service: 数据查询服务
        llm_client: LLM 客户端
        build_panel_func: 构建面板的回调函数
        should_force_single_route_func: 判断是否强制单路的回调函数
        filter_datasource: 过滤数据源（可选）
        use_cache: 是否使用缓存
        intent_confidence: 意图置信度
        layout_snapshot: 布局快照（可选）
        user_id: 用户 ID（可选）

    Yields:
        Dict[str, Any]: 研究消息
    """
    stream_id = f"stream-{uuid4().hex[:16]}"
    start_time = time.time()

    logger.info(
        "开始流式研究任务 (task_id=%s, stream_id=%s): %s",
        task_id,
        stream_id,
        user_query,
    )

    # P0 修复：检查 LLM 组件是否可用
    if not query_planner:
        logger.error("研究任务失败: query_planner 未初始化或不可用")
        yield {
            "type": "research_error",
            "stream_id": stream_id,
            "task_id": task_id,
            "step_id": "initialization",
            "error_code": "COMPONENT_UNAVAILABLE",
            "error_message": "LLM 组件未初始化，无法执行复杂研究任务。请检查环境配置或稍后重试。",
            "timestamp": datetime.now().isoformat(),
        }
        yield {
            "type": "research_complete",
            "stream_id": stream_id,
            "task_id": task_id,
            "success": False,
            "message": "研究失败：LLM 组件不可用",
            "total_time": time.time() - start_time,
            "timestamp": datetime.now().isoformat(),
        }
        return

    try:
        # ========== 第一步：LLM 查询规划 ==========
        yield {
            "type": "research_step",
            "stream_id": stream_id,
            "task_id": task_id,
            "step_id": "planning",
            "step_type": "planning",
            "action": "LLM 正在规划研究方案...",
            "status": "processing",
            "timestamp": datetime.now().isoformat(),
        }

        query_plan: QueryPlan = query_planner.plan(user_query)

        if not query_plan.sub_queries:
            yield {
                "type": "research_error",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": "planning",
                "error_code": "PLANNING_ERROR",
                "error_message": "查询规划未生成子查询，无法继续研究",
                "timestamp": datetime.now().isoformat(),
            }
            yield {
                "type": "research_complete",
                "stream_id": stream_id,
                "task_id": task_id,
                "success": False,
                "message": "研究失败：查询规划未生成子查询",
                "total_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat(),
            }
            return

        # 分类子查询
        data_sub_queries = [
            sq for sq in query_plan.sub_queries if sq.task_type == "data_fetch"
        ]
        analysis_sub_queries = [
            sq for sq in query_plan.sub_queries if sq.task_type in {"analysis", "report"}
        ]

        if not data_sub_queries:
            yield {
                "type": "research_error",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": "planning",
                "error_code": "PLANNING_ERROR",
                "error_message": "查询规划未包含数据获取任务",
                "timestamp": datetime.now().isoformat(),
            }
            yield {
                "type": "research_complete",
                "stream_id": stream_id,
                "task_id": task_id,
                "success": False,
                "message": "研究失败：查询规划未包含数据获取任务",
                "total_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat(),
            }
            return

        # 规划完成，推送开始消息
        yield {
            "type": "research_start",
            "stream_id": stream_id,
            "task_id": task_id,
            "query": user_query,
            "plan": {
                "reasoning": query_plan.reasoning,
                "sub_queries": [
                    {
                        "query": sq.query,
                        "task_type": sq.task_type,
                        "datasource": sq.datasource,
                    }
                    for sq in query_plan.sub_queries
                ],
                "estimated_time": query_plan.estimated_time,
            },
            "timestamp": datetime.now().isoformat(),
        }

        yield {
            "type": "research_step",
            "stream_id": stream_id,
            "task_id": task_id,
            "step_id": "planning",
            "step_type": "planning",
            "action": f"规划完成：{len(data_sub_queries)} 个数据任务，{len(analysis_sub_queries)} 个分析任务",
            "status": "success",
            "details": {
                "data_task_count": len(data_sub_queries),
                "analysis_task_count": len(analysis_sub_queries),
            },
            "timestamp": datetime.now().isoformat(),
        }

        # ========== 第二步：执行数据子查询 ==========
        aggregated_datasets: List[QueryDataset] = []
        success_count = 0

        for idx, sub_query in enumerate(data_sub_queries):
            step_id = f"data_fetch_{idx}"

            # 开始执行
            yield {
                "type": "research_step",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": step_id,
                "step_type": "data_fetch",
                "action": f"正在获取数据：{sub_query.query}",
                "status": "processing",
                "timestamp": datetime.now().isoformat(),
            }

            try:
                # 执行查询
                effective_datasource = filter_datasource or sub_query.datasource
                prefer_single_route = should_force_single_route_func(effective_datasource)
                query_result = data_query_service.query(
                    user_query=sub_query.query,
                    filter_datasource=effective_datasource,
                    use_cache=use_cache,
                    prefer_single_route=prefer_single_route,
                    user_id=user_id,
                )

                if query_result.status == "success":
                    # 聚合数据集
                    datasets = query_result.datasets or []
                    if datasets:
                        aggregated_datasets.extend(datasets)
                    else:
                        aggregated_datasets.append(dataset_from_result(query_result))

                    # 生成面板
                    panel_result = build_panel_func(
                        query_result=query_result,
                        datasets=datasets or [dataset_from_result(query_result)],
                        intent_confidence=intent_confidence,
                        user_query=sub_query.query,
                        layout_snapshot=layout_snapshot,
                    )

                    # 推送面板消息
                    yield {
                        "type": "research_panel",
                        "stream_id": stream_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "step_index": idx + 1,
                        "panel_payload": panel_result.payload.model_dump(),
                        "panel_data_blocks": {
                            key: block.model_dump()
                            for key, block in (panel_result.data_blocks or {}).items()
                        },
                        "source_query": sub_query.query,
                        "timestamp": datetime.now().isoformat(),
                    }

                    # 步骤成功
                    yield {
                        "type": "research_step",
                        "stream_id": stream_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "step_type": "data_fetch",
                        "action": f"数据获取成功：{query_result.feed_title or '数据'}",
                        "status": "success",
                        "details": {
                            "item_count": len(query_result.items or []),
                            "feed_title": query_result.feed_title,
                        },
                        "timestamp": datetime.now().isoformat(),
                    }

                    success_count += 1

                else:
                    # 查询失败
                    yield {
                        "type": "research_step",
                        "stream_id": stream_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "step_type": "data_fetch",
                        "action": f"数据获取失败：{query_result.reasoning or '未知错误'}",
                        "status": "error",
                        "details": {
                            "error": query_result.reasoning,
                        },
                        "timestamp": datetime.now().isoformat(),
                    }

            except Exception as exc:
                logger.error(
                    "数据子查询执行异常: %s - %s",
                    sub_query.query,
                    exc,
                    exc_info=True,
                )
                yield {
                    "type": "research_step",
                    "stream_id": stream_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "step_type": "data_fetch",
                    "action": f"数据获取异常：{exc}",
                    "status": "error",
                    "details": {
                        "error": str(exc),
                    },
                    "timestamp": datetime.now().isoformat(),
                }

        # 检查是否有成功的数据查询
        if success_count == 0:
            yield {
                "type": "research_error",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": None,
                "error_code": "ALL_DATA_FETCH_FAILED",
                "error_message": "所有数据获取任务均失败",
                "timestamp": datetime.now().isoformat(),
            }
            yield {
                "type": "research_complete",
                "stream_id": stream_id,
                "task_id": task_id,
                "success": False,
                "message": "研究失败：所有数据获取任务均失败",
                "total_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat(),
            }
            return

        # ========== 第三步：执行分析子查询 ==========
        if analysis_sub_queries and aggregated_datasets and llm_client:
            yield from _execute_analysis_queries(
                stream_id=stream_id,
                task_id=task_id,
                analysis_sub_queries=analysis_sub_queries,
                aggregated_datasets=aggregated_datasets,
                llm_client=llm_client,
            )

        # ========== 第四步：研究完成 ==========
        total_time = time.time() - start_time
        yield {
            "type": "research_complete",
            "stream_id": stream_id,
            "task_id": task_id,
            "success": True,
            "message": f"研究完成，共获取 {success_count} 组数据",
            "total_time": total_time,
            "summary": None,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            "流式研究任务完成 (task_id=%s, success_count=%d, total_time=%.2fs)",
            task_id,
            success_count,
            total_time,
        )

    except Exception as exc:
        logger.error(
            "流式研究任务异常 (task_id=%s): %s",
            task_id,
            exc,
            exc_info=True,
        )
        yield {
            "type": "research_error",
            "stream_id": stream_id,
            "task_id": task_id,
            "step_id": None,
            "error_code": "RESEARCH_ERROR",
            "error_message": str(exc),
            "timestamp": datetime.now().isoformat(),
        }
        yield {
            "type": "research_complete",
            "stream_id": stream_id,
            "task_id": task_id,
            "success": False,
            "message": f"研究失败：{exc}",
            "total_time": time.time() - start_time,
            "timestamp": datetime.now().isoformat(),
        }


def _execute_analysis_queries(
    stream_id: str,
    task_id: str,
    analysis_sub_queries: List[SubQuery],
    aggregated_datasets: List[QueryDataset],
    llm_client,
) -> Generator[Dict[str, Any], None, None]:
    """执行分析子查询并生成流式消息。"""
    dataset_summary, total_items = build_dataset_preview(aggregated_datasets)

    if not dataset_summary or total_items == 0:
        return

    for idx, sub_query in enumerate(analysis_sub_queries):
        step_id = f"analysis_{idx}"

        # 开始分析
        yield {
            "type": "research_step",
            "stream_id": stream_id,
            "task_id": task_id,
            "step_id": step_id,
            "step_type": "analysis",
            "action": f"正在分析：{sub_query.query}",
            "status": "processing",
            "timestamp": datetime.now().isoformat(),
        }

        try:
            prompt = build_analysis_prompt(sub_query.query, dataset_summary)
            response = llm_client.chat(
                messages=[
                    {"role": "system", "content": "你是一名资深的数据分析师，擅长归纳总结。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )

            # 空值检查
            if response is None or not response.strip():
                raise ValueError("LLM 返回空响应")

            # 推送分析结果
            yield {
                "type": "research_analysis",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": step_id,
                "step_index": idx + 1,
                "analysis_text": response.strip(),
                "is_complete": True,
                "timestamp": datetime.now().isoformat(),
            }

            # 分析成功
            yield {
                "type": "research_step",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": step_id,
                "step_type": "analysis",
                "action": "分析完成",
                "status": "success",
                "details": {
                    "item_count": total_items,
                },
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as exc:
            logger.warning("分析子查询失败: %s - %s", sub_query.query, exc)
            yield {
                "type": "research_step",
                "stream_id": stream_id,
                "task_id": task_id,
                "step_id": step_id,
                "step_type": "analysis",
                "action": f"分析失败：{exc}",
                "status": "error",
                "details": {
                    "error": str(exc),
                },
                "timestamp": datetime.now().isoformat(),
            }
