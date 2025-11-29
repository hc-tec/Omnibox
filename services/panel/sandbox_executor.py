"""
Restricted sandbox executor for data transformations.

当前实现仅支持少量 builtin 转换，用于演示数据绑定→ViewModel 的流程。
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Sequence
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


DEFAULT_BUILTINS: Dict[str, BuiltinFunc] = {
    "head": _builtin_head,
    "select_fields": _builtin_select_fields,
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
