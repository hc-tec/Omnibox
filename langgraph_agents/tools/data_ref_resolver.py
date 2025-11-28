"""
数据引用解析器 - 统一的工具间数据引用机制。

V6.0 Phase 2: 提供统一的数据引用解析接口，支持多种引用格式：
1. data_id 字符串 (如 "lg-abc123")
2. step_id 整数引用 (如 1, 2, 3)
3. step_id 字符串格式 (如 "$step.1", "$step.2")
4. 带 JSONPath 的引用 (如 "$step.1.items", "$step.1.items[0].title")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from ..state import DataReference

logger = logging.getLogger(__name__)


@dataclass
class ResolvedData:
    """解析后的数据结构。"""
    data: Any  # 实际数据
    source_step_id: Optional[int]  # 来源步骤 ID
    source_data_id: Optional[str]  # 来源 data_id
    source_type: str  # 引用类型: "data_id" | "step_id" | "json_path"


class DataRefResolver:
    """
    统一的数据引用解析器。

    使用方式:
        resolver = DataRefResolver(data_stash, data_store)
        result = resolver.resolve("$step.1")
        result = resolver.resolve("lg-abc123")
        result = resolver.resolve(1)
    """

    # 步骤引用的正则模式
    STEP_REF_PATTERN = re.compile(r'^\$step\.(\d+)(?:\.(.+))?$')

    def __init__(
        self,
        data_stash: List[DataReference],
        data_store,
        working_memory: Optional[Dict[str, Any]] = None
    ):
        """
        初始化解析器。

        Args:
            data_stash: 当前的 data_stash 列表
            data_store: 外部数据存储
            working_memory: 可选的工作记忆（轻量工具结果）
        """
        self.data_stash = data_stash
        self.data_store = data_store
        self.working_memory = working_memory or {}

        # 构建 step_id -> DataReference 的索引
        self._step_index: Dict[int, DataReference] = {
            ref.step_id: ref for ref in data_stash
        }

    def resolve(
        self,
        ref: Union[str, int],
        require_success: bool = True
    ) -> ResolvedData:
        """
        解析数据引用。

        Args:
            ref: 数据引用，支持多种格式:
                - 字符串 data_id (如 "lg-abc123")
                - 整数 step_id (如 1)
                - 字符串 step 引用 (如 "$step.1")
                - 带 JSONPath 的引用 (如 "$step.1.items")
            require_success: 是否要求源数据状态为 success

        Returns:
            ResolvedData 对象

        Raises:
            ValueError: 无效的引用格式或引用不存在
        """
        if isinstance(ref, int):
            return self._resolve_step_id(ref, None, require_success)

        if not isinstance(ref, str):
            raise ValueError(f"不支持的引用类型: {type(ref)}")

        # 尝试解析 $step.N 格式
        match = self.STEP_REF_PATTERN.match(ref)
        if match:
            step_id = int(match.group(1))
            json_path = match.group(2)  # 可能为 None
            return self._resolve_step_id(step_id, json_path, require_success)

        # 尝试解析为纯数字（step_id）
        if ref.isdigit():
            return self._resolve_step_id(int(ref), None, require_success)

        # 否则视为 data_id
        return self._resolve_data_id(ref)

    def _resolve_step_id(
        self,
        step_id: int,
        json_path: Optional[str],
        require_success: bool
    ) -> ResolvedData:
        """解析 step_id 引用。"""
        data_ref = self._step_index.get(step_id)
        if not data_ref:
            available_steps = list(self._step_index.keys())
            raise ValueError(
                f"未找到 step_id={step_id} 的数据引用。"
                f"可用的步骤: {available_steps}"
            )

        if require_success and data_ref.status != "success":
            raise ValueError(
                f"step_id={step_id} 的执行状态为 '{data_ref.status}'，无法引用。"
                f"错误信息: {data_ref.error_message or '无'}"
            )

        if not data_ref.data_id:
            raise ValueError(
                f"step_id={step_id} 没有关联的 data_id（可能是 needs_user_input 状态）"
            )

        # 从 data_store 加载数据
        data = self.data_store.load(data_ref.data_id)
        if data is None:
            raise ValueError(f"data_store 中未找到 data_id={data_ref.data_id}")

        # 如果指定了 JSONPath，提取字段
        if json_path:
            data = self._extract_json_path(data, json_path)
            source_type = "json_path"
        else:
            source_type = "step_id"

        return ResolvedData(
            data=data,
            source_step_id=step_id,
            source_data_id=data_ref.data_id,
            source_type=source_type
        )

    def _resolve_data_id(self, data_id: str) -> ResolvedData:
        """解析 data_id 引用。"""
        data = self.data_store.load(data_id)
        if data is None:
            # 检查是否是有效的 data_id 格式
            if data_id.startswith("lg-"):
                raise ValueError(f"data_id '{data_id}' 不存在于 data_store 中")
            else:
                raise ValueError(
                    f"无效的数据引用格式: '{data_id}'。"
                    f"期望格式: data_id (如 'lg-abc123') 或 step 引用 (如 '$step.1')"
                )

        # 查找对应的 step_id（如果有）
        source_step_id = None
        for ref in self.data_stash:
            if ref.data_id == data_id:
                source_step_id = ref.step_id
                break

        return ResolvedData(
            data=data,
            source_step_id=source_step_id,
            source_data_id=data_id,
            source_type="data_id"
        )

    def _extract_json_path(self, data: Any, path: str) -> Any:
        """
        从数据中提取 JSONPath 指定的字段。

        支持的路径格式:
        - "field" -> data["field"]
        - "field.subfield" -> data["field"]["subfield"]
        - "items[0]" -> data["items"][0]
        - "items[0].title" -> data["items"][0]["title"]
        """
        if not path:
            return data

        current = data
        # 分割路径，支持点号和方括号
        parts = re.split(r'\.(?![^\[]*\])', path)

        for part in parts:
            if current is None:
                break

            # 检查是否有数组索引
            array_match = re.match(r'^(\w+)\[(\d+)\]$', part)
            if array_match:
                field_name = array_match.group(1)
                index = int(array_match.group(2))

                if isinstance(current, dict):
                    current = current.get(field_name)
                else:
                    current = getattr(current, field_name, None)

                if isinstance(current, list) and index < len(current):
                    current = current[index]
                else:
                    current = None
            else:
                # 普通字段访问
                if isinstance(current, dict):
                    current = current.get(part)
                elif isinstance(current, list) and part.isdigit():
                    idx = int(part)
                    current = current[idx] if idx < len(current) else None
                else:
                    current = getattr(current, part, None)

        return current

    def list_available_refs(self) -> List[Dict[str, Any]]:
        """
        列出所有可用的数据引用。

        返回格式:
        [
            {
                "step_id": 1,
                "data_id": "lg-abc123",
                "tool": "fetch_public_data",
                "status": "success",
                "summary": "获取30条数据..."
            },
            ...
        ]
        """
        refs = []
        for ref in self.data_stash:
            refs.append({
                "step_id": ref.step_id,
                "data_id": ref.data_id,
                "tool": ref.tool_name,
                "status": ref.status,
                "summary": ref.summary,
            })
        return refs

    def get_ref_by_tool(self, tool_name: str) -> Optional[DataReference]:
        """获取指定工具的最新数据引用。"""
        for ref in reversed(self.data_stash):
            if ref.tool_name == tool_name and ref.status == "success":
                return ref
        return None


def create_resolver_from_context(context) -> Optional[DataRefResolver]:
    """
    从工具执行上下文创建解析器的工厂函数。

    Args:
        context: ToolExecutionContext

    Returns:
        DataRefResolver 或 None（如果缺少必要组件）
    """
    data_store = context.extras.get("data_store")
    data_stash = context.extras.get("data_stash", [])
    working_memory = context.extras.get("working_memory", {})

    if data_store is None:
        return None

    return DataRefResolver(data_stash, data_store, working_memory)
