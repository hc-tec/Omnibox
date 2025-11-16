from __future__ import annotations

"""compare_data 工具实现：对比分析多个数据源。"""

import json
import logging
from typing import Any, Dict, List

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool

logger = logging.getLogger(__name__)


def _load_source_data(
    source_refs: List[str],
    context: ToolExecutionContext
) -> tuple[bool, List[Dict[str, Any]], str]:
    """
    加载多个数据源。

    Args:
        source_refs: 数据引用 ID 列表
        context: 工具执行上下文

    Returns:
        (success, loaded_data, error_message) 元组
    """
    data_store = context.extras.get("data_store")
    if data_store is None:
        return False, [], "data_store 不可用"

    loaded_data = []
    for ref in source_refs:
        data = data_store.load(ref)
        if data is None:
            return False, [], f"无效的数据引用: {ref}"

        # 提取 items
        if isinstance(data, dict):
            items = data.get("items", [])
        elif isinstance(data, list):
            items = data
        else:
            return False, [], f"数据格式异常: {type(data)}"

        loaded_data.append({
            "ref": ref,
            "items": items,
            "count": len(items)
        })

    return True, loaded_data, ""


def _extract_simple_themes(items: List[Dict[str, Any]]) -> List[str]:
    """
    简单提取主题（基于关键字频率）。

    Args:
        items: 数据项列表

    Returns:
        主题列表
    """
    # 简化实现：提取标题中的高频词
    from collections import Counter

    words = []
    for item in items:
        title = item.get("title", "") or item.get("name", "")
        if isinstance(title, str):
            # 简单分词（按空格和标点）
            import re
            words.extend(re.findall(r'\w+', title.lower()))

    # 统计词频，取前 5 个
    word_counts = Counter(words)
    # 过滤掉常见停用词
    stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for"}
    filtered = [(word, count) for word, count in word_counts.most_common(20)
                if word not in stopwords and len(word) > 2]

    return [word for word, _ in filtered[:5]]


def _compare_diff(
    loaded_data: List[Dict[str, Any]],
    use_semantic: bool,
    llm_client
) -> Dict[str, Any]:
    """
    差异对比。

    Args:
        loaded_data: 加载的数据列表
        use_semantic: 是否使用语义对比
        llm_client: LLM 客户端（可选）

    Returns:
        对比结果
    """
    if use_semantic and llm_client:
        # 使用 LLM 进行语义对比
        return _compare_with_llm(loaded_data, "diff", llm_client)
    else:
        # 简单对比：提取每个数据源的主题
        all_themes = {}
        for data in loaded_data:
            themes = _extract_simple_themes(data["items"])
            all_themes[data["ref"]] = themes

        # 找出共同主题
        if len(all_themes) >= 2:
            theme_sets = [set(themes) for themes in all_themes.values()]
            common = set.intersection(*theme_sets)
            common_themes = list(common)
        else:
            common_themes = []

        # 找出独特主题
        unique_themes = {}
        for ref, themes in all_themes.items():
            unique = [t for t in themes if t not in common_themes]
            unique_themes[ref] = unique

        return {
            "comparison_type": "diff",
            "common_themes": common_themes,
            "unique_themes": unique_themes,
            "reasoning": "基于关键词频率的简单对比"
        }


def _compare_with_llm(
    loaded_data: List[Dict[str, Any]],
    comparison_type: str,
    llm_client
) -> Dict[str, Any]:
    """
    使用 LLM 进行语义对比。

    Args:
        loaded_data: 加载的数据列表
        comparison_type: 对比类型
        llm_client: LLM 客户端

    Returns:
        对比结果
    """
    # 构造 LLM Prompt
    data_summaries = []
    for i, data in enumerate(loaded_data, 1):
        items_preview = data["items"][:10]  # 只取前 10 条
        summary = f"数据源 {i} (ref: {data['ref']}, 共 {data['count']} 条):\n"
        for item in items_preview:
            title = item.get("title", "") or item.get("name", "未命名")
            summary += f"  - {title}\n"
        data_summaries.append(summary)

    prompt = f"""请对比分析以下 {len(loaded_data)} 个数据源，识别共同主题和独特观点。

对比类型: {comparison_type}

{chr(10).join(data_summaries)}

请以 JSON 格式返回结果：
{{
  "common_themes": ["主题1", "主题2"],
  "unique_themes": {{
    "数据源1 ref": ["独特观点1"],
    "数据源2 ref": ["独特观点2"]
  }},
  "gap_analysis": ["认知空白1", "认知空白2"],
  "reasoning": "分析推理过程"
}}
"""

    try:
        # 调用 LLM
        response = llm_client.generate(prompt, temperature=0.3)

        # 解析 JSON
        # 尝试提取 JSON 块
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析
            json_str = response

        result = json.loads(json_str)

        # 确保包含必需字段
        result["comparison_type"] = comparison_type
        if "common_themes" not in result:
            result["common_themes"] = []
        if "unique_themes" not in result:
            result["unique_themes"] = {}

        return result

    except json.JSONDecodeError as e:
        logger.error("compare_with_llm: LLM 返回非 JSON 格式 - %s", e)
        raise ValueError(f"LLM 返回格式错误，无法解析 JSON: {e}")
    except Exception as e:
        logger.exception("compare_with_llm: LLM 调用失败 - %s", e)
        raise


def register_data_compare_tool(registry: ToolRegistry) -> None:
    """向注册表注册 compare_data 工具。"""

    @tool(
        registry,
        plugin_id="compare_data",
        description="对比分析多个数据源，识别共同主题和认知空白",
        schema={
            "type": "object",
            "properties": {
                "source_refs": {
                    "type": "array",
                    "description": "数据引用 ID 列表（必填，2-5 个）",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 5,
                    "examples": [
                        ["lg-abc123", "lg-def456"]
                    ]
                },
                "comparison_type": {
                    "type": "string",
                    "description": "对比类型（必填）",
                    "enum": ["diff", "intersection", "gap_analysis", "trend", "structure"],
                    "default": "diff"
                },
                "use_semantic": {
                    "type": "boolean",
                    "description": "是否使用 LLM 进行语义对比（可选，默认 false）",
                    "default": False
                }
            },
            "required": ["source_refs", "comparison_type"]
        }
    )
    def compare_data(
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        """
        对比分析多个数据源。

        支持的对比类型：
        - diff: 差异对比（识别共同和独特主题）
        - intersection: 交集分析
        - gap_analysis: 缺口分析（找出认知空白）
        - trend: 趋势对比
        - structure: 结构对比
        """
        # 1. 参数验证
        source_refs = call.args.get("source_refs")
        if not source_refs:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_compare",
                    "error_code": "E101"
                },
                status="error",
                error_message="缺少必填参数 source_refs"
            )

        if not isinstance(source_refs, list) or len(source_refs) < 2:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_compare",
                    "error_code": "E102"
                },
                status="error",
                error_message="source_refs 必须是包含至少 2 个元素的数组"
            )

        if len(source_refs) > 5:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_compare",
                    "error_code": "E102"
                },
                status="error",
                error_message="source_refs 最多支持 5 个数据源对比"
            )

        comparison_type = call.args.get("comparison_type", "diff")
        use_semantic = call.args.get("use_semantic", False)

        logger.info(
            "compare_data: 对比 %d 个数据源, 类型=%s, 语义=%s",
            len(source_refs),
            comparison_type,
            use_semantic
        )

        try:
            # 2. 检查语义对比依赖
            if use_semantic:
                llm_client = context.extras.get("planner_llm")
                if llm_client is None:
                    return ToolExecutionPayload(
                        call=call,
                        raw_output={
                            "type": "data_compare",
                            "error_code": "E501"
                        },
                        status="error",
                        error_message="语义对比需要 LLM，但 planner_llm 不可用"
                    )
            else:
                llm_client = None

            # 3. 加载数据
            success, loaded_data, error_msg = _load_source_data(source_refs, context)
            if not success:
                return ToolExecutionPayload(
                    call=call,
                    raw_output={
                        "type": "data_compare",
                        "error_code": "E105" if "data_store" not in error_msg else "E501"
                    },
                    status="error",
                    error_message=error_msg
                )

            # 4. 执行对比

            if comparison_type == "diff":
                result = _compare_diff(loaded_data, use_semantic, llm_client)
            elif comparison_type == "gap_analysis":
                # Gap 分析需要使用 LLM
                if not llm_client:
                    return ToolExecutionPayload(
                        call=call,
                        raw_output={
                            "type": "data_compare",
                            "error_code": "E501"
                        },
                        status="error",
                        error_message="Gap 分析需要 LLM 支持，请设置 use_semantic=true"
                    )
                result = _compare_with_llm(loaded_data, "gap_analysis", llm_client)
            elif comparison_type in ["intersection", "trend", "structure"]:
                # 未实现的对比类型
                return ToolExecutionPayload(
                    call=call,
                    raw_output={
                        "type": "data_compare",
                        "error_code": "E103"
                    },
                    status="error",
                    error_message=f"对比类型 '{comparison_type}' 尚未实现，请使用 'diff' 或 'gap_analysis'"
                )
            else:
                # 无效的对比类型
                return ToolExecutionPayload(
                    call=call,
                    raw_output={
                        "type": "data_compare",
                        "error_code": "E102"
                    },
                    status="error",
                    error_message=f"无效的对比类型: {comparison_type}"
                )

            # 4. 返回结果
            result["type"] = "data_compare"
            result["sources_count"] = len(source_refs)

            logger.info(
                "compare_data: 完成对比, 共同主题=%d, 独特主题数=%d",
                len(result.get("common_themes", [])),
                len(result.get("unique_themes", {}))
            )

            return ToolExecutionPayload(
                call=call,
                raw_output=result,
                status="success"
            )

        except ValueError as e:
            # LLM 返回格式错误
            logger.error("compare_data: LLM 解析失败 - %s", e)
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_compare",
                    "error_code": "E502"
                },
                status="error",
                error_message=f"LLM 解析失败: {e}"
            )

        except TimeoutError as e:
            logger.error("compare_data: LLM 超时 - %s", e)
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_compare",
                    "error_code": "E501"
                },
                status="error",
                error_message=f"LLM 调用超时（超过 60 秒）: {e}"
            )

        except Exception as e:
            logger.exception("compare_data: 执行失败 - %s", e)
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "data_compare",
                    "error_code": "E505"
                },
                status="error",
                error_message=f"未预期的异常: {e}"
            )
