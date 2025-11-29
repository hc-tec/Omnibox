"""
Restricted sandbox executor for data transformations.

当前实现仅支持少量 builtin 转换，用于演示数据绑定→ViewModel 的流程。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Sequence
import ast

from services.panel.panel_spec import TransformationSpec


class SandboxExecutionError(RuntimeError):
    """Raised when transformation cannot be executed safely."""

    def __init__(self, message: str, *, detail: Dict | None = None):
        super().__init__(message)
        self.detail = detail or {}


BuiltinFunc = Callable[[Sequence[Dict], Dict], List[Dict]]


def _builtin_head(records: Sequence[Dict], params: Dict) -> List[Dict]:
    limit = int(params.get("limit", 5))
    return [dict(record) for record in records[: max(limit, 0)]]


def _builtin_select_fields(records: Sequence[Dict], params: Dict) -> List[Dict]:
    fields = params.get("fields") or []
    if not fields:
        return [dict(record) for record in records]
    selected = []
    for record in records:
        projection = {field: record.get(field) for field in fields}
        selected.append(projection)
    return selected


def _builtin_sort_by(records: Sequence[Dict], params: Dict) -> List[Dict]:
    field = params.get("field")
    if not field:
        raise SandboxExecutionError("sort_by requires 'field' parameter")
    order = str(params.get("order", "asc")).lower()
    reverse = order == "desc"
    try:
        sorted_records = sorted(records, key=lambda item: item.get(field), reverse=reverse)
    except TypeError as exc:  # pragma: no cover - rare mixed-type sort
        raise SandboxExecutionError("sort_by encountered non-comparable values") from exc
    return [dict(record) for record in sorted_records]


def _builtin_slice(records: Sequence[Dict], params: Dict) -> List[Dict]:
    start = int(params.get("start", 0))
    stop = params.get("stop")
    if stop is None:
        sliced = records[start:]
    else:
        sliced = records[start : int(stop)]
    return [dict(record) for record in sliced]


def _builtin_group_count(records: Sequence[Dict], params: Dict) -> List[Dict]:
    field = params.get("field")
    if not field:
        raise SandboxExecutionError("group_count requires 'field' parameter")
    limit = int(params.get("limit", 10))
    counts: Dict[Any, int] = {}
    for record in records:
        key = record.get(field)
        counts[key] = counts.get(key, 0) + 1
    pairs = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    top_pairs = pairs[: max(limit, 0)]
    return [{field: key, "count": value} for key, value in top_pairs]


def _builtin_rename_fields(records: Sequence[Dict], params: Dict) -> List[Dict]:
    mapping = params.get("mapping") or {}
    if not isinstance(mapping, dict) or not mapping:
        raise SandboxExecutionError("rename_fields requires 'mapping' dict parameter")
    renamed: List[Dict] = []
    for record in records:
        new_record = dict(record)
        for old_key, new_key in mapping.items():
            if old_key in new_record:
                value = new_record.pop(old_key)
                new_record[new_key] = value
        renamed.append(new_record)
    return renamed


def _to_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None
    return None


def _builtin_aggregate_numeric(records: Sequence[Dict], params: Dict) -> List[Dict]:
    field = params.get("field")
    if not field:
        raise SandboxExecutionError("aggregate_numeric requires 'field' parameter")
    values: List[float] = []
    for record in records:
        number = _to_number(record.get(field))
        if number is not None:
            values.append(number)
    if not values:
        return [
            {
                "field": field,
                "count": 0,
                "sum": 0.0,
                "avg": None,
                "min": None,
                "max": None,
            }
        ]
    total = sum(values)
    return [
        {
            "field": field,
            "count": len(values),
            "sum": total,
            "avg": total / len(values),
            "min": min(values),
            "max": max(values),
        }
    ]


def _builtin_coerce_number(records: Sequence[Dict], params: Dict) -> List[Dict]:
    field = params.get("field")
    if not field:
        raise SandboxExecutionError("coerce_number requires 'field' parameter")
    target_field = params.get("target_field", field)
    coerced: List[Dict] = []
    for record in records:
        updated = dict(record)
        number = _to_number(record.get(field))
        updated[target_field] = number
        coerced.append(updated)
    return coerced


DEFAULT_BUILTINS: Dict[str, BuiltinFunc] = {
    "head": _builtin_head,
    "select_fields": _builtin_select_fields,
    "sort_by": _builtin_sort_by,
    "slice": _builtin_slice,
    "group_count": _builtin_group_count,
    "rename_fields": _builtin_rename_fields,
    "aggregate_numeric": _builtin_aggregate_numeric,
    "coerce_number": _builtin_coerce_number,
}


class SandboxExecutor:
    """Minimal sandbox，用于在受控环境下执行 TransformationSpec。"""

    def __init__(self, builtins: Dict[str, BuiltinFunc] | None = None):
        self.builtins = builtins or DEFAULT_BUILTINS

    def execute(self, records: Sequence[Dict], spec: TransformationSpec | None) -> List[Dict]:
        if spec is None:
            return [dict(record) for record in records]

        if spec.type == "builtin":
            return self._run_builtin(records, spec)

        if spec.type == "code_ref":
            return self._run_code_ref(records, spec)

        if spec.type == "inline_python":
            return self._run_inline_python(records, spec)

        if spec.type == "pipeline":
            return self._run_pipeline(records, spec)

        raise SandboxExecutionError(
            f"Transformation type '{spec.type}' is not enabled",
            detail={"spec": spec.model_dump()},
        )

    def _run_builtin(self, records: Sequence[Dict], spec: TransformationSpec) -> List[Dict]:
        name = spec.code or spec.params.get("name")
        if not name:
            raise SandboxExecutionError("builtin transformation missing name")

        func = self.builtins.get(name)
        if not func:
            raise SandboxExecutionError(f"builtin transformation '{name}' not registered")

        return func(records, spec.params)

    def _run_code_ref(self, records: Sequence[Dict], spec: TransformationSpec) -> List[Dict]:
        name = spec.code
        if not name:
            raise SandboxExecutionError("code_ref missing name")
        if name not in self.builtins:
            raise SandboxExecutionError(f"code_ref '{name}' not registered")
        return self.builtins[name](records, spec.params)

    def _run_inline_python(self, records: Sequence[Dict], spec: TransformationSpec) -> List[Dict]:
        code = spec.code
        if not code:
            raise SandboxExecutionError("inline_python missing code")
        # 只允许简单表达式，并注入受限环境
        try:
            parsed = ast.parse(code, mode="eval")
        except SyntaxError as exc:
            raise SandboxExecutionError("inline python parse error", detail={"error": str(exc)})

        allowed_names = {"records": [dict(r) for r in records], "len": len}
        compiled = compile(parsed, "<sandbox>", "eval")
        try:
            result = eval(compiled, {"__builtins__": {}}, allowed_names)
        except Exception as exc:
            raise SandboxExecutionError("inline python runtime error", detail={"error": str(exc)})

        if not isinstance(result, list):
            raise SandboxExecutionError("inline python must return list[dict]")
        return [dict(item) for item in result]

    def _run_pipeline(self, records: Sequence[Dict], spec: TransformationSpec) -> List[Dict]:
        steps = spec.params.get("steps")
        if not isinstance(steps, list) or not steps:
            raise SandboxExecutionError("pipeline requires non-empty 'steps' list")
        current = [dict(record) for record in records]
        for index, step in enumerate(steps, start=1):
            step_type = step.get("type", "builtin")
            if step_type != "builtin":
                raise SandboxExecutionError(
                    "pipeline only supports builtin steps",
                    detail={"step": index, "type": step_type},
                )
            step_spec = TransformationSpec(
                type="builtin",
                code=step.get("code"),
                params=step.get("params") or {},
            )
            current = self._run_builtin(current, step_spec)
        return current
