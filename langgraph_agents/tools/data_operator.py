from __future__ import annotations

"""通用数据算子：使用 LLM 生成并执行 Python transform 代码。"""

import json
import logging
import math
import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..json_utils import parse_json_payload
from ..llm_retry import retry_with_backoff
from ..prompt_loader import load_prompt
from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from ..utils.raw_schema_profiler import build_raw_schema, build_sample_records
from .registry import ToolRegistry, tool
from .data_ref_resolver import create_resolver_from_context
from .data_payload_utils import (
    unwrap_payload,
    extract_records,
    build_source_metadata,
)

logger = logging.getLogger(__name__)

SAFE_BUILTINS = {
    "len": len,
    "range": range,
    "min": min,
    "max": max,
    "sum": sum,
    "sorted": sorted,
    "any": any,
    "all": all,
    "abs": abs,
    "round": round,
    "enumerate": enumerate,
}


@dataclass
class SourceContext:
    records: List[Dict[str, Any]]
    payload: Any
    metadata: Dict[str, Any]
    source_data_id: Optional[str] = None
    source_step_id: Optional[int] = None


def register_data_operator_tool(registry: ToolRegistry) -> None:
    """
    注册 data_operator 工具。

    ResearchAgent 可通过该工具把“自然语言逻辑 + 数据样例”交给专门的 Coder，
    由 Coder 生成 Python transform 函数并在安全沙盒中执行。
    """

    @tool(
        registry,
        plugin_id="data_operator",
        description="根据自然语言指令与数据样例，生成并执行 Python transform 代码。",
        schema={
            "type": "object",
            "properties": {
                "source_ref": {
                    "type": ["string", "integer", "object", "array"],
                    "description": "数据引用（data_id/step引用），也可直接提供列表/字典",
                },
                "instruction": {
                    "type": "string",
                    "description": "需要完成的转换/筛选/聚合描述（自然语言）",
                },
                "max_samples": {
                    "type": "integer",
                    "description": "提供给 Coder 的样例数量（默认 5，范围 1-5）",
                    "minimum": 1,
                    "maximum": 5,
                },
            },
            "required": ["source_ref", "instruction"],
        },
    )
    def data_operator(call: ToolCall, context: ToolExecutionContext) -> ToolExecutionPayload:
        extras = context.extras or {}
        planner_llm = extras.get("planner_llm")
        data_store = extras.get("data_store")
        coder_prompt = extras.get("data_operator_prompt") or load_prompt("schema_coder_system.txt")

        if planner_llm is None:
            return ToolExecutionPayload(
                call=call,
                status="error",
                error_message="planner_llm 不可用，无法生成代码",
                raw_output={"type": "data_operator", "error": "planner_llm_unavailable"},
            )
        if data_store is None:
            return ToolExecutionPayload(
                call=call,
                status="error",
                error_message="data_store 不可用，无法读取数据",
                raw_output={"type": "data_operator", "error": "data_store_unavailable"},
            )

        instruction = call.args.get("instruction")
        if not instruction or not isinstance(instruction, str):
            return ToolExecutionPayload(
                call=call,
                status="error",
                error_message="instruction 必须是字符串",
                raw_output={"type": "data_operator", "error": "invalid_instruction"},
            )

        source_ref = call.args.get("source_ref")
        max_samples = call.args.get("max_samples") or 5
        try:
            max_samples = int(max_samples)
        except (TypeError, ValueError):
            max_samples = 5
        max_samples = max(1, min(max_samples, 5))

        source_context = _resolve_records(source_ref, context, data_store)
        if not source_context or not source_context.records:
            return ToolExecutionPayload(
                call=call,
                status="error",
                error_message="无法解析 source_ref 对应的数据记录",
                raw_output={"type": "data_operator", "error": "records_not_available"},
            )

        schema_context = _build_schema_context(source_context, extras, max_samples)
        prompt = _build_prompt(instruction, schema_context, coder_prompt)

        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def call_llm():
            return planner_llm.generate(prompt, temperature=0.1, role="schema_coder")

        try:
            response = call_llm()
            parsed = parse_json_payload(response)
        except Exception as exc:
            logger.exception("data_operator: LLM解析失败")
            return ToolExecutionPayload(
                call=call,
                status="error",
                error_message=f"无法解析生成的 JSON：{exc}",
                raw_output={"type": "data_operator", "error": "llm_parse_failed"},
            )

        code = parsed.get("code") or parsed.get("python")
        explanation = parsed.get("explanation")
        if not code or "def transform" not in code and "def process_data" not in code:
            logger.warning("data_operator: 生成的代码无效")
            return ToolExecutionPayload(
                call=call,
                status="error",
                error_message="生成的代码无效，缺少 transform 函数",
                raw_output={"type": "data_operator", "error": "invalid_code", "code": code},
            )

        try:
            result = _execute_transform(code, source_context.records)
        except Exception as exc:
            logger.exception("data_operator: 代码执行失败")
            return ToolExecutionPayload(
                call=call,
                status="error",
                error_message=f"生成的代码执行失败: {exc}",
                raw_output={
                    "type": "data_operator",
                    "error": "execution_failed",
                    "code": code,
                    "exception": str(exc),
                },
            )

        normalized_result = _normalize_transform_result(result, source_context, instruction, explanation)
        trimmed_result = _trim_result(normalized_result)
        raw_output = {
            "type": "data_operator",
            "instruction": instruction,
            "code": code,
            "explanation": explanation,
            "sample_size": schema_context.get("sample_count"),
            "result": trimmed_result,
        }
        for key in ("items", "metadata", "summary", "feed_title", "generated_path", "source", "cache_hit", "reasoning"):
            if isinstance(trimmed_result, dict) and key in trimmed_result:
                raw_output[key] = trimmed_result[key]
        if isinstance(trimmed_result, dict) and trimmed_result.get("type"):
            raw_output["result_type"] = trimmed_result.get("type")
        return ToolExecutionPayload(
            call=call,
            status="success",
            raw_output=raw_output,
        )


def _resolve_records(source_ref: Any, context: ToolExecutionContext, data_store) -> Optional[SourceContext]:
    resolver = create_resolver_from_context(context)

    if isinstance(source_ref, list):
        payload = {"items": source_ref}
        metadata = build_source_metadata(payload, None, None)
        return SourceContext(
            records=extract_records(payload),
            payload=payload,
            metadata=metadata,
        )

    if isinstance(source_ref, dict):
        metadata = build_source_metadata(source_ref, None, None)
        return SourceContext(
            records=extract_records(source_ref),
            payload=source_ref,
            metadata=metadata,
        )

    if resolver:
        try:
            resolved = resolver.resolve(source_ref, require_success=False)
            payload, payload_ref = unwrap_payload(resolved.data, data_store)
            metadata = build_source_metadata(payload, resolved.source_data_id, resolved.source_step_id, payload_ref)
            return SourceContext(
                records=extract_records(payload),
                payload=payload,
                metadata=metadata,
                source_data_id=resolved.source_data_id,
                source_step_id=resolved.source_step_id,
            )
        except ValueError as exc:
            logger.warning("data_operator: 数据引用解析失败: %s", exc)
            return None

    if isinstance(source_ref, str):
        data = data_store.load(source_ref)
        payload, payload_ref = unwrap_payload(data, data_store)
        metadata = build_source_metadata(payload, source_ref, None, payload_ref)
        return SourceContext(
            records=extract_records(payload),
            payload=payload,
            metadata=metadata,
            source_data_id=source_ref,
        )

    return None


def _build_schema_context(
    source_context: SourceContext,
    extras: Dict[str, Any],
    max_samples: int,
) -> Dict[str, Any]:
    schema = {}
    samples: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = dict(source_context.metadata or {})

    registry = extras.get("schema_registry")
    if registry and source_context.source_data_id:
        record = registry.get(source_context.source_data_id)
        if record:
            schema = record.raw_schema or {}
            samples = record.samples[:max_samples] if record.samples else []
            registry_metadata = record.metadata or {}
            metadata.update({k: v for k, v in registry_metadata.items() if v is not None})

    if not schema:
        schema = build_raw_schema(source_context.payload or source_context.records)
    if not samples:
        samples = build_sample_records(source_context.payload or source_context.records, max_samples=max_samples)

    sample_count = metadata.get("sample_count", len(samples))
    metadata["sample_count"] = sample_count

    return {
        "schema": schema,
        "samples": samples,
        "metadata": metadata,
        "sample_count": sample_count,
    }


def _build_prompt(
    instruction: str,
    schema_context: Dict[str, Any],
    base_prompt: str,
) -> str:
    samples = schema_context.get("samples") or []
    raw_schema = schema_context.get("schema") or {}
    sample_count = schema_context.get("sample_count", len(samples))
    schema_json = json.dumps(raw_schema, ensure_ascii=False, indent=2)
    samples_json = json.dumps(samples, ensure_ascii=False, indent=2)
    sample_note = (
        f"（共 {sample_count} 条样本，字段可能包含 __truncated__/__preview__ 标记）"
    )
    metadata = schema_context.get("metadata") or {}
    source_notes: List[str] = []
    if metadata.get("generated_path"):
        source_notes.append(f"- 数据路由: {metadata['generated_path']}")
    if metadata.get("feed_title"):
        source_notes.append(f"- 数据标题: {metadata['feed_title']}")
    if metadata.get("datasource"):
        source_notes.append(f"- 数据来源: {metadata['datasource']}")
    if metadata.get("item_count"):
        source_notes.append(f"- 总记录数: {metadata['item_count']}")
    source_section = ""
    if source_notes:
        source_section = "## 数据上下文\n" + "\n".join(source_notes) + "\n\n"

    return (
        f"{base_prompt}\n\n"
        f"{source_section}"
        f"## 转换指令\n{instruction}\n\n"
        f"## 数据 Schema (原始 RSS 推断)\n{schema_json}\n\n"
        f"## 数据样例 {sample_note}\n{samples_json}\n\n"
        "注意：\n"
        "- 样本仅用于理解结构，真实执行将在完整 records 上进行。\n"
        "- 如果样本字段被 __truncated__/__omitted__ 标记，请在代码中直接访问记录原字段。\n"
        "- transform(records) 必须返回 dict，如 {\"items\": [...], \"metadata\": {...}}。\n"
        "- 禁止打印、网络请求或文件操作。\n"
    )


def _execute_transform(code: str, records: List[Dict[str, Any]]) -> Any:
    sandbox_globals: Dict[str, Any] = {
        "__builtins__": SAFE_BUILTINS,
        "json": json,
        "math": math,
        "statistics": statistics,
    }
    exec_namespace: Dict[str, Any] = {}
    compiled = compile(code, "<data_operator>", "exec")
    exec(compiled, sandbox_globals, exec_namespace)
    transform = exec_namespace.get("transform") or exec_namespace.get("process_data")
    if not callable(transform):
        raise ValueError("生成的代码缺少 transform(records) 函数")

    safe_records = json.loads(json.dumps(records, ensure_ascii=False))
    result = transform(safe_records)
    return result


def _normalize_transform_result(
    result: Any,
    source_context: SourceContext,
    instruction: str,
    explanation: Optional[str],
) -> Dict[str, Any]:
    """
    将用户生成的结果标准化为 DataQueryResult 兼容结构，确保后续适配器可复用。
    """
    normalized: Dict[str, Any]
    if isinstance(result, dict):
        normalized = dict(result)
    else:
        normalized = {"items": result}

    raw_items = normalized.get("items")
    if isinstance(raw_items, list):
        items = raw_items
    elif raw_items is None:
        items = []
    else:
        items = [raw_items]
    normalized["items"] = items

    metadata = dict(normalized.get("metadata") or {})
    metadata.setdefault("instruction", instruction)
    if explanation:
        metadata.setdefault("transformation_reason", explanation)
    source_meta = source_context.metadata or {}
    metadata.setdefault("source_data_id", source_meta.get("source_data_id"))
    metadata.setdefault("source_route", source_meta.get("generated_path"))
    metadata.setdefault("source_datasource", source_meta.get("datasource"))
    metadata.setdefault("source_feed_title", source_meta.get("feed_title"))
    metadata.setdefault("item_count", len(items))
    normalized["metadata"] = metadata

    generated_path = normalized.get("generated_path") or source_meta.get("generated_path")
    if generated_path:
        normalized["generated_path"] = generated_path
        normalized.setdefault("route", generated_path)

    feed_title = normalized.get("feed_title") or source_meta.get("feed_title")
    if instruction:
        feed_title = f"{feed_title} · {instruction}" if feed_title else f"数据算子结果：{instruction}"
    normalized["feed_title"] = feed_title
    if feed_title:
        normalized.setdefault("title", feed_title)

    normalized["source"] = normalized.get("source") or source_meta.get("datasource") or "data_operator"
    normalized["cache_hit"] = False
    normalized["reasoning"] = explanation or instruction
    normalized["type"] = normalized.get("type") or "data_operator_result"
    return normalized


def _trim_result(result: Any) -> Any:
    if isinstance(result, dict):
        trimmed = dict(result)
        items = trimmed.get("items")
        if isinstance(items, list) and len(items) > 200:
            trimmed["items"] = items[:200]
            trimmed["truncated"] = True
        return trimmed
    if isinstance(result, list) and len(result) > 200:
        return result[:200]
    return result
