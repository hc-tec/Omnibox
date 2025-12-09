"""
模板服务

Phase 4: 负责模板的创建、实例化、导出、导入
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

from .models import (
    Workflow, WorkflowStep, Variable, VariableType,
    WorkflowStatus, TemplateCategory
)
from .store import WorkflowStore, get_workflow_store

logger = logging.getLogger(__name__)

# 全局单例
_template_service: Optional["TemplateService"] = None


def get_template_service() -> "TemplateService":
    """获取 TemplateService 全局单例"""
    global _template_service
    if _template_service is None:
        _template_service = TemplateService()
    return _template_service


def reset_template_service() -> None:
    """重置全局单例（测试用）"""
    global _template_service
    _template_service = None


class WorkflowTemplateExport(BaseModel):
    """工作流模板导出格式"""

    class Meta(BaseModel):
        version: str = Field(default="1.0", description="模板格式版本")
        exported_at: str = Field(default_factory=lambda: datetime.now().isoformat())
        source_workflow_id: str = Field(..., description="源工作流 ID")

    class TemplateContent(BaseModel):
        name: str
        description: str
        category: Optional[str] = None
        tags: List[str] = Field(default_factory=list)
        steps: List[Dict[str, Any]]
        variables: Dict[str, Dict[str, Any]]

    class Preset(BaseModel):
        name: str
        variable_values: Dict[str, Any]

    meta: Meta
    template: TemplateContent
    presets: List[Preset] = Field(default_factory=list)


class TemplateService:
    """
    模板服务

    职责：
    1. 从工作流创建模板
    2. 从模板实例化工作流
    3. 模板导出/导入
    4. 变量校验
    """

    def __init__(self, workflow_store: Optional[WorkflowStore] = None):
        self._store = workflow_store or get_workflow_store()

    def create_template_from_workflow(
        self,
        workflow_id: str,
        category: str = TemplateCategory.CUSTOM.value,
        author: str = "anonymous",
        preview_image: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[Workflow]:
        """
        从现有工作流创建模板

        Args:
            workflow_id: 源工作流 ID
            category: 模板分类
            author: 模板作者
            preview_image: 预览图 URL
            tags: 标签列表

        Returns:
            新创建的模板，失败返回 None
        """
        # 加载源工作流
        source = self._store.load_workflow(workflow_id)
        if not source:
            logger.error(f"TemplateService: 源工作流不存在 {workflow_id}")
            return None

        # 创建模板（复制源工作流）
        template = Workflow.create(
            name=source.name,
            description=source.description,
            steps=source.get_steps(),
            variables=source.get_variables(),
            is_template=True
        )

        # 设置模板元数据
        template.category = category
        template.author = author
        template.preview_image = preview_image
        template.status = WorkflowStatus.TEMPLATE.value
        template.template_source_id = workflow_id

        if tags:
            template.set_tags(tags)
        else:
            template.set_tags(source.get_tags())

        # 提取变量（如果源工作流没有定义变量，尝试从步骤参数提取）
        if not source.get_variables():
            extracted = self._extract_variables_from_steps(source.get_steps())
            if extracted:
                template.set_variables(extracted)
                logger.info(f"TemplateService: 从步骤中提取了 {len(extracted)} 个变量")

        # 保存
        self._store.save_workflow(template)
        logger.info(f"TemplateService: 创建模板 {template.workflow_id} from {workflow_id}")

        return template

    def instantiate_template(
        self,
        template_id: str,
        variable_values: Dict[str, Any],
        new_name: Optional[str] = None
    ) -> Optional[Workflow]:
        """
        从模板创建工作流实例

        Args:
            template_id: 模板 ID
            variable_values: 变量值
            new_name: 新工作流名称（可选）

        Returns:
            新创建的工作流，失败返回 None
        """
        # 加载模板
        template = self._store.load_workflow(template_id)
        if not template:
            logger.error(f"TemplateService: 模板不存在 {template_id}")
            return None

        if not template.is_template:
            logger.error(f"TemplateService: {template_id} 不是模板")
            return None

        # 校验变量
        errors = self.validate_variable_values(template_id, variable_values)
        if errors:
            logger.error(f"TemplateService: 变量校验失败 {errors}")
            return None

        # 创建工作流实例
        workflow = Workflow.create(
            name=new_name or f"{template.name} (实例)",
            description=template.description,
            steps=template.get_steps(),
            variables=template.get_variables(),
            is_template=False
        )

        # 关联源模板
        workflow.template_source_id = template_id
        workflow.status = WorkflowStatus.READY.value
        workflow.set_tags(template.get_tags())

        # 替换步骤中的变量引用
        resolved_steps = self._resolve_variables_in_steps(
            workflow.get_steps(),
            variable_values
        )
        workflow.set_steps(resolved_steps)

        # 保存
        self._store.save_workflow(workflow)

        # 增加模板使用计数
        self._store.increment_usage_count(template_id)

        logger.info(f"TemplateService: 从模板 {template_id} 创建实例 {workflow.workflow_id}")
        return workflow

    def export_template(self, template_id: str) -> Optional[WorkflowTemplateExport]:
        """
        导出模板为 JSON 结构

        Args:
            template_id: 模板 ID

        Returns:
            WorkflowTemplateExport 对象，失败返回 None
        """
        template = self._store.load_workflow(template_id)
        if not template:
            logger.error(f"TemplateService: 模板不存在 {template_id}")
            return None

        # 构建导出结构
        export = WorkflowTemplateExport(
            meta=WorkflowTemplateExport.Meta(
                source_workflow_id=template.workflow_id
            ),
            template=WorkflowTemplateExport.TemplateContent(
                name=template.name,
                description=template.description,
                category=template.category,
                tags=template.get_tags(),
                steps=[step.model_dump() for step in template.get_steps()],
                variables={
                    name: var.model_dump()
                    for name, var in template.get_variables().items()
                }
            )
        )

        logger.info(f"TemplateService: 导出模板 {template_id}")
        return export

    def import_template(
        self,
        template_data: Dict[str, Any],
        author: str = "imported"
    ) -> Optional[Workflow]:
        """
        从 JSON 导入模板

        Args:
            template_data: 模板 JSON 数据
            author: 导入后的作者标记

        Returns:
            新创建的模板，失败返回 None
        """
        try:
            # 解析导入数据
            export = WorkflowTemplateExport.model_validate(template_data)
        except Exception as e:
            logger.error(f"TemplateService: 导入数据格式错误 {e}")
            return None

        # 重建步骤
        steps = [
            WorkflowStep(**step_data)
            for step_data in export.template.steps
        ]

        # 重建变量
        variables = {
            name: Variable(**var_data)
            for name, var_data in export.template.variables.items()
        }

        # 创建模板
        template = Workflow.create(
            name=export.template.name,
            description=export.template.description,
            steps=steps,
            variables=variables,
            is_template=True
        )

        template.category = export.template.category
        template.author = author
        template.status = WorkflowStatus.TEMPLATE.value
        template.set_tags(export.template.tags)

        # 保存
        self._store.save_workflow(template)
        logger.info(f"TemplateService: 导入模板 {template.workflow_id}")

        return template

    def validate_variable_values(
        self,
        template_id: str,
        values: Dict[str, Any]
    ) -> List[str]:
        """
        校验变量值是否满足模板要求

        Args:
            template_id: 模板 ID
            values: 变量值

        Returns:
            错误信息列表，空列表表示校验通过
        """
        template = self._store.load_workflow(template_id)
        if not template:
            return [f"模板不存在: {template_id}"]

        errors = []
        variables = template.get_variables()

        for name, var in variables.items():
            value = values.get(name)

            # 必填校验
            if var.required and value is None:
                errors.append(f"变量 '{name}' 是必填项")
                continue

            # 跳过可选且未提供的
            if value is None:
                continue

            # 类型校验
            if var.var_type == VariableType.STRING:
                if not isinstance(value, str):
                    errors.append(f"变量 '{name}' 应为字符串类型")
            elif var.var_type == VariableType.NUMBER:
                if not isinstance(value, (int, float)):
                    errors.append(f"变量 '{name}' 应为数字类型")
            elif var.var_type == VariableType.BOOLEAN:
                if not isinstance(value, bool):
                    errors.append(f"变量 '{name}' 应为布尔类型")
            elif var.var_type == VariableType.LIST:
                if not isinstance(value, list):
                    errors.append(f"变量 '{name}' 应为列表类型")

            # 枚举值校验
            if var.enum_values and value not in var.enum_values:
                errors.append(f"变量 '{name}' 的值必须是 {var.enum_values} 之一")

        return errors

    def _extract_variables_from_steps(
        self,
        steps: List[WorkflowStep]
    ) -> Dict[str, Variable]:
        """
        从步骤参数中提取可能的变量

        分析步骤参数，将字符串类型的参数提取为变量。
        这是一个启发式方法，用于帮助用户快速模板化。
        """
        variables = {}

        for step in steps:
            params = step.params

            # 提取 query 参数（fetch 步骤常用）
            if "query" in params and isinstance(params["query"], str):
                var_name = f"{step.name}_query".lower().replace(" ", "_")
                variables[var_name] = Variable(
                    name=var_name,
                    var_type=VariableType.STRING,
                    description=f"{step.name} 的查询参数",
                    default=params["query"],
                    required=True
                )

            # 提取 instruction 参数（process 步骤常用）
            if "instruction" in params and isinstance(params["instruction"], str):
                var_name = f"{step.name}_instruction".lower().replace(" ", "_")
                variables[var_name] = Variable(
                    name=var_name,
                    var_type=VariableType.STRING,
                    description=f"{step.name} 的处理指令",
                    default=params["instruction"],
                    required=True
                )

        return variables

    def _resolve_variables_in_steps(
        self,
        steps: List[WorkflowStep],
        values: Dict[str, Any]
    ) -> List[WorkflowStep]:
        """
        在步骤参数中替换变量引用

        支持 ${var_name} 语法
        """
        resolved_steps = []

        for step in steps:
            # 深拷贝步骤
            step_dict = step.model_dump()
            params = step_dict.get("params", {})

            # 替换参数中的变量
            resolved_params = self._resolve_variables_in_dict(params, values)
            step_dict["params"] = resolved_params

            resolved_steps.append(WorkflowStep(**step_dict))

        return resolved_steps

    def _resolve_variables_in_dict(
        self,
        data: Dict[str, Any],
        values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """递归替换字典中的变量引用"""
        result = {}

        for key, value in data.items():
            if isinstance(value, str):
                # 替换 ${var_name} 格式的变量
                resolved = value
                for var_name, var_value in values.items():
                    placeholder = f"${{{var_name}}}"
                    if placeholder in resolved:
                        # 如果整个值就是一个变量引用，直接替换
                        if resolved == placeholder:
                            resolved = var_value
                            break
                        # 否则字符串替换
                        resolved = resolved.replace(placeholder, str(var_value))
                result[key] = resolved
            elif isinstance(value, dict):
                result[key] = self._resolve_variables_in_dict(value, values)
            elif isinstance(value, list):
                result[key] = [
                    self._resolve_variables_in_dict(item, values)
                    if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value

        return result
