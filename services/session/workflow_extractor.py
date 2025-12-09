"""工作流提取器

从 Session 的执行记录中提取 Workflow 模板。

核心功能：
1. 将 RecordedStep 列表转换为 WorkflowStep 列表
2. 推断变量定义（将具体值抽象为变量）
3. 保持依赖关系（DAG 结构）
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from services.workflow.models import (
    Workflow,
    WorkflowStep,
    WorkflowStatus,
    StepType,
    Variable,
    VariableType,
    TemplateCategory,
)
from services.workflow.store import WorkflowStore, get_workflow_store

from .models import SessionState, RecordedStep

logger = logging.getLogger(__name__)


# 工具到步骤类型的映射
TOOL_TO_STEP_TYPE: Dict[str, StepType] = {
    "fetch_public_data": StepType.FETCH,
    "fetch_rss_data": StepType.FETCH,
    "fetch_bilibili_data": StepType.FETCH,
    "fetch_weibo_data": StepType.FETCH,
    "data_operator": StepType.PROCESS,
    "analyze_data": StepType.ANALYZE,
    "generate_report": StepType.OUTPUT,
}


class WorkflowExtractor:
    """
    工作流提取器

    职责：
    1. 从 Session 的 recorded_steps 提取 Workflow
    2. 将具体参数值转换为变量引用
    3. 保持步骤间的依赖关系
    """

    def __init__(self, workflow_store: Optional[WorkflowStore] = None):
        """
        初始化 WorkflowExtractor

        Args:
            workflow_store: 工作流存储层
        """
        self.workflow_store = workflow_store or get_workflow_store()

    def extract_workflow(
        self,
        session_state: SessionState,
        name: str,
        description: str = "",
        category: Optional[TemplateCategory] = None,
        extract_variables: bool = True,
        save_to_store: bool = True,
    ) -> Workflow:
        """
        从 Session 状态提取 Workflow

        Args:
            session_state: Session 状态
            name: 工作流名称
            description: 工作流描述
            category: 模板分类
            extract_variables: 是否提取变量（将具体值抽象为变量）
            save_to_store: 是否保存到存储层

        Returns:
            提取的 Workflow 实例
        """
        recorded_steps = session_state.recorded_steps

        if not recorded_steps:
            logger.warning(f"Session {session_state.session_id} 没有执行记录")
            # 创建空工作流
            workflow = Workflow.create(
                name=name,
                description=description,
                is_template=True
            )
            if category:
                workflow.category = category.value
            if save_to_store:
                self.workflow_store.save_workflow(workflow)
            return workflow

        # 转换步骤
        workflow_steps: List[WorkflowStep] = []
        variables: Dict[str, Variable] = {}

        # step_id 映射（RecordedStep.step_id → WorkflowStep.step_id）
        # 因为 RecordedStep 的 step_id 可能不连续
        step_id_map: Dict[int, int] = {}

        for idx, recorded_step in enumerate(recorded_steps, start=1):
            step_id_map[recorded_step.step_id] = idx

        for idx, recorded_step in enumerate(recorded_steps, start=1):
            # 转换依赖关系
            new_depends_on = [
                step_id_map[dep_id]
                for dep_id in recorded_step.depends_on
                if dep_id in step_id_map
            ]

            # 处理参数
            params = recorded_step.params.copy()
            if extract_variables:
                params, new_vars = self._extract_variables_from_params(
                    params, idx, recorded_step.tool_id
                )
                variables.update(new_vars)

            # 确定步骤类型
            step_type = TOOL_TO_STEP_TYPE.get(
                recorded_step.tool_id,
                StepType.PROCESS  # 默认为处理类型
            )

            # 创建 WorkflowStep
            workflow_step = WorkflowStep(
                step_id=idx,
                name=recorded_step.tool_name or recorded_step.tool_id,
                description=recorded_step.summary,
                step_type=step_type,
                tool_id=recorded_step.tool_id,
                params=params,
                depends_on=new_depends_on,
                output_name=f"step_{idx}_output"
            )
            workflow_steps.append(workflow_step)

        # 创建 Workflow
        workflow = Workflow.create(
            name=name,
            description=description or self._generate_description(recorded_steps),
            steps=workflow_steps,
            variables=variables if variables else None,
            is_template=True
        )

        # 设置元数据
        workflow.status = WorkflowStatus.TEMPLATE.value
        if category:
            workflow.category = category.value

        # 关联来源 Session
        # workflow.template_source_id 可用于追溯

        logger.info(
            f"WorkflowExtractor: 从 Session {session_state.session_id} "
            f"提取 Workflow {workflow.workflow_id}，"
            f"包含 {len(workflow_steps)} 个步骤，{len(variables)} 个变量"
        )

        # 保存到存储层
        if save_to_store:
            self.workflow_store.save_workflow(workflow)
            logger.info(f"WorkflowExtractor: 已保存 Workflow {workflow.workflow_id}")

        return workflow

    def _extract_variables_from_params(
        self,
        params: Dict[str, Any],
        step_id: int,
        tool_id: str
    ) -> tuple[Dict[str, Any], Dict[str, Variable]]:
        """
        从参数中提取变量

        将某些参数值抽象为变量引用，使工作流可以复用。

        规则：
        - query 类参数抽象为字符串变量
        - datasource 类参数保持不变（运行时绑定）
        - 数值/布尔类参数保持具体值

        Args:
            params: 原始参数
            step_id: 步骤 ID
            tool_id: 工具 ID

        Returns:
            (处理后的参数, 新变量定义)
        """
        new_params = params.copy()
        new_variables: Dict[str, Variable] = {}

        # 识别可变量化的参数
        variable_candidates = {
            "query": VariableType.STRING,
            "search_query": VariableType.STRING,
            "keywords": VariableType.LIST,
            "instruction": VariableType.STRING,
            "prompt": VariableType.STRING,
        }

        for param_name, var_type in variable_candidates.items():
            if param_name in new_params:
                original_value = new_params[param_name]

                # 生成变量名
                var_name = f"{param_name}_{step_id}"

                # 创建变量定义
                variable = Variable(
                    name=var_name,
                    var_type=var_type,
                    description=f"步骤 {step_id} 的 {param_name} 参数",
                    default=original_value,
                    required=False  # 有默认值，所以非必填
                )
                new_variables[var_name] = variable

                # 将参数值替换为变量引用
                new_params[param_name] = {"$var": var_name}

        return new_params, new_variables

    def _generate_description(self, recorded_steps: List[RecordedStep]) -> str:
        """
        根据执行步骤生成工作流描述

        Args:
            recorded_steps: 执行记录列表

        Returns:
            生成的描述
        """
        if not recorded_steps:
            return ""

        # 统计工具使用
        tool_counts: Dict[str, int] = {}
        for step in recorded_steps:
            tool_name = step.tool_name or step.tool_id
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        # 生成描述
        parts = []
        for tool_name, count in tool_counts.items():
            if count == 1:
                parts.append(tool_name)
            else:
                parts.append(f"{tool_name}×{count}")

        return f"包含 {len(recorded_steps)} 个步骤：{', '.join(parts)}"

    def extract_and_save(
        self,
        session_state: SessionState,
        name: str,
        description: str = "",
        category: Optional[TemplateCategory] = None,
    ) -> str:
        """
        提取并保存工作流（便捷方法）

        Args:
            session_state: Session 状态
            name: 工作流名称
            description: 工作流描述
            category: 模板分类

        Returns:
            工作流 ID
        """
        workflow = self.extract_workflow(
            session_state=session_state,
            name=name,
            description=description,
            category=category,
            extract_variables=True,
            save_to_store=True
        )
        return workflow.workflow_id


# 全局单例
_extractor: Optional[WorkflowExtractor] = None


def get_workflow_extractor() -> WorkflowExtractor:
    """获取 WorkflowExtractor 单例"""
    global _extractor
    if _extractor is None:
        _extractor = WorkflowExtractor()
    return _extractor


def reset_workflow_extractor():
    """重置提取器（测试用）"""
    global _extractor
    _extractor = None
