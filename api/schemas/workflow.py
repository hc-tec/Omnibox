"""工作流 API Schema 定义

Phase 3: Workspace UI 后端接口的请求/响应模型。
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

from services.workflow.models import (
    WorkflowStatus,
    StepType,
    VariableType,
    RunStatus,
)


# ========== 变量 Schemas ==========

class VariableSchema(BaseModel):
    """变量定义"""
    name: str = Field(..., description="变量名")
    var_type: VariableType = Field(..., description="变量类型")
    description: str = Field("", description="变量描述")
    default: Optional[Any] = Field(None, description="默认值")
    required: bool = Field(True, description="是否必填")
    enum_values: Optional[List[Any]] = Field(None, description="枚举值限制")


# ========== 步骤 Schemas ==========

class WorkflowStepSchema(BaseModel):
    """工作流步骤"""
    step_id: int = Field(..., description="步骤编号")
    name: str = Field(..., description="步骤名称")
    description: str = Field("", description="步骤描述")
    step_type: StepType = Field(..., description="步骤类型")
    tool_id: str = Field(..., description="工具 ID")
    params: Dict[str, Any] = Field(default_factory=dict, description="工具参数")
    depends_on: List[int] = Field(default_factory=list, description="依赖的步骤 ID")
    output_name: str = Field("", description="输出产物名称")


class WorkflowStepCreate(BaseModel):
    """创建步骤请求"""
    name: str = Field(..., description="步骤名称", min_length=1, max_length=100)
    description: str = Field("", description="步骤描述", max_length=500)
    step_type: StepType = Field(..., description="步骤类型")
    tool_id: str = Field(..., description="工具 ID", min_length=1)
    params: Dict[str, Any] = Field(default_factory=dict, description="工具参数")
    depends_on: List[int] = Field(default_factory=list, description="依赖的步骤 ID")
    output_name: str = Field("", description="输出产物名称")


# ========== 工作流 Schemas ==========

class WorkflowCreate(BaseModel):
    """创建工作流请求"""
    name: str = Field(
        ...,
        description="工作流名称",
        min_length=1,
        max_length=100
    )
    description: str = Field(
        "",
        description="工作流描述",
        max_length=500
    )
    steps: List[WorkflowStepCreate] = Field(
        default_factory=list,
        description="步骤列表"
    )
    variables: Dict[str, VariableSchema] = Field(
        default_factory=dict,
        description="变量定义"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="标签列表"
    )
    is_template: bool = Field(
        False,
        description="是否为模板"
    )


class WorkflowUpdate(BaseModel):
    """更新工作流请求（部分更新）"""
    name: Optional[str] = Field(
        None,
        description="工作流名称",
        min_length=1,
        max_length=100
    )
    description: Optional[str] = Field(
        None,
        description="工作流描述",
        max_length=500
    )
    status: Optional[WorkflowStatus] = Field(
        None,
        description="状态"
    )
    steps: Optional[List[WorkflowStepCreate]] = Field(
        None,
        description="步骤列表"
    )
    variables: Optional[Dict[str, VariableSchema]] = Field(
        None,
        description="变量定义"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="标签列表"
    )


class WorkflowResponse(BaseModel):
    """工作流响应"""
    workflow_id: str = Field(..., description="工作流唯一标识")
    name: str = Field(..., description="工作流名称")
    description: str = Field(..., description="工作流描述")
    status: WorkflowStatus = Field(..., description="状态")
    steps: List[WorkflowStepSchema] = Field(..., description="步骤列表")
    variables: Dict[str, VariableSchema] = Field(..., description="变量定义")
    tags: List[str] = Field(..., description="标签列表")
    is_template: bool = Field(..., description="是否为模板")
    template_source_id: Optional[str] = Field(None, description="来源模板 ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    """工作流列表响应"""
    total: int = Field(..., description="总数")
    items: List[WorkflowResponse] = Field(..., description="工作流列表")


# ========== 执行实例 Schemas ==========

class RunCreate(BaseModel):
    """启动执行请求"""
    variable_values: Dict[str, Any] = Field(
        default_factory=dict,
        description="变量值"
    )


class StepStatusSchema(BaseModel):
    """步骤状态"""
    step_id: int = Field(..., description="步骤编号")
    status: str = Field(..., description="状态：pending/running/completed/failed")
    artifact_id: Optional[str] = Field(None, description="产物 ID")
    error_message: Optional[str] = Field(None, description="错误信息")


class RunResponse(BaseModel):
    """执行实例响应"""
    run_id: str = Field(..., description="执行实例 ID")
    workflow_id: str = Field(..., description="工作流 ID")
    status: RunStatus = Field(..., description="执行状态")
    current_step_id: Optional[int] = Field(None, description="当前执行步骤")
    completed_step_ids: List[int] = Field(..., description="已完成步骤")
    step_statuses: List[StepStatusSchema] = Field(
        default_factory=list,
        description="步骤状态列表"
    )
    variable_values: Dict[str, Any] = Field(..., description="变量值")
    artifact_ids: Dict[int, str] = Field(..., description="步骤 → 产物 ID 映射")
    progress_percent: float = Field(..., description="进度百分比")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")

    model_config = {"from_attributes": True}


class RunListResponse(BaseModel):
    """执行实例列表响应"""
    total: int = Field(..., description="总数")
    items: List[RunResponse] = Field(..., description="执行实例列表")


# ========== 产物 Schemas ==========

class ArtifactSchema(BaseModel):
    """数据产物"""
    artifact_id: str = Field(..., description="产物唯一标识")
    artifact_type: str = Field(..., description="产物类型：dataset/analysis/insight/document")
    name: str = Field(..., description="产物名称")
    description: str = Field("", description="产物描述")
    summary: str = Field("", description="数据摘要")
    schema_info: Optional[Dict[str, Any]] = Field(None, description="数据 schema")
    statistics: Optional[Dict[str, Any]] = Field(None, description="统计信息")
    sample_items: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="示例数据"
    )
    tags: List[str] = Field(default_factory=list, description="标签")
    created_at: datetime = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


class ArtifactListResponse(BaseModel):
    """产物列表响应"""
    total: int = Field(..., description="总数")
    items: List[ArtifactSchema] = Field(..., description="产物列表")


class ArtifactDataResponse(BaseModel):
    """产物数据响应"""
    artifact_id: str = Field(..., description="产物 ID")
    data: Any = Field(..., description="完整数据")
    total_rows: int = Field(..., description="总行数")


# ========== 进度事件 Schemas ==========

class ProgressEventSchema(BaseModel):
    """进度事件（WebSocket 推送）"""
    run_id: str = Field(..., description="执行实例 ID")
    event_type: str = Field(
        ...,
        description="事件类型：step_started/step_completed/step_failed/run_completed/run_failed"
    )
    step_id: Optional[int] = Field(None, description="步骤 ID")
    step_name: Optional[str] = Field(None, description="步骤名称")
    artifact_id: Optional[str] = Field(None, description="产物 ID")
    message: str = Field("", description="消息")
    progress_percent: float = Field(0.0, description="进度百分比")
    timestamp: datetime = Field(..., description="时间戳")
