"""
WorkflowStore 存储层测试
"""

import os
import pytest
import tempfile

from services.workflow.models import (
    Workflow,
    WorkflowStep,
    WorkflowRun,
    WorkflowStatus,
    StepType,
    RunStatus,
    Variable,
    VariableType,
)
from services.workflow.store import (
    WorkflowStore,
    reset_workflow_store,
)


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # 设置环境变量指向临时数据库
    old_env = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_path

    yield db_path

    # 清理
    os.environ.pop("DATABASE_URL", None)
    if old_env:
        os.environ["DATABASE_URL"] = old_env
    reset_workflow_store()

    # 删除临时文件
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def workflow_store(temp_db):
    """创建测试用的 WorkflowStore"""
    from services.database.connection import DatabaseConnection
    DatabaseConnection.reset()  # 重置连接以使用新的数据库

    store = WorkflowStore()
    return store


class TestWorkflowStore:
    """WorkflowStore 测试"""

    def test_save_and_load_workflow(self, workflow_store):
        """测试保存和加载工作流"""
        workflow = Workflow.create(
            name="测试工作流",
            description="测试描述"
        )

        # 保存
        workflow_id = workflow_store.save_workflow(workflow)
        assert workflow_id == workflow.workflow_id

        # 加载
        loaded = workflow_store.load_workflow(workflow_id)
        assert loaded is not None
        assert loaded.name == "测试工作流"
        assert loaded.description == "测试描述"

    def test_save_workflow_with_steps(self, workflow_store):
        """测试保存带步骤的工作流"""
        workflow = Workflow.create(name="带步骤工作流")
        workflow.set_steps([
            WorkflowStep(step_id=1, name="步骤1", step_type=StepType.FETCH, tool_id="t1"),
            WorkflowStep(step_id=2, name="步骤2", step_type=StepType.PROCESS, tool_id="t2", depends_on=[1]),
        ])

        workflow_store.save_workflow(workflow)

        loaded = workflow_store.load_workflow(workflow.workflow_id)
        steps = loaded.get_steps()
        assert len(steps) == 2
        assert steps[1].depends_on == [1]

    def test_save_workflow_with_variables(self, workflow_store):
        """测试保存带变量的工作流"""
        workflow = Workflow.create(name="带变量工作流")
        workflow.set_variables({
            "keyword": Variable(
                name="keyword",
                var_type=VariableType.STRING,
                required=True
            )
        })

        workflow_store.save_workflow(workflow)

        loaded = workflow_store.load_workflow(workflow.workflow_id)
        variables = loaded.get_variables()
        assert "keyword" in variables
        assert variables["keyword"].var_type == VariableType.STRING

    def test_update_workflow(self, workflow_store):
        """测试更新工作流"""
        workflow = Workflow.create(name="原始名称")
        workflow_store.save_workflow(workflow)

        # 更新
        workflow.name = "新名称"
        workflow.status = WorkflowStatus.READY.value
        workflow_store.save_workflow(workflow)

        # 验证
        loaded = workflow_store.load_workflow(workflow.workflow_id)
        assert loaded.name == "新名称"
        assert loaded.status == WorkflowStatus.READY.value

    def test_list_workflows(self, workflow_store):
        """测试列出工作流"""
        # 创建多个工作流
        for i in range(3):
            workflow = Workflow.create(name=f"工作流 {i}")
            workflow_store.save_workflow(workflow)

        # 创建一个模板
        template = Workflow.create(name="模板", is_template=True)
        workflow_store.save_workflow(template)

        # 列出全部
        all_workflows = workflow_store.list_workflows()
        assert len(all_workflows) == 4

        # 只列出模板
        templates = workflow_store.list_workflows(is_template=True)
        assert len(templates) == 1
        assert templates[0].name == "模板"

    def test_list_workflows_by_status(self, workflow_store):
        """测试按状态列出工作流"""
        # 创建不同状态的工作流
        draft = Workflow.create(name="草稿")
        draft.status = WorkflowStatus.DRAFT.value
        workflow_store.save_workflow(draft)

        ready = Workflow.create(name="就绪")
        ready.status = WorkflowStatus.READY.value
        workflow_store.save_workflow(ready)

        # 查询草稿
        drafts = workflow_store.list_workflows(status=WorkflowStatus.DRAFT)
        assert len(drafts) == 1
        assert drafts[0].name == "草稿"

    def test_delete_workflow(self, workflow_store):
        """测试删除工作流"""
        workflow = Workflow.create(name="待删除")
        workflow_store.save_workflow(workflow)

        # 删除
        result = workflow_store.delete_workflow(workflow.workflow_id)
        assert result is True

        # 验证已删除
        loaded = workflow_store.load_workflow(workflow.workflow_id)
        assert loaded is None

    def test_delete_nonexistent_workflow(self, workflow_store):
        """测试删除不存在的工作流"""
        result = workflow_store.delete_workflow("nonexistent-id")
        assert result is False


class TestWorkflowRunStore:
    """WorkflowRun 存储测试"""

    def test_save_and_load_run(self, workflow_store):
        """测试保存和加载执行实例"""
        run = WorkflowRun.create(
            workflow_id="wf-test",
            variable_values={"keyword": "测试"}
        )

        # 保存
        run_id = workflow_store.save_run(run)
        assert run_id == run.run_id

        # 加载
        loaded = workflow_store.load_run(run_id)
        assert loaded is not None
        assert loaded.workflow_id == "wf-test"
        assert loaded.get_variable_values()["keyword"] == "测试"

    def test_update_run(self, workflow_store):
        """测试更新执行实例"""
        run = WorkflowRun.create(workflow_id="wf-test")
        workflow_store.save_run(run)

        # 更新
        run.status = RunStatus.RUNNING.value
        run.add_completed_step(1)
        run.add_artifact(1, "artifact-a")
        workflow_store.save_run(run)

        # 验证
        loaded = workflow_store.load_run(run.run_id)
        assert loaded.status == RunStatus.RUNNING.value
        assert loaded.get_completed_step_ids() == [1]
        assert loaded.get_artifact_ids()[1] == "artifact-a"

    def test_list_runs_by_workflow(self, workflow_store):
        """测试按工作流列出执行实例"""
        # 创建多个执行实例
        for i in range(3):
            run = WorkflowRun.create(workflow_id="wf-test1")
            workflow_store.save_run(run)

        run2 = WorkflowRun.create(workflow_id="wf-test2")
        workflow_store.save_run(run2)

        # 查询
        runs = workflow_store.list_runs(workflow_id="wf-test1")
        assert len(runs) == 3

    def test_list_runs_by_status(self, workflow_store):
        """测试按状态列出执行实例"""
        # 创建不同状态的实例
        running = WorkflowRun.create(workflow_id="wf-test")
        running.status = RunStatus.RUNNING.value
        workflow_store.save_run(running)

        completed = WorkflowRun.create(workflow_id="wf-test")
        completed.status = RunStatus.COMPLETED.value
        workflow_store.save_run(completed)

        # 查询运行中
        running_runs = workflow_store.list_runs(status=RunStatus.RUNNING)
        assert len(running_runs) == 1

    def test_update_run_status(self, workflow_store):
        """测试更新执行状态"""
        run = WorkflowRun.create(workflow_id="wf-test")
        workflow_store.save_run(run)

        # 更新状态
        result = workflow_store.update_run_status(
            run.run_id,
            RunStatus.FAILED,
            error_message="测试错误"
        )
        assert result is True

        # 验证
        loaded = workflow_store.load_run(run.run_id)
        assert loaded.status == RunStatus.FAILED.value
        assert loaded.error_message == "测试错误"

    def test_delete_run(self, workflow_store):
        """测试删除执行实例"""
        run = WorkflowRun.create(workflow_id="wf-test")
        workflow_store.save_run(run)

        # 删除
        result = workflow_store.delete_run(run.run_id)
        assert result is True

        # 验证已删除
        loaded = workflow_store.load_run(run.run_id)
        assert loaded is None

    def test_stats(self, workflow_store):
        """测试统计信息"""
        # 创建工作流
        workflow = Workflow.create(name="测试")
        workflow_store.save_workflow(workflow)

        template = Workflow.create(name="模板", is_template=True)
        workflow_store.save_workflow(template)

        # 创建执行实例
        running = WorkflowRun.create(workflow_id=workflow.workflow_id)
        running.status = RunStatus.RUNNING.value
        workflow_store.save_run(running)

        completed = WorkflowRun.create(workflow_id=workflow.workflow_id)
        completed.status = RunStatus.COMPLETED.value
        workflow_store.save_run(completed)

        # 获取统计
        stats = workflow_store.stats()
        assert stats["total_workflows"] == 2
        assert stats["total_runs"] == 2
        assert stats["template_count"] == 1
        assert stats["running_count"] == 1
