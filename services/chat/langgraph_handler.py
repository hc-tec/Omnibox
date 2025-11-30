"""
LangGraph 研究处理模块

从 ChatService 拆分出来，负责 LangGraph 工作流的研究任务处理。
"""

import logging
from typing import Any, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


def handle_langgraph_research(
    research_service,
    user_query: str,
    filter_datasource: Optional[str],
    intent_confidence: float,
    client_task_id: Optional[str],
    chat_response_class,
) -> Any:
    """
    处理 LangGraph 研究工作流（多轮动态研究）。

    Args:
        research_service: 研究服务实例
        user_query: 用户查询
        filter_datasource: 过滤数据源（可选）
        intent_confidence: 意图置信度
        client_task_id: 客户端任务 ID（可选）
        chat_response_class: ChatResponse 类引用

    Returns:
        ChatResponse 对象
    """
    logger.debug("处理 LangGraph 研究工作流")

    if not research_service:
        return chat_response_class(
            success=False,
            intent_type="error",
            message="研究服务未启用，请使用简单查询模式",
            metadata={"error": "research_service_not_available"},
        )

    task_id = client_task_id or f"task-{uuid4().hex}"

    try:
        # 调用 ResearchService 执行研究
        research_result = research_service.research(
            user_query=user_query,
            filter_datasource=filter_datasource,
            task_id=task_id,
        )

        if research_result.success:
            # 格式化执行步骤
            execution_steps = [
                {
                    "step_id": step.step_id,
                    "node": step.node_name,
                    "action": step.action,
                    "status": step.status,
                    "timestamp": step.timestamp,
                }
                for step in research_result.execution_steps
            ]

            metadata: Dict[str, Any] = {
                "mode": "research",
                "intent_confidence": intent_confidence,
                "total_steps": len(research_result.execution_steps),
                "execution_steps": execution_steps,
                "data_stash_count": len(research_result.data_stash),
            }
            if research_result.metadata:
                metadata.update(research_result.metadata)
            metadata.setdefault("task_id", task_id)
            metadata["panel_previews"] = getattr(research_result, "panel_previews", [])

            return chat_response_class(
                success=True,
                intent_type="research",
                message=research_result.final_report,
                metadata=metadata,
            )
        else:
            return chat_response_class(
                success=False,
                intent_type="research",
                message=f"研究任务失败：{research_result.error}",
                metadata={
                    "mode": "research",
                    "error": research_result.error,
                    "intent_confidence": intent_confidence,
                    "task_id": task_id,
                    "panel_previews": getattr(research_result, "panel_previews", []),
                },
            )

    except Exception as exc:
        logger.error("研究任务执行失败: %s", exc, exc_info=True)
        return chat_response_class(
            success=False,
            intent_type="research",
            message=f"研究任务执行失败：{exc}",
            metadata={
                "mode": "research",
                "error": str(exc),
                "task_id": task_id,
            },
        )
