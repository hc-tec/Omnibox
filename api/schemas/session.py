"""Session API Schema 定义"""

from typing import Optional, Dict, Any, List
from datetime import datetime

from pydantic import BaseModel, Field

from api.schemas.panel import PanelPayload, DataBlock


class CreateSessionRequest(BaseModel):
    """创建 Session 请求"""
    workspace_id: Optional[str] = Field(None, description="关联的 Workspace ID")
    source_workflow_id: Optional[str] = Field(None, description="来源 Workflow ID（从模板创建）")
    name: str = Field("", description="Session 名称")


class SessionInfo(BaseModel):
    """Session 信息"""
    session_id: str = Field(..., description="Session ID")
    name: str = Field("", description="Session 名称")
    status: str = Field(..., description="Session 状态")
    workspace_id: Optional[str] = Field(None, description="关联的 Workspace ID")
    source_workflow_id: Optional[str] = Field(None, description="来源 Workflow ID")

    # 统计信息
    data_stash_count: int = Field(0, description="data_stash 条目数")
    chat_history_count: int = Field(0, description="对话历史条目数")
    recorded_steps_count: int = Field(0, description="执行步骤数")

    # 时间戳
    created_at: datetime = Field(..., description="创建时间")
    last_active_at: datetime = Field(..., description="最后活跃时间")


class CreateSessionResponse(BaseModel):
    """创建 Session 响应"""
    success: bool = Field(..., description="是否成功")
    session: SessionInfo = Field(..., description="Session 信息")


class GetSessionResponse(BaseModel):
    """获取 Session 响应"""
    success: bool = Field(..., description="是否成功")
    session: Optional[SessionInfo] = Field(None, description="Session 信息")
    error: Optional[str] = Field(None, description="错误信息")


class SessionChatRequest(BaseModel):
    """Session 内对话请求"""
    query: str = Field(..., description="用户查询", min_length=1, max_length=2000)
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="额外上下文（如 artifact_refs, filter_datasource）"
    )


class SessionChatResponse(BaseModel):
    """Session 内对话响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field("", description="响应消息")
    final_report: Optional[str] = Field(None, description="最终报告")
    # data_stash 中的数据引用列表
    data: Optional[Any] = Field(None, description="执行结果数据（data_stash 引用列表）")
    data_blocks: Dict[str, Any] = Field(
        default_factory=dict,
        description="数据块字典"
    )

    # Session 状态摘要
    session_summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Session 状态摘要（data_stash_count, chat_history_count 等）"
    )

    # 执行信息
    execution_steps: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="本次执行的步骤"
    )

    error: Optional[str] = Field(None, description="错误信息")


class RecordedStepInfo(BaseModel):
    """执行步骤信息"""
    step_id: int = Field(..., description="步骤编号")
    tool_id: str = Field(..., description="工具 ID")
    tool_name: str = Field("", description="工具名称")
    params: Dict[str, Any] = Field(default_factory=dict, description="参数")
    artifact_id: Optional[str] = Field(None, description="产物 ID")
    data_id: Optional[str] = Field(None, description="数据 ID")
    summary: str = Field("", description="执行摘要")
    status: str = Field("success", description="执行状态")
    error_message: Optional[str] = Field(None, description="错误信息")
    depends_on: List[int] = Field(default_factory=list, description="依赖步骤")
    trigger_query: str = Field("", description="触发查询")
    executed_at: datetime = Field(..., description="执行时间")


class GetRecordedStepsResponse(BaseModel):
    """获取执行步骤响应"""
    success: bool = Field(..., description="是否成功")
    session_id: str = Field(..., description="Session ID")
    steps: List[RecordedStepInfo] = Field(default_factory=list, description="执行步骤列表")
    error: Optional[str] = Field(None, description="错误信息")


class SaveAsTemplateRequest(BaseModel):
    """保存为模板请求"""
    name: str = Field(..., description="工作流名称", min_length=1, max_length=100)
    description: str = Field("", description="工作流描述")
    category: Optional[str] = Field(None, description="模板分类")
    extract_variables: bool = Field(True, description="是否提取变量")


class SaveAsTemplateResponse(BaseModel):
    """保存为模板响应"""
    success: bool = Field(..., description="是否成功")
    workflow_id: Optional[str] = Field(None, description="生成的 Workflow ID")
    workflow_name: Optional[str] = Field(None, description="Workflow 名称")
    steps_count: Optional[int] = Field(None, description="步骤数量")
    variables_count: Optional[int] = Field(None, description="变量数量")
    error: Optional[str] = Field(None, description="错误信息")


class CloseSessionResponse(BaseModel):
    """关闭 Session 响应"""
    success: bool = Field(..., description="是否成功")
    session_id: str = Field(..., description="Session ID")
    error: Optional[str] = Field(None, description="错误信息")


class ListSessionsResponse(BaseModel):
    """列出 Sessions 响应"""
    success: bool = Field(..., description="是否成功")
    sessions: List[SessionInfo] = Field(default_factory=list, description="Session 列表")
    total: int = Field(0, description="总数")
    error: Optional[str] = Field(None, description="错误信息")
