"""
工作流存储层

Phase 2: WorkflowStore - SQLite 持久化
"""

import logging
from typing import Optional, List

from sqlmodel import Session, select, SQLModel

from services.database.connection import DatabaseConnection, get_db_connection
from .models import Workflow, WorkflowRun, WorkflowStatus, RunStatus

logger = logging.getLogger(__name__)

# 全局单例
_workflow_store: Optional["WorkflowStore"] = None


def get_workflow_store() -> "WorkflowStore":
    """获取 WorkflowStore 全局单例"""
    global _workflow_store
    if _workflow_store is None:
        _workflow_store = WorkflowStore()
    return _workflow_store


def reset_workflow_store() -> None:
    """重置全局单例（测试用）"""
    global _workflow_store
    _workflow_store = None


class WorkflowStore:
    """
    工作流存储层

    职责：
    1. Workflow CRUD
    2. WorkflowRun CRUD
    3. 查询（按状态、按模板）
    """

    def __init__(self):
        """初始化存储层，确保表已创建"""
        self._db = get_db_connection()
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """确保数据库表已创建"""
        # 导入模型以注册到 SQLModel
        from .models import Workflow, WorkflowRun
        SQLModel.metadata.create_all(self._db.engine)
        logger.info("WorkflowStore: 数据库表已初始化")

    def _get_session(self) -> Session:
        """获取数据库会话"""
        return self._db.get_session()

    # ========== Workflow CRUD ==========

    def save_workflow(self, workflow: Workflow) -> str:
        """
        保存工作流

        Args:
            workflow: 工作流对象

        Returns:
            workflow_id
        """
        with self._get_session() as session:
            # 检查是否存在
            existing = session.exec(
                select(Workflow).where(Workflow.workflow_id == workflow.workflow_id)
            ).first()

            if existing:
                # 更新现有记录
                existing.name = workflow.name
                existing.description = workflow.description
                existing.status = workflow.status
                existing.steps_json = workflow.steps_json
                existing.variables_json = workflow.variables_json
                existing.updated_at = workflow.updated_at
                existing.is_template = workflow.is_template
                existing.template_source_id = workflow.template_source_id
                existing.tags_json = workflow.tags_json
                session.add(existing)
            else:
                # 新增记录
                session.add(workflow)

            session.commit()
            logger.info(f"WorkflowStore: 保存工作流 {workflow.workflow_id}")
            return workflow.workflow_id

    def load_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """
        加载工作流

        Args:
            workflow_id: 工作流 ID

        Returns:
            Workflow 对象，不存在返回 None
        """
        with self._get_session() as session:
            workflow = session.exec(
                select(Workflow).where(Workflow.workflow_id == workflow_id)
            ).first()
            return workflow

    def list_workflows(
        self,
        status: Optional[WorkflowStatus] = None,
        is_template: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Workflow]:
        """
        查询工作流列表

        Args:
            status: 按状态筛选
            is_template: 按模板标记筛选
            tags: 按标签筛选（任一匹配）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            Workflow 列表
        """
        with self._get_session() as session:
            query = select(Workflow)

            if status:
                query = query.where(Workflow.status == status.value)
            if is_template is not None:
                query = query.where(Workflow.is_template == is_template)

            query = query.order_by(Workflow.updated_at.desc())
            query = query.offset(offset).limit(limit)

            workflows = list(session.exec(query).all())

            # 标签筛选（JSON 字段，需要后处理）
            if tags:
                workflows = [
                    w for w in workflows
                    if any(tag in w.get_tags() for tag in tags)
                ]

            return workflows

    def delete_workflow(self, workflow_id: str) -> bool:
        """
        删除工作流

        Args:
            workflow_id: 工作流 ID

        Returns:
            是否删除成功
        """
        with self._get_session() as session:
            workflow = session.exec(
                select(Workflow).where(Workflow.workflow_id == workflow_id)
            ).first()

            if not workflow:
                return False

            session.delete(workflow)
            session.commit()
            logger.info(f"WorkflowStore: 删除工作流 {workflow_id}")
            return True

    # ========== WorkflowRun CRUD ==========

    def save_run(self, run: WorkflowRun) -> str:
        """
        保存执行实例

        Args:
            run: 执行实例对象

        Returns:
            run_id
        """
        with self._get_session() as session:
            # 检查是否存在
            existing = session.exec(
                select(WorkflowRun).where(WorkflowRun.run_id == run.run_id)
            ).first()

            if existing:
                # 更新现有记录
                existing.status = run.status
                existing.current_step_id = run.current_step_id
                existing.completed_step_ids_json = run.completed_step_ids_json
                existing.variable_values_json = run.variable_values_json
                existing.artifact_ids_json = run.artifact_ids_json
                existing.started_at = run.started_at
                existing.completed_at = run.completed_at
                existing.error_message = run.error_message
                existing.execution_state_json = run.execution_state_json
                session.add(existing)
            else:
                # 新增记录
                session.add(run)

            session.commit()
            logger.debug(f"WorkflowStore: 保存执行实例 {run.run_id}")
            return run.run_id

    def load_run(self, run_id: str) -> Optional[WorkflowRun]:
        """
        加载执行实例

        Args:
            run_id: 执行实例 ID

        Returns:
            WorkflowRun 对象，不存在返回 None
        """
        with self._get_session() as session:
            run = session.exec(
                select(WorkflowRun).where(WorkflowRun.run_id == run_id)
            ).first()
            return run

    def list_runs(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[RunStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[WorkflowRun]:
        """
        查询执行实例列表

        Args:
            workflow_id: 按工作流 ID 筛选
            status: 按状态筛选
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            WorkflowRun 列表
        """
        with self._get_session() as session:
            query = select(WorkflowRun)

            if workflow_id:
                query = query.where(WorkflowRun.workflow_id == workflow_id)
            if status:
                query = query.where(WorkflowRun.status == status.value)

            query = query.order_by(WorkflowRun.started_at.desc())
            query = query.offset(offset).limit(limit)

            return list(session.exec(query).all())

    def update_run_status(
        self,
        run_id: str,
        status: RunStatus,
        current_step_id: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        更新执行状态

        Args:
            run_id: 执行实例 ID
            status: 新状态
            current_step_id: 当前步骤 ID
            error_message: 错误信息

        Returns:
            是否更新成功
        """
        with self._get_session() as session:
            run = session.exec(
                select(WorkflowRun).where(WorkflowRun.run_id == run_id)
            ).first()

            if not run:
                return False

            run.status = status.value
            if current_step_id is not None:
                run.current_step_id = current_step_id
            if error_message is not None:
                run.error_message = error_message

            session.add(run)
            session.commit()
            logger.info(f"WorkflowStore: 更新执行状态 {run_id} -> {status.value}")
            return True

    def delete_run(self, run_id: str) -> bool:
        """
        删除执行实例

        Args:
            run_id: 执行实例 ID

        Returns:
            是否删除成功
        """
        with self._get_session() as session:
            run = session.exec(
                select(WorkflowRun).where(WorkflowRun.run_id == run_id)
            ).first()

            if not run:
                return False

            session.delete(run)
            session.commit()
            logger.info(f"WorkflowStore: 删除执行实例 {run_id}")
            return True

    # ========== 统计 ==========

    def stats(self) -> dict:
        """获取存储统计信息"""
        with self._get_session() as session:
            total_workflows = len(list(session.exec(select(Workflow)).all()))
            total_runs = len(list(session.exec(select(WorkflowRun)).all()))

            template_count = len(list(session.exec(
                select(Workflow).where(Workflow.is_template == True)
            ).all()))

            running_count = len(list(session.exec(
                select(WorkflowRun).where(WorkflowRun.status == RunStatus.RUNNING.value)
            ).all()))

            return {
                "total_workflows": total_workflows,
                "total_runs": total_runs,
                "template_count": template_count,
                "running_count": running_count
            }
