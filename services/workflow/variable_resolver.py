"""
变量解析器

Phase 2: 模板变量替换系统
支持 ${var_name} 语法
"""

import re
import logging
from typing import Any, Dict, List, Optional

from .models import Variable, VariableType

logger = logging.getLogger(__name__)

# 变量引用正则：${var_name} 或 ${var_name.field} 或 ${var_name[0]}
VARIABLE_PATTERN = re.compile(r'\$\{([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*|\[\d+\])*)\}')


class VariableValidationError(Exception):
    """变量验证错误"""
    pass


class VariableResolver:
    """
    变量解析器

    支持的引用格式：
    - ${var_name} - 简单变量引用
    - ${var_name.field} - 嵌套字段引用（对象类型）
    - ${var_name[0]} - 数组索引引用（列表类型）
    """

    def validate(
        self,
        variables: Dict[str, Variable],
        values: Dict[str, Any]
    ) -> List[str]:
        """
        验证变量值

        Args:
            variables: 变量定义
            values: 变量值

        Returns:
            错误信息列表，空列表表示验证通过
        """
        errors = []

        for name, var in variables.items():
            value = values.get(name)

            # 检查必填
            if var.required and value is None and var.default is None:
                errors.append(f"缺少必填变量: {name}")
                continue

            # 如果有值，检查类型
            if value is not None:
                type_error = self._validate_type(name, var, value)
                if type_error:
                    errors.append(type_error)

                # 检查枚举值
                if var.enum_values and value not in var.enum_values:
                    errors.append(
                        f"变量 {name} 的值 {value} 不在允许列表中: {var.enum_values}"
                    )

        return errors

    def _validate_type(self, name: str, var: Variable, value: Any) -> Optional[str]:
        """验证变量类型"""
        expected_type = var.var_type

        if expected_type == VariableType.STRING:
            if not isinstance(value, str):
                return f"变量 {name} 应为字符串，实际为 {type(value).__name__}"

        elif expected_type == VariableType.NUMBER:
            if not isinstance(value, (int, float)):
                return f"变量 {name} 应为数字，实际为 {type(value).__name__}"

        elif expected_type == VariableType.BOOLEAN:
            if not isinstance(value, bool):
                return f"变量 {name} 应为布尔值，实际为 {type(value).__name__}"

        elif expected_type == VariableType.LIST:
            if not isinstance(value, list):
                return f"变量 {name} 应为列表，实际为 {type(value).__name__}"

        elif expected_type == VariableType.DATASOURCE:
            # 数据源引用可以是字符串或字典
            if not isinstance(value, (str, dict)):
                return f"变量 {name} 应为数据源引用（字符串或字典），实际为 {type(value).__name__}"

        return None

    def resolve(
        self,
        template: Any,
        variables: Dict[str, Variable],
        values: Dict[str, Any]
    ) -> Any:
        """
        解析模板中的变量引用

        Args:
            template: 待解析的模板（可以是 dict/list/str/其他）
            variables: 变量定义
            values: 变量值

        Returns:
            解析后的值

        Raises:
            VariableValidationError: 变量验证失败
        """
        # 验证变量
        errors = self.validate(variables, values)
        if errors:
            raise VariableValidationError("; ".join(errors))

        # 合并默认值
        merged_values = self._merge_defaults(variables, values)

        # 递归解析
        return self._resolve_value(template, merged_values)

    def _merge_defaults(
        self,
        variables: Dict[str, Variable],
        values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """合并变量值和默认值"""
        merged = {}
        for name, var in variables.items():
            if name in values and values[name] is not None:
                merged[name] = values[name]
            elif var.default is not None:
                merged[name] = var.default
        return merged

    def _resolve_value(self, value: Any, resolved_values: Dict[str, Any]) -> Any:
        """递归解析值中的变量引用"""
        if isinstance(value, str):
            return self._resolve_string(value, resolved_values)

        elif isinstance(value, dict):
            return {k: self._resolve_value(v, resolved_values) for k, v in value.items()}

        elif isinstance(value, list):
            return [self._resolve_value(item, resolved_values) for item in value]

        else:
            return value

    def _resolve_string(self, text: str, resolved_values: Dict[str, Any]) -> Any:
        """
        解析字符串中的变量引用

        如果整个字符串是单个变量引用，返回变量的原始类型。
        否则返回替换后的字符串。
        """
        # 检查是否是完整的单个变量引用
        match = VARIABLE_PATTERN.fullmatch(text)
        if match:
            # 整个字符串是单个变量引用，返回原始类型
            path = match.group(1)
            return self._get_value_by_path(path, resolved_values)

        # 否则，替换字符串中的所有变量引用
        def replace_var(m):
            path = m.group(1)
            value = self._get_value_by_path(path, resolved_values)
            return str(value) if value is not None else m.group(0)

        return VARIABLE_PATTERN.sub(replace_var, text)

    def _get_value_by_path(self, path: str, resolved_values: Dict[str, Any]) -> Any:
        """
        根据路径获取值

        支持的路径格式：
        - var_name
        - var_name.field
        - var_name[0]
        - var_name.field[0].sub_field
        """
        # 解析路径
        parts = self._parse_path(path)
        if not parts:
            return None

        # 获取根变量
        root_var = parts[0]
        if root_var not in resolved_values:
            logger.warning(f"VariableResolver: 变量 {root_var} 未定义")
            return None

        value = resolved_values[root_var]

        # 遍历路径
        for part in parts[1:]:
            if value is None:
                return None

            if isinstance(part, int):
                # 数组索引
                if isinstance(value, list) and 0 <= part < len(value):
                    value = value[part]
                else:
                    logger.warning(f"VariableResolver: 索引 {part} 越界")
                    return None

            elif isinstance(part, str):
                # 字段访问
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = getattr(value, part, None)

        return value

    def _parse_path(self, path: str) -> List[Any]:
        """
        解析变量路径

        返回路径部分列表，字符串表示字段，整数表示索引。
        例如：
        - "var_name" -> ["var_name"]
        - "var_name.field" -> ["var_name", "field"]
        - "var_name[0]" -> ["var_name", 0]
        - "var_name.field[0].sub" -> ["var_name", "field", 0, "sub"]
        """
        parts = []
        current = ""

        i = 0
        while i < len(path):
            char = path[i]

            if char == '.':
                # 字段分隔符
                if current:
                    parts.append(current)
                    current = ""
            elif char == '[':
                # 数组索引开始
                if current:
                    parts.append(current)
                    current = ""
                # 找到对应的 ]
                j = path.find(']', i)
                if j == -1:
                    break
                index_str = path[i + 1:j]
                if index_str.isdigit():
                    parts.append(int(index_str))
                i = j
            else:
                current += char

            i += 1

        if current:
            parts.append(current)

        return parts

    def extract_variables(self, template: Any) -> List[str]:
        """
        提取模板中引用的所有变量名

        Args:
            template: 模板

        Returns:
            变量名列表（去重）
        """
        variables = set()

        def extract_from_value(value):
            if isinstance(value, str):
                for match in VARIABLE_PATTERN.finditer(value):
                    # 提取根变量名
                    path = match.group(1)
                    root_var = path.split('.')[0].split('[')[0]
                    variables.add(root_var)
            elif isinstance(value, dict):
                for v in value.values():
                    extract_from_value(v)
            elif isinstance(value, list):
                for item in value:
                    extract_from_value(item)

        extract_from_value(template)
        return list(variables)
