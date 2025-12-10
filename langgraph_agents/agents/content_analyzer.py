"""
ContentAnalyzer Agent - 内容分析 Agent

唯一可以访问 DataStore 原始数据的 Agent。
通过两阶段设计确保 token 安全：
1. 字段选择：AI 查看 schema，智能选择需要的字段
2. 内容分析：基于过滤后的数据执行分析
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Any, Tuple

from ..json_utils import parse_json_payload
from ..llm_retry import retry_with_backoff
from ..prompt_loader import load_prompt
from ..runtime import LangGraphRuntime
from ..tools.data_ref_resolver import DataRefResolver, ResolvedData
from ..utils.raw_schema_profiler import summarize_payload

logger = logging.getLogger(__name__)

# 安全限制常量
MAX_RECORDS = 10  # 最多分析的记录数（硬限制）
MAX_FIELDS = 8  # 最多选择的字段数
MAX_FIELD_LENGTH = 1000  # 单个字段值的最大字符数
MAX_TOTAL_TOKENS_ESTIMATE = 50000  # 总 token 预估上限


class ContentAnalyzer:
    """
    内容分析 Agent

    唯一可以访问 DataStore 原始数据的 Agent。
    """

    def __init__(self, runtime: LangGraphRuntime):
        self.runtime = runtime
        self.data_store = runtime.data_store
        self.schema_registry = runtime.schema_registry
        self.llm = runtime.planner_llm
        self.system_prompt = load_prompt("content_analyzer_system.txt")

    def analyze(
        self,
        source_ref: str,
        task: str,
        limit: Optional[int] = None,
        resolver: Optional[DataRefResolver] = None,
        resolved: Optional[ResolvedData] = None,
    ) -> Dict[str, Any]:
        """
        执行内容分析（两阶段）

        Args:
            source_ref: 数据引用，如 "$step.2" 或 "lg-xxx"
            task: 分析任务描述
            limit: 限制记录数，默认从 task 中推断
            resolver: 可选的数据引用解析器
            resolved: 已解析的数据引用结果（可选，避免重复解析）

        Returns:
            分析结果
        """
        logger.info(f"ContentAnalyzer 开始分析: source_ref={source_ref}, task={task[:50]}...")

        data_id, raw_data, _ = self._resolve_reference(source_ref, resolver, resolved)
        if not data_id:
            raise ValueError(f"无法解析 source_ref: {source_ref}")

        # 预取数据，避免重复加载
        if raw_data is None:
            raw_data = self.data_store.load(data_id)
        if not raw_data:
            raise ValueError(f"未找到数据: {data_id}")

        structured_data = self._coerce_structured_data(data_id, raw_data)

        records = self._extract_records(structured_data)
        if not records:
            raise ValueError(f"数据中没有记录: {data_id}")

        # 获取 schema 信息（若缺失则基于原始数据兜底生成）
        schema_info = self._get_schema_info(data_id, structured_data)

        # 阶段1：字段选择
        field_selection = self._select_fields(schema_info, task, limit, len(records))
        logger.info(
            f"ContentAnalyzer 字段选择: {field_selection['selected_fields']}, "
            f"limit={field_selection['limit']}"
        )

        # 阶段2：加载数据并分析
        effective_limit = max(1, min(field_selection["limit"], len(records)))
        analysis_result = self._execute_analysis(
            data_id=data_id,
            records=records[:effective_limit],
            selected_fields=field_selection["selected_fields"],
            limit=effective_limit,
            task=task
        )

        logger.info("ContentAnalyzer 分析完成")

        return {
            "type": "content_analysis",
            "task": task,
            "source_ref": source_ref,
            "data_id": data_id,
            "fields_used": field_selection["selected_fields"],
            "records_analyzed": effective_limit,
            "analysis": analysis_result,
        }

    def _resolve_reference(
        self,
        source_ref: str,
        resolver: Optional[DataRefResolver],
        resolved: Optional[ResolvedData],
    ) -> Tuple[Optional[str], Optional[Any], Optional[int]]:
        """
        解析数据引用，优先使用统一的 DataRefResolver。

        返回: (data_id, raw_data, source_step_id)
        """
        resolved_data: Optional[ResolvedData] = resolved

        if resolved_data is None and resolver is not None:
            try:
                resolved_data = resolver.resolve(source_ref, require_success=False)
            except ValueError as exc:
                raise ValueError(f"无法解析 source_ref: {source_ref}: {exc}") from exc

        if resolved_data is not None:
            data_id = resolved_data.source_data_id or (str(source_ref) if isinstance(source_ref, (str, int)) else None)
            return data_id, resolved_data.data, resolved_data.source_step_id

        if isinstance(source_ref, str) and source_ref.startswith("lg-"):
            return source_ref, None, None

        if isinstance(source_ref, (str, int)):
            return str(source_ref), None, None

        raise ValueError(f"不支持的 source_ref 类型: {type(source_ref)}")

    def _get_schema_info(self, data_id: str, raw_data: Any) -> Dict[str, Any]:
        """
        获取 schema 信息，如缺失则从原始数据生成兜底 schema。
        """
        schema_info = None

        if hasattr(self.schema_registry, "get_schema"):
            schema_info = self.schema_registry.get_schema(data_id)  # type: ignore[assignment]

        if not schema_info and hasattr(self.schema_registry, "get"):
            record = self.schema_registry.get(data_id)  # type: ignore[attr-defined]
            if record:
                if hasattr(record, "raw_schema"):
                    schema_info = {
                        "schema": getattr(record, "raw_schema", {}) or {},
                        "samples": getattr(record, "samples", []) or [],
                        "metadata": getattr(record, "metadata", {}) or {},
                    }
                elif isinstance(record, dict):
                    schema_info = {
                        "schema": record.get("schema", {}) or {},
                        "samples": record.get("samples", []) or [],
                        "metadata": record.get("metadata", {}) or {},
                    }

        if not schema_info:
            schema_info = summarize_payload(raw_data)

        if not isinstance(schema_info, dict):
            raise ValueError(f"schema 信息格式错误，期望 dict，实际为 {type(schema_info)} (data_id={data_id})")

        metadata = schema_info.get("metadata") or {}
        sample_count = schema_info.get("sample_count") or metadata.get("sample_count")
        if sample_count is None:
            sample_count = len(schema_info.get("samples") or [])
            metadata["sample_count"] = sample_count
        schema_info["metadata"] = metadata
        schema_info["sample_count"] = sample_count

        return schema_info

    def _resolve_data_id(self, source_ref: str) -> Optional[str]:
        """
        解析数据引用为 data_id

        支持：
        - "$step.2" - 从 data_stash 查找
        - "lg-xxx" - 直接使用
        """
        data_id, _, _ = self._resolve_reference(source_ref, None, None)
        return data_id

    def _select_fields(
        self,
        schema_info: Dict[str, Any],
        task: str,
        limit: Optional[int],
        record_count: int,
    ) -> Dict[str, Any]:
        """
        阶段1：字段选择

        让 AI 查看 schema，智能选择需要的字段
        """
        raw_schema = schema_info.get("schema", {})
        if isinstance(raw_schema, str):
            try:
                parsed_schema = json.loads(raw_schema)
                raw_schema = parsed_schema if isinstance(parsed_schema, dict) else {}
            except Exception:
                logger.warning("schema 字段为字符串且无法解析为 JSON，使用空 schema")
                raw_schema = {}
        if not isinstance(raw_schema, dict):
            logger.warning("schema 字段格式异常，期望 dict，实际为 %s，使用空 schema", type(raw_schema))
            raw_schema = {}
        metadata = schema_info.get("metadata", {}) or {}
        total_records = (
            metadata.get("total_records")
            or metadata.get("item_count")
            or metadata.get("sample_count")
            or record_count
            or 0
        )
        if total_records <= 0 and record_count:
            total_records = record_count

        # 构建 schema 描述
        schema_desc = self._format_schema(raw_schema)

        # 推断 limit
        if limit is None:
            limit = self._infer_limit_from_task(task, total_records)
        limit = max(1, min(limit, MAX_RECORDS, record_count if record_count else MAX_RECORDS))  # 硬限制

        # 构建 prompt
        prompt = f"""{self.system_prompt}

## 当前任务

**分析任务**: {task}

**可用数据**:
- 总记录数: {total_records}
- 你将分析其中的前 {limit} 条记录

**数据 Schema**（字段列表）:
{schema_desc}

## 你的任务

请选择完成分析任务所需的字段。

输出 JSON 格式:
{{
  "selected_fields": ["field1", "field2", ...],
  "reasoning": "为什么选择这些字段...",
  "limit": {limit}
}}
"""

        # 调用 LLM
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def call_llm():
            return self.llm.generate(prompt, temperature=0.1, role="content_analyzer_field_selection")

        try:
            response = call_llm()
            data = parse_json_payload(response)

            # 验证和清洗
            selected_fields = data.get("selected_fields", [])
            if not selected_fields:
                # 降级：使用默认字段
                selected_fields = ["title", "description"]

            # 限制字段数量
            if len(selected_fields) > MAX_FIELDS:
                logger.warning(
                    f"选择的字段过多（{len(selected_fields)}），截断为 {MAX_FIELDS} 个"
                )
                selected_fields = selected_fields[:MAX_FIELDS]

            return {
                "selected_fields": selected_fields,
                "reasoning": data.get("reasoning", ""),
                "limit": min(data.get("limit", limit), MAX_RECORDS)
            }

        except Exception as exc:
            logger.error(f"字段选择失败: {exc}", exc_info=True)
            # 降级：返回默认字段
            return {
                "selected_fields": ["title", "description"],
                "reasoning": "字段选择失败，使用默认字段",
                "limit": min(limit, MAX_RECORDS)
            }

    def _execute_analysis(
        self,
        data_id: str,
        records: List[Dict[str, Any]],
        selected_fields: List[str],
        limit: int,
        task: str
    ) -> Dict[str, Any]:
        """
        阶段2：执行分析

        加载过滤后的数据，执行分析
        """
        if not records:
            raise ValueError(f"数据中没有记录: {data_id}")

        # 过滤字段并截断值
        filtered_records = self._filter_and_truncate(records[:limit], selected_fields)

        # Token 安全检查
        self._check_token_safety(filtered_records)

        # 构建分析 prompt
        data_json = json.dumps(filtered_records, ensure_ascii=False, indent=2)
        prompt = f"""{self.system_prompt}

## 阶段2：内容分析

**分析任务**: {task}

**数据**（共 {len(filtered_records)} 条记录，字段: {', '.join(selected_fields)}）:
```json
{data_json}
```

## 你的任务

基于上述数据，执行分析任务。

输出 JSON 格式:
{{
  "analysis_result": {{
    "items": [
      {{
        "index": 0,
        "title": "原始标题",
        ...  // 分析结果字段
      }}
    ],
    "summary": "整体分析总结"
  }}
}}
"""

        # 调用 LLM
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def call_llm():
            return self.llm.generate(prompt, temperature=0.2, role="content_analyzer_analysis")

        try:
            response = call_llm()
            data = parse_json_payload(response)
            return data.get("analysis_result", {})

        except Exception as exc:
            logger.error(f"内容分析失败: {exc}", exc_info=True)
            # 返回错误信息
            return {
                "items": [],
                "summary": f"分析失败: {str(exc)}",
                "error": str(exc)
            }

    def _format_schema(self, raw_schema: Dict[str, Any]) -> str:
        """格式化 schema 为易读文本"""
        lines = []
        for field, info in raw_schema.items():
            if not isinstance(info, dict):
                info = {"type": str(info)}
            field_type = info.get("type", "unknown")
            sample = info.get("sample", "")

            # 截断过长的 sample
            if isinstance(sample, str) and len(sample) > 100:
                sample = sample[:100] + "..."

            sample_str = f" (示例: {sample})" if sample else ""
            lines.append(f"- {field} ({field_type}){sample_str}")

        return "\n".join(lines) if lines else "暂无字段信息"

    def _infer_limit_from_task(self, task: str, total_records: int) -> int:
        """从任务描述中推断需要分析的记录数"""
        task_lower = task.lower()

        # 检查是否提到具体数字
        import re
        numbers = re.findall(r'前(\d+)|top\s*(\d+)|(\d+)\s*条', task_lower)
        if numbers:
            for groups in numbers:
                for num_str in groups:
                    if num_str:
                        return min(int(num_str), MAX_RECORDS)

        # 默认：全部数据（但不超过限制）
        return min(total_records, MAX_RECORDS)

    def _extract_records(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从原始数据中提取记录列表"""
        # 尝试不同的可能字段
        for key in ["items", "records", "data", "results"]:
            if key in raw_data and isinstance(raw_data[key], list):
                return self._normalize_records(raw_data[key])

        # 如果是列表，直接返回
        if isinstance(raw_data, list):
            return self._normalize_records(raw_data)

        # 如果是单条记录，包装为列表
        if isinstance(raw_data, dict):
            return [raw_data]

        return []

    def _normalize_records(self, records: List[Any]) -> List[Dict[str, Any]]:
        """
        规范化记录列表，确保元素为字典。

        对于非字典元素，转换为 {"text": str(value)}，避免后续字段访问报错。
        """
        normalized: List[Dict[str, Any]] = []
        for item in records:
            if isinstance(item, dict):
                normalized.append(item)
            else:
                normalized.append({"text": str(item)})
        return normalized

    def _coerce_structured_data(self, data_id: str, raw_data: Any) -> Any:
        """
        将数据强制转换为可解析的结构化格式，避免上游将列表/字典序列化为字符串时导致的属性错误。
        """
        if isinstance(raw_data, (dict, list)):
            return raw_data

        # 处理 bytes
        if isinstance(raw_data, (bytes, bytearray)):
            try:
                raw_data = raw_data.decode("utf-8")
            except Exception:
                raise ValueError(f"数据格式错误: data_id={data_id}，无法解码为 UTF-8 字符串")

        # 尝试解析字符串为 JSON
        if isinstance(raw_data, str):
            try:
                parsed = json.loads(raw_data)
                if isinstance(parsed, (dict, list)):
                    return parsed
                raise ValueError  # 进入统一错误提示
            except Exception:
                raise ValueError(
                    f"数据格式错误: data_id={data_id}，期望列表/字典，但收到字符串且无法解析为 JSON"
                )

        raise ValueError(
            f"数据格式错误: data_id={data_id}，期望列表/字典，实际类型 {type(raw_data)}"
        )

    def _filter_and_truncate(
        self,
        records: List[Dict[str, Any]],
        selected_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """过滤字段并截断值"""
        filtered = []

        for record in records:
            if not isinstance(record, dict):
                continue
            filtered_record = {}
            for field in selected_fields:
                if field in record:
                    value = record[field]

                    # 截断过长的字符串值
                    if isinstance(value, str) and len(value) > MAX_FIELD_LENGTH:
                        value = value[:MAX_FIELD_LENGTH] + "..."

                    filtered_record[field] = value

            filtered.append(filtered_record)

        return filtered

    def _check_token_safety(self, filtered_records: List[Dict[str, Any]]) -> None:
        """检查 token 安全性"""
        # 粗略估算 token 数
        data_json = json.dumps(filtered_records, ensure_ascii=False)
        estimated_tokens = len(data_json) * 1.5  # 粗略估算

        if estimated_tokens > MAX_TOTAL_TOKENS_ESTIMATE:
            raise ValueError(
                f"数据量过大，预估 {int(estimated_tokens)} tokens，"
                f"超过限制 {MAX_TOTAL_TOKENS_ESTIMATE}"
            )

        logger.info(f"Token 安全检查通过，预估 {int(estimated_tokens)} tokens")


def create_content_analyzer(runtime: LangGraphRuntime) -> ContentAnalyzer:
    """创建 ContentAnalyzer 实例"""
    return ContentAnalyzer(runtime)
