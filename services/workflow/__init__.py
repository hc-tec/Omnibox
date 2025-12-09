"""
工作流引擎模块

Phase 2: Workflow Engine
- 工作流定义与持久化
- 多步骤 DAG 执行
- 进度追踪与中断/恢复
- 与 DataArtifact 集成

复用现有组件：
- langgraph_agents.state.ExecutionPlan - 作为内部执行单元
- langgraph_agents.execution_engine.ExecutionEngine - 底层执行器
- services.artifact.DataArtifact - 步骤产物
"""

from .models import (
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
from .store import WorkflowStore, get_workflow_store, reset_workflow_store
from .engine import WorkflowEngine, WorkflowExecutionError, create_workflow_engine
from .variable_resolver import VariableResolver, VariableValidationError

__all__ = [
    # 模型
    "Workflow",
    "WorkflowStep",
    "WorkflowRun",
    "WorkflowStatus",
    "StepType",
    "RunStatus",
    "Variable",
    "VariableType",
    "ProgressEvent",
    # 存储
    "WorkflowStore",
    "get_workflow_store",
    "reset_workflow_store",
    # 引擎
    "WorkflowEngine",
    "WorkflowExecutionError",
    "create_workflow_engine",
    # 变量解析
    "VariableResolver",
    "VariableValidationError",
]
