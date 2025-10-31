"""
字段语义分析器：根据原始RSS记录推断字段类型与语义标签。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
import re


@dataclass
class FieldProfile:
    path: str
    data_type: str
    sample: List[Any] = field(default_factory=list)
    semantic: List[str] = field(default_factory=list)
    nullable: bool = False


@dataclass(order=True)
class FieldRule:
    priority: int
    name: str = field(compare=False)
    matcher: Callable[[str, FieldProfile], bool] = field(compare=False)


class FieldProfiler:
    """
    字段语义分析器，支持注册自定义匹配规则。
    """

    _rules: List[FieldRule] = []

    def __init__(self, max_samples: int = 5):
        self.max_samples = max_samples

    @classmethod
    def register_rule(cls, name: str, matcher: Callable[[str, FieldProfile], bool], priority: int = 100) -> None:
        cls._rules.append(FieldRule(priority=priority, name=name, matcher=matcher))
        cls._rules.sort()

    @classmethod
    def clear_rules(cls) -> None:
        cls._rules.clear()

    @classmethod
    def unregister_rule(cls, name: str) -> None:
        cls._rules = [rule for rule in cls._rules if rule.name != name]

    @classmethod
    def reset_rules(cls) -> None:
        cls.clear_rules()
        _register_default_rules()

    def profile(self, records: Sequence[Dict[str, Any]]) -> Dict[str, FieldProfile]:
        flattened = self._collect_fields(records)
        for path, profile in flattened.items():
            for rule in self._rules:
                try:
                    if rule.matcher(path, profile):
                        profile.semantic.append(rule.name)
                except Exception:
                    continue
        return flattened

    def _collect_fields(self, records: Sequence[Dict[str, Any]]) -> Dict[str, FieldProfile]:
        profiles: Dict[str, FieldProfile] = {}
        for record in records:
            self._walk(record, profiles, prefix="")
            if len(profiles) >= 256:
                break
        return profiles

    def _walk(
        self,
        value: Any,
        profiles: Dict[str, FieldProfile],
        prefix: str,
    ) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                next_prefix = f"{prefix}.{key}" if prefix else key
                self._walk(child, profiles, next_prefix)
        elif isinstance(value, list):
            if prefix and prefix not in profiles:
                profiles[prefix] = FieldProfile(
                    path=prefix,
                    data_type="array",
                    sample=[],
                    semantic=[],
                    nullable=False,
                )
            if prefix:
                profile = profiles[prefix]
                if len(profile.sample) < self.max_samples:
                    profile.sample.append(value[: self.max_samples])
            child_prefix = f"{prefix}[]" if prefix else "[]"
            for child in value[: self.max_samples]:
                self._walk(child, profiles, child_prefix)
        else:
            if prefix not in profiles:
                profiles[prefix] = FieldProfile(
                    path=prefix,
                    data_type=self._infer_type(value),
                    sample=[],
                    semantic=[],
                    nullable=False,
                )
            profile = profiles[prefix]
            if value is None:
                profile.nullable = True
            elif len(profile.sample) < self.max_samples:
                profile.sample.append(value)
            profile.data_type = self._merge_type(profile.data_type, self._infer_type(value))

    @staticmethod
    def _infer_type(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, (datetime,)):
            return "datetime"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        if isinstance(value, str):
            return "string"
        return "unknown"

    @staticmethod
    def _merge_type(original: str, new_type: str) -> str:
        if original == new_type or new_type == "null":
            return original
        if original == "null":
            return new_type
        if {original, new_type} <= {"number", "null"}:
            return "number"
        if {original, new_type} <= {"string", "datetime", "null"}:
            return "string"
        return "mixed"


profiler = FieldProfiler()


def _rule_title(path: str, profile: FieldProfile) -> bool:
    return profile.data_type == "string" and bool(re.search(r"(title|name|subject)$", path, re.IGNORECASE))


def _rule_summary(path: str, profile: FieldProfile) -> bool:
    return profile.data_type == "string" and bool(re.search(r"(description|summary|content|abstract)$", path, re.IGNORECASE))


def _rule_url(path: str, profile: FieldProfile) -> bool:
    if profile.data_type != "string":
        return False
    return any(isinstance(sample, str) and sample.startswith(("http://", "https://")) for sample in profile.sample)


def _rule_datetime(path: str, profile: FieldProfile) -> bool:
    if profile.data_type != "string":
        return False
    for sample in profile.sample:
        if isinstance(sample, str):
            try:
                datetime.fromisoformat(sample.replace("Z", "+00:00"))
                return True
            except ValueError:
                continue
    return False


def _rule_image(path: str, profile: FieldProfile) -> bool:
    if profile.data_type != "string":
        return False
    return any(
        isinstance(sample, str) and re.search(r"\.(png|jpe?g|gif|svg|webp)$", sample, re.IGNORECASE)
        for sample in profile.sample
    )


def _rule_category(path: str, profile: FieldProfile) -> bool:
    return profile.data_type in {"array", "string"} and "category" in path.lower()


def _rule_author(path: str, profile: FieldProfile) -> bool:
    return profile.data_type == "string" and bool(re.search(r"(author|creator|uploader)$", path, re.IGNORECASE))


def _rule_identifier(path: str, profile: FieldProfile) -> bool:
    return bool(re.search(r"(id|guid|uuid)$", path, re.IGNORECASE))


def _register_default_rules() -> None:
    FieldProfiler.register_rule("title", _rule_title, priority=10)
    FieldProfiler.register_rule("summary", _rule_summary, priority=20)
    FieldProfiler.register_rule("url", _rule_url, priority=30)
    FieldProfiler.register_rule("datetime", _rule_datetime, priority=40)
    FieldProfiler.register_rule("image", _rule_image, priority=50)
    FieldProfiler.register_rule("category", _rule_category, priority=60)
    FieldProfiler.register_rule("author", _rule_author, priority=70)
    FieldProfiler.register_rule("identifier", _rule_identifier, priority=80)


_register_default_rules()

__all__ = ["FieldProfiler", "FieldRule", "FieldProfile", "profiler"]
