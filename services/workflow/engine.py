"""
工作流执行引擎

Phase 2: WorkflowEngine - 工作流生命周期管理
"""

import logging
from datetime import datetime
from typing import Callable, Optional, Dict, Any, List

from langgraph_agents.state import ExecutionPlan, ToolCall, GraphState, DataReference
from langgraph_agents.execution_engine import ExecutionEngine
from langgraph_agents.runtime import ToolExecutionContext
from langgraph_agents.tools.registry import ToolRegistry
from langgraph_agents.storage import ResearchDataStore

from services.artifact import (
    DataArtifact,
    ArtifactStore,
    ArtifactType,
    suggest_views,
    get_artifact_store,
)

from .models import (
    Workflow,
    WorkflowStep,
    WorkflowRun,
    RunStatus,
    StepType,
    ProgressEvent,
)
from .store import WorkflowStore, get_workflow_store
from .variable_resolver import VariableResolver, VariableValidationError

logger = logging.getLogger(__name__)

# 进度回调类型
ProgressCallback = Callable[[ProgressEvent], None]


class WorkflowExecutionError(Exception):
    """工作流执行错误"""
    pass


class WorkflowEngine:
    """
    工作流执行引擎

    职责：
    1. 将 Workflow 转换为 ExecutionPlan
    2. 调用 ExecutionEngine 执行
    3. 管理执行生命周期（运行、暂停、恢复）
    4. 进度回调通知
    5. 产物关联管理
    """

    def __init__(
        self,
        workflow_store: Optional[WorkflowStore] = None,
        artifact_store: Optional[ArtifactStore] = None,
        tool_registry: Optional[ToolRegistry] = None,
        data_store: Optional[ResearchDataStore] = None,
        progress_callback: Optional[ProgressCallback] = None
    ):
        """
        初始化执行引擎

        Args:
            workflow_store: 工作流存储层
            artifact_store: 产物存储层
            tool_registry: 工具注册表
            data_store: 数据存储
            progress_callback: 进度回调函数
        """
        self.workflow_store = workflow_store or get_workflow_store()
        self.artifact_store = artifact_store or get_artifact_store()
        self.tool_registry = tool_registry
        self.data_store = data_store
        self.progress_callback = progress_callback
        self.variable_resolver = VariableResolver()

        # 当前执行的 run（用于暂停/恢复）
        self._current_run: Optional[WorkflowRun] = None
        self._pause_requested: bool = False

    def start_run(
        self,
        workflow_id: str,
        variable_values: Optional[Dict[str, Any]] = None
    ) -> WorkflowRun:
        """
        启动工作流执行

        Args:
            workflow_id: 工作流 ID
            variable_values: 变量值

        Returns:
            WorkflowRun 实例

        Raises:
            WorkflowExecutionError: 执行失败
        """
        # 1. 加载工作流
        workflow = self.workflow_store.load_workflow(workflow_id)
        if not workflow:
            raise WorkflowExecutionError(f"工作流不存在: {workflow_id}")

        # 2. 验证依赖关系
        errors = workflow.validate_dependencies()
        if errors:
            raise WorkflowExecutionError(f"工作流依赖验证失败: {'; '.join(errors)}")

        # 3. 验证变量
        variables = workflow.get_variables()
        values = variable_values or {}
        try:
            # 验证并合并默认值
            validation_errors = self.variable_resolver.validate(variables, values)
            if validation_errors:
                raise WorkflowExecutionError(f"变量验证失败: {'; '.join(validation_errors)}")
        except VariableValidationError as e:
            raise WorkflowExecutionError(str(e))

        # 4. 创建执行实例
        run = WorkflowRun.create(workflow_id=workflow_id, variable_values=values)
        run.status = RunStatus.RUNNING.value
        run.started_at = datetime.now()
        self.workflow_store.save_run(run)

        # 5. 发送开始事件
        self._emit_progress(ProgressEvent(
            run_id=run.run_id,
            event_type="started",
            message=f"开始执行工作流: {workflow.name}",
            progress_percent=0.0
        ))

        # 6. 执行工作流
        try:
            self._current_run = run
            self._pause_requested = False
            self._execute_workflow(workflow, run)
        except Exception as e:
            logger.error(f"WorkflowEngine: 执行失败 - {e}", exc_info=True)
            run.status = RunStatus.FAILED.value
            run.error_message = str(e)
            run.completed_at = datetime.now()
            self.workflow_store.save_run(run)

            self._emit_progress(ProgressEvent(
                run_id=run.run_id,
                event_type="failed",
                message=f"执行失败: {e}",
                progress_percent=run.calculate_progress(len(workflow.get_steps()))
            ))
            raise WorkflowExecutionError(str(e))
        finally:
            self._current_run = None

        return run

    def pause_run(self, run_id: str) -> bool:
        """
        暂停执行（步骤级暂停：当前步骤完成后暂停）

        Args:
            run_id: 执行实例 ID

        Returns:
            是否成功请求暂停
        """
        run = self.workflow_store.load_run(run_id)
        if not run:
            logger.warning(f"WorkflowEngine: 执行实例不存在 {run_id}")
            return False

        if run.status != RunStatus.RUNNING.value:
            logger.warning(f"WorkflowEngine: 执行实例状态不是 RUNNING: {run.status}")
            return False

        # 如果是当前正在执行的 run，设置暂停标志
        if self._current_run and self._current_run.run_id == run_id:
            self._pause_requested = True
            logger.info(f"WorkflowEngine: 请求暂停 {run_id}")
            return True

        # 否则直接更新状态
        run.status = RunStatus.PAUSED.value
        self.workflow_store.save_run(run)
        logger.info(f"WorkflowEngine: 已暂停 {run_id}")
        return True

    def resume_run(self, run_id: str) -> Optional[WorkflowRun]:
        """
        恢复执行

        Args:
            run_id: 执行实例 ID

        Returns:
            WorkflowRun 实例，失败返回 None
        """
        run = self.workflow_store.load_run(run_id)
        if not run:
            logger.warning(f"WorkflowEngine: 执行实例不存在 {run_id}")
            return None

        if run.status != RunStatus.PAUSED.value:
            logger.warning(f"WorkflowEngine: 执行实例状态不是 PAUSED: {run.status}")
            return None

        # 加载工作流
        workflow = self.workflow_store.load_workflow(run.workflow_id)
        if not workflow:
            logger.error(f"WorkflowEngine: 工作流不存在 {run.workflow_id}")
            return None

        # 恢复执行
        run.status = RunStatus.RUNNING.value
        self.workflow_store.save_run(run)

        self._emit_progress(ProgressEvent(
            run_id=run.run_id,
            event_type="resumed",
            message="恢复执行",
            progress_percent=run.calculate_progress(len(workflow.get_steps()))
        ))

        try:
            self._current_run = run
            self._pause_requested = False
            self._execute_workflow(workflow, run)
        except Exception as e:
            logger.error(f"WorkflowEngine: 恢复执行失败 - {e}", exc_info=True)
            run.status = RunStatus.FAILED.value
            run.error_message = str(e)
            run.completed_at = datetime.now()
            self.workflow_store.save_run(run)
            return None
        finally:
            self._current_run = None

        return run

    def cancel_run(self, run_id: str) -> bool:
        """
        取消执行

        Args:
            run_id: 执行实例 ID

        Returns:
            是否取消成功
        """
        run = self.workflow_store.load_run(run_id)
        if not run:
            return False

        if run.status in (RunStatus.COMPLETED.value, RunStatus.CANCELLED.value):
            return False

        run.status = RunStatus.CANCELLED.value
        run.completed_at = datetime.now()
        self.workflow_store.save_run(run)

        self._emit_progress(ProgressEvent(
            run_id=run.run_id,
            event_type="cancelled",
            message="执行已取消"
        ))

        logger.info(f"WorkflowEngine: 取消执行 {run_id}")
        return True

    def get_run_status(self, run_id: str) -> Optional[WorkflowRun]:
        """获取执行状态"""
        return self.workflow_store.load_run(run_id)

    def _execute_workflow(self, workflow: Workflow, run: WorkflowRun) -> None:
        """
        执行工作流

        Args:
            workflow: 工作流定义
            run: 执行实例
        """
        steps = workflow.get_steps()
        variables = workflow.get_variables()
        values = run.get_variable_values()
        completed_step_ids = run.get_completed_step_ids()

        total_steps = len(steps)

        # 按依赖顺序执行
        max_iterations = total_steps * 2  # 防止死循环
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # 检查是否请求暂停
            if self._pause_requested:
                run.status = RunStatus.PAUSED.value
                self.workflow_store.save_run(run)
                self._emit_progress(ProgressEvent(
                    run_id=run.run_id,
                    event_type="paused",
                    message="执行已暂停",
                    progress_percent=run.calculate_progress(total_steps)
                ))
                logger.info(f"WorkflowEngine: 执行已暂停 {run.run_id}")
                return

            # 获取就绪的步骤
            ready_steps = self._get_ready_steps(steps, completed_step_ids)

            if not ready_steps:
                # 没有就绪步骤
                if len(completed_step_ids) == total_steps:
                    # 全部完成
                    break
                else:
                    # 可能存在循环依赖
                    logger.error(
                        f"WorkflowEngine: 无就绪步骤，可能存在循环依赖。"
                        f"已完成: {completed_step_ids}，总步骤: {total_steps}"
                    )
                    raise WorkflowExecutionError("执行计划存在循环依赖或无法继续")

            # 串行执行第一个就绪步骤
            step = ready_steps[0]

            # 更新当前步骤
            run.current_step_id = step.step_id
            self.workflow_store.save_run(run)

            # 发送步骤开始事件
            self._emit_progress(ProgressEvent(
                run_id=run.run_id,
                event_type="step_started",
                step_id=step.step_id,
                step_name=step.name,
                message=f"开始执行: {step.name}",
                progress_percent=run.calculate_progress(total_steps)
            ))

            # 执行步骤
            try:
                artifact_id = self._execute_step(workflow, run, step, variables, values)

                # 记录产物
                if artifact_id:
                    run.add_artifact(step.step_id, artifact_id)

                # 标记为已完成
                completed_step_ids.append(step.step_id)
                run.add_completed_step(step.step_id)
                self.workflow_store.save_run(run)

                # 发送步骤完成事件
                self._emit_progress(ProgressEvent(
                    run_id=run.run_id,
                    event_type="step_completed",
                    step_id=step.step_id,
                    step_name=step.name,
                    artifact_id=artifact_id,
                    message=f"完成: {step.name}",
                    progress_percent=run.calculate_progress(total_steps)
                ))

                logger.info(f"WorkflowEngine: 步骤 {step.step_id} ({step.name}) 执行完成")

            except Exception as e:
                logger.error(f"WorkflowEngine: 步骤 {step.step_id} 执行失败: {e}", exc_info=True)
                # 步骤失败，整个工作流失败
                raise WorkflowExecutionError(f"步骤 {step.name} 执行失败: {e}")

        # 全部完成
        run.status = RunStatus.COMPLETED.value
        run.completed_at = datetime.now()
        run.current_step_id = None
        self.workflow_store.save_run(run)

        self._emit_progress(ProgressEvent(
            run_id=run.run_id,
            event_type="completed",
            message=f"工作流执行完成",
            progress_percent=100.0
        ))

        logger.info(f"WorkflowEngine: 工作流执行完成 {run.run_id}")

    def _get_ready_steps(
        self,
        steps: List[WorkflowStep],
        completed_step_ids: List[int]
    ) -> List[WorkflowStep]:
        """获取所有依赖已满足的就绪步骤"""
        ready = []
        completed_set = set(completed_step_ids)

        for step in steps:
            # 跳过已完成的步骤
            if step.step_id in completed_set:
                continue

            # 检查依赖是否满足
            if all(dep_id in completed_set for dep_id in step.depends_on):
                ready.append(step)

        return ready

    def _execute_step(
        self,
        workflow: Workflow,
        run: WorkflowRun,
        step: WorkflowStep,
        variables: Dict,
        values: Dict[str, Any]
    ) -> Optional[str]:
        """
        执行单个步骤

        Returns:
            产物 ID，无产物返回 None
        """
        # 解析步骤参数中的变量
        resolved_params = self.variable_resolver.resolve(
            step.params,
            variables,
            values
        )

        # 解析步骤引用（$ref）
        resolved_params = self._resolve_step_references(resolved_params, run)

        logger.info(
            f"WorkflowEngine: 执行步骤 {step.step_id} ({step.tool_id}) "
            f"参数: {resolved_params}"
        )

        # 检查工具注册表
        if not self.tool_registry:
            logger.warning("WorkflowEngine: 工具注册表未配置，跳过实际执行")
            return self._create_mock_artifact(workflow, run, step)

        # 构建 ToolCall
        tool_call = ToolCall(
            plugin_id=step.tool_id,
            args=resolved_params,
            step_id=step.step_id,
            description=step.description or step.name
        )

        # 构建执行上下文
        context = ToolExecutionContext(
            extras={
                "data_store": self.data_store,
                "workflow_id": workflow.workflow_id,
                "run_id": run.run_id
            }
        )

        # 执行工具
        result = self.tool_registry.execute(tool_call, context)

        if result.status == "error":
            raise WorkflowExecutionError(
                f"工具执行失败: {result.error_message}"
            )

        # 创建 DataArtifact
        artifact_id = self._create_artifact_from_result(
            workflow, run, step, result
        )

        return artifact_id

    def _resolve_step_references(
        self,
        params: Dict[str, Any],
        run: WorkflowRun
    ) -> Dict[str, Any]:
        """
        解析参数中的步骤引用（$ref）

        格式：{"$ref": {"step_id": 1, "json_path": "data.field"}}
        """
        def resolve_value(value):
            if isinstance(value, dict):
                if "$ref" in value:
                    ref_data = value["$ref"]
                    step_id = ref_data.get("step_id")
                    artifact_ids = run.get_artifact_ids()

                    if step_id not in artifact_ids:
                        logger.warning(f"WorkflowEngine: 步骤 {step_id} 的产物不存在")
                        return value

                    artifact_id = artifact_ids[step_id]
                    artifact = self.artifact_store.load_artifact(artifact_id)

                    if not artifact:
                        return value

                    # 返回 data_id 作为引用
                    return artifact.data_id

                return {k: resolve_value(v) for k, v in value.items()}

            elif isinstance(value, list):
                return [resolve_value(item) for item in value]

            return value

        return resolve_value(params)

    def _create_artifact_from_result(
        self,
        workflow: Workflow,
        run: WorkflowRun,
        step: WorkflowStep,
        result
    ) -> str:
        """从工具执行结果创建 DataArtifact"""
        # 保存原始数据
        data_id = None
        if self.data_store and result.raw_output:
            data_id = self.data_store.save(result.raw_output)

        # 推断产物类型
        artifact_type = self._infer_artifact_type(step.step_type)

        # 创建 DataArtifact
        artifact = DataArtifact(
            step_id=step.step_id,
            tool_name=step.tool_id,
            data_id=data_id,
            summary=self._generate_summary(result.raw_output),
            status="success",
            artifact_type=artifact_type,
            name=step.output_name or f"{step.name}_output",
        )

        # 设置来源
        artifact.source.workflow_id = workflow.workflow_id
        artifact.source.step_id = step.step_id
        artifact.source.tool_name = step.tool_id

        # 自动生成 ViewSpec
        if artifact.schema_info or artifact.sample_items:
            artifact.suggested_views = suggest_views(
                artifact.schema_info,
                artifact.statistics,
                artifact.sample_items
            )

        # 保存产物
        artifact_id = self.artifact_store.save_artifact(artifact)

        logger.info(f"WorkflowEngine: 创建产物 {artifact_id} (step={step.step_id})")
        return artifact_id

    def _create_mock_artifact(
        self,
        workflow: Workflow,
        run: WorkflowRun,
        step: WorkflowStep
    ) -> str:
        """创建模拟产物（测试用）"""
        artifact_type = self._infer_artifact_type(step.step_type)

        artifact = DataArtifact(
            step_id=step.step_id,
            tool_name=step.tool_id,
            summary=f"[模拟] {step.name} 执行完成",
            status="success",
            artifact_type=artifact_type,
            name=step.output_name or f"{step.name}_output",
        )

        artifact.source.workflow_id = workflow.workflow_id
        artifact.source.step_id = step.step_id
        artifact.source.tool_name = step.tool_id

        artifact_id = self.artifact_store.save_artifact(artifact)
        return artifact_id

    def _infer_artifact_type(self, step_type: StepType) -> ArtifactType:
        """根据步骤类型推断产物类型"""
        mapping = {
            StepType.FETCH: ArtifactType.DATASET,
            StepType.PROCESS: ArtifactType.ANALYSIS,
            StepType.ANALYZE: ArtifactType.INSIGHT,
            StepType.OUTPUT: ArtifactType.DOCUMENT,
        }
        return mapping.get(step_type, ArtifactType.DATASET)

    def _generate_summary(self, raw_output: Any, max_chars: int = 200) -> str:
        """生成简单摘要"""
        if raw_output is None:
            return "无数据"

        if isinstance(raw_output, list):
            return f"包含 {len(raw_output)} 条记录"

        if isinstance(raw_output, dict):
            keys = list(raw_output.keys())[:5]
            return f"包含字段: {', '.join(keys)}"

        text = str(raw_output)
        if len(text) > max_chars:
            return text[:max_chars - 3] + "..."
        return text

    def _emit_progress(self, event: ProgressEvent) -> None:
        """发送进度事件"""
        if self.progress_callback:
            try:
                self.progress_callback(event)
            except Exception as e:
                logger.warning(f"WorkflowEngine: 进度回调失败 - {e}")

        logger.debug(
            f"WorkflowEngine: 进度事件 [{event.event_type}] "
            f"run={event.run_id} step={event.step_id} {event.message}"
        )


# 便捷函数
def create_workflow_engine(
    progress_callback: Optional[ProgressCallback] = None,
    **kwargs
) -> WorkflowEngine:
    """创建 WorkflowEngine 实例"""
    return WorkflowEngine(progress_callback=progress_callback, **kwargs)
