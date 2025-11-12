"""
研究服务
职责：封装 LangGraph Agents，提供复杂多轮研究能力。
"""

import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from langgraph_agents import (
    LangGraphRuntime,
    create_langgraph_app,
    InMemoryResearchDataStore,
)
from langgraph_agents.tools import ToolRegistry
from langgraph_agents.config import LangGraphConfig

logger = logging.getLogger(__name__)


@dataclass
class ResearchStep:
    """单个研究步骤记录"""

    step_id: int
    node_name: str  # router / planner / tool_executor / reflector / synthesizer
    action: str  # 步骤描述
    status: str  # success / error / in_progress
    timestamp: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class ResearchResult:
    """研究结果"""

    success: bool
    final_report: str
    data_stash: List[Dict[str, Any]] = field(default_factory=list)
    execution_steps: List[ResearchStep] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class ResearchService:
    """
    研究服务（封装 LangGraph Agents）。

    职责：
    1. 初始化 LangGraph 运行时和工具
    2. 执行复杂多轮研究任务
    3. 返回结构化研究结果
    """

    def __init__(
        self,
        router_llm,
        planner_llm,
        reflector_llm,
        synthesizer_llm,
        data_query_service,
        config: Optional[LangGraphConfig] = None,
    ):
        """
        初始化研究服务。

        Args:
            router_llm: 路由 LLM 客户端
            planner_llm: 规划 LLM 客户端
            reflector_llm: 反思 LLM 客户端
            synthesizer_llm: 综合 LLM 客户端
            data_query_service: 数据查询服务（用于工具调用）
            config: LangGraph 配置（可选）
        """
        self.data_query_service = data_query_service
        self.config = config or LangGraphConfig.default()

        # 初始化数据存储
        self.data_store = InMemoryResearchDataStore(
            max_items=self.config.data_store.max_items,
            ttl_seconds=self.config.data_store.ttl_seconds,
        )

        # 初始化工具注册表
        self.tool_registry = self._init_tools()

        # 初始化 LangGraph 运行时
        self.runtime = LangGraphRuntime(
            router_llm=router_llm,
            planner_llm=planner_llm,
            reflector_llm=reflector_llm,
            synthesizer_llm=synthesizer_llm,
            tool_registry=self.tool_registry,
            data_store=self.data_store,
        )

        # 创建 LangGraph 应用
        self.app = create_langgraph_app(self.runtime)

        logger.info("ResearchService 初始化完成")

    def _init_tools(self) -> ToolRegistry:
        """
        初始化工具注册表。

        注册默认工具：
        - query_data: 查询数据源
        - search_notes: 搜索笔记（如果启用）
        """
        registry = ToolRegistry()

        # 工具 1: 查询数据
        @registry.register_tool(
            plugin_id="query_data",
            description="查询数据源获取信息。可以查询 RSS、新闻、论坛、社交媒体等各类数据源。",
            schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "查询内容，用自然语言描述需要什么数据",
                    },
                    "datasource": {
                        "type": "string",
                        "description": "指定数据源（可选），如 'github'、'bilibili'、'zhihu' 等",
                    },
                },
                "required": ["query"],
            },
        )
        def query_data_tool(query: str, datasource: Optional[str] = None):
            """查询数据工具"""
            try:
                result = self.data_query_service.query(
                    user_query=query,
                    filter_datasource=datasource,
                    use_cache=True,
                )

                if result.status == "success":
                    # 限制返回数据量，避免状态膨胀
                    items = result.feed_items[:20] if result.feed_items else []
                    return {
                        "status": "success",
                        "feed_title": result.feed_title,
                        "source": result.source,
                        "item_count": len(items),
                        "items": [
                            {
                                "title": item.title,
                                "link": item.link,
                                "description": item.description[:200]
                                if item.description
                                else None,  # 截断描述
                                "pubDate": item.pubDate,
                                "author": item.author,
                            }
                            for item in items
                        ],
                    }
                else:
                    return {
                        "status": result.status,
                        "error": result.clarification_question or "查询失败",
                    }

            except Exception as exc:
                logger.error(f"query_data 工具执行失败: {exc}", exc_info=True)
                return {"status": "error", "error": str(exc)}

        logger.info(f"已注册 {len(registry.list_tools())} 个工具")
        return registry

    def research(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        max_steps: int = 20,
    ) -> ResearchResult:
        """
        执行复杂研究任务。

        Args:
            user_query: 用户的研究问题
            filter_datasource: 过滤特定数据源（可选）
            callback: 实时回调函数，用于流式推送进度（可选）
            max_steps: 最大步骤数，防止无限循环

        Returns:
            ResearchResult 对象
        """
        logger.info(f"开始研究任务: {user_query}")

        try:
            # 准备初始状态
            initial_state = {
                "original_query": user_query,
                "chat_history": [],
            }

            # 准备配置（使用线程 ID 管理状态）
            thread_id = f"research-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            config = {"configurable": {"thread_id": thread_id}}

            # 执行步骤记录
            execution_steps: List[ResearchStep] = []
            step_counter = 0

            # 流式执行 LangGraph 工作流
            for event in self.app.stream(initial_state, config):
                step_counter += 1

                # 防止无限循环
                if step_counter > max_steps:
                    logger.warning(f"达到最大步骤数 {max_steps}，终止研究")
                    break

                # 解析事件
                step = self._parse_event(event, step_counter)
                if step:
                    execution_steps.append(step)
                    logger.debug(
                        f"步骤 {step.step_id}: {step.node_name} - {step.action}"
                    )

                # 实时回调
                if callback:
                    try:
                        callback(
                            {
                                "type": "step",
                                "step": step.step_id if step else step_counter,
                                "node": step.node_name if step else "unknown",
                                "action": step.action if step else "processing",
                                "event": event,
                            }
                        )
                    except Exception as cb_exc:
                        logger.warning(f"回调函数执行失败: {cb_exc}")

            # 获取最终状态
            final_state = self.app.get_state(config).values

            # 提取最终报告
            final_report = final_state.get("final_report") or "研究未完成"

            # 格式化数据引用
            data_stash = self._format_data_stash(final_state.get("data_stash", []))

            # 构建结果
            result = ResearchResult(
                success=True,
                final_report=final_report,
                data_stash=data_stash,
                execution_steps=execution_steps,
                metadata={
                    "query": user_query,
                    "total_steps": len(execution_steps),
                    "datasource_filter": filter_datasource,
                    "thread_id": thread_id,
                    "storage_stats": self.data_store.stats(),
                },
            )

            logger.info(
                f"研究任务完成，共执行 {len(execution_steps)} 个步骤，报告长度 {len(final_report)} 字符"
            )
            return result

        except Exception as exc:
            logger.error(f"研究任务失败: {exc}", exc_info=True)
            return ResearchResult(
                success=False,
                final_report="",
                data_stash=[],
                execution_steps=[],
                metadata={"query": user_query},
                error=str(exc),
            )

    def _parse_event(
        self, event: Dict[str, Any], step_id: int
    ) -> Optional[ResearchStep]:
        """
        解析 LangGraph 事件为研究步骤。

        LangGraph 事件格式：
        {
            "node_name": {"key": value, ...}
        }
        """
        if not event:
            return None

        # 提取节点名称和数据
        for node_name, node_data in event.items():
            if not isinstance(node_data, dict):
                continue

            # 根据节点类型解析动作
            action = self._describe_action(node_name, node_data)

            return ResearchStep(
                step_id=step_id,
                node_name=node_name,
                action=action,
                status="success",
                timestamp=datetime.now().isoformat(),
                details={"data": node_data},
            )

        return None

    def _describe_action(self, node_name: str, node_data: Dict[str, Any]) -> str:
        """根据节点名称和数据描述动作"""
        if node_name == "router":
            decision = node_data.get("router_decision", {})
            route = decision.get("route", "unknown") if isinstance(decision, dict) else "unknown"
            return f"路由决策: {route}"

        elif node_name == "simple_chat":
            return "简单对话响应"

        elif node_name == "planner":
            tool_call = node_data.get("next_tool_call")
            if tool_call:
                plugin_id = tool_call.get("plugin_id", "unknown")
                return f"规划下一步: 调用工具 {plugin_id}"
            return "规划下一步"

        elif node_name == "tool_executor":
            return "执行工具调用"

        elif node_name == "data_stasher":
            return "数据暂存和摘要"

        elif node_name == "reflector":
            reflection = node_data.get("reflection", {})
            decision = reflection.get("decision", "unknown") if isinstance(reflection, dict) else "unknown"
            return f"反思决策: {decision}"

        elif node_name == "synthesizer":
            return "生成最终报告"

        elif node_name == "wait_for_human":
            return "等待人工介入"

        else:
            return f"执行节点: {node_name}"

    def _format_data_stash(
        self, data_stash: List[Any]
    ) -> List[Dict[str, Any]]:
        """格式化数据引用列表"""
        formatted = []
        for ref in data_stash:
            # 检查是否是 DataReference 对象
            if hasattr(ref, "data_id"):
                formatted.append(
                    {
                        "step_id": ref.step_id,
                        "tool_name": ref.tool_name,
                        "data_id": ref.data_id,
                        "summary": ref.summary[:200],  # 截断摘要
                        "status": ref.status,
                    }
                )
            elif isinstance(ref, dict):
                formatted.append(ref)

        return formatted

    def close(self):
        """清理资源"""
        if self.data_query_service:
            if hasattr(self.data_query_service, "close"):
                self.data_query_service.close()
        logger.info("ResearchService 已关闭")
