"""
工作流数据模型

Phase 2: Workflow Engine 核心模型定义
- Workflow: 工作流模板（持久化）
- WorkflowStep: 步骤定义
- WorkflowRun: 执行实例
- Variable: 模板变量
"""

import json
import uuid
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField


class WorkflowStatus(str, Enum):
    """工作流状态"""
    DRAFT = "draft"           # 草稿（编辑中）
    READY = "ready"           # 就绪（可执行）
    TEMPLATE = "template"     # 模板（已发布）


class TemplateCategory(str, Enum):
    """模板分类"""
    DATA_ANALYSIS = "data_analysis"           # 数据分析
    CONTENT_RESEARCH = "content_research"     # 内容研究
    COMPETITIVE = "competitive"               # 竞品分析
    SOCIAL_MONITORING = "social_monitoring"   # 社交监控
    REPORT_GENERATION = "report_generation"   # 报告生成
    CUSTOM = "custom"                         # 自定义


class StepType(str, Enum):
    """步骤类型"""
    FETCH = "fetch"           # 数据采集
    PROCESS = "process"       # 数据处理
    ANALYZE = "analyze"       # 数据分析
    OUTPUT = "output"         # 结果输出


class VariableType(str, Enum):
    """变量类型"""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATASOURCE = "datasource"  # 数据源引用
    LIST = "list"


class RunStatus(str, Enum):
    """执行状态"""
    PENDING = "pending"       # 等待执行
    RUNNING = "running"       # 执行中
    PAUSED = "paused"         # 已暂停
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 执行失败
    CANCELLED = "cancelled"   # 已取消


class Variable(BaseModel):
    """工作流变量定义"""
    name: str = Field(..., description="变量名")
    var_type: VariableType = Field(..., description="变量类型")
    description: str = Field("", description="变量描述")
    default: Optional[Any] = Field(None, description="默认值")
    required: bool = Field(True, description="是否必填")
    enum_values: Optional[List[Any]] = Field(None, description="枚举值限制")


class WorkflowStep(BaseModel):
    """工作流步骤定义"""
    step_id: int = Field(..., description="步骤编号")
    name: str = Field(..., description="步骤名称（用户可读）")
    description: str = Field("", description="步骤描述")
    step_type: StepType = Field(..., description="步骤类型")

    # 工具配置
    tool_id: str = Field(..., description="工具 ID（如 fetch_public_data）")
    params: Dict[str, Any] = Field(default_factory=dict, description="工具参数")

    # 依赖关系
    depends_on: List[int] = Field(default_factory=list, description="依赖的步骤 ID")

    # 输出配置
    output_name: str = Field("", description="输出产物名称")

    @classmethod
    def create_fetch_step(
        cls,
        step_id: int,
        name: str,
        query: str,
        depends_on: Optional[List[int]] = None,
        output_name: str = ""
    ) -> "WorkflowStep":
        """快捷创建数据采集步骤"""
        return cls(
            step_id=step_id,
            name=name,
            step_type=StepType.FETCH,
            tool_id="fetch_public_data",
            params={"query": query},
            depends_on=depends_on or [],
            output_name=output_name or f"{name}_output"
        )

    @classmethod
    def create_process_step(
        cls,
        step_id: int,
        name: str,
        instruction: str,
        source_step_id: int,
        depends_on: Optional[List[int]] = None,
        output_name: str = ""
    ) -> "WorkflowStep":
        """快捷创建数据处理步骤"""
        return cls(
            step_id=step_id,
            name=name,
            step_type=StepType.PROCESS,
            tool_id="data_operator",
            params={
                "instruction": instruction,
                "source_ref": {"$ref": {"step_id": source_step_id}}
            },
            depends_on=depends_on or [source_step_id],
            output_name=output_name or f"{name}_output"
        )


class Workflow(SQLModel, table=True):
    """
    工作流定义（持久化）

    工作流是可执行的 DAG，包含步骤定义和变量配置。
    支持模板化，可保存、分享、复用。
    """
    __tablename__ = "workflows"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    workflow_id: str = SQLField(index=True, description="工作流唯一标识")

    # 基本信息
    name: str = SQLField(..., description="工作流名称")
    description: str = SQLField(default="", description="工作流描述")
    status: str = SQLField(default=WorkflowStatus.DRAFT.value, description="状态")

    # 步骤定义（JSON 存储）
    steps_json: str = SQLField(default="[]", description="步骤列表 JSON")

    # 变量定义（JSON 存储）
    variables_json: str = SQLField(default="{}", description="变量定义 JSON")

    # 元数据
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now)

    # 模板相关
    is_template: bool = SQLField(default=False, description="是否为模板")
    template_source_id: Optional[str] = SQLField(default=None, description="来源模板 ID")

    # 模板元数据
    category: Optional[str] = SQLField(default=None, description="模板分类")
    author: Optional[str] = SQLField(default=None, description="模板作者")
    usage_count: int = SQLField(default=0, description="使用次数")
    preview_image: Optional[str] = SQLField(default=None, description="预览图 URL")
    version: str = SQLField(default="1.0.0", description="模板版本")

    # 标签
    tags_json: str = SQLField(default="[]", description="标签 JSON")

    def get_steps(self) -> List[WorkflowStep]:
        """获取步骤列表"""
        try:
            data = json.loads(self.steps_json)
            return [WorkflowStep(**item) for item in data]
        except (json.JSONDecodeError, TypeError):
            return []

    def set_steps(self, steps: List[WorkflowStep]) -> None:
        """设置步骤列表"""
        self.steps_json = json.dumps(
            [step.model_dump() for step in steps],
            ensure_ascii=False
        )
        self.updated_at = datetime.now()

    def get_variables(self) -> Dict[str, Variable]:
        """获取变量定义"""
        try:
            data = json.loads(self.variables_json)
            return {name: Variable(**var) for name, var in data.items()}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_variables(self, variables: Dict[str, Variable]) -> None:
        """设置变量定义"""
        self.variables_json = json.dumps(
            {name: var.model_dump() for name, var in variables.items()},
            ensure_ascii=False
        )
        self.updated_at = datetime.now()

    def get_tags(self) -> List[str]:
        """获取标签列表"""
        try:
            return json.loads(self.tags_json)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_tags(self, tags: List[str]) -> None:
        """设置标签列表"""
        self.tags_json = json.dumps(tags, ensure_ascii=False)
        self.updated_at = datetime.now()

    def add_step(self, step: WorkflowStep) -> None:
        """添加步骤"""
        steps = self.get_steps()
        steps.append(step)
        self.set_steps(steps)

    def add_variable(self, variable: Variable) -> None:
        """添加变量"""
        variables = self.get_variables()
        variables[variable.name] = variable
        self.set_variables(variables)

    def validate_dependencies(self) -> List[str]:
        """
        验证步骤依赖关系

        Returns:
            错误信息列表，空列表表示验证通过
        """
        errors = []
        steps = self.get_steps()
        step_ids = {step.step_id for step in steps}

        for step in steps:
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    errors.append(f"步骤 {step.step_id} 依赖不存在的步骤 {dep_id}")
                elif dep_id >= step.step_id:
                    # 只在依赖存在时检查是否为后序步骤
                    errors.append(f"步骤 {step.step_id} 依赖后序步骤 {dep_id}（可能存在循环依赖）")

        return errors

    @staticmethod
    def generate_workflow_id() -> str:
        """生成工作流 ID"""
        return f"wf-{uuid.uuid4().hex[:12]}"

    @classmethod
    def create(
        cls,
        name: str,
        description: str = "",
        steps: Optional[List[WorkflowStep]] = None,
        variables: Optional[Dict[str, Variable]] = None,
        is_template: bool = False
    ) -> "Workflow":
        """工厂方法：创建工作流"""
        workflow = cls(
            workflow_id=cls.generate_workflow_id(),
            name=name,
            description=description,
            status=WorkflowStatus.DRAFT.value,
            is_template=is_template
        )
        if steps:
            workflow.set_steps(steps)
        if variables:
            workflow.set_variables(variables)
        return workflow


class WorkflowRun(SQLModel, table=True):
    """
    工作流执行实例

    记录一次工作流执行的状态、进度、产物关联。
    支持暂停/恢复。
    """
    __tablename__ = "workflow_runs"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    run_id: str = SQLField(index=True, description="执行实例唯一标识")
    workflow_id: str = SQLField(index=True, description="关联的工作流 ID")

    # 执行状态
    status: str = SQLField(default=RunStatus.PENDING.value)
    current_step_id: Optional[int] = SQLField(default=None, description="当前执行步骤")
    completed_step_ids_json: str = SQLField(default="[]", description="已完成步骤")

    # 变量值（运行时）
    variable_values_json: str = SQLField(default="{}", description="变量实际值")

    # 产物关联：step_id → artifact_id
    artifact_ids_json: str = SQLField(default="{}", description="步骤 → 产物 ID 映射")

    # 执行信息
    started_at: Optional[datetime] = SQLField(default=None)
    completed_at: Optional[datetime] = SQLField(default=None)
    error_message: Optional[str] = SQLField(default=None)

    # 进度快照（用于恢复执行）
    execution_state_json: Optional[str] = SQLField(default=None, description="ExecutionEngine 状态快照")

    def get_completed_step_ids(self) -> List[int]:
        """获取已完成步骤 ID 列表"""
        try:
            return json.loads(self.completed_step_ids_json)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_completed_step_ids(self, step_ids: List[int]) -> None:
        """设置已完成步骤 ID 列表"""
        self.completed_step_ids_json = json.dumps(step_ids)

    def add_completed_step(self, step_id: int) -> None:
        """添加已完成步骤"""
        step_ids = self.get_completed_step_ids()
        if step_id not in step_ids:
            step_ids.append(step_id)
            self.set_completed_step_ids(step_ids)

    def get_variable_values(self) -> Dict[str, Any]:
        """获取变量值"""
        try:
            return json.loads(self.variable_values_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_variable_values(self, values: Dict[str, Any]) -> None:
        """设置变量值"""
        self.variable_values_json = json.dumps(values, ensure_ascii=False)

    def get_artifact_ids(self) -> Dict[int, str]:
        """获取产物 ID 映射"""
        try:
            data = json.loads(self.artifact_ids_json)
            return {int(k): v for k, v in data.items()}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_artifact_ids(self, artifact_ids: Dict[int, str]) -> None:
        """设置产物 ID 映射"""
        self.artifact_ids_json = json.dumps(artifact_ids, ensure_ascii=False)

    def add_artifact(self, step_id: int, artifact_id: str) -> None:
        """添加步骤产物关联"""
        artifact_ids = self.get_artifact_ids()
        artifact_ids[step_id] = artifact_id
        self.set_artifact_ids(artifact_ids)

    def get_execution_state(self) -> Optional[Dict[str, Any]]:
        """获取执行状态快照"""
        if not self.execution_state_json:
            return None
        try:
            return json.loads(self.execution_state_json)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_execution_state(self, state: Dict[str, Any]) -> None:
        """设置执行状态快照"""
        self.execution_state_json = json.dumps(state, ensure_ascii=False)

    def calculate_progress(self, total_steps: int) -> float:
        """计算执行进度百分比"""
        if total_steps == 0:
            return 0.0
        completed = len(self.get_completed_step_ids())
        return round(completed / total_steps * 100, 1)

    @staticmethod
    def generate_run_id() -> str:
        """生成执行实例 ID"""
        return f"run-{uuid.uuid4().hex[:12]}"

    @classmethod
    def create(
        cls,
        workflow_id: str,
        variable_values: Optional[Dict[str, Any]] = None
    ) -> "WorkflowRun":
        """工厂方法：创建执行实例"""
        run = cls(
            run_id=cls.generate_run_id(),
            workflow_id=workflow_id,
            status=RunStatus.PENDING.value
        )
        if variable_values:
            run.set_variable_values(variable_values)
        return run


class ProgressEvent(BaseModel):
    """进度事件（用于 WebSocket 推送）"""
    run_id: str = Field(..., description="执行实例 ID")
    event_type: str = Field(..., description="事件类型")
    step_id: Optional[int] = Field(None, description="步骤 ID")
    step_name: Optional[str] = Field(None, description="步骤名称")
    artifact_id: Optional[str] = Field(None, description="产物 ID")
    message: str = Field("", description="消息")
    progress_percent: float = Field(0.0, description="进度百分比")
    timestamp: datetime = Field(default_factory=datetime.now)
