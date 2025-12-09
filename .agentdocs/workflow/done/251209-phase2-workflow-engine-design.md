# Phase 2: Workflow Engine 设计方案

**创建日期**: 2025-12-09
**状态**: ✅ 已完成
**完成日期**: 2025-12-09
**目标**: 建立工作流引擎层，支持多步骤 DAG 执行、进度追踪、中断/恢复

---

## 一、现状分析

### 1.1 可直接复用的现有组件

| 组件 | 文件位置 | 功能 | 复用策略 |
|------|---------|------|---------|
| **ExecutionPlan** | `langgraph_agents/state.py` | DAG 执行计划 | ✅ 作为内部执行单元 |
| **ExecutionEngine** | `langgraph_agents/execution_engine.py` | 步骤调度器 | ✅ 作为底层执行器 |
| **StashReference** | `langgraph_agents/state.py` | 依赖解析 | ✅ 直接复用 |
| **KnowledgeGraph** | `langgraph_agents/knowledge_graph.py` | 数据血缘 | ✅ 追踪产物关系 |
| **DataArtifact** | `services/artifact/models.py` | 数据产物 | ✅ Phase 1 成果 |
| **ArtifactStore** | `services/artifact/store.py` | 产物存储 | ✅ Phase 1 成果 |
| **DatabaseConnection** | `services/database/connection.py` | SQLite 连接 | ✅ 直接复用 |

### 1.2 现有 ExecutionPlan 结构

```python
# langgraph_agents/state.py
class ExecutionPlan(BaseModel):
    steps: List[ToolCall]              # 有序的工具调用列表
    dependencies: Dict[int, List[int]] # 依赖关系 DAG
    reasoning: str                     # 规划推理过程

    def get_ready_steps(completed_step_ids) -> List[ToolCall]  # 获取就绪步骤
    def is_complete(completed_step_ids) -> bool                 # 检查是否完成
```

### 1.3 差距分析

| 需求 | 现有支持 | 缺失部分 |
|------|---------|---------|
| DAG 执行 | ✅ ExecutionEngine | - |
| 依赖解析 | ✅ StashReference | - |
| 数据血缘 | ✅ KnowledgeGraph | - |
| 持久化 | ❌ 仅内存 | 需新增 SQLite 存储 |
| 用户可见元数据 | ❌ 无 | 需新增 name/description/status |
| 模板变量 | ❌ 无 | 需新增 Variable 系统 |
| 进度追踪 | ⚠️ 日志级别 | 需新增 WebSocket 回调 |
| 中断/恢复 | ❌ 无 | 需新增状态持久化 |
| 与 DataArtifact 集成 | ❌ 无 | 需新增步骤输出关联 |

### 1.4 关键区分：ExecutionPlan vs Workflow

| 维度 | ExecutionPlan | Workflow（新增） |
|------|--------------|------------------|
| **定位** | LangGraph 内部执行单元 | 用户可见的工作流模板 |
| **生命周期** | 单次对话内 | 持久化，可复用 |
| **生成方式** | PlannerAgent 自动生成 | 用户定义 + AI 辅助 |
| **参数** | 固定值 | 支持模板变量 |
| **步骤定义** | ToolCall（内部工具 ID） | WorkflowStep（用户可读） |
| **产物关联** | DataReference（临时） | DataArtifact（持久化） |

**设计原则**：Workflow 是 ExecutionPlan 的高层封装，运行时将 Workflow 转换为 ExecutionPlan 交给 ExecutionEngine 执行。

---

## 二、架构设计

### 2.1 层次关系

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Workflow Engine 层（新增）                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Workflow (持久化模板)                                       │   │
│  │  + name, description, status                                 │   │
│  │  + steps: List[WorkflowStep]                                │   │
│  │  + variables: Dict[str, Variable]                           │   │
│  │                                                              │   │
│  │  WorkflowStep (步骤定义)                                     │   │
│  │  + step_type: fetch | process | analyze | output            │   │
│  │  + tool_id, params, depends_on                              │   │
│  │  + output_artifact_id (关联 DataArtifact)                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓ 转换                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  WorkflowEngine (调度器)                                     │   │
│  │  + run_workflow() → 创建 ExecutionPlan → 调用 ExecutionEngine│   │
│  │  + pause() / resume() → 状态持久化                          │   │
│  │  + progress_callback → WebSocket 通知                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓ 调用                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  WorkflowStore (持久化)                                      │   │
│  │  + SQLite 存储 (Workflow, WorkflowStep, WorkflowRun)        │   │
│  │  + CRUD + 查询                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ 复用
┌─────────────────────────────────────────────────────────────────────┐
│                    现有 LangGraph 基础设施（不修改）                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ExecutionEngine + ExecutionPlan + StashReference           │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ 复用
┌─────────────────────────────────────────────────────────────────────┐
│                    Phase 1 DataArtifact 基础设施                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  DataArtifact + ArtifactStore + ViewSuggester               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
用户创建/执行工作流
        │
        ▼
┌───────────────────┐
│  Workflow (模板)   │◄─── 持久化到 SQLite
│  + variables      │
└───────┬───────────┘
        │ 填入变量值
        ▼
┌───────────────────┐
│  WorkflowRun      │◄─── 执行实例，记录运行状态
│  + variable_values│
│  + status         │
└───────┬───────────┘
        │ 转换
        ▼
┌───────────────────┐
│  ExecutionPlan    │◄─── 内部执行计划
│  + ToolCalls      │
└───────┬───────────┘
        │ 执行
        ▼
┌───────────────────┐
│  ExecutionEngine  │
│  + 步骤调度       │
│  + 依赖解析       │
└───────┬───────────┘
        │ 每步产出
        ▼
┌───────────────────┐
│  DataArtifact     │◄─── 关联到 WorkflowStep
│  + 自动 ViewSpec  │
└───────────────────┘
```

---

## 三、数据模型设计

### 3.1 Workflow 模型

**文件位置**: `services/workflow/models.py`（新建）

```python
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

class Variable(BaseModel):
    """工作流变量定义"""
    name: str
    var_type: VariableType
    description: str = ""
    default: Optional[Any] = None
    required: bool = True
    # 可选：枚举值限制
    enum_values: Optional[List[Any]] = None

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

class Workflow(SQLModel, table=True):
    """工作流定义（持久化）"""
    __tablename__ = "workflows"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    workflow_id: str = SQLField(index=True, description="工作流唯一标识")

    # 基本信息
    name: str = SQLField(..., description="工作流名称")
    description: str = SQLField("", description="工作流描述")
    status: str = SQLField(default=WorkflowStatus.DRAFT, description="状态")

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

    # 方法：JSON 序列化/反序列化
    def get_steps(self) -> List[WorkflowStep]: ...
    def set_steps(self, steps: List[WorkflowStep]): ...
    def get_variables(self) -> Dict[str, Variable]: ...
    def set_variables(self, variables: Dict[str, Variable]): ...
```

### 3.2 WorkflowRun 模型（执行实例）

```python
class RunStatus(str, Enum):
    """执行状态"""
    PENDING = "pending"       # 等待执行
    RUNNING = "running"       # 执行中
    PAUSED = "paused"         # 已暂停
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 执行失败
    CANCELLED = "cancelled"   # 已取消

class WorkflowRun(SQLModel, table=True):
    """工作流执行实例"""
    __tablename__ = "workflow_runs"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    run_id: str = SQLField(index=True, description="执行实例唯一标识")
    workflow_id: str = SQLField(index=True, description="关联的工作流 ID")

    # 执行状态
    status: str = SQLField(default=RunStatus.PENDING)
    current_step_id: Optional[int] = SQLField(default=None, description="当前执行步骤")
    completed_step_ids_json: str = SQLField(default="[]", description="已完成步骤")

    # 变量值（运行时）
    variable_values_json: str = SQLField(default="{}", description="变量实际值")

    # 产物关联
    artifact_ids_json: str = SQLField(default="{}", description="步骤 → 产物 ID 映射")

    # 执行信息
    started_at: Optional[datetime] = SQLField(default=None)
    completed_at: Optional[datetime] = SQLField(default=None)
    error_message: Optional[str] = SQLField(default=None)

    # 进度快照（用于恢复）
    execution_state_json: Optional[str] = SQLField(default=None, description="ExecutionEngine 状态快照")
```

### 3.3 与 DataArtifact 的关联

```python
# 在 DataArtifact 的 source 中扩展
class ArtifactSource(BaseModel):
    workflow_id: Optional[str] = None    # 所属工作流
    workflow_run_id: Optional[str] = None  # 所属执行实例（新增）
    step_id: int                         # 步骤编号
    tool_name: str                       # 生成工具
    created_at: datetime
```

---

## 四、核心组件设计

### 4.1 WorkflowEngine（执行引擎）

**文件位置**: `services/workflow/engine.py`（新建）

```python
from typing import Callable, Optional, Dict, Any
from .models import Workflow, WorkflowRun, WorkflowStep, RunStatus
from .store import WorkflowStore
from services.artifact import ArtifactStore, DataArtifact
from langgraph_agents.state import ExecutionPlan, ToolCall
from langgraph_agents.execution_engine import ExecutionEngine

class ProgressEvent(BaseModel):
    """进度事件"""
    run_id: str
    event_type: Literal["started", "step_started", "step_completed", "completed", "failed", "paused"]
    step_id: Optional[int] = None
    step_name: Optional[str] = None
    artifact_id: Optional[str] = None
    message: str = ""
    progress_percent: float = 0.0

ProgressCallback = Callable[[ProgressEvent], None]

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
        workflow_store: WorkflowStore,
        artifact_store: ArtifactStore,
        execution_engine: ExecutionEngine,
        progress_callback: Optional[ProgressCallback] = None
    ):
        self.workflow_store = workflow_store
        self.artifact_store = artifact_store
        self.execution_engine = execution_engine
        self.progress_callback = progress_callback

    def start_run(
        self,
        workflow_id: str,
        variable_values: Dict[str, Any]
    ) -> WorkflowRun:
        """
        启动工作流执行

        1. 加载 Workflow
        2. 验证变量值
        3. 创建 WorkflowRun
        4. 转换为 ExecutionPlan
        5. 开始执行
        """
        ...

    def pause_run(self, run_id: str) -> bool:
        """暂停执行（保存状态快照）"""
        ...

    def resume_run(self, run_id: str) -> bool:
        """恢复执行（从状态快照恢复）"""
        ...

    def cancel_run(self, run_id: str) -> bool:
        """取消执行"""
        ...

    def get_run_status(self, run_id: str) -> WorkflowRun:
        """获取执行状态"""
        ...

    def _convert_to_execution_plan(
        self,
        workflow: Workflow,
        variable_values: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        将 Workflow 转换为 ExecutionPlan

        1. 解析 steps
        2. 替换变量引用（${var_name}）
        3. 构建 ToolCall 列表
        4. 构建依赖图
        """
        ...

    def _on_step_complete(
        self,
        run: WorkflowRun,
        step: WorkflowStep,
        result: Any
    ):
        """
        步骤完成回调

        1. 创建 DataArtifact
        2. 更新 WorkflowRun 状态
        3. 触发进度回调
        """
        ...
```

### 4.2 WorkflowStore（存储层）

**文件位置**: `services/workflow/store.py`（新建）

```python
class WorkflowStore:
    """
    工作流存储层

    职责：
    1. Workflow CRUD
    2. WorkflowRun CRUD
    3. 查询（按状态、按模板）
    """

    def save_workflow(self, workflow: Workflow) -> str: ...
    def load_workflow(self, workflow_id: str) -> Optional[Workflow]: ...
    def list_workflows(self, status: Optional[str] = None) -> List[Workflow]: ...
    def delete_workflow(self, workflow_id: str) -> bool: ...

    def save_run(self, run: WorkflowRun) -> str: ...
    def load_run(self, run_id: str) -> Optional[WorkflowRun]: ...
    def list_runs(self, workflow_id: str) -> List[WorkflowRun]: ...
    def update_run_status(self, run_id: str, status: RunStatus, **kwargs) -> bool: ...
```

### 4.3 变量替换系统

```python
class VariableResolver:
    """
    变量解析器

    支持的引用格式：
    - ${var_name} - 简单变量引用
    - ${var_name.field} - 嵌套字段引用（对象类型）
    - ${var_name[0]} - 数组索引引用（列表类型）
    """

    def resolve(
        self,
        template: Dict[str, Any],
        variables: Dict[str, Variable],
        values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        解析模板中的变量引用

        1. 验证必填变量
        2. 应用默认值
        3. 递归替换引用
        4. 类型检查
        """
        ...
```

---

## 五、集成方案

### 5.1 与现有 LangGraph 工具集成

WorkflowStep 的 `tool_id` 对应 LangGraph 工具注册表中的工具：

| tool_id | 对应工具 | 步骤类型 |
|---------|---------|---------|
| `fetch_public_data` | 公开数据获取 | fetch |
| `fetch_private_data` | 私有数据获取 | fetch |
| `data_operator` | 数据操作（过滤/聚合） | process |
| `search_data_sources` | 数据源搜索 | fetch |
| `synthesizer` | 综合分析 | analyze |
| `ask_user_clarification` | 用户交互 | output |

### 5.2 与 Phase 1 DataArtifact 集成

```python
# WorkflowEngine._on_step_complete 中

def _on_step_complete(self, run: WorkflowRun, step: WorkflowStep, result: Any):
    # 1. 从工具结果创建 DataArtifact
    artifact = DataArtifact.from_enhanced_reference(
        ref=result.data_ref,
        workflow_id=run.workflow_id,
        artifact_type=self._infer_artifact_type(step.step_type),
        name=step.output_name or f"{step.name}_output"
    )

    # 2. 扩展 source 信息
    artifact.source.workflow_run_id = run.run_id

    # 3. 自动生成 ViewSpec
    artifact.suggested_views = suggest_views(
        artifact.schema_info,
        artifact.statistics,
        artifact.sample_items
    )

    # 4. 保存产物
    artifact_id = self.artifact_store.save_artifact(artifact)

    # 5. 更新 run 的产物映射
    run.artifact_ids[step.step_id] = artifact_id
    self.workflow_store.save_run(run)
```

### 5.3 进度推送（WebSocket）

```python
# 与现有 WebSocket 机制集成

class WorkflowProgressCallback:
    """WebSocket 进度推送"""

    def __init__(self, websocket_manager):
        self.ws = websocket_manager

    def __call__(self, event: ProgressEvent):
        # 推送到前端
        self.ws.send_message({
            "type": "workflow_progress",
            "run_id": event.run_id,
            "event_type": event.event_type,
            "step_id": event.step_id,
            "step_name": event.step_name,
            "artifact_id": event.artifact_id,
            "message": event.message,
            "progress_percent": event.progress_percent
        })
```

---

## 六、前端类型定义

**文件位置**: `frontend/src/types/workflow.ts`（新建）

```typescript
/**
 * 工作流类型定义
 */

export type WorkflowStatus = 'draft' | 'ready' | 'template';
export type StepType = 'fetch' | 'process' | 'analyze' | 'output';
export type VariableType = 'string' | 'number' | 'boolean' | 'datasource' | 'list';
export type RunStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';

export interface Variable {
  name: string;
  var_type: VariableType;
  description: string;
  default?: unknown;
  required: boolean;
  enum_values?: unknown[];
}

export interface WorkflowStep {
  step_id: number;
  name: string;
  description: string;
  step_type: StepType;
  tool_id: string;
  params: Record<string, unknown>;
  depends_on: number[];
  output_name: string;
}

export interface Workflow {
  workflow_id: string;
  name: string;
  description: string;
  status: WorkflowStatus;
  steps: WorkflowStep[];
  variables: Record<string, Variable>;
  is_template: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkflowRun {
  run_id: string;
  workflow_id: string;
  status: RunStatus;
  current_step_id?: number;
  completed_step_ids: number[];
  variable_values: Record<string, unknown>;
  artifact_ids: Record<number, string>;  // step_id → artifact_id
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface ProgressEvent {
  run_id: string;
  event_type: 'started' | 'step_started' | 'step_completed' | 'completed' | 'failed' | 'paused';
  step_id?: number;
  step_name?: string;
  artifact_id?: string;
  message: string;
  progress_percent: number;
}
```

---

## 七、实施计划

### 7.1 分阶段实施

| 阶段 | 内容 | 预计工作量 |
|------|------|-----------|
| 2.1 | 创建设计文档（本文档） | 0.5 天 |
| 2.2 | 实现 Workflow/WorkflowStep/WorkflowRun 模型 | 1 天 |
| 2.3 | 实现 WorkflowStore + SQLite 持久化 | 1 天 |
| 2.4 | 实现 WorkflowEngine + 变量解析 | 1.5 天 |
| 2.5 | 与 Phase 1 DataArtifact 集成 | 0.5 天 |
| 2.6 | 单元测试 + 集成测试 | 1 天 |

**总计**: 约 5.5 天

### 7.2 依赖关系

```
Phase 2.1 (设计文档)
    │
    ▼
Phase 2.2 (模型) ◄─── 依赖 Phase 1 DataArtifact
    │
    ▼
Phase 2.3 (存储) ◄─── 依赖 services/database/connection
    │
    ▼
Phase 2.4 (引擎) ◄─── 依赖 langgraph_agents/execution_engine
    │
    ▼
Phase 2.5 (集成) ◄─── 依赖 services/artifact/store
    │
    ▼
Phase 2.6 (测试)
```

### 7.3 向后兼容保证

1. **现有 LangGraph 工作流**：不受影响，继续使用 ExecutionPlan/ExecutionEngine
2. **现有 DataArtifact**：扩展 source 字段，无破坏性变更
3. **现有数据库**：新增 workflows/workflow_runs 表，不修改现有表

### 7.4 回滚策略

如果出现问题：
1. 删除 `services/workflow/` 目录
2. 删除 workflows/workflow_runs 表
3. 不影响 Phase 1 DataArtifact 功能

---

## 八、待确认问题

请确认以下设计决策：

| 问题 | 选项 A | 选项 B | 建议 |
|------|--------|--------|------|
| **执行模式** | 串行执行（简单） | 并行执行（复杂） | A: 先串行，后续优化 | A
| **变量引用语法** | `${var_name}` | `{{var_name}}` | A: 更通用 | A
| **暂停实现** | 步骤级（当前步骤完成后暂停） | 立即暂停（中断执行） | A: 更简单可靠 | A
| **模板存储** | 同一张表 is_template 标记 | 单独 workflow_templates 表 | A: 简单 | A

---

## 九、TODO 清单

- [x] 用户确认设计方案 (2025-12-09)
- [x] Phase 2.1: 创建目录结构
  - [x] `services/workflow/__init__.py`
  - [x] `services/workflow/models.py`
  - [x] `services/workflow/store.py`
  - [x] `services/workflow/engine.py`
  - [x] `services/workflow/variable_resolver.py`
- [x] Phase 2.2: 实现模型
- [x] Phase 2.3: 实现存储层
- [x] Phase 2.4: 实现执行引擎
- [x] Phase 2.5: 集成 DataArtifact
- [x] Phase 2.6: 单元测试（54 个测试全部通过）

---

## 十、实施进度

- [x] 用户确认设计方案 (2025-12-09)
- [x] Phase 2.1: 创建目录结构 (2025-12-09)
- [x] Phase 2.2: 实现模型 (2025-12-09)
- [x] Phase 2.3: 实现存储层 (2025-12-09)
- [x] Phase 2.4: 实现执行引擎 (2025-12-09)
- [x] Phase 2.5: 集成 DataArtifact (2025-12-09)
- [x] Phase 2.6: 单元测试 (2025-12-09)

---

## 十一、实施总结

### 11.1 创建的文件

| 文件 | 说明 |
|------|------|
| `services/workflow/__init__.py` | 模块入口，导出所有公共接口 |
| `services/workflow/models.py` | Workflow、WorkflowStep、WorkflowRun、Variable 模型 |
| `services/workflow/store.py` | WorkflowStore + SQLite 持久化 |
| `services/workflow/engine.py` | WorkflowEngine 执行引擎 |
| `services/workflow/variable_resolver.py` | 变量解析器（${var_name} 语法） |
| `frontend/src/types/workflow.ts` | 前端 TypeScript 类型定义 |
| `tests/services/workflow/test_models.py` | 模型单元测试（19个） |
| `tests/services/workflow/test_store.py` | 存储层单元测试（15个） |
| `tests/services/workflow/test_variable_resolver.py` | 变量解析器测试（20个） |

### 11.2 复用的现有组件

- `services.database.connection.DatabaseConnection` - SQLite 连接管理
- `services.artifact.DataArtifact` - 步骤产物（Phase 1）
- `services.artifact.ArtifactStore` - 产物存储（Phase 1）
- `services.artifact.suggest_views` - ViewSpec 推断（Phase 1）

### 11.3 已确认设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 执行模式 | 串行执行 | 先简单，后续优化 |
| 变量语法 | `${var_name}` | 更通用 |
| 暂停方式 | 步骤级暂停 | 更简单可靠 |
| 模板存储 | 同表 is_template 标记 | 简单 |

### 11.4 测试覆盖

- 54 个单元测试全部通过
- 覆盖：模型创建、依赖验证、存储 CRUD、变量解析、嵌套结构
