"""
研究服务
职责：封装 LangGraph Agents，提供复杂多轮研究能力。
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from langgraph_agents.runtime import LangGraphRuntime, ToolExecutionContext
from langgraph_agents.graph_builder import create_langgraph_app
from langgraph_agents.storage import InMemoryResearchDataStore
from langgraph_agents.tools.registry import ToolRegistry, tool
from langgraph_agents.tools.bootstrap import register_default_tools
from langgraph_agents.config import LangGraphConfig
from langgraph_agents.state import ToolCall, ToolExecutionPayload
from services.research_task_hub import ResearchTaskHub
from services.research_constants import (
    StepStatus,
    NodeName,
    StreamEventType,
    ErrorMessages,
    DefaultConfig,
    ResearchConfig,
)

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

        # 创建工具执行上下文（注入依赖）
        tool_context = ToolExecutionContext(
            data_query_service=data_query_service,
            note_backend=None,  # 暂不支持笔记搜索
        )

        # 初始化 LangGraph 运行时
        self.runtime = LangGraphRuntime(
            router_llm=router_llm,
            planner_llm=planner_llm,
            reflector_llm=reflector_llm,
            synthesizer_llm=synthesizer_llm,
            tool_registry=self.tool_registry,
            data_store=self.data_store,
            tool_context=tool_context,
        )

        # 创建 LangGraph 应用
        self.app = create_langgraph_app(self.runtime)
        self.task_hub = ResearchTaskHub()

        # 创建线程池用于处理任务恢复（避免手动创建 daemon 线程）
        self._executor = ThreadPoolExecutor(
            max_workers=DefaultConfig.THREAD_POOL_SIZE,
            thread_name_prefix="research-resume",
        )

        logger.info("ResearchService 初始化完成")

    # ===== 任务事件流 =====
    def register_stream(self, task_id: str):
        """为指定任务注册实时事件监听队列。"""
        return self.task_hub.register_listener(task_id)

    def unregister_stream(self, task_id: str, queue) -> None:
        self.task_hub.unregister_listener(task_id, queue)

    def submit_human_response(self, task_id: str, response: str) -> None:
        """
        记录人工回复并触发 LangGraph 继续执行。

        Args:
            task_id: 任务ID
            response: 用户的补充信息

        Raises:
            KeyError: 任务不存在时抛出
        """
        try:
            self.task_hub.submit_human_response(task_id, response)
        except KeyError:
            logger.warning("提交人工回复时未找到任务 %s", task_id)
            raise

        # 使用线程池异步恢复任务（避免手动创建线程）
        future = self._executor.submit(
            self._resume_task_after_human_input,
            task_id,
            response,
        )

        # 添加回调处理异常（不阻塞当前线程）
        def _handle_resume_result(fut):
            try:
                fut.result()  # 获取结果，如果有异常会抛出
            except Exception as exc:
                logger.error(
                    "任务 %s 恢复失败: %s",
                    task_id,
                    exc,
                    exc_info=True,
                )
                # 标记任务为错误状态
                self.task_hub.mark_error(task_id, f"任务恢复失败: {str(exc)}")

        future.add_done_callback(_handle_resume_result)

    def cancel_task(self, task_id: str, reason: str = "用户取消") -> None:
        """标记任务已取消。"""
        self.task_hub.cancel_task(task_id, reason)

    def has_task(self, task_id: str) -> bool:
        return self.task_hub.has_task(task_id)

    def _init_tools(self) -> ToolRegistry:
        """
        初始化工具注册表。

        使用 langgraph_agents 提供的默认工具：
        - fetch_public_data: 查询公共数据源（RSSHub）
        - search_private_notes: 搜索私人笔记（如果启用）
        """
        registry = ToolRegistry()

        # 注册默认工具（fetch_public_data 和 search_private_notes）
        register_default_tools(registry)

        logger.info(f"已注册 {len(registry.list_tools())} 个工具")
        return registry

    def research(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        max_steps: int = DefaultConfig.MAX_STEPS,
        task_id: Optional[str] = None,
        initial_state: Optional[Dict[str, Any]] = None,
        reuse_task: bool = False,
    ) -> ResearchResult:
        """
        执行复杂研究任务（向后兼容方法）。

        推荐使用 research_with_config() 方法传递配置对象。

        Args:
            user_query: 用户的研究问题
            filter_datasource: 过滤特定数据源（可选）
            callback: 实时回调函数（可选）
            max_steps: 最大步骤数
            task_id: 任务ID（可选，默认自动生成）
            initial_state: 初始状态（可选，用于续写任务）
            reuse_task: 是否复用任务（可选）

        Returns:
            ResearchResult 对象
        """
        config = ResearchConfig(
            user_query=user_query,
            filter_datasource=filter_datasource,
            callback=callback,
            max_steps=max_steps,
            task_id=task_id,
            initial_state=initial_state,
            reuse_task=reuse_task,
        )
        return self.research_with_config(config)

    def research_with_config(self, config: ResearchConfig) -> ResearchResult:
        """
        执行复杂研究任务（推荐使用此方法）。

        Args:
            config: 研究配置对象

        Returns:
            ResearchResult 对象

        Raises:
            ValueError: 配置参数无效时抛出
            RuntimeError: 任务被取消时抛出
        """
        task_identifier = config.task_id or f"task-{uuid4().hex}"
        logger.info("开始研究任务: %s (task=%s)", config.user_query, task_identifier)

        # 创建面板预览回调闭包（捕获 task_id）
        def emit_panel_preview(payload: Dict[str, Any]) -> None:
            """工具调用时使用的面板预览回调，闭包捕获当前 task_id"""
            event = {
                "type": StreamEventType.PANEL_PREVIEW,
                "task_id": task_identifier,
                "timestamp": datetime.utcnow().isoformat(),
                "data": payload,
            }
            self.task_hub.publish_event(task_identifier, event)

        # 注入到 tool_context，供 emit_panel_preview 工具使用
        self.runtime.tool_context.extras["emit_panel_preview"] = emit_panel_preview

        try:
            base_state = dict(config.initial_state) if config.initial_state else {}
            base_state.setdefault("original_query", config.user_query)
            base_state.setdefault("chat_history", [])

            thread_id = f"research-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            langgraph_config = {"configurable": {"thread_id": thread_id}}
            self.task_hub.ensure_task(task_identifier, thread_id, config.user_query, config.filter_datasource)
            if config.reuse_task:
                self.task_hub.mark_processing(task_identifier)

            execution_steps: List[ResearchStep] = []
            step_counter = 0

            for event in self.app.stream(base_state, langgraph_config):
                step_counter += 1

                if step_counter > config.max_steps:
                    logger.warning("达到最大步数 %s，停止研究", config.max_steps)
                    break

                step = self._parse_event(event, step_counter)
                if step:
                    execution_steps.append(step)
                    logger.debug("步骤 %s: %s - %s", step.step_id, step.node_name, step.action)
                    self._publish_stream_step(task_identifier, step)

                    if step.node_name == NodeName.WAIT_FOR_HUMAN:
                        request = self._extract_human_request(event, step.node_name)
                        if request:
                            self.task_hub.mark_human_request(task_identifier, request)
                            self._publish_human_request(task_identifier, request)

                if config.callback:
                    try:
                        config.callback(
                            {
                                "type": "step",
                                "step": step.step_id if step else step_counter,
                                "node": step.node_name if step else "unknown",
                                "action": step.action if step else "processing",
                                "event": event,
                            }
                        )
                    except Exception as cb_exc:
                        logger.warning("回调函数执行失败: %s", cb_exc)

                if self.task_hub.is_cancelled(task_identifier):
                    raise RuntimeError(ErrorMessages.TASK_CANCELLED)

            final_state = self.app.get_state(langgraph_config).values
            self.task_hub.set_last_state(task_identifier, final_state)

            final_report = final_state.get("final_report") or "研究未产出"
            data_stash = self._format_data_stash(final_state.get("data_stash", []))

            metadata = {
                "query": config.user_query,
                "total_steps": len(execution_steps),
                "datasource_filter": config.filter_datasource,
                "thread_id": thread_id,
                "task_id": task_identifier,
                "storage_stats": self.data_store.stats(),
            }

            result = ResearchResult(
                success=True,
                final_report=final_report,
                data_stash=data_stash,
                execution_steps=execution_steps,
                metadata=metadata,
            )

            self.task_hub.mark_completed(task_identifier, final_report, True, metadata)

            logger.info(
                "研究任务完成，共执行 %s 个步骤，报告长度 %s 字符",
                len(execution_steps),
                len(final_report),
            )
            return result

        except RuntimeError as exc:
            message = "研究任务已取消" if str(exc) == ErrorMessages.TASK_CANCELLED else str(exc)
            logger.warning(message)
            self.task_hub.mark_error(task_identifier, message)
            return ResearchResult(
                success=False,
                final_report="",
                data_stash=[],
                execution_steps=[],
                metadata={"query": config.user_query, "task_id": task_identifier},
                error=message,
            )

        except Exception as exc:
            logger.error("研究任务失败: %s", exc, exc_info=True)
            self.task_hub.mark_error(task_identifier, str(exc))
            return ResearchResult(
                success=False,
                final_report="",
                data_stash=[],
                execution_steps=[],
                metadata={"query": config.user_query, "task_id": task_identifier},
                error=str(exc),
            )

        finally:
            # 清理注入的回调，避免内存泄漏
            self.runtime.tool_context.extras.pop("emit_panel_preview", None)


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

        elif node_name == NodeName.WAIT_FOR_HUMAN:
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

    def _publish_stream_step(self, task_id: str, step: ResearchStep) -> None:
        event = {
            "type": StreamEventType.STEP,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "step_id": step.step_id,
                "node": step.node_name,
                "action": step.action,
                "status": step.status,
                "details": step.details or {},
            },
        }
        self.task_hub.publish_event(task_id, event)

    def _publish_human_request(self, task_id: str, message: str) -> None:
        event = {
            "type": StreamEventType.HUMAN_IN_LOOP,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {"message": message},
        }
        self.task_hub.publish_event(task_id, event)


    @staticmethod
    def _extract_human_request(event: Dict[str, Any], node_name: str) -> Optional[str]:
        node_data = event.get(node_name)
        if not isinstance(node_data, dict):
            return None
        return node_data.get("human_in_loop_request")

    def _resume_task_after_human_input(self, task_id: str, response: str) -> None:
        """
        恢复被人工介入暂停的研究任务。

        Args:
            task_id: 任务ID
            response: 用户的补充信息

        Raises:
            无（内部捕获异常，避免影响主流程）
        """
        context = self.task_hub.get_task(task_id)
        if not context:
            logger.warning("无法续写研究任务 %s：上下文不存在", task_id)
            self.task_hub.mark_error(task_id, ErrorMessages.CONTEXT_NOT_FOUND.format(task_id=task_id))
            return

        # 验证基础信息
        if not context.base_query:
            logger.error("任务 %s 缺少 base_query，无法续写", task_id)
            self.task_hub.mark_error(task_id, "任务缺少查询信息")
            return

        # 构建初始状态
        base_query = context.base_query
        base_state = dict(context.last_state or {})

        # 验证 last_state 的有效性
        if context.last_state and not isinstance(context.last_state, dict):
            logger.warning("任务 %s 的 last_state 类型无效，将使用默认状态", task_id)
            base_state = {}

        if not base_state:
            base_state = {
                "original_query": base_query,
                "chat_history": [],
            }

        # 验证必要的状态字段
        if "original_query" not in base_state:
            base_state["original_query"] = base_query
        if "chat_history" not in base_state or not isinstance(base_state.get("chat_history"), list):
            base_state["chat_history"] = []

        history = list(base_state.get("chat_history") or [])
        history.append(f"【用户补充】{response}")
        base_state["chat_history"] = history
        base_state.pop("human_in_loop_request", None)
        base_state.pop("final_report", None)

        try:
            # 使用配置对象续写任务
            config = ResearchConfig(
                user_query=base_query,
                filter_datasource=context.filter_datasource,
                max_steps=DefaultConfig.MAX_STEPS,
                task_id=task_id,
                initial_state=base_state,
                reuse_task=True,
            )
            logger.info("开始续写研究任务 %s，用户补充：%s", task_id, response[:50])
            self.research_with_config(config)
            logger.info("研究任务 %s 续写完成", task_id)

        except ValueError as exc:
            # 配置验证错误
            error_msg = f"配置验证失败: {str(exc)}"
            logger.error("续写研究任务 %s 失败: %s", task_id, error_msg)
            self.task_hub.mark_error(task_id, error_msg)

        except RuntimeError as exc:
            # 任务取消或运行时错误
            if str(exc) == ErrorMessages.TASK_CANCELLED:
                logger.info("研究任务 %s 已被取消", task_id)
            else:
                logger.error("续写研究任务 %s 运行时错误: %s", task_id, exc, exc_info=True)
                self.task_hub.mark_error(task_id, str(exc))

        except Exception as exc:  # pragma: no cover
            # 未预期的错误
            logger.error("续写研究任务 %s 失败: %s", task_id, exc, exc_info=True)
            self.task_hub.mark_error(task_id, f"未预期的错误: {str(exc)}")

    def close(self):
        """清理资源"""
        # 关闭线程池，等待正在执行的任务完成
        if hasattr(self, "_executor"):
            logger.info("正在关闭研究任务线程池...")
            self._executor.shutdown(wait=True, cancel_futures=False)
            logger.info("研究任务线程池已关闭")

        # 关闭数据查询服务
        if self.data_query_service:
            if hasattr(self.data_query_service, "close"):
                self.data_query_service.close()

        logger.info("ResearchService 已关闭")
