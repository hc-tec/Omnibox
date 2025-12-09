"""工作流 Controller

Phase 3: Workspace UI 后端接口
提供工作流管理和执行的 RESTful API 端点。
"""

import logging
from datetime import datetime
from typing import Optional, List

import asyncio
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, WebSocket, WebSocketDisconnect

from api.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowListResponse,
    WorkflowStepSchema,
    VariableSchema,
    RunCreate,
    RunResponse,
    RunListResponse,
    StepStatusSchema,
    ArtifactSchema,
    ArtifactListResponse,
    ArtifactDataResponse,
    ProgressEventSchema,
)
from services.workflow.store import get_workflow_store
from services.workflow.models import (
    Workflow,
    WorkflowStep,
    WorkflowRun,
    WorkflowStatus,
    RunStatus,
    Variable,
)
from services.artifact.store import get_artifact_store
from services.artifact.models import ArtifactType

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(
    prefix="/api/v1/workflows",
    tags=["workflows"]
)


# ========== 辅助函数 ==========

def _workflow_to_response(workflow: Workflow) -> WorkflowResponse:
    """将 Workflow 模型转换为 API 响应"""
    steps = workflow.get_steps()
    variables = workflow.get_variables()
    tags = workflow.get_tags()

    return WorkflowResponse(
        workflow_id=workflow.workflow_id,
        name=workflow.name,
        description=workflow.description,
        status=WorkflowStatus(workflow.status),
        steps=[
            WorkflowStepSchema(
                step_id=s.step_id,
                name=s.name,
                description=s.description,
                step_type=s.step_type,
                tool_id=s.tool_id,
                params=s.params,
                depends_on=s.depends_on,
                output_name=s.output_name,
            )
            for s in steps
        ],
        variables={
            name: VariableSchema(
                name=v.name,
                var_type=v.var_type,
                description=v.description,
                default=v.default,
                required=v.required,
                enum_values=v.enum_values,
            )
            for name, v in variables.items()
        },
        tags=tags,
        is_template=workflow.is_template,
        template_source_id=workflow.template_source_id,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
    )


def _run_to_response(run: WorkflowRun, total_steps: int = 0) -> RunResponse:
    """将 WorkflowRun 模型转换为 API 响应"""
    artifact_ids = run.get_artifact_ids()
    completed_step_ids = run.get_completed_step_ids()

    # 构建步骤状态列表
    step_statuses = []
    for step_id in range(1, total_steps + 1):
        if step_id in completed_step_ids:
            status = "completed"
        elif run.current_step_id == step_id:
            status = "running"
        else:
            status = "pending"

        step_statuses.append(StepStatusSchema(
            step_id=step_id,
            status=status,
            artifact_id=artifact_ids.get(step_id),
            error_message=run.error_message if status == "running" and run.status == RunStatus.FAILED.value else None
        ))

    return RunResponse(
        run_id=run.run_id,
        workflow_id=run.workflow_id,
        status=RunStatus(run.status),
        current_step_id=run.current_step_id,
        completed_step_ids=completed_step_ids,
        step_statuses=step_statuses,
        variable_values=run.get_variable_values(),
        artifact_ids=artifact_ids,
        progress_percent=run.calculate_progress(total_steps),
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
    )


# ========== 工作流 CRUD ==========

@router.get("", response_model=WorkflowListResponse, summary="列出工作流")
async def list_workflows(
    status: Optional[str] = Query(None, description="状态筛选：draft/ready/template"),
    is_template: Optional[bool] = Query(None, description="是否为模板"),
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """列出工作流"""
    try:
        store = get_workflow_store()

        status_filter = WorkflowStatus(status) if status else None
        workflows = store.list_workflows(
            status=status_filter,
            is_template=is_template,
            limit=limit,
            offset=offset,
        )

        # 计算总数（简化处理，后续可优化为独立 count 查询）
        all_workflows = store.list_workflows(
            status=status_filter,
            is_template=is_template,
            limit=10000,
            offset=0,
        )
        total = len(all_workflows)

        items = [_workflow_to_response(w) for w in workflows]
        return WorkflowListResponse(total=total, items=items)

    except Exception as e:
        logger.error(f"列出工作流失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"列出工作流失败: {str(e)}")


@router.post("", response_model=WorkflowResponse, status_code=201, summary="创建工作流")
async def create_workflow(request: WorkflowCreate):
    """创建工作流"""
    try:
        store = get_workflow_store()

        # 创建步骤列表
        steps = [
            WorkflowStep(
                step_id=i + 1,
                name=s.name,
                description=s.description,
                step_type=s.step_type,
                tool_id=s.tool_id,
                params=s.params,
                depends_on=s.depends_on,
                output_name=s.output_name or f"{s.name}_output",
            )
            for i, s in enumerate(request.steps)
        ]

        # 创建变量字典
        variables = {
            name: Variable(
                name=v.name,
                var_type=v.var_type,
                description=v.description,
                default=v.default,
                required=v.required,
                enum_values=v.enum_values,
            )
            for name, v in request.variables.items()
        }

        # 创建工作流
        workflow = Workflow.create(
            name=request.name,
            description=request.description,
            steps=steps,
            variables=variables,
            is_template=request.is_template,
        )
        workflow.set_tags(request.tags)

        # 验证依赖关系
        errors = workflow.validate_dependencies()
        if errors:
            raise HTTPException(status_code=400, detail=f"步骤依赖验证失败: {errors}")

        # 保存
        store.save_workflow(workflow)
        logger.info(f"创建工作流: {workflow.workflow_id}")

        return _workflow_to_response(workflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建工作流失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建工作流失败: {str(e)}")


@router.get("/{workflow_id}", response_model=WorkflowResponse, summary="获取工作流详情")
async def get_workflow(workflow_id: str):
    """获取工作流详情"""
    store = get_workflow_store()
    workflow = store.load_workflow(workflow_id)

    if not workflow:
        raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")

    return _workflow_to_response(workflow)


@router.patch("/{workflow_id}", response_model=WorkflowResponse, summary="更新工作流")
async def update_workflow(workflow_id: str, request: WorkflowUpdate):
    """更新工作流"""
    try:
        store = get_workflow_store()
        workflow = store.load_workflow(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")

        # 更新字段
        if request.name is not None:
            workflow.name = request.name
        if request.description is not None:
            workflow.description = request.description
        if request.status is not None:
            workflow.status = request.status.value
        if request.tags is not None:
            workflow.set_tags(request.tags)

        # 更新步骤
        if request.steps is not None:
            steps = [
                WorkflowStep(
                    step_id=i + 1,
                    name=s.name,
                    description=s.description,
                    step_type=s.step_type,
                    tool_id=s.tool_id,
                    params=s.params,
                    depends_on=s.depends_on,
                    output_name=s.output_name or f"{s.name}_output",
                )
                for i, s in enumerate(request.steps)
            ]
            workflow.set_steps(steps)

            # 验证依赖关系
            errors = workflow.validate_dependencies()
            if errors:
                raise HTTPException(status_code=400, detail=f"步骤依赖验证失败: {errors}")

        # 更新变量
        if request.variables is not None:
            variables = {
                name: Variable(
                    name=v.name,
                    var_type=v.var_type,
                    description=v.description,
                    default=v.default,
                    required=v.required,
                    enum_values=v.enum_values,
                )
                for name, v in request.variables.items()
            }
            workflow.set_variables(variables)

        workflow.updated_at = datetime.now()
        store.save_workflow(workflow)
        logger.info(f"更新工作流: {workflow_id}")

        return _workflow_to_response(workflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新工作流失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新工作流失败: {str(e)}")


@router.delete("/{workflow_id}", status_code=204, summary="删除工作流")
async def delete_workflow(workflow_id: str):
    """删除工作流"""
    store = get_workflow_store()
    success = store.delete_workflow(workflow_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")

    return None


# ========== 执行管理 ==========

@router.post("/{workflow_id}/runs", response_model=RunResponse, status_code=201, summary="启动执行")
async def start_run(
    workflow_id: str,
    request: RunCreate,
    background_tasks: BackgroundTasks,
):
    """启动工作流执行"""
    try:
        store = get_workflow_store()
        workflow = store.load_workflow(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")

        # 创建执行实例
        run = WorkflowRun.create(
            workflow_id=workflow_id,
            variable_values=request.variable_values,
        )
        run.started_at = datetime.now()
        run.status = RunStatus.RUNNING.value

        # 保存执行实例
        store.save_run(run)
        logger.info(f"启动执行: {run.run_id} (workflow: {workflow_id})")

        # TODO: 在后台任务中启动 ExecutionEngine
        # background_tasks.add_task(_execute_workflow, run.run_id)

        total_steps = len(workflow.get_steps())
        return _run_to_response(run, total_steps)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"启动执行失败: {str(e)}")


@router.get("/{workflow_id}/runs", response_model=RunListResponse, summary="列出执行记录")
async def list_runs(
    workflow_id: str,
    status: Optional[str] = Query(None, description="状态筛选"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """列出工作流的执行记录"""
    try:
        store = get_workflow_store()

        # 验证工作流存在
        workflow = store.load_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")

        status_filter = RunStatus(status) if status else None
        runs = store.list_runs(
            workflow_id=workflow_id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )

        total_steps = len(workflow.get_steps())
        items = [_run_to_response(r, total_steps) for r in runs]

        # 计算总数
        all_runs = store.list_runs(workflow_id=workflow_id, limit=10000)
        total = len(all_runs)

        return RunListResponse(total=total, items=items)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"列出执行记录失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"列出执行记录失败: {str(e)}")


@router.get("/{workflow_id}/runs/{run_id}", response_model=RunResponse, summary="获取执行详情")
async def get_run(workflow_id: str, run_id: str):
    """获取执行详情"""
    store = get_workflow_store()

    workflow = store.load_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")

    run = store.load_run(run_id)
    if not run or run.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail=f"执行记录不存在: {run_id}")

    total_steps = len(workflow.get_steps())
    return _run_to_response(run, total_steps)


@router.post("/{workflow_id}/runs/{run_id}/pause", response_model=RunResponse, summary="暂停执行")
async def pause_run(workflow_id: str, run_id: str):
    """暂停执行"""
    store = get_workflow_store()

    workflow = store.load_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")

    run = store.load_run(run_id)
    if not run or run.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail=f"执行记录不存在: {run_id}")

    if run.status != RunStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail=f"只能暂停运行中的执行，当前状态: {run.status}")

    store.update_run_status(run_id, RunStatus.PAUSED)
    run = store.load_run(run_id)

    total_steps = len(workflow.get_steps())
    return _run_to_response(run, total_steps)


@router.post("/{workflow_id}/runs/{run_id}/resume", response_model=RunResponse, summary="恢复执行")
async def resume_run(
    workflow_id: str,
    run_id: str,
    background_tasks: BackgroundTasks,
):
    """恢复执行"""
    store = get_workflow_store()

    workflow = store.load_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")

    run = store.load_run(run_id)
    if not run or run.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail=f"执行记录不存在: {run_id}")

    if run.status != RunStatus.PAUSED.value:
        raise HTTPException(status_code=400, detail=f"只能恢复已暂停的执行，当前状态: {run.status}")

    store.update_run_status(run_id, RunStatus.RUNNING)
    run = store.load_run(run_id)

    # TODO: 在后台任务中恢复 ExecutionEngine
    # background_tasks.add_task(_resume_execution, run_id)

    total_steps = len(workflow.get_steps())
    return _run_to_response(run, total_steps)


@router.post("/{workflow_id}/runs/{run_id}/cancel", response_model=RunResponse, summary="取消执行")
async def cancel_run(workflow_id: str, run_id: str):
    """取消执行"""
    store = get_workflow_store()

    workflow = store.load_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")

    run = store.load_run(run_id)
    if not run or run.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail=f"执行记录不存在: {run_id}")

    if run.status not in (RunStatus.RUNNING.value, RunStatus.PAUSED.value):
        raise HTTPException(status_code=400, detail=f"只能取消运行中或暂停的执行，当前状态: {run.status}")

    store.update_run_status(run_id, RunStatus.CANCELLED)
    run = store.load_run(run_id)

    total_steps = len(workflow.get_steps())
    return _run_to_response(run, total_steps)


# ========== 产物查询 ==========

@router.get("/{workflow_id}/artifacts", response_model=ArtifactListResponse, summary="列出工作流产物")
async def list_workflow_artifacts(
    workflow_id: str,
    artifact_type: Optional[str] = Query(None, description="类型筛选"),
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """列出工作流产生的产物"""
    try:
        workflow_store = get_workflow_store()
        artifact_store = get_artifact_store()

        # 验证工作流存在
        workflow = workflow_store.load_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")

        type_filter = ArtifactType(artifact_type) if artifact_type else None
        artifacts = artifact_store.list_artifacts(
            workflow_id=workflow_id,
            artifact_type=type_filter,
            limit=limit,
            offset=offset,
        )

        items = [
            ArtifactSchema(
                artifact_id=a.artifact_id,
                artifact_type=a.artifact_type.value,
                name=a.name,
                description=a.description,
                summary=a.summary,
                schema_info=a.schema_info,
                statistics=a.statistics,
                sample_items=a.sample_items or [],
                tags=a.tags,
                created_at=a.source.created_at if a.source else datetime.now(),
            )
            for a in artifacts
        ]

        # 计算总数
        all_artifacts = artifact_store.list_artifacts(workflow_id=workflow_id, limit=10000)
        total = len(all_artifacts)

        return ArtifactListResponse(total=total, items=items)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"列出产物失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"列出产物失败: {str(e)}")


@router.get("/{workflow_id}/artifacts/{artifact_id}", response_model=ArtifactSchema, summary="获取产物详情")
async def get_artifact(workflow_id: str, artifact_id: str):
    """获取产物详情"""
    artifact_store = get_artifact_store()
    artifact = artifact_store.load_artifact(artifact_id)

    if not artifact:
        raise HTTPException(status_code=404, detail=f"产物不存在: {artifact_id}")

    # 验证产物属于该工作流
    if artifact.source and artifact.source.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail=f"产物不属于该工作流")

    return ArtifactSchema(
        artifact_id=artifact.artifact_id,
        artifact_type=artifact.artifact_type.value,
        name=artifact.name,
        description=artifact.description,
        summary=artifact.summary,
        schema_info=artifact.schema_info,
        statistics=artifact.statistics,
        sample_items=artifact.sample_items or [],
        tags=artifact.tags,
        created_at=artifact.source.created_at if artifact.source else datetime.now(),
    )


@router.get("/{workflow_id}/artifacts/{artifact_id}/data", response_model=ArtifactDataResponse, summary="获取产物数据")
async def get_artifact_data(workflow_id: str, artifact_id: str):
    """获取产物完整数据"""
    artifact_store = get_artifact_store()
    artifact = artifact_store.load_artifact(artifact_id)

    if not artifact:
        raise HTTPException(status_code=404, detail=f"产物不存在: {artifact_id}")

    # 验证产物属于该工作流
    if artifact.source and artifact.source.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail=f"产物不属于该工作流")

    # 加载完整数据
    data = artifact_store.load_data(artifact.data_id) if artifact.data_id else None

    total_rows = 0
    if isinstance(data, list):
        total_rows = len(data)
    elif isinstance(data, dict) and "items" in data:
        total_rows = len(data["items"])

    return ArtifactDataResponse(
        artifact_id=artifact_id,
        data=data,
        total_rows=total_rows,
    )


# ========== WebSocket 进度推送 ==========

# 活跃的 WebSocket 连接管理（run_id -> List[WebSocket]）
_active_connections: dict[str, list[WebSocket]] = {}


async def broadcast_progress(run_id: str, event: ProgressEventSchema):
    """向所有监听该 run 的客户端广播进度事件"""
    if run_id not in _active_connections:
        return

    message = event.model_dump()
    message["timestamp"] = message["timestamp"].isoformat() if hasattr(message["timestamp"], "isoformat") else str(message["timestamp"])

    disconnected = []
    for ws in _active_connections[run_id]:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)

    # 移除断开的连接
    for ws in disconnected:
        _active_connections[run_id].remove(ws)


@router.websocket("/{workflow_id}/runs/{run_id}/stream")
async def run_progress_stream(websocket: WebSocket, workflow_id: str, run_id: str):
    """
    工作流执行进度 WebSocket 流

    连接后实时推送执行进度事件，直到执行完成或客户端断开。

    消息格式（ProgressEventSchema）：
    ```json
    {
        "run_id": "run-abc123",
        "event_type": "step_started|step_completed|step_failed|run_completed|run_failed",
        "step_id": 1,
        "step_name": "数据采集",
        "artifact_id": "artifact-xyz789",
        "message": "正在执行...",
        "progress_percent": 50.0,
        "timestamp": "2025-01-01T12:00:00.000000"
    }
    ```

    连接地址: ws://host:port/api/v1/workflows/{workflow_id}/runs/{run_id}/stream
    """
    # 验证工作流和执行实例
    store = get_workflow_store()
    workflow = store.load_workflow(workflow_id)

    if not workflow:
        await websocket.close(code=4004, reason="工作流不存在")
        return

    run = store.load_run(run_id)
    if not run or run.workflow_id != workflow_id:
        await websocket.close(code=4004, reason="执行记录不存在")
        return

    # 接受连接
    await websocket.accept()
    logger.info(f"WebSocket 连接建立: run={run_id}")

    # 注册连接
    if run_id not in _active_connections:
        _active_connections[run_id] = []
    _active_connections[run_id].append(websocket)

    try:
        # 发送当前状态
        total_steps = len(workflow.get_steps())
        steps = workflow.get_steps()
        completed_step_ids = run.get_completed_step_ids()

        initial_event = ProgressEventSchema(
            run_id=run_id,
            event_type="status_update",
            step_id=run.current_step_id,
            step_name=steps[run.current_step_id - 1].name if run.current_step_id and run.current_step_id <= len(steps) else None,
            message=f"当前状态: {run.status}",
            progress_percent=run.calculate_progress(total_steps),
            timestamp=datetime.now(),
        )
        await websocket.send_json(initial_event.model_dump(mode="json"))

        # 保持连接，等待进度更新或执行完成
        while True:
            # 检查执行状态
            run = store.load_run(run_id)
            if not run:
                break

            # 如果执行已结束，发送完成事件并关闭
            if run.status in (RunStatus.COMPLETED.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value):
                final_event = ProgressEventSchema(
                    run_id=run_id,
                    event_type=f"run_{run.status}",
                    message=run.error_message or f"执行{run.status}",
                    progress_percent=run.calculate_progress(total_steps),
                    timestamp=datetime.now(),
                )
                await websocket.send_json(final_event.model_dump(mode="json"))
                break

            # 等待客户端 ping 或超时（保持连接活跃）
            try:
                # 设置超时，允许客户端发送 ping 或其他消息
                data = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
                # 处理客户端消息（如 ping）
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # 超时是正常的，继续轮询状态
                pass
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket 客户端断开: run={run_id}")
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}", exc_info=True)
    finally:
        # 移除连接
        if run_id in _active_connections and websocket in _active_connections[run_id]:
            _active_connections[run_id].remove(websocket)
            if not _active_connections[run_id]:
                del _active_connections[run_id]
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info(f"WebSocket 连接关闭: run={run_id}")
