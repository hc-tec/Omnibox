"""Session 控制器

提供 Session 管理的 REST API：
- 创建/获取/关闭 Session
- 在 Session 内执行查询（保持上下文）
- 获取执行步骤记录
- 保存为工作流模板
"""

import logging
from typing import Optional, Any, List
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.concurrency import run_in_threadpool

from api.schemas.session import (
    CreateSessionRequest,
    CreateSessionResponse,
    GetSessionResponse,
    SessionInfo,
    SessionChatRequest,
    SessionChatResponse,
    GetRecordedStepsResponse,
    RecordedStepInfo,
    SaveAsTemplateRequest,
    SaveAsTemplateResponse,
    CloseSessionResponse,
    ListSessionsResponse,
)
from api.schemas.panel import PanelPayload

from services.session import (
    SessionRuntimeManager,
    get_session_runtime_manager,
    SessionState,
    SessionStatus,
    RecordedStep,
    get_workflow_extractor,
)
from services.workflow.models import TemplateCategory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

# 全局 RuntimeManager 实例
_runtime_manager: Optional[SessionRuntimeManager] = None


def get_runtime_manager() -> SessionRuntimeManager:
    """获取 SessionRuntimeManager（依赖注入）"""
    global _runtime_manager
    if _runtime_manager is None:
        raise HTTPException(
            status_code=503,
            detail="SessionRuntimeManager 未初始化"
        )
    return _runtime_manager


def initialize_session_services(
    llm_client: Any = None,
    data_query_service: Any = None
):
    """
    初始化 Session 服务

    Args:
        llm_client: LLM 客户端
        data_query_service: 数据查询服务
    """
    global _runtime_manager
    _runtime_manager = get_session_runtime_manager(
        llm_client=llm_client,
        data_query_service=data_query_service
    )
    _runtime_manager.start_cleanup_thread()
    logger.info("Session 服务初始化完成")


def shutdown_session_services():
    """关闭 Session 服务"""
    global _runtime_manager
    if _runtime_manager:
        _runtime_manager.stop_cleanup_thread()
        _runtime_manager = None
    logger.info("Session 服务已关闭")


def _session_state_to_info(state: SessionState) -> SessionInfo:
    """将 SessionState 转换为 SessionInfo"""
    return SessionInfo(
        session_id=state.session_id,
        name=f"Session {state.session_id[:12]}",
        status=state.status.value,
        workspace_id=None,  # SessionState 不存储 workspace_id
        source_workflow_id=state.source_workflow_id,
        data_stash_count=len(state.data_stash),
        chat_history_count=len(state.chat_history),
        recorded_steps_count=len(state.recorded_steps),
        created_at=state.created_at,
        last_active_at=state.last_active_at,
    )


@router.post(
    "",
    response_model=CreateSessionResponse,
    summary="创建 Session",
    description="创建新的工作会话"
)
async def create_session(
    request: CreateSessionRequest,
    runtime_manager: SessionRuntimeManager = Depends(get_runtime_manager)
) -> CreateSessionResponse:
    """创建新 Session"""
    try:
        state = await run_in_threadpool(
            runtime_manager.create_session,
            workspace_id=request.workspace_id,
            source_workflow_id=request.source_workflow_id,
            name=request.name
        )

        return CreateSessionResponse(
            success=True,
            session=_session_state_to_info(state)
        )

    except Exception as e:
        logger.error(f"创建 Session 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{session_id}",
    response_model=GetSessionResponse,
    summary="获取 Session",
    description="获取 Session 信息"
)
async def get_session(
    session_id: str,
    runtime_manager: SessionRuntimeManager = Depends(get_runtime_manager)
) -> GetSessionResponse:
    """获取 Session 信息"""
    try:
        state = await run_in_threadpool(
            runtime_manager.get_session,
            session_id=session_id
        )

        if not state:
            return GetSessionResponse(
                success=False,
                session=None,
                error=f"Session 不存在或已过期: {session_id}"
            )

        return GetSessionResponse(
            success=True,
            session=_session_state_to_info(state)
        )

    except Exception as e:
        logger.error(f"获取 Session 失败: {e}", exc_info=True)
        return GetSessionResponse(
            success=False,
            session=None,
            error=str(e)
        )


@router.post(
    "/{session_id}/chat",
    response_model=SessionChatResponse,
    summary="Session 内对话",
    description="在 Session 内执行查询，保持上下文"
)
async def session_chat(
    session_id: str,
    request: SessionChatRequest,
    runtime_manager: SessionRuntimeManager = Depends(get_runtime_manager)
) -> SessionChatResponse:
    """在 Session 内执行查询"""
    try:
        # 执行查询
        result = await run_in_threadpool(
            runtime_manager.execute_in_session,
            session_id=session_id,
            query=request.query,
            context=request.context
        )

        # 获取更新后的 Session 状态
        state = await run_in_threadpool(
            runtime_manager.get_session,
            session_id=session_id
        )

        session_summary = None
        if state:
            session_summary = {
                "data_stash_count": len(state.data_stash),
                "chat_history_count": len(state.chat_history),
                "recorded_steps_count": len(state.recorded_steps),
            }

        return SessionChatResponse(
            success=True,
            message="执行成功",
            final_report=result.final_report,
            # 将 data_stash 转换为可序列化的格式
            data=[ref.model_dump() if hasattr(ref, 'model_dump') else ref for ref in result.data_stash],
            data_blocks={},  # LangGraphExecutionResult 不包含 data_blocks
            session_summary=session_summary,
            execution_steps=result.execution_steps,
        )

    except ValueError as e:
        # Session 不存在
        return SessionChatResponse(
            success=False,
            message=str(e),
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Session 对话失败: {e}", exc_info=True)
        return SessionChatResponse(
            success=False,
            message="执行失败",
            error=str(e)
        )


@router.get(
    "/{session_id}/steps",
    response_model=GetRecordedStepsResponse,
    summary="获取执行步骤",
    description="获取 Session 记录的所有执行步骤"
)
async def get_recorded_steps(
    session_id: str,
    runtime_manager: SessionRuntimeManager = Depends(get_runtime_manager)
) -> GetRecordedStepsResponse:
    """获取 Session 的执行步骤"""
    try:
        steps = await run_in_threadpool(
            runtime_manager.get_recorded_steps,
            session_id=session_id
        )

        step_infos = [
            RecordedStepInfo(
                step_id=step.step_id,
                tool_id=step.tool_id,
                tool_name=step.tool_name,
                params=step.params,
                artifact_id=step.artifact_id,
                data_id=step.data_id,
                summary=step.summary,
                status=step.status,
                error_message=step.error_message,
                depends_on=step.depends_on,
                trigger_query=step.trigger_query,
                executed_at=step.executed_at,
            )
            for step in steps
        ]

        return GetRecordedStepsResponse(
            success=True,
            session_id=session_id,
            steps=step_infos
        )

    except Exception as e:
        logger.error(f"获取执行步骤失败: {e}", exc_info=True)
        return GetRecordedStepsResponse(
            success=False,
            session_id=session_id,
            steps=[],
            error=str(e)
        )


@router.post(
    "/{session_id}/save-as-template",
    response_model=SaveAsTemplateResponse,
    summary="保存为模板",
    description="将 Session 的执行记录保存为 Workflow 模板"
)
async def save_as_template(
    session_id: str,
    request: SaveAsTemplateRequest,
    runtime_manager: SessionRuntimeManager = Depends(get_runtime_manager)
) -> SaveAsTemplateResponse:
    """将 Session 保存为 Workflow 模板"""
    try:
        # 获取 Session 状态
        state = await run_in_threadpool(
            runtime_manager.get_session,
            session_id=session_id
        )

        if not state:
            return SaveAsTemplateResponse(
                success=False,
                error=f"Session 不存在或已过期: {session_id}"
            )

        if not state.recorded_steps:
            return SaveAsTemplateResponse(
                success=False,
                error="Session 没有执行记录，无法保存为模板"
            )

        # 解析 category
        category = None
        if request.category:
            try:
                category = TemplateCategory(request.category)
            except ValueError:
                category = TemplateCategory.CUSTOM

        # 提取工作流
        extractor = get_workflow_extractor()
        workflow = await run_in_threadpool(
            extractor.extract_workflow,
            session_state=state,
            name=request.name,
            description=request.description,
            category=category,
            extract_variables=request.extract_variables,
            save_to_store=True
        )

        return SaveAsTemplateResponse(
            success=True,
            workflow_id=workflow.workflow_id,
            workflow_name=workflow.name,
            steps_count=len(workflow.get_steps()),
            variables_count=len(workflow.get_variables()),
        )

    except Exception as e:
        logger.error(f"保存为模板失败: {e}", exc_info=True)
        return SaveAsTemplateResponse(
            success=False,
            error=str(e)
        )


@router.delete(
    "/{session_id}",
    response_model=CloseSessionResponse,
    summary="关闭 Session",
    description="关闭并清理 Session"
)
async def close_session(
    session_id: str,
    runtime_manager: SessionRuntimeManager = Depends(get_runtime_manager)
) -> CloseSessionResponse:
    """关闭 Session"""
    try:
        success = await run_in_threadpool(
            runtime_manager.close_session,
            session_id=session_id
        )

        if success:
            return CloseSessionResponse(
                success=True,
                session_id=session_id
            )
        else:
            return CloseSessionResponse(
                success=False,
                session_id=session_id,
                error="Session 不存在"
            )

    except Exception as e:
        logger.error(f"关闭 Session 失败: {e}", exc_info=True)
        return CloseSessionResponse(
            success=False,
            session_id=session_id,
            error=str(e)
        )


@router.get(
    "",
    response_model=ListSessionsResponse,
    summary="列出 Sessions",
    description="列出所有 Sessions"
)
async def list_sessions(
    workspace_id: Optional[str] = Query(None, description="过滤 Workspace ID"),
    status: Optional[str] = Query(None, description="过滤状态"),
    limit: int = Query(100, ge=1, le=1000, description="最大返回数量"),
    runtime_manager: SessionRuntimeManager = Depends(get_runtime_manager)
) -> ListSessionsResponse:
    """列出 Sessions"""
    try:
        # 解析状态
        status_filter = None
        if status:
            try:
                status_filter = SessionStatus(status)
            except ValueError:
                pass

        # 从存储层获取列表
        sessions = await run_in_threadpool(
            runtime_manager.session_store.list_sessions,
            workspace_id=workspace_id,
            status=status_filter,
            limit=limit
        )

        session_infos = []
        for session in sessions:
            state = session.get_state()
            info = SessionInfo(
                session_id=session.session_id,
                name=session.name,
                status=session.status,
                workspace_id=session.workspace_id,
                source_workflow_id=session.source_workflow_id,
                data_stash_count=len(state.data_stash),
                chat_history_count=len(state.chat_history),
                recorded_steps_count=len(state.recorded_steps),
                created_at=session.created_at,
                last_active_at=session.last_active_at,
            )
            session_infos.append(info)

        return ListSessionsResponse(
            success=True,
            sessions=session_infos,
            total=len(session_infos)
        )

    except Exception as e:
        logger.error(f"列出 Sessions 失败: {e}", exc_info=True)
        return ListSessionsResponse(
            success=False,
            sessions=[],
            total=0,
            error=str(e)
        )
