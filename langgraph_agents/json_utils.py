from __future__ import annotations

"""LangGraph Agent JSON 解析辅助函数。"""

import json
import re
from typing import Any, Dict


def parse_json_payload(text: str) -> Dict[str, Any]:
    """
    将 LLM 输出解析为 JSON。
    使用多种策略尝试提取有效的 JSON 对象。

    策略：
    1. 直接解析整个字符串
    2. 去除前后的 markdown 代码块标记
    3. 使用平衡括号匹配提取第一个完整 JSON
    4. 使用正则匹配第一个 JSON 对象

    Args:
        text: LLM 输出的文本

    Returns:
        解析后的 JSON 字典

    Raises:
        json.JSONDecodeError: 所有策略都失败时
    """
    text = text.strip()

    # 策略1: 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 策略2: 去除 markdown 代码块标记
    if text.startswith("```"):
        # 去除 ```json 或 ```
        lines = text.split("\n")
        if len(lines) > 2:
            # 去除第一行和最后一行的 ```
            inner_text = "\n".join(lines[1:-1])
            try:
                return json.loads(inner_text.strip())
            except json.JSONDecodeError:
                pass

    # 策略3: 使用平衡括号匹配提取第一个完整 JSON
    json_obj = _extract_first_json_balanced(text)
    if json_obj:
        try:
            return json.loads(json_obj)
        except json.JSONDecodeError:
            pass

    # 策略4: 回退到简单正则（兼容旧版本）
    match = re.search(r"\{[^{}]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 所有策略都失败
    raise json.JSONDecodeError(
        f"无法从文本中提取有效 JSON。文本前100字符: {text[:100]}...",
        text,
        0,
    )


def _extract_first_json_balanced(text: str) -> str:
    """
    使用括号平衡算法提取第一个完整的 JSON 对象。

    这个方法比简单正则更可靠，可以正确处理嵌套对象。

    Args:
        text: 输入文本

    Returns:
        提取的 JSON 字符串，如果没找到返回空字符串
    """
    # 找到第一个 {
    start = text.find("{")
    if start == -1:
        return ""

    # 使用栈来匹配括号
    stack = []
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]

        # 处理转义字符
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        # 处理字符串边界
        if char == '"':
            in_string = not in_string
            continue

        # 只在字符串外部处理括号
        if not in_string:
            if char == "{":
                stack.append(char)
            elif char == "}":
                if stack:
                    stack.pop()
                    # 找到匹配的结束括号
                    if not stack:
                        return text[start : i + 1]

    # 未找到匹配的结束括号
    return ""

