from __future__ import annotations

"""extract_insights 工具实现：使用 LLM 从数据中提取洞察、趋势、模式。

V5.0 Phase 3 (P1) 工具。
"""

import json
import logging
import time
from typing import Any, Dict, List, Literal

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from .registry import ToolRegistry, tool
from ..json_utils import parse_json_payload

logger = logging.getLogger(__name__)


# 分析类型对应的 Prompt 模板
ANALYSIS_PROMPTS = {
    "summary": """分析以下数据并生成摘要：

数据：
{data}

请提取关键信息并生成结构化摘要。返回 JSON 格式：
{{
  "insights": [
    {{
      "type": "summary",
      "title": "摘要标题",
      "description": "摘要内容",
      "evidence": ["支撑证据"],
      "confidence": 0.9,
      "actionable": false
    }}
  ],
  "overall_summary": "整体总结",
  "next_actions": ["建议的下一步行动"]
}}""",

    "trend": """分析以下数据中的趋势：

数据：
{data}

请识别时间序列趋势、增长模式或衰减趋势。返回 JSON 格式：
{{
  "insights": [
    {{
      "type": "trend",
      "title": "趋势标题",
      "description": "趋势描述",
      "evidence": ["数据点"],
      "confidence": 0.85,
      "actionable": true
    }}
  ],
  "overall_summary": "趋势总结",
  "next_actions": ["建议行动"]
}}""",

    "pattern": """分析以下数据中的模式：

数据：
{data}

请识别重复模式、共同特征或结构性规律。返回 JSON 格式：
{{
  "insights": [
    {{
      "type": "pattern",
      "title": "模式标题",
      "description": "模式描述",
      "evidence": ["示例"],
      "confidence": 0.8,
      "actionable": true
    }}
  ],
  "overall_summary": "模式总结",
  "next_actions": ["建议行动"]
}}""",

    "anomaly": """分析以下数据中的异常：

数据：
{data}

请识别异常值、认知空白或被忽视的领域。返回 JSON 格式：
{{
  "insights": [
    {{
      "type": "anomaly",
      "title": "异常标题",
      "description": "异常描述",
      "evidence": ["具体证据"],
      "confidence": 0.7,
      "actionable": true
    }}
  ],
  "overall_summary": "异常总结",
  "next_actions": ["建议行动"]
}}""",

    "narrative_structure": """分析以下视频/文章的叙事结构：

数据：
{data}

请识别叙事模式、结构特点和内容组织方式。返回 JSON 格式：
{{
  "insights": [
    {{
      "type": "pattern",
      "title": "叙事结构",
      "description": "结构描述",
      "evidence": ["示例"],
      "confidence": 0.85,
      "actionable": true
    }}
  ],
  "overall_summary": "叙事结构总结",
  "next_actions": ["可借鉴的结构模式"]
}}""",

    "viewpoint_extraction": """提取以下数据中的核心观点：

数据：
{data}

请提取高频观点、独特见解和论证方式。返回 JSON 格式：
{{
  "insights": [
    {{
      "type": "viewpoint",
      "title": "观点标题",
      "description": "观点描述",
      "evidence": ["引用"],
      "confidence": 0.8,
      "actionable": true
    }}
  ],
  "overall_summary": "观点总结",
  "next_actions": ["可执行的观点应用"]
}}"""
}


def register_insights_extractor_tool(registry: ToolRegistry) -> None:
    """向注册表注册 extract_insights 工具。"""

    @tool(
        registry,
        plugin_id="extract_insights",
        description="使用 LLM 从数据中提取洞察、趋势、模式",
        execution_mode="full",  # 需要数据持久化和质量检查
        schema={
            "type": "object",
            "properties": {
                "source_ref": {
                    "type": "string",
                    "description": "数据源引用（必填）",
                    "minLength": 1
                },
                "analysis_type": {
                    "type": "string",
                    "description": "分析类型（必填）",
                    "enum": ["summary", "trend", "pattern", "anomaly", "narrative_structure", "viewpoint_extraction"]
                },
                "focus_areas": {
                    "type": "array",
                    "description": "关注领域（可选）",
                    "items": {"type": "string"},
                    "maxItems": 5
                },
                "output_format": {
                    "type": "string",
                    "description": "输出格式（可选）",
                    "enum": ["structured", "natural_language"],
                    "default": "structured"
                }
            },
            "required": ["source_ref", "analysis_type"]
        }
    )
    def extract_insights(
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        """
        使用 LLM 从数据中提取洞察。

        支持功能：
        - 6 种分析类型：summary, trend, pattern, anomaly, narrative_structure, viewpoint_extraction
        - 结构化洞察输出
        - 建议的下一步行动

        容量限制：
        - 最大输入数据量: 500 条（自动采样）
        - 单条记录最大 token: 2000 tokens
        - 超时: 60 秒
        """
        start_time = time.time()

        # 1. 参数验证
        source_ref = call.args.get("source_ref")
        if not source_ref:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "insights",
                    "error_code": "E101"
                },
                status="error",
                error_message="缺少必填参数 source_ref"
            )

        analysis_type = call.args.get("analysis_type")
        if not analysis_type:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "insights",
                    "error_code": "E101"
                },
                status="error",
                error_message="缺少必填参数 analysis_type"
            )

        # 2. 从 data_store 加载数据
        data_store = context.extras.get("data_store")
        if not data_store:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "insights",
                    "error_code": "E303"
                },
                status="error",
                error_message="data_store 不可用"
            )

        try:
            data_package = data_store.load(source_ref)
        except Exception as e:
            logger.error(f"extract_insights: 加载数据失败 - {e}")
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "insights",
                    "error_code": "E301"
                },
                status="error",
                error_message=f"数据源 {source_ref} 不存在或无法加载"
            )

        if not data_package:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "insights",
                    "error_code": "E301"
                },
                status="error",
                error_message=f"数据源 {source_ref} 为空"
            )

        # 提取数据项（支持多种数据结构）
        items = _extract_items_from_package(data_package)
        if not items:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "insights",
                    "insights": [],
                    "overall_summary": "数据源为空，无法提取洞察",
                    "next_actions": []
                },
                status="success"
            )

        # 3. 采样（最大 500 条）
        source_item_count = len(items)
        if len(items) > 500:
            logger.info(f"extract_insights: 数据量 {len(items)} 超过限制，采样到 500 条")
            # 均匀采样
            step = len(items) // 500
            items = items[::step][:500]

        # 4. 准备数据摘要（避免 token 超限）
        data_summary = _prepare_data_summary(items, analysis_type)

        # 5. 获取 LLM 客户端
        planner_llm = context.extras.get("planner_llm")
        if not planner_llm:
            logger.error("extract_insights: planner_llm 不可用")
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "insights",
                    "error_code": "E303"
                },
                status="error",
                error_message="LLM 服务不可用"
            )

        # 6. 构建 Prompt
        prompt_template = ANALYSIS_PROMPTS.get(analysis_type)
        if not prompt_template:
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "insights",
                    "error_code": "E102"
                },
                status="error",
                error_message=f"不支持的分析类型: {analysis_type}"
            )

        # 添加关注领域
        focus_areas = call.args.get("focus_areas", [])
        if focus_areas:
            focus_text = "\n关注领域：\n" + "\n".join([f"- {area}" for area in focus_areas])
            prompt = prompt_template.replace("{data}", f"{data_summary}\n{focus_text}")
        else:
            prompt = prompt_template.replace("{data}", data_summary)

        # 7. 调用 LLM
        try:
            logger.info(f"extract_insights: 调用 LLM 进行 {analysis_type} 分析")
            response = planner_llm.generate(prompt, temperature=0.2)

            if not response or not response.strip():
                raise ValueError("LLM 返回空响应")

            # 8. 解析 LLM 输出
            try:
                insights_data = parse_json_payload(response)
            except Exception as e:
                logger.error(f"extract_insights: LLM 输出解析失败 - {e}")
                # 降级：返回简单摘要
                insights_data = {
                    "insights": [{
                        "type": analysis_type,
                        "title": "数据分析",
                        "description": response[:500],  # 截断
                        "evidence": [],
                        "confidence": 0.5,
                        "actionable": False
                    }],
                    "overall_summary": response[:200],
                    "next_actions": []
                }

        except Exception as e:
            logger.error(f"extract_insights: LLM 调用失败 - {e}")
            return ToolExecutionPayload(
                call=call,
                raw_output={
                    "type": "insights",
                    "error_code": "E501"
                },
                status="error",
                error_message=f"LLM 调用失败: {str(e)}"
            )

        # 9. 添加元数据
        analysis_time_ms = int((time.time() - start_time) * 1000)
        insights_data["metadata"] = {
            "source_item_count": source_item_count,
            "sampled_count": len(items),
            "analysis_time_ms": analysis_time_ms,
            "model_used": getattr(planner_llm, "model_name", "unknown")
        }

        logger.info(
            f"extract_insights: 成功 - {len(items)} 条数据，"
            f"{len(insights_data.get('insights', []))} 个洞察，耗时 {analysis_time_ms}ms"
        )

        return ToolExecutionPayload(
            call=call,
            raw_output={
                "type": "insights",
                **insights_data
            },
            status="success"
        )


def _prepare_data_summary(items: List[Dict], analysis_type: str) -> str:
    """准备数据摘要（避免 token 超限）。"""
    # 根据分析类型选择重要字段
    important_fields = _get_important_fields(analysis_type)

    # 构建数据摘要
    summaries = []
    for i, item in enumerate(items[:100], 1):  # 最多展示 100 条的详细信息
        summary_parts = [f"{i}. "]

        # 提取重要字段
        for field in important_fields:
            if field in item:
                value = item[field]
                if isinstance(value, str):
                    # 截断长文本
                    value = value[:200]
                summary_parts.append(f"{field}: {value}")

        summaries.append(" | ".join(summary_parts))

    # 如果数据超过 100 条，添加统计信息
    if len(items) > 100:
        summaries.append(f"\n... 还有 {len(items) - 100} 条数据（已省略）")

    return "\n".join(summaries)


def _get_important_fields(analysis_type: str) -> List[str]:
    """根据分析类型返回重要字段。"""
    # 基础字段
    base_fields = ["title", "description", "content"]

    # 根据分析类型添加特定字段
    if analysis_type == "trend":
        return base_fields + ["published_at", "stats", "view_count", "like_count"]
    elif analysis_type == "pattern":
        return base_fields + ["category", "tags", "author"]
    elif analysis_type == "anomaly":
        return base_fields + ["stats", "view_count"]
    elif analysis_type == "narrative_structure":
        return base_fields + ["duration", "chapters", "structure"]
    elif analysis_type == "viewpoint_extraction":
        return base_fields + ["keywords", "summary", "tags"]
    else:
        return base_fields


def _extract_items_from_package(data_package: Any) -> List[Dict]:
    """
    从数据包中提取数据项列表。

    支持多种数据结构：
    - dict with "items" key: {"items": [...]}
    - dict with "data" key: {"data": [...]}
    - list: [...]
    - DataQueryResult: .datasets[0].items
    """
    # 1. 如果是字典
    if isinstance(data_package, dict):
        # 尝试 "items" 字段
        if "items" in data_package:
            items = data_package["items"]
            if isinstance(items, list):
                return items
        # 尝试 "data" 字段
        if "data" in data_package:
            data = data_package["data"]
            if isinstance(data, list):
                return data
        # 尝试 "results" 字段
        if "results" in data_package:
            results = data_package["results"]
            if isinstance(results, list):
                return results

    # 2. 如果是列表，直接返回
    if isinstance(data_package, list):
        return data_package

    # 3. 如果是 DataQueryResult 对象（有 datasets 属性）
    if hasattr(data_package, "datasets") and data_package.datasets:
        first_dataset = data_package.datasets[0]
        if hasattr(first_dataset, "items"):
            return first_dataset.items

    # 4. 无法提取，返回空列表
    logger.warning(
        f"无法从数据包中提取 items，类型：{type(data_package)}，"
        f"keys: {data_package.keys() if isinstance(data_package, dict) else 'N/A'}"
    )
    return []
