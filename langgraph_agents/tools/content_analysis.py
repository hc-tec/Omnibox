"""
内容分析工具 - 唯一可访问原始数据的工具
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..state import ToolCall, ToolExecutionPayload
from ..runtime import ToolExecutionContext
from ..agents.content_analyzer import create_content_analyzer
from ..schema_registry import SchemaRegistry
from .registry import ToolRegistry, tool
from .data_ref_resolver import create_resolver_from_context

logger = logging.getLogger(__name__)


def register_content_analysis_tool(registry: ToolRegistry) -> None:
    """注册内容分析工具"""

    @tool(
        registry,
        plugin_id="analyze_content",
        description="对数据进行深度内容分析（如主题提取、情感分析、要点总结等）。这是唯一可以访问原始数据的工具，用于需要查看具体内容的分析任务。",
        schema={
            "type": "object",
            "properties": {
                "source_ref": {
                    "type": "string",
                    "description": "数据引用，如 '$step.2' 或 data_id"
                },
                "task": {
                    "type": "string",
                    "description": "分析任务描述，如 '分析前三个热搜的主题和情感'"
                },
                "limit": {
                    "type": "integer",
                    "description": "限制分析的记录数（可选，默认从 task 中推断），最大值为 10",
                    "minimum": 1,
                    "maximum": 10
                }
            },
            "required": ["source_ref", "task"]
        },
        execution_mode="full"
    )
    def analyze_content_impl(
        call: ToolCall,
        ctx: ToolExecutionContext
    ) -> ToolExecutionPayload:
        """
        内容分析工具实现

        这个工具会：
        1. 启动 ContentAnalyzer Agent
        2. Agent 查看 schema，AI 智能选择字段
        3. 加载选定字段的数据
        4. 执行分析
        5. 返回分析结果
        """
        args = call.args
        source_ref = args.get("source_ref")
        task = args.get("task")
        limit = args.get("limit")

        if not source_ref or not task:
            return ToolExecutionPayload(
                call=call,
                status="error",
                error_message="缺少必需参数: source_ref 和 task",
                raw_output={}
            )

        try:
            # 从 context 获取所需组件
            data_store = ctx.extras.get("data_store")
            planner_llm = ctx.extras.get("planner_llm")
            schema_registry = (
                ctx.extras.get("schema_registry")
                or getattr(data_store, "schema_registry", None)
                or SchemaRegistry()
            )

            if not data_store or not planner_llm:
                return ToolExecutionPayload(
                    call=call,
                    status="error",
                    error_message="缺少必需的运行时组件: data_store 或 planner_llm",
                    raw_output={}
                )

            resolver = create_resolver_from_context(ctx)
            resolved = None
            if resolver:
                try:
                    resolved = resolver.resolve(source_ref, require_success=False)
                except ValueError as exc:
                    error_text = str(exc)
                    logger.warning("analyze_content 数据引用解析失败: %s", error_text)
                    return ToolExecutionPayload(
                        call=call,
                        status="error",
                        error_message=error_text,
                        raw_output={"error": error_text},
                    )

            # 构造临时 runtime（只包含需要的组件）
            temp_runtime = type('obj', (object,), {
                'data_store': data_store,
                'schema_registry': schema_registry,
                'planner_llm': planner_llm
            })()

            # 创建 ContentAnalyzer
            analyzer = create_content_analyzer(temp_runtime)

            # 执行分析
            result = analyzer.analyze(
                source_ref=source_ref,
                task=task,
                limit=limit,
                resolver=resolver,
                resolved=resolved,
            )

            logger.info(
                f"analyze_content 执行成功: "
                f"分析了 {result['records_analyzed']} 条记录，"
                f"使用字段 {result['fields_used']}"
            )

            return ToolExecutionPayload(
                call=call,
                status="success",
                raw_output=result
            )

        except ValueError as e:
            # 参数错误或数据问题
            logger.warning(f"analyze_content 参数错误: {e}")
            return ToolExecutionPayload(
                call=call,
                status="error",
                error_message=str(e),
                raw_output={"error": str(e)}
            )

        except Exception as e:
            # 其他错误
            logger.error(f"analyze_content 执行失败: {e}", exc_info=True)
            return ToolExecutionPayload(
                call=call,
                status="error",
                error_message=f"分析失败: {str(e)}",
                raw_output={"error": str(e)}
            )
