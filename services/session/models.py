"""Session 数据模型

Session = 一个完整的工作会话，支持：
1. 跨请求保持 LangGraph 执行上下文
2. 自动记录执行步骤（渐进式 DAG 构建）
3. 可导出为 Workflow 模板
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
import json

from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField

from .config import get_session_config


class SessionStatus(str, Enum):
    """Session 状态"""
    ACTIVE = "active"           # 活跃中
    IDLE = "idle"               # 空闲（可恢复）
    EXPIRED = "expired"         # 已过期
    CLOSED = "closed"           # 已关闭


class RecordedStep(BaseModel):
    """
    记录的执行步骤（用于渐进式 DAG 构建）

    与 WorkflowStep 的区别：
    - RecordedStep: 运行时记录的实际执行，参数是具体值
    - WorkflowStep: 模板定义，参数可以是变量引用
    """
    step_id: int = Field(..., description="步骤编号（自增）")
    tool_id: str = Field(..., description="工具 ID")
    tool_name: str = Field("", description="工具名称（用户可读）")

    # 执行参数（具体值，非变量引用）
    params: Dict[str, Any] = Field(default_factory=dict)

    # 执行结果
    artifact_id: Optional[str] = Field(None, description="产物 ID")
    data_id: Optional[str] = Field(None, description="数据 ID（DataStore）")
    summary: str = Field("", description="执行摘要")
    status: str = Field("success", description="执行状态")
    error_message: Optional[str] = Field(None, description="错误信息")

    # 依赖关系（自动推断）
    depends_on: List[int] = Field(default_factory=list, description="依赖的步骤 ID")
    input_refs: List[str] = Field(default_factory=list, description="引用的 data_id 列表")

    # 时间戳
    executed_at: datetime = Field(default_factory=datetime.now)

    # 原始查询（触发这次执行的用户输入）
    trigger_query: str = Field("", description="触发查询")


class SessionState(BaseModel):
    """
    Session 运行时状态（内存 + 可序列化）

    这是跨请求保持的核心状态
    """
    session_id: str
    status: SessionStatus = SessionStatus.ACTIVE

    # LangGraph 状态（跨请求保持）
    data_stash: List[Dict[str, Any]] = Field(default_factory=list, description="DataReference 列表")
    chat_history: List[Dict[str, str]] = Field(default_factory=list, description="对话历史")
    working_memory: Dict[str, Any] = Field(default_factory=dict, description="工作记忆")

    # 执行记录（渐进式 DAG）
    recorded_steps: List[RecordedStep] = Field(default_factory=list)

    # 产物映射
    artifact_ids: Dict[int, str] = Field(default_factory=dict, description="step_id → artifact_id")

    # 关联的 Workflow（如果从模板创建）
    source_workflow_id: Optional[str] = None

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    last_active_at: datetime = Field(default_factory=datetime.now)

    # 配置（从全局配置初始化，可单独覆盖）
    timeout_minutes: int = Field(default=60, description="Session 超时时间")
    data_stash_limit: int = Field(default=100, description="data_stash 上限")
    chat_history_limit: int = Field(default=20, description="chat_history 滑动窗口大小")

    @classmethod
    def create(
        cls,
        session_id: Optional[str] = None,
        source_workflow_id: Optional[str] = None,
        **kwargs
    ) -> "SessionState":
        """创建新的 SessionState，使用全局配置"""
        config = get_session_config()
        return cls(
            session_id=session_id or f"sess-{uuid4().hex[:12]}",
            source_workflow_id=source_workflow_id,
            timeout_minutes=kwargs.get("timeout_minutes", config.timeout_minutes),
            data_stash_limit=kwargs.get("data_stash_limit", config.data_stash_limit),
            chat_history_limit=kwargs.get("chat_history_limit", config.chat_history_limit),
            **{k: v for k, v in kwargs.items() if k not in ("timeout_minutes", "data_stash_limit", "chat_history_limit")}
        )

    def is_expired(self) -> bool:
        """检查是否已过期"""
        if self.status == SessionStatus.EXPIRED:
            return True
        if self.status == SessionStatus.CLOSED:
            return True
        elapsed = datetime.now() - self.last_active_at
        return elapsed > timedelta(minutes=self.timeout_minutes)

    def touch(self):
        """更新最后活跃时间"""
        self.last_active_at = datetime.now()
        if self.status == SessionStatus.IDLE:
            self.status = SessionStatus.ACTIVE

    def get_next_step_id(self) -> int:
        """获取下一个步骤 ID"""
        if not self.recorded_steps:
            return 1
        return max(s.step_id for s in self.recorded_steps) + 1

    def add_to_data_stash(self, ref_dict: Dict[str, Any]):
        """添加到 data_stash，自动应用上限"""
        self.data_stash.append(ref_dict)

        # 应用上限（如果配置了）
        if self.data_stash_limit > 0 and len(self.data_stash) > self.data_stash_limit:
            # 移除最老的
            self.data_stash = self.data_stash[-self.data_stash_limit:]

    def add_to_chat_history(self, role: str, content: str):
        """添加到对话历史，自动应用滑动窗口"""
        self.chat_history.append({"role": role, "content": content})

        # 应用滑动窗口（如果配置了）
        if self.chat_history_limit > 0:
            # 保留最近 N 轮（每轮 2 条：user + assistant）
            max_messages = self.chat_history_limit * 2
            if len(self.chat_history) > max_messages:
                self.chat_history = self.chat_history[-max_messages:]

    def add_recorded_step(self, step: RecordedStep):
        """添加记录的步骤"""
        self.recorded_steps.append(step)
        if step.artifact_id:
            self.artifact_ids[step.step_id] = step.artifact_id


class Session(SQLModel, table=True):
    """Session 持久化模型"""
    __tablename__ = "sessions"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    session_id: str = SQLField(index=True, unique=True)

    # 基本信息
    name: str = SQLField(default="", description="Session 名称")
    status: str = SQLField(default=SessionStatus.ACTIVE.value)

    # 状态快照（JSON 序列化）
    state_json: str = SQLField(default="{}", description="SessionState JSON")

    # 关联
    workspace_id: Optional[str] = SQLField(default=None, index=True)
    source_workflow_id: Optional[str] = SQLField(default=None)

    # 时间戳
    created_at: datetime = SQLField(default_factory=datetime.now)
    last_active_at: datetime = SQLField(default_factory=datetime.now)
    closed_at: Optional[datetime] = SQLField(default=None)

    @classmethod
    def create(
        cls,
        workspace_id: Optional[str] = None,
        source_workflow_id: Optional[str] = None,
        name: str = ""
    ) -> "Session":
        """创建新的 Session"""
        session_id = f"sess-{uuid4().hex[:12]}"
        state = SessionState.create(
            session_id=session_id,
            source_workflow_id=source_workflow_id
        )

        session = cls(
            session_id=session_id,
            name=name or f"Session {session_id[:8]}",
            workspace_id=workspace_id,
            source_workflow_id=source_workflow_id
        )
        session.set_state(state)
        return session

    def get_state(self) -> SessionState:
        """反序列化状态"""
        data = json.loads(self.state_json)

        # 处理 recorded_steps 的反序列化
        if "recorded_steps" in data:
            data["recorded_steps"] = [
                RecordedStep(**step) if isinstance(step, dict) else step
                for step in data["recorded_steps"]
            ]

        return SessionState(**data)

    def set_state(self, state: SessionState):
        """序列化状态"""
        self.state_json = json.dumps(
            state.model_dump(),
            default=str,
            ensure_ascii=False
        )
        self.status = state.status.value
        self.last_active_at = state.last_active_at
