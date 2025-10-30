"""
路径构建器
职责：根据路由定义和参数值构建完整的URL路径
"""
import logging
import re
from typing import Any, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PathBuilder:
    """
    URL路径构建器
    根据path_template和参数值生成完整路径
    """

    def __init__(self, path_prefix: str = ""):
        """
        初始化路径构建器

        Args:
            path_prefix: 路径前缀（可选）
        """
        self.path_prefix = path_prefix

    def build(
        self,
        route_def: Dict[str, Any],
        parameters: Dict[str, Any],
        selected_template_index: int = 0,
    ) -> str:
        """
        构建完整的URL路径

        Args:
            route_def: 路由定义
            parameters: 参数字典
            selected_template_index: 使用哪个path_template（如果有多个）

        Returns:
            完整的URL路径

        Example:
            >>> route_def = {
            ...     "datasource": "hupu",
            ...     "path_template": ["/bbs/:id?/:order?"]
            ... }
            >>> parameters = {"id": "bxj", "order": "1"}
            >>> builder.build(route_def, parameters)
            '/hupu/bbs/bxj/1'
        """
        # 获取provider
        provider = route_def.get("datasource") or route_def.get("provider_id", "")

        # 获取path_template
        path_templates = route_def.get("path_template", [])

        if not path_templates:
            raise ValueError("路由定义中缺少path_template")

        if isinstance(path_templates, str):
            path_template = path_templates
        elif isinstance(path_templates, list):
            if selected_template_index >= len(path_templates):
                selected_template_index = 0
            path_template = path_templates[selected_template_index]
        else:
            raise ValueError(f"不支持的path_template类型: {type(path_templates)}")

        # 替换参数
        filled_path = self._fill_parameters(path_template, parameters)

        # 组装完整路径
        if provider:
            full_path = f"/{provider}{filled_path}"
        else:
            full_path = filled_path

        # 添加前缀
        if self.path_prefix:
            full_path = f"{self.path_prefix}{full_path}"

        # 清理路径（移除多余的斜杠）
        full_path = re.sub(r'/+', '/', full_path)

        logger.debug(f"构建路径: {path_template} + {parameters} → {full_path}")

        return full_path

    def _fill_parameters(
        self,
        template: str,
        parameters: Dict[str, Any],
    ) -> str:
        """
        填充path_template中的参数

        Args:
            template: 路径模板（如 /bbs/:id?/:order?）
            parameters: 参数字典

        Returns:
            填充后的路径
        """
        # 匹配 :param 或 :param?
        param_pattern = r':(\w+)\??'

        def replace_param(match):
            param_name = match.group(1)
            param_value = parameters.get(param_name)

            if param_value is not None:
                # 对参数值进行URL编码（如果需要）
                return str(param_value)
            else:
                # 参数未提供，如果是可选参数则返回空
                if match.group(0).endswith('?'):
                    return ""
                else:
                    # 必需参数但未提供
                    logger.warning(f"缺少必需参数: {param_name}")
                    return f":{param_name}"  # 保留占位符

        filled = re.sub(param_pattern, replace_param, template)

        # 清理连续的斜杠
        filled = re.sub(r'/+', '/', filled)

        # 移除末尾的斜杠（如果有）
        if filled.endswith('/') and len(filled) > 1:
            filled = filled[:-1]

        return filled

    def validate_parameters(
        self,
        route_def: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        验证参数是否满足路由要求

        Args:
            route_def: 路由定义
            parameters: 参数字典

        Returns:
            (是否有效, 错误信息)
        """
        route_params = route_def.get("parameters", [])

        for param_def in route_params:
            param_name = param_def.get("name")
            is_required = param_def.get("required", False)

            if is_required and param_name not in parameters:
                return False, f"缺少必需参数: {param_name}"

            # 检查参数值是否在可选值范围内
            if param_name in parameters:
                options = param_def.get("options", [])
                if options:
                    valid_values = []
                    for opt in options:
                        if isinstance(opt, dict):
                            valid_values.append(opt.get("value"))
                        else:
                            valid_values.append(opt)

                    if parameters[param_name] not in valid_values:
                        logger.warning(
                            f"参数 {param_name} 的值 {parameters[param_name]} "
                            f"不在可选值范围内: {valid_values}"
                        )

        return True, None


# 便捷函数
def build_path(
    route_def: Dict[str, Any],
    parameters: Dict[str, Any],
    path_prefix: str = "",
) -> str:
    """
    便捷函数：构建路径

    Args:
        route_def: 路由定义
        parameters: 参数字典
        path_prefix: 路径前缀

    Returns:
        完整的URL路径
    """
    builder = PathBuilder(path_prefix=path_prefix)
    return builder.build(route_def, parameters)
