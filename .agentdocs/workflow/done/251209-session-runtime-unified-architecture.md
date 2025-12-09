# Phase 6: Session Runtime 统一架构设计方案

**创建日期**: 2025-12-09
**状态**: 实现完成
**目标**: 统一对话式执行与工作流执行，支持多轮对话上下文保持、工作流保存与回放

## 实现进度

- [x] Phase 6.1: Session 数据模型 + Store (`services/session/models.py`, `store.py`, `config.py`)
- [x] Phase 6.2: SessionRuntimeManager (`services/session/runtime_manager.py`)
- [x] Phase 6.3: StepRecorder（已集成到 RuntimeManager 中）
- [x] Phase 6.4: WorkflowExtractor (`services/session/workflow_extractor.py`)
- [x] Phase 6.5: Session API 端点 (`api/controllers/session_controller.py`)
- [x] Phase 6.6: 前端 sessionStore (`frontend/src/features/workspace/stores/sessionStore.ts`)
- [x] Phase 6.7: ChatInteractionArea 改造（使用 Session API）
- [x] Phase 6.8: SaveAsTemplateDialog 组件

---

## 一、问题分析

### 1.1 核心问题

当前 Workspace 中的 `ChatInteractionArea` 每次请求都是**无状态**的：

```
用户请求1: "获取B站热点"
  → 后端创建新的 LangGraphRuntime + GraphState
  → 执行完成，返回结果
  → GraphState 被丢弃 ❌ (data_stash、chat_history 全部丢失)

用户请求2: "基于上面的数据做对比分析"
  → 后端又创建新的 LangGraphRuntime + GraphState
  → data_stash 为空，无法引用之前的数据 ❌
  → LLM: "抱歉，我没有看到之前的数据..."
```

### 1.2 现有架构割裂

| 机制 | 入口 | 状态管理 | 产物 | 适用场景 |
|------|------|---------|------|---------|
| **SyncLangGraphExecutor** | ChatInteractionArea | 无状态 | 丢失 | 单次查询 |
| **WorkflowEngine** | WorkflowPanel | 持久化 | DataArtifact | 预定义 DAG |

**问题**：
1. 用户无法在对话中引用之前的数据（上下文丢失）
2. 对话产生的执行序列无法保存为可复用的工作流
3. WorkflowEngine 需要预先定义 DAG，无法动态构建

### 1.3 用户期望

1. **多轮对话上下文保持** - 在一个 Workspace 会话中，多次对话能引用之前的数据
2. **渐进式工作流构建** - 对话执行的步骤自动记录，可保存为模板
3. **工作流回放** - 保存的模板可以用不同变量重新执行

---

## 二、现状分析

### 2.1 现有可复用组件

| 组件 | 文件位置 | 功能 | 复用策略 |
|------|---------|------|---------|
| **SyncLangGraphExecutor** | `langgraph_agents/sync_executor.py` | LangGraph 同步执行 | ✅ 作为执行核心 |
| **LangGraphRuntime** | `langgraph_agents/runtime.py` | 运行时上下文 | ✅ 跨请求复用 |
| **GraphState** | `langgraph_agents/state.py` | 执行状态 | ✅ Session 持久化 |
| **WorkflowEngine** | `services/workflow/engine.py` | DAG 执行 | ✅ 模板执行模式 |
| **WorkflowStore** | `services/workflow/store.py` | 工作流持久化 | ✅ 直接复用 |
| **ArtifactStore** | `services/artifact/store.py` | 产物存储 | ✅ 直接复用 |
| **ResearchDataStore** | `langgraph_agents/storage.py` | 数据存储 | ✅ 直接复用 |

### 2.2 需要新增的组件

| 组件 | 说明 |
|------|------|
| **SessionRuntimeManager** | Session 生命周期管理，维护 session_id → Runtime 映射 |
| **SessionState** | Session 持久化状态（data_stash、recorded_steps 等） |
| **SessionStore** | Session SQLite 存储层 |
| **StepRecorder** | 执行步骤记录器，构建渐进式 DAG |
| **WorkflowExtractor** | 从 Session 提取 Workflow 模板 |

### 2.3 关键代码位置

```python
# 当前无状态执行（问题根源）
# langgraph_agents/sync_executor.py:122-139

def execute(self, user_query, ...):
    # 每次都创建全新的 initial_state
    initial_state: GraphState = {
        "original_query": user_query,
        "chat_history": [],         # ❌ 每次都是空的
        "data_stash": [],           # ❌ 每次都是空的
        "working_memory": {},       # ❌ 每次都是空的
        ...
    }
```

---

## 三、统一架构设计

### 3.1 核心概念

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Workspace Session 统一架构                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Session = 一个完整的工作会话                                               │
│   ├─ 包含多轮对话                                                            │
│   ├─ 保持 LangGraph 执行上下文（data_stash、chat_history）                   │
│   ├─ 自动记录执行步骤（构建渐进式 DAG）                                       │
│   └─ 可导出为 Workflow 模板                                                  │
│                                                                              │
│   Workflow = 可复用的工作流模板                                              │
│   ├─ 从 Session 提取                                                        │
│   ├─ 支持变量参数化                                                          │
│   └─ 可重复执行（回放）                                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 架构层次图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端层                                          │
│                                                                              │
│   WorkspaceLayout                                                           │
│   ├─ WorkflowPanel (左侧)                                                   │
│   ├─ MainCanvas (中间)                                                      │
│   │   └─ ChatInteractionArea ──── 传递 session_id ────┐                    │
│   └─ ArtifactPanel (右侧)                              │                    │
│                                                        │                    │
│   workspaceStore                                       │                    │
│   ├─ sessionId: string | null  ◄───────────────────────┘                   │
│   ├─ sessionState: SessionState                                             │
│   └─ createSession() / closeSession()                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API 层                                          │
│                                                                              │
│   POST /api/v1/sessions                    创建 Session                      │
│   DELETE /api/v1/sessions/{id}             关闭 Session                      │
│   GET /api/v1/sessions/{id}                获取 Session 状态                 │
│   POST /api/v1/sessions/{id}/chat          Session 内对话（核心）            │
│   POST /api/v1/sessions/{id}/export        导出为 Workflow 模板              │
│                                                                              │
│   POST /api/v1/workflows/{id}/runs         执行 Workflow（已有）             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Service 层                                        │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                   SessionRuntimeManager（核心新增）                   │   │
│   │                                                                       │   │
│   │   职责：                                                              │   │
│   │   1. 管理 session_id → SessionState 的映射                           │   │
│   │   2. 创建/恢复 LangGraphRuntime                                      │   │
│   │   3. 跨请求保持 data_stash、chat_history、working_memory            │   │
│   │   4. 记录执行步骤（StepRecorder）                                    │   │
│   │   5. 会话超时清理                                                    │   │
│   │                                                                       │   │
│   │   _sessions: Dict[str, SessionState]  ◄─── 内存缓存                  │   │
│   │   _session_store: SessionStore        ◄─── SQLite 持久化             │   │
│   │                                                                       │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│          ┌───────────────────┼───────────────────┐                         │
│          ▼                   ▼                   ▼                         │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                  │
│   │ ChatService  │   │WorkflowEngine│   │WorkflowExtractor│               │
│   │ (修改)       │   │ (不变)       │   │ (新增)       │                  │
│   └──────────────┘   └──────────────┘   └──────────────┘                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Storage 层                                        │
│                                                                              │
│   SessionStore (新增)     WorkflowStore      ArtifactStore                  │
│   ├─ sessions 表          ├─ workflows 表    ├─ artifacts 表                │
│   └─ session_steps 表     └─ workflow_runs   └─ (现有)                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 三种执行模式

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            三种执行模式                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   模式 1: 对话式执行（渐进 DAG 构建）                                        │
│   ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│   用户输入 ──▶ SessionRuntimeManager ──▶ SyncLangGraphExecutor             │
│                       │                         │                           │
│                       │ 恢复 data_stash         │ 执行                      │
│                       │ 恢复 chat_history       │                           │
│                       ▼                         ▼                           │
│               SessionState ◄──────── 更新状态，记录步骤                     │
│                       │                                                      │
│                       ▼                                                      │
│               recorded_steps[] ◄─── 自动推断依赖关系                        │
│                                                                              │
│   特点：                                                                     │
│   - 用户无需预定义工作流                                                     │
│   - 每次对话自动累积上下文                                                   │
│   - 执行序列自动转为 DAG                                                     │
│                                                                              │
│   ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│   模式 2: 保存为模板                                                         │
│   ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│   用户点击"保存" ──▶ WorkflowExtractor ──▶ Workflow                        │
│                             │                                                │
│                             │ 分析 recorded_steps                            │
│                             │ 提取变量（参数化）                              │
│                             │ 构建 DAG（depends_on）                         │
│                             ▼                                                │
│                       WorkflowStore ◄─── 持久化                             │
│                                                                              │
│   特点：                                                                     │
│   - 从执行历史自动生成模板                                                   │
│   - 支持变量抽取（用户可自定义）                                             │
│   - 可发布到模板市场                                                         │
│                                                                              │
│   ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│   模式 3: 模板回放                                                           │
│   ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│   用户选择模板 ──▶ 填入变量 ──▶ WorkflowEngine ──▶ 按 DAG 执行             │
│                                       │                                      │
│                                       │ start_run()                          │
│                                       │ 变量解析                              │
│                                       │ 步骤调度                              │
│                                       ▼                                      │
│                               WorkflowRun ◄─── 支持暂停/恢复                │
│                                                                              │
│   特点：                                                                     │
│   - 复用已有 WorkflowEngine                                                  │
│   - 支持不同变量值重复执行                                                   │
│   - 完整的生命周期管理                                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 四、数据模型设计

### 4.1 Session 模型

**文件位置**: `services/session/models.py`（新建）

```python
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField

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

    # 配置
    timeout_minutes: int = Field(default=60, description="Session 超时时间")

    def is_expired(self) -> bool:
        """检查是否已过期"""
        from datetime import timedelta
        if self.status == SessionStatus.EXPIRED:
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

    def get_state(self) -> SessionState:
        """反序列化状态"""
        import json
        data = json.loads(self.state_json)
        return SessionState(**data)

    def set_state(self, state: SessionState):
        """序列化状态"""
        import json
        self.state_json = json.dumps(state.model_dump(), default=str, ensure_ascii=False)
        self.status = state.status.value
        self.last_active_at = state.last_active_at
```

### 4.2 SessionStore

**文件位置**: `services/session/store.py`（新建）

```python
class SessionStore:
    """
    Session 存储层

    职责：
    1. Session CRUD
    2. 状态持久化
    3. 过期清理
    """

    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
        self._ensure_tables()

    def create_session(
        self,
        workspace_id: Optional[str] = None,
        source_workflow_id: Optional[str] = None,
        name: str = ""
    ) -> Session:
        """创建新 Session"""
        ...

    def load_session(self, session_id: str) -> Optional[Session]:
        """加载 Session"""
        ...

    def save_session(self, session: Session) -> bool:
        """保存 Session"""
        ...

    def update_state(self, session_id: str, state: SessionState) -> bool:
        """更新状态"""
        ...

    def close_session(self, session_id: str) -> bool:
        """关闭 Session"""
        ...

    def list_sessions(
        self,
        workspace_id: Optional[str] = None,
        status: Optional[SessionStatus] = None
    ) -> List[Session]:
        """列出 Sessions"""
        ...

    def cleanup_expired(self, older_than_minutes: int = 120) -> int:
        """清理过期 Sessions"""
        ...
```

### 4.3 StepRecorder

**文件位置**: `services/session/step_recorder.py`（新建）

```python
class StepRecorder:
    """
    执行步骤记录器

    职责：
    1. 记录每次工具执行
    2. 自动推断依赖关系
    3. 构建渐进式 DAG
    """

    def record_step(
        self,
        session_state: SessionState,
        tool_id: str,
        tool_name: str,
        params: Dict[str, Any],
        result: Any,
        trigger_query: str
    ) -> RecordedStep:
        """
        记录执行步骤

        Args:
            session_state: 当前 Session 状态
            tool_id: 工具 ID
            tool_name: 工具名称
            params: 执行参数
            result: 执行结果（DataReference 或其他）
            trigger_query: 触发这次执行的用户查询

        Returns:
            RecordedStep
        """
        step_id = session_state.get_next_step_id()

        # 自动推断依赖关系
        depends_on, input_refs = self._infer_dependencies(
            params,
            session_state.recorded_steps,
            session_state.data_stash
        )

        # 提取结果信息
        artifact_id = None
        data_id = None
        summary = ""

        if hasattr(result, 'data_id'):
            data_id = result.data_id
        if hasattr(result, 'artifact_id'):
            artifact_id = result.artifact_id
        if hasattr(result, 'summary'):
            summary = result.summary

        step = RecordedStep(
            step_id=step_id,
            tool_id=tool_id,
            tool_name=tool_name,
            params=params,
            artifact_id=artifact_id,
            data_id=data_id,
            summary=summary,
            depends_on=depends_on,
            input_refs=input_refs,
            trigger_query=trigger_query,
        )

        session_state.recorded_steps.append(step)

        if artifact_id:
            session_state.artifact_ids[step_id] = artifact_id

        return step

    def _infer_dependencies(
        self,
        params: Dict[str, Any],
        recorded_steps: List[RecordedStep],
        data_stash: List[Dict[str, Any]]
    ) -> Tuple[List[int], List[str]]:
        """
        自动推断依赖关系

        规则：
        1. 如果参数中引用了某个 data_id，找到产生该 data_id 的步骤
        2. 如果参数中包含 source_ref，解析为步骤依赖
        """
        depends_on = []
        input_refs = []

        # 构建 data_id → step_id 映射
        data_id_to_step = {}
        for step in recorded_steps:
            if step.data_id:
                data_id_to_step[step.data_id] = step.step_id

        # 递归扫描参数，查找引用
        def scan_refs(value):
            if isinstance(value, str):
                # 检查是否是 data_id
                if value in data_id_to_step:
                    input_refs.append(value)
                    depends_on.append(data_id_to_step[value])
            elif isinstance(value, dict):
                for v in value.values():
                    scan_refs(v)
            elif isinstance(value, list):
                for item in value:
                    scan_refs(item)

        scan_refs(params)

        return list(set(depends_on)), list(set(input_refs))
```

---

## 五、核心组件设计

### 5.1 SessionRuntimeManager

**文件位置**: `services/session/runtime_manager.py`（新建）

```python
from typing import Optional, Dict, Any, Callable
from threading import Lock
from datetime import datetime
import logging

from langgraph_agents.sync_executor import SyncLangGraphExecutor, LangGraphExecutionResult
from langgraph_agents.runtime import LangGraphRuntime
from query_processor.llm_client import LLMClient
from services.data_query_service import DataQueryService

from .models import SessionState, SessionStatus, RecordedStep
from .store import SessionStore
from .step_recorder import StepRecorder

logger = logging.getLogger(__name__)


class SessionRuntimeManager:
    """
    Session Runtime 管理器

    职责：
    1. 管理 session_id → SessionState 的映射
    2. 创建/恢复 LangGraphRuntime
    3. 跨请求保持执行上下文
    4. 记录执行步骤
    5. 会话超时清理
    """

    def __init__(
        self,
        session_store: SessionStore,
        llm_client: LLMClient,
        data_query_service: DataQueryService,
        default_timeout_minutes: int = 60
    ):
        self.session_store = session_store
        self.llm_client = llm_client
        self.data_query_service = data_query_service
        self.default_timeout_minutes = default_timeout_minutes

        # 内存缓存：session_id → SessionState
        self._sessions: Dict[str, SessionState] = {}

        # Runtime 缓存：session_id → SyncLangGraphExecutor
        self._executors: Dict[str, SyncLangGraphExecutor] = {}

        # 线程安全
        self._lock = Lock()

        # 步骤记录器
        self.step_recorder = StepRecorder()

    def create_session(
        self,
        workspace_id: Optional[str] = None,
        source_workflow_id: Optional[str] = None,
        name: str = ""
    ) -> SessionState:
        """
        创建新 Session

        Returns:
            SessionState
        """
        with self._lock:
            # 创建持久化记录
            session = self.session_store.create_session(
                workspace_id=workspace_id,
                source_workflow_id=source_workflow_id,
                name=name
            )

            # 创建内存状态
            state = SessionState(
                session_id=session.session_id,
                source_workflow_id=source_workflow_id,
                timeout_minutes=self.default_timeout_minutes
            )

            self._sessions[session.session_id] = state

            logger.info(f"SessionRuntimeManager: 创建 Session {session.session_id}")
            return state

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        获取 Session 状态

        优先从内存获取，否则从数据库恢复
        """
        with self._lock:
            # 检查内存缓存
            if session_id in self._sessions:
                state = self._sessions[session_id]
                if not state.is_expired():
                    state.touch()
                    return state
                else:
                    # 过期，清理
                    self._cleanup_session(session_id)
                    return None

            # 从数据库恢复
            session = self.session_store.load_session(session_id)
            if not session:
                return None

            state = session.get_state()
            if state.is_expired():
                self._cleanup_session(session_id)
                return None

            state.touch()
            self._sessions[session_id] = state
            return state

    def execute_in_session(
        self,
        session_id: str,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        panel_callback: Optional[Callable] = None
    ) -> LangGraphExecutionResult:
        """
        在 Session 内执行查询（核心方法）

        与直接调用 SyncLangGraphExecutor.execute() 的区别：
        1. 恢复之前的 data_stash、chat_history、working_memory
        2. 执行完成后更新 Session 状态
        3. 记录执行步骤（渐进式 DAG）

        Args:
            session_id: Session ID
            query: 用户查询
            context: 额外上下文（如 artifact_refs）
            panel_callback: 面板预览回调

        Returns:
            LangGraphExecutionResult
        """
        # 获取 Session 状态
        state = self.get_session(session_id)
        if not state:
            raise ValueError(f"Session 不存在或已过期: {session_id}")

        # 获取或创建 Executor
        executor = self._get_or_create_executor(session_id)

        # 构建初始状态（从 Session 恢复）
        initial_state = self._build_initial_state(state, query, context)

        # 执行
        logger.info(f"SessionRuntimeManager: 执行查询 session={session_id} query={query[:50]}")

        # 直接调用 executor.app.invoke（绕过 execute() 的状态重置）
        config = {
            "recursion_limit": executor.recursion_limit,
            "configurable": {"thread_id": session_id},
        }

        final_state = executor.app.invoke(initial_state, config)
        result = executor._extract_result(final_state)

        # 更新 Session 状态
        self._update_session_state(state, final_state, query, result)

        # 持久化
        self._persist_session(session_id, state)

        return result

    def close_session(self, session_id: str) -> bool:
        """关闭 Session"""
        with self._lock:
            self._cleanup_session(session_id)
            return self.session_store.close_session(session_id)

    def _get_or_create_executor(self, session_id: str) -> SyncLangGraphExecutor:
        """获取或创建 Executor"""
        if session_id not in self._executors:
            executor = SyncLangGraphExecutor(
                llm_client=self.llm_client,
                data_query_service=self.data_query_service
            )
            self._executors[session_id] = executor
        return self._executors[session_id]

    def _build_initial_state(
        self,
        session_state: SessionState,
        query: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        从 Session 状态构建 LangGraph 初始状态

        关键：恢复 data_stash、chat_history、working_memory
        """
        from langgraph_agents.state import GraphState, DataReference

        # 恢复 data_stash
        data_stash = []
        for ref_dict in session_state.data_stash:
            try:
                data_stash.append(DataReference(**ref_dict))
            except Exception as e:
                logger.warning(f"恢复 DataReference 失败: {e}")

        # 构建初始状态
        initial_state: GraphState = {
            "original_query": query,
            "chat_history": session_state.chat_history.copy(),
            "data_stash": data_stash,
            "working_memory": session_state.working_memory.copy(),
            "next_tool_call": None,
            "reflection": None,
            "final_report": None,
            "human_in_loop_request": None,
            "router_decision": None,
            "pending_tool_result": None,
            "last_tool_result": None,
            "last_error": None,
            "execution_plan": None,
            "completed_step_ids": [],
            "knowledge_graph": None,
        }

        # 添加额外上下文
        if context:
            if "artifact_refs" in context:
                initial_state["working_memory"]["artifact_refs"] = context["artifact_refs"]

        return initial_state

    def _update_session_state(
        self,
        session_state: SessionState,
        final_state: Dict[str, Any],
        query: str,
        result: LangGraphExecutionResult
    ):
        """
        更新 Session 状态

        1. 更新 data_stash（累积）
        2. 更新 chat_history
        3. 更新 working_memory
        4. 记录执行步骤
        """
        # 更新 data_stash（新增的）
        new_refs = final_state.get("data_stash", [])
        existing_ids = {ref.get("data_id") for ref in session_state.data_stash if ref.get("data_id")}

        for ref in new_refs:
            ref_dict = ref.model_dump() if hasattr(ref, 'model_dump') else ref
            if ref_dict.get("data_id") not in existing_ids:
                session_state.data_stash.append(ref_dict)

        # 更新 chat_history
        session_state.chat_history.append({
            "role": "user",
            "content": query
        })
        if result.final_report:
            session_state.chat_history.append({
                "role": "assistant",
                "content": result.final_report
            })

        # 更新 working_memory
        new_memory = final_state.get("working_memory", {})
        session_state.working_memory.update(new_memory)

        # 记录执行步骤
        for ref in new_refs:
            ref_obj = ref if hasattr(ref, 'tool_name') else type('Ref', (), ref)()
            tool_name = getattr(ref_obj, 'tool_name', 'unknown')

            if tool_name and tool_name != 'unknown':
                # 查找对应的执行参数
                params = {}
                for step in result.execution_steps:
                    if step.get("tool_name") == tool_name:
                        params = step.get("params", {})
                        break

                self.step_recorder.record_step(
                    session_state=session_state,
                    tool_id=tool_name,
                    tool_name=tool_name,
                    params=params,
                    result=ref_obj,
                    trigger_query=query
                )

        session_state.touch()

    def _persist_session(self, session_id: str, state: SessionState):
        """持久化 Session 状态"""
        session = self.session_store.load_session(session_id)
        if session:
            session.set_state(state)
            self.session_store.save_session(session)

    def _cleanup_session(self, session_id: str):
        """清理 Session（内存）"""
        self._sessions.pop(session_id, None)
        self._executors.pop(session_id, None)

    def cleanup_expired_sessions(self) -> int:
        """清理所有过期的 Sessions"""
        with self._lock:
            expired = []
            for session_id, state in self._sessions.items():
                if state.is_expired():
                    expired.append(session_id)

            for session_id in expired:
                self._cleanup_session(session_id)

            # 同时清理数据库
            db_cleaned = self.session_store.cleanup_expired()

            logger.info(f"SessionRuntimeManager: 清理 {len(expired)} 个内存 Session，{db_cleaned} 个数据库 Session")
            return len(expired) + db_cleaned
```

### 5.2 WorkflowExtractor

**文件位置**: `services/session/workflow_extractor.py`（新建）

```python
class WorkflowExtractor:
    """
    从 Session 提取 Workflow 模板

    职责：
    1. 分析 recorded_steps
    2. 提取可参数化的变量
    3. 构建 Workflow 定义
    """

    def extract_workflow(
        self,
        session_state: SessionState,
        name: str,
        description: str = "",
        variable_hints: Optional[Dict[str, str]] = None
    ) -> Workflow:
        """
        从 Session 提取 Workflow

        Args:
            session_state: Session 状态
            name: 工作流名称
            description: 工作流描述
            variable_hints: 变量提示（参数名 → 变量名）

        Returns:
            Workflow 实例
        """
        steps = []
        variables = {}

        for recorded_step in session_state.recorded_steps:
            # 转换为 WorkflowStep
            step, step_variables = self._convert_step(
                recorded_step,
                variable_hints or {}
            )
            steps.append(step)
            variables.update(step_variables)

        workflow = Workflow(
            name=name,
            description=description,
            status=WorkflowStatus.DRAFT.value
        )
        workflow.set_steps(steps)
        workflow.set_variables(variables)

        return workflow

    def _convert_step(
        self,
        recorded_step: RecordedStep,
        variable_hints: Dict[str, str]
    ) -> Tuple[WorkflowStep, Dict[str, Variable]]:
        """
        转换 RecordedStep 为 WorkflowStep

        - 分析参数，提取可参数化的值
        - 替换为变量引用
        """
        variables = {}
        params = {}

        for key, value in recorded_step.params.items():
            # 检查是否应该参数化
            if key in variable_hints:
                var_name = variable_hints[key]
                variables[var_name] = Variable(
                    name=var_name,
                    var_type=self._infer_type(value),
                    default=value,
                    required=False
                )
                params[key] = f"${{{var_name}}}"
            elif self._should_parameterize(key, value):
                # 自动推断需要参数化的值
                var_name = f"{recorded_step.tool_id}_{key}"
                variables[var_name] = Variable(
                    name=var_name,
                    var_type=self._infer_type(value),
                    default=value,
                    required=False
                )
                params[key] = f"${{{var_name}}}"
            else:
                params[key] = value

        # 处理步骤引用
        for dep_step_id in recorded_step.depends_on:
            # 将 data_id 引用转换为 $ref 格式
            for key, value in params.items():
                if value in recorded_step.input_refs:
                    params[key] = {"$ref": {"step_id": dep_step_id}}

        step = WorkflowStep(
            step_id=recorded_step.step_id,
            name=recorded_step.tool_name or recorded_step.tool_id,
            description=recorded_step.summary,
            step_type=self._infer_step_type(recorded_step.tool_id),
            tool_id=recorded_step.tool_id,
            params=params,
            depends_on=recorded_step.depends_on,
            output_name=f"step_{recorded_step.step_id}_output"
        )

        return step, variables

    def _should_parameterize(self, key: str, value: Any) -> bool:
        """判断是否应该自动参数化"""
        # 典型的用户输入参数
        parameterizable_keys = {
            "query", "keyword", "search_term",
            "platform", "datasource",
            "instruction", "filter", "condition",
            "limit", "count", "max_items"
        }
        return key.lower() in parameterizable_keys

    def _infer_type(self, value: Any) -> VariableType:
        """推断变量类型"""
        if isinstance(value, bool):
            return VariableType.BOOLEAN
        elif isinstance(value, int) or isinstance(value, float):
            return VariableType.NUMBER
        elif isinstance(value, list):
            return VariableType.LIST
        else:
            return VariableType.STRING

    def _infer_step_type(self, tool_id: str) -> StepType:
        """推断步骤类型"""
        fetch_tools = {"fetch_public_data", "fetch_private_data", "search_data_sources"}
        process_tools = {"data_operator", "filter_data", "aggregate_data"}
        analyze_tools = {"extract_insights", "compare_data"}

        if tool_id in fetch_tools:
            return StepType.FETCH
        elif tool_id in process_tools:
            return StepType.PROCESS
        elif tool_id in analyze_tools:
            return StepType.ANALYZE
        else:
            return StepType.OUTPUT
```

---

## 六、API 设计

### 6.1 Session API

**文件位置**: `api/controllers/session_controller.py`（新建）

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    workspace_id: Optional[str] = None
    source_workflow_id: Optional[str] = None
    name: str = ""


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str
    created_at: str


class SessionChatRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None


class SessionChatResponse(BaseModel):
    success: bool
    message: str
    final_report: Optional[str] = None
    data_stash_count: int
    recorded_steps_count: int
    panel_data: Optional[Dict[str, Any]] = None


class ExportWorkflowRequest(BaseModel):
    name: str
    description: str = ""
    variable_hints: Optional[Dict[str, str]] = None


class ExportWorkflowResponse(BaseModel):
    workflow_id: str
    name: str
    steps_count: int
    variables_count: int


@router.post("", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """创建新 Session"""
    ...


@router.get("/{session_id}")
async def get_session(session_id: str):
    """获取 Session 状态"""
    ...


@router.delete("/{session_id}")
async def close_session(session_id: str):
    """关闭 Session"""
    ...


@router.post("/{session_id}/chat", response_model=SessionChatResponse)
async def session_chat(session_id: str, request: SessionChatRequest):
    """
    在 Session 内执行对话（核心 API）

    与 /api/v1/chat 的区别：
    - 保持多轮对话上下文
    - 自动记录执行步骤
    - 可引用之前的数据
    """
    ...


@router.post("/{session_id}/export", response_model=ExportWorkflowResponse)
async def export_as_workflow(session_id: str, request: ExportWorkflowRequest):
    """将 Session 导出为 Workflow 模板"""
    ...


@router.get("/{session_id}/steps")
async def get_recorded_steps(session_id: str):
    """获取记录的执行步骤"""
    ...


@router.get("/{session_id}/artifacts")
async def get_session_artifacts(session_id: str):
    """获取 Session 产生的所有 Artifacts"""
    ...
```

### 6.2 WebSocket 支持

```python
@router.websocket("/{session_id}/stream")
async def session_chat_stream(websocket: WebSocket, session_id: str):
    """
    Session 内流式对话

    支持：
    - 实时进度推送
    - 步骤执行通知
    - 面板预览
    """
    ...
```

---

## 七、前端改造

### 7.1 workspaceStore 扩展

**文件位置**: `frontend/src/features/workspace/stores/workspaceStore.ts`

```typescript
// 新增状态
const sessionId = ref<string | null>(null)
const sessionState = ref<SessionState | null>(null)

// 新增 actions
async function createSession(workflowId?: string) {
  const response = await api.createSession({
    workspace_id: currentWorkflowId.value,
    source_workflow_id: workflowId
  })
  sessionId.value = response.session_id
  sessionState.value = {
    session_id: response.session_id,
    status: 'active',
    data_stash: [],
    recorded_steps: [],
    chat_history: []
  }
}

async function closeSession() {
  if (sessionId.value) {
    await api.closeSession(sessionId.value)
    sessionId.value = null
    sessionState.value = null
  }
}

async function chatInSession(query: string, context?: Record<string, any>) {
  if (!sessionId.value) {
    await createSession()
  }

  const response = await api.sessionChat(sessionId.value!, {
    query,
    context
  })

  // 更新本地状态
  if (response.panel_data) {
    currentStepOutput.value = {
      stepId: sessionState.value!.recorded_steps.length,
      stepName: '对话结果',
      data: response.panel_data
    }
  }

  return response
}

async function exportAsWorkflow(name: string, description?: string) {
  if (!sessionId.value) {
    throw new Error('No active session')
  }

  return await api.exportAsWorkflow(sessionId.value, {
    name,
    description
  })
}
```

### 7.2 ChatInteractionArea 修改

```typescript
// 修改 handleSend 方法
async function handleSend() {
  if (!canSend.value) return

  const text = inputText.value.trim()

  try {
    // 使用 Session 内对话（而非直接 usePanelActions）
    const result = await store.chatInSession(text, {
      artifact_refs: selectedArtifact.value
        ? [selectedArtifact.value.artifact_id]
        : undefined
    })

    if (result.panel_data) {
      emit('result', result.panel_data, result.message)
    }

    inputText.value = ''
    resetTextareaHeight()
  } catch (e) {
    console.error('对话失败:', e)
    emit('error', e instanceof Error ? e.message : '未知错误')
  }
}
```

### 7.3 新增组件：保存为模板对话框

```vue
<!-- SaveAsTemplateDialog.vue -->
<template>
  <Dialog v-model:open="open">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>保存为工作流模板</DialogTitle>
        <DialogDescription>
          将当前会话的执行步骤保存为可复用的工作流模板
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <div>
          <Label>模板名称</Label>
          <Input v-model="name" placeholder="例如：竞品分析工作流" />
        </div>

        <div>
          <Label>描述</Label>
          <Textarea v-model="description" placeholder="描述这个工作流的用途..." />
        </div>

        <div>
          <Label>执行步骤预览</Label>
          <div class="rounded-lg border p-3 bg-muted/20 max-h-48 overflow-auto">
            <div v-for="step in recordedSteps" :key="step.step_id" class="text-sm mb-2">
              <span class="font-mono text-primary">{{ step.step_id }}.</span>
              {{ step.tool_name || step.tool_id }}
              <span v-if="step.depends_on.length" class="text-muted-foreground">
                (依赖: {{ step.depends_on.join(', ') }})
              </span>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="open = false">取消</Button>
        <Button @click="handleSave" :disabled="!name">保存</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
```

---

## 八、实施计划

### 8.1 分阶段实施

| Phase | 内容 | 预计工作量 |
|-------|------|-----------|
| **6.1** | Session 模型 + Store | 1 天 |
| **6.2** | SessionRuntimeManager 核心实现 | 2 天 |
| **6.3** | StepRecorder + 依赖推断 | 1 天 |
| **6.4** | Session API 端点 | 1 天 |
| **6.5** | WorkflowExtractor | 0.5 天 |
| **6.6** | 前端 workspaceStore 改造 | 1 天 |
| **6.7** | ChatInteractionArea 集成 | 0.5 天 |
| **6.8** | 保存为模板功能 | 0.5 天 |
| **6.9** | 单元测试 + 集成测试 | 1 天 |

**总计**: 约 8.5 天

### 8.2 依赖关系

```
Phase 6.1 (Session 模型)
    │
    ├───────────────────┐
    ▼                   ▼
Phase 6.2 (RuntimeManager)   Phase 6.3 (StepRecorder)
    │                   │
    └───────┬───────────┘
            ▼
    Phase 6.4 (API)
            │
    ┌───────┴───────┐
    ▼               ▼
Phase 6.5       Phase 6.6 (前端)
(Extractor)         │
    │               ▼
    │         Phase 6.7 (ChatInteraction)
    │               │
    └───────┬───────┘
            ▼
    Phase 6.8 (保存模板)
            │
            ▼
    Phase 6.9 (测试)
```

### 8.3 向后兼容保证

1. **现有 /api/v1/chat**：保持不变，仍然是无状态单次查询
2. **现有 WorkflowEngine**：不修改，模板执行仍然使用它
3. **现有 DataArtifact**：不修改，Session 产物仍然使用它
4. **渐进式迁移**：前端可以选择使用 Session API 或传统 API

### 8.4 回滚策略

如果出现问题：
1. 前端回退到使用 `usePanelActions.submit()`
2. 删除 `services/session/` 目录
3. 删除 sessions 表
4. 不影响现有功能

---

## 九、待确认问题

请确认以下设计决策：

| 问题 | 选项 A | 选项 B | 建议 |
|------|--------|--------|------|
| **Session 超时** | 60 分钟（较短） | 24 小时（较长） | A: 节省资源 | 最好做成可配置的
| **data_stash 上限** | 无限制 | 最多 100 条 | B: 防止内存溢出 | 也最好做成可配置的
| **chat_history 策略** | 保留全部 | 滑动窗口（最近 20 轮） | B: 节省 Token | 最好做成可配置的
| **自动保存** | 每次执行后自动持久化 | 手动触发 | A: 更可靠 | A
| **Session 命名** | 自动生成 | 用户指定 | A + B: 默认自动，可修改 | 同意

---

## 十、TODO 清单

- [ ] 用户确认设计方案
- [ ] Phase 6.1: Session 模型 + Store
  - [ ] `services/session/__init__.py`
  - [ ] `services/session/models.py`
  - [ ] `services/session/store.py`
- [ ] Phase 6.2: SessionRuntimeManager
  - [ ] `services/session/runtime_manager.py`
  - [ ] 单元测试
- [ ] Phase 6.3: StepRecorder
  - [ ] `services/session/step_recorder.py`
  - [ ] 依赖推断测试
- [ ] Phase 6.4: Session API
  - [ ] `api/controllers/session_controller.py`
  - [ ] API 测试
- [ ] Phase 6.5: WorkflowExtractor
  - [ ] `services/session/workflow_extractor.py`
- [ ] Phase 6.6: 前端 workspaceStore
  - [ ] Session 状态管理
  - [ ] API 调用
- [ ] Phase 6.7: ChatInteractionArea 集成
- [ ] Phase 6.8: 保存为模板功能
  - [ ] SaveAsTemplateDialog.vue
- [ ] Phase 6.9: 测试
  - [ ] 单元测试
  - [ ] 集成测试
  - [ ] 端到端测试

---

## 十一、参考资料

- [Phase 2: Workflow Engine 设计](./done/251209-phase2-workflow-engine-design.md)
- [Phase 1: DataArtifact 设计](./done/251209-phase1-data-artifact-design.md)
- [LangGraph V5.0 架构](../langgraph-v5.0-flexible-agent-architecture.md)
- [全局 WebSocket 连接管理器](./251115-debugging-research-flow.md)
