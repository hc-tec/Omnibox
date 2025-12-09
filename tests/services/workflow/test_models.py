"""
Workflow 模型测试
"""

import pytest
from datetime import datetime

from services.workflow.models import (
    Workflow,
    WorkflowStep,
    WorkflowRun,
    WorkflowStatus,
    StepType,
    RunStatus,
    Variable,
    VariableType,
    ProgressEvent,
)


class TestWorkflowModel:
    """Workflow 模型测试"""

    def test_create_workflow(self):
        """测试创建工作流"""
        workflow = Workflow.create(
            name="测试工作流",
            description="这是一个测试工作流"
        )

        assert workflow.workflow_id.startswith("wf-")
        assert workflow.name == "测试工作流"
        assert workflow.status == WorkflowStatus.DRAFT.value
        assert workflow.is_template is False

    def test_workflow_with_steps(self):
        """测试带步骤的工作流"""
        steps = [
            WorkflowStep(
                step_id=1,
                name="采集数据",
                step_type=StepType.FETCH,
                tool_id="fetch_public_data",
                params={"query": "测试查询"},
            ),
            WorkflowStep(
                step_id=2,
                name="处理数据",
                step_type=StepType.PROCESS,
                tool_id="data_operator",
                params={"instruction": "过滤"},
                depends_on=[1],
            ),
        ]

        workflow = Workflow.create(
            name="多步骤工作流",
            steps=steps
        )

        loaded_steps = workflow.get_steps()
        assert len(loaded_steps) == 2
        assert loaded_steps[0].name == "采集数据"
        assert loaded_steps[1].depends_on == [1]

    def test_workflow_with_variables(self):
        """测试带变量的工作流"""
        variables = {
            "keyword": Variable(
                name="keyword",
                var_type=VariableType.STRING,
                description="搜索关键词",
                required=True
            ),
            "limit": Variable(
                name="limit",
                var_type=VariableType.NUMBER,
                description="返回数量",
                default=10,
                required=False
            ),
        }

        workflow = Workflow.create(
            name="带变量工作流",
            variables=variables
        )

        loaded_vars = workflow.get_variables()
        assert len(loaded_vars) == 2
        assert loaded_vars["keyword"].var_type == VariableType.STRING
        assert loaded_vars["limit"].default == 10

    def test_validate_dependencies_success(self):
        """测试依赖验证 - 成功"""
        workflow = Workflow.create(name="测试")
        workflow.set_steps([
            WorkflowStep(step_id=1, name="步骤1", step_type=StepType.FETCH, tool_id="t1"),
            WorkflowStep(step_id=2, name="步骤2", step_type=StepType.PROCESS, tool_id="t2", depends_on=[1]),
            WorkflowStep(step_id=3, name="步骤3", step_type=StepType.ANALYZE, tool_id="t3", depends_on=[1, 2]),
        ])

        errors = workflow.validate_dependencies()
        assert errors == []

    def test_validate_dependencies_missing_dep(self):
        """测试依赖验证 - 依赖不存在"""
        workflow = Workflow.create(name="测试")
        workflow.set_steps([
            WorkflowStep(step_id=1, name="步骤1", step_type=StepType.FETCH, tool_id="t1"),
            WorkflowStep(step_id=2, name="步骤2", step_type=StepType.PROCESS, tool_id="t2", depends_on=[99]),
        ])

        errors = workflow.validate_dependencies()
        assert len(errors) == 1
        assert "步骤 2 依赖不存在的步骤 99" in errors[0]

    def test_validate_dependencies_circular(self):
        """测试依赖验证 - 循环依赖"""
        workflow = Workflow.create(name="测试")
        workflow.set_steps([
            WorkflowStep(step_id=1, name="步骤1", step_type=StepType.FETCH, tool_id="t1", depends_on=[2]),
            WorkflowStep(step_id=2, name="步骤2", step_type=StepType.PROCESS, tool_id="t2"),
        ])

        errors = workflow.validate_dependencies()
        assert len(errors) == 1
        assert "后序步骤" in errors[0]

    def test_add_step(self):
        """测试添加步骤"""
        workflow = Workflow.create(name="测试")
        workflow.add_step(WorkflowStep(
            step_id=1,
            name="新步骤",
            step_type=StepType.FETCH,
            tool_id="fetch_public_data"
        ))

        steps = workflow.get_steps()
        assert len(steps) == 1
        assert steps[0].name == "新步骤"

    def test_tags(self):
        """测试标签功能"""
        workflow = Workflow.create(name="测试")
        workflow.set_tags(["数据分析", "B站", "竞品"])

        tags = workflow.get_tags()
        assert len(tags) == 3
        assert "B站" in tags


class TestWorkflowStep:
    """WorkflowStep 测试"""

    def test_create_fetch_step(self):
        """测试快捷创建采集步骤"""
        step = WorkflowStep.create_fetch_step(
            step_id=1,
            name="获取视频",
            query="B站影视飓风最新视频"
        )

        assert step.step_type == StepType.FETCH
        assert step.tool_id == "fetch_public_data"
        assert step.params["query"] == "B站影视飓风最新视频"
        assert step.output_name == "获取视频_output"

    def test_create_process_step(self):
        """测试快捷创建处理步骤"""
        step = WorkflowStep.create_process_step(
            step_id=2,
            name="过滤视频",
            instruction="筛选播放量超过10万的",
            source_step_id=1
        )

        assert step.step_type == StepType.PROCESS
        assert step.tool_id == "data_operator"
        assert step.depends_on == [1]
        assert "$ref" in str(step.params["source_ref"])


class TestWorkflowRun:
    """WorkflowRun 测试"""

    def test_create_run(self):
        """测试创建执行实例"""
        run = WorkflowRun.create(
            workflow_id="wf-test123",
            variable_values={"keyword": "测试"}
        )

        assert run.run_id.startswith("run-")
        assert run.workflow_id == "wf-test123"
        assert run.status == RunStatus.PENDING.value
        assert run.get_variable_values()["keyword"] == "测试"

    def test_completed_steps(self):
        """测试已完成步骤管理"""
        run = WorkflowRun.create(workflow_id="wf-test")

        run.add_completed_step(1)
        run.add_completed_step(2)
        run.add_completed_step(1)  # 重复添加

        step_ids = run.get_completed_step_ids()
        assert step_ids == [1, 2]

    def test_artifact_ids(self):
        """测试产物 ID 映射"""
        run = WorkflowRun.create(workflow_id="wf-test")

        run.add_artifact(1, "artifact-a")
        run.add_artifact(2, "artifact-b")

        artifact_ids = run.get_artifact_ids()
        assert artifact_ids[1] == "artifact-a"
        assert artifact_ids[2] == "artifact-b"

    def test_calculate_progress(self):
        """测试进度计算"""
        run = WorkflowRun.create(workflow_id="wf-test")

        # 0/5 完成
        assert run.calculate_progress(5) == 0.0

        # 2/5 完成
        run.add_completed_step(1)
        run.add_completed_step(2)
        assert run.calculate_progress(5) == 40.0

        # 5/5 完成
        run.add_completed_step(3)
        run.add_completed_step(4)
        run.add_completed_step(5)
        assert run.calculate_progress(5) == 100.0

    def test_execution_state(self):
        """测试执行状态快照"""
        run = WorkflowRun.create(workflow_id="wf-test")

        state = {"current_step": 2, "data": {"key": "value"}}
        run.set_execution_state(state)

        loaded_state = run.get_execution_state()
        assert loaded_state["current_step"] == 2
        assert loaded_state["data"]["key"] == "value"


class TestVariable:
    """Variable 测试"""

    def test_string_variable(self):
        """测试字符串变量"""
        var = Variable(
            name="keyword",
            var_type=VariableType.STRING,
            description="搜索关键词",
            required=True
        )

        assert var.name == "keyword"
        assert var.var_type == VariableType.STRING
        assert var.default is None

    def test_number_variable_with_default(self):
        """测试带默认值的数字变量"""
        var = Variable(
            name="limit",
            var_type=VariableType.NUMBER,
            default=10,
            required=False
        )

        assert var.default == 10
        assert var.required is False

    def test_enum_variable(self):
        """测试枚举变量"""
        var = Variable(
            name="platform",
            var_type=VariableType.STRING,
            enum_values=["bilibili", "youtube", "douyin"],
            required=True
        )

        assert var.enum_values == ["bilibili", "youtube", "douyin"]


class TestProgressEvent:
    """ProgressEvent 测试"""

    def test_create_event(self):
        """测试创建进度事件"""
        event = ProgressEvent(
            run_id="run-test",
            event_type="step_completed",
            step_id=1,
            step_name="采集数据",
            artifact_id="artifact-a",
            message="步骤完成",
            progress_percent=50.0
        )

        assert event.run_id == "run-test"
        assert event.event_type == "step_completed"
        assert event.progress_percent == 50.0
        assert isinstance(event.timestamp, datetime)
