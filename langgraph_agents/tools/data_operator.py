from __future__ import annotations

"""通用数据算子：使用 LLM 生成并执行 Python transform 代码。"""

import json
import logging
import math
import statistics
from typing import Any, Dict, List, Optional

from ..json_utils import parse_json_payload
from ..llm_retry import retry_with_backoff
from ..prompt_loader import load_prompt
from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool
from .data_ref_resolver import create_resolver_from_context

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
                    "description": "提供给 Coder 的样例数量（默认 20，范围 1-100）",
                    "minimum": 1,
                    "maximum": 100,
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
        max_samples = call.args.get("max_samples") or 20
        try:
            max_samples = int(max_samples)
        except (TypeError, ValueError):
            max_samples = 20
        max_samples = max(1, min(max_samples, 100))

        records = _resolve_records(source_ref, context, data_store)
        if not records:
            return ToolExecutionPayload(
                call=call,
                status="error",
                error_message="无法解析 source_ref 对应的数据记录",
                raw_output={"type": "data_operator", "error": "records_not_available"},
            )

        sample = records[:max_samples]
        schema_hint = _infer_schema(sample)

        prompt = _build_prompt(instruction, sample, schema_hint, coder_prompt)

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
            result = _execute_transform(code, records)
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

        trimmed_result = _trim_result(result)
        raw_output = {
            "type": "data_operator",
            "instruction": instruction,
            "code": code,
            "explanation": explanation,
            "sample_size": len(sample),
            "result": trimmed_result,
        }
        return ToolExecutionPayload(
            call=call,
            status="success",
            raw_output=raw_output,
        )


def _resolve_records(source_ref: Any, context: ToolExecutionContext, data_store) -> List[Dict[str, Any]]:
    resolver = create_resolver_from_context(context)
    if isinstance(source_ref, (list, dict)):
        return _extract_records(source_ref)

    if resolver:
        try:
            resolved = resolver.resolve(source_ref, require_success=False)
            return _extract_records(resolved.data)
        except ValueError as exc:
            logger.warning("data_operator: 数据引用解析失败: %s", exc)
            return []

    if isinstance(source_ref, str):
        data = data_store.load(source_ref)
        return _extract_records(data)

    return []


def _extract_records(payload: Any) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "records", "data", "results"):
            items = payload.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
    return []


def _infer_schema(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    schema: Dict[str, Any] = {}
    for record in records:
        for key, value in record.items():
            field = schema.setdefault(key, {"types": set(), "examples": []})
            field["types"].add(type(value).__name__)
            if len(field["examples"]) < 3 and value not in field["examples"]:
                field["examples"].append(value)
    readable: Dict[str, Any] = {}
    for key, value in schema.items():
        readable[key] = {
            "types": sorted(value["types"]),
            "examples": value["examples"],
        }
    return readable


def _build_prompt(
    instruction: str,
    samples: List[Dict[str, Any]],
    schema_hint: Dict[str, Any],
    base_prompt: str,
) -> str:
    samples_json = json.dumps(samples, ensure_ascii=False, indent=2)
    schema_json = json.dumps(schema_hint, ensure_ascii=False, indent=2)
    return (
        f"{base_prompt}\n\n"
        f"## 转换指令\n{instruction}\n\n"
        f"## 数据 Schema 提示\n{schema_json}\n\n"
        f"## 数据样例\n{samples_json}\n"
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

