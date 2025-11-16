"""
ExecutionEngine - 多步执行计划调度器（V5.0 Phase 4）。

负责执行 ExecutionPlan，处理依赖解析和任务调度。
"""

import json
import logging
from typing import List, Optional

from .state import ExecutionPlan, ToolCall, GraphState, DataReference, StashReference
from .runtime import ToolExecutionContext
from .tools.registry import ToolRegistry
from .storage import ResearchDataStore
from query_processor.llm_client import LLMClient

logger = logging.getLogger(__name__)


def _ensure_serializable(payload) -> str:
    """确保数据可序列化（复用自 DataStasher）。"""
    try:
        return json.dumps(payload, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(payload), ensure_ascii=False)


def _default_summary(payload, max_chars: int) -> str:
    """生成兜底摘要（复用自 DataStasher）。"""
    text = _ensure_serializable(payload)
    return (text[: max_chars - 3] + "...") if len(text) > max_chars else text


class ExecutionEngine:
    """
    执行引擎，负责调度 ExecutionPlan 中的步骤。

    Phase 4 简化实现：
    - 串行执行（按依赖顺序）
    - 基础依赖解析（StashReference）
    - 错误处理和回滚
    - 集成 DataStasher 逻辑，每步执行后立即保存数据
    """

    def __init__(
        self,
        registry: ToolRegistry,
        data_store: ResearchDataStore,
        summarizer_llm: Optional[LLMClient] = None,
        cheap_summary_max_chars: int = 320
    ):
        """
        初始化执行引擎。

        Args:
            registry: 工具注册表
            data_store: 数据存储
            summarizer_llm: 可选的摘要生成 LLM
            cheap_summary_max_chars: 摘要最大字符数
        """
        self.registry = registry
        self.data_store = data_store
        self.summarizer_llm = summarizer_llm
        self.cheap_summary_max_chars = cheap_summary_max_chars

    def execute_plan(
        self,
        plan: ExecutionPlan,
        state: GraphState,
        context: ToolExecutionContext
    ) -> GraphState:
        """
        执行完整的执行计划。

        Args:
            plan: 执行计划
            state: 当前 GraphState
            context: 工具执行上下文

        Returns:
            更新后的 GraphState
        """
        logger.info(
            f"ExecutionEngine: 开始执行计划，共 {len(plan.steps)} 个步骤"
        )

        # 初始化 completed_step_ids
        completed_step_ids = state.get("completed_step_ids", [])

        # 循环执行，直到所有步骤完成
        max_iterations = len(plan.steps) * 2  # 防止死循环
        iteration = 0

        while not plan.is_complete(completed_step_ids) and iteration < max_iterations:
            iteration += 1

            # 获取就绪的步骤
            ready_steps = plan.get_ready_steps(completed_step_ids)

            if not ready_steps:
                logger.error(
                    f"ExecutionEngine: 无就绪步骤，可能存在循环依赖。"
                    f"已完成: {completed_step_ids}，总步骤: {[s.step_id for s in plan.steps]}"
                )
                state["last_error"] = "执行计划存在循环依赖或无法继续"
                break

            # Phase 4 简化：串行执行第一个就绪步骤
            # 未来 Phase 5 可实现并行执行
            step = ready_steps[0]

            logger.info(
                f"ExecutionEngine: 执行步骤 {step.step_id} - {step.description}"
            )

            # 解析依赖参数
            resolved_call = self._resolve_dependencies(step, state, context)

            # 执行工具
            try:
                result = self.registry.execute(resolved_call, context)

                # 更新 state
                state["last_tool_result"] = result
                state["pending_tool_result"] = result

                # 保存数据到 data_store 并更新 data_stash
                data_ref = self._save_to_stash(result, state)
                data_stash: List[DataReference] = list(state.get("data_stash", []))
                data_stash.append(data_ref)
                state["data_stash"] = data_stash

                # 标记为已完成
                completed_step_ids.append(step.step_id)
                state["completed_step_ids"] = completed_step_ids

                logger.info(
                    f"ExecutionEngine: 步骤 {step.step_id} 执行完成，"
                    f"状态: {result.status}"
                )

                # 如果执行失败，记录错误但继续（部分失败容忍）
                if result.status == "error":
                    logger.warning(
                        f"ExecutionEngine: 步骤 {step.step_id} 执行失败: "
                        f"{result.error_message}"
                    )
                    state["last_error"] = result.error_message

            except Exception as e:
                logger.error(
                    f"ExecutionEngine: 步骤 {step.step_id} 执行异常: {e}",
                    exc_info=True
                )
                state["last_error"] = str(e)
                # 记录为已完成（避免死循环），但标记失败
                completed_step_ids.append(step.step_id)
                state["completed_step_ids"] = completed_step_ids

        # 检查是否全部完成
        if plan.is_complete(completed_step_ids):
            logger.info(
                f"ExecutionEngine: 计划执行完成，共完成 {len(completed_step_ids)} 个步骤"
            )
        else:
            logger.warning(
                f"ExecutionEngine: 计划未完全执行，"
                f"完成 {len(completed_step_ids)}/{len(plan.steps)} 个步骤"
            )

        return state

    def _save_to_stash(
        self,
        result: "ToolExecutionPayload",
        state: GraphState
    ) -> DataReference:
        """
        保存工具执行结果到 data_store 并创建 DataReference。

        复用 DataStasher 的逻辑，确保多步执行中的数据正确保存。

        Args:
            result: 工具执行结果
            state: 当前状态

        Returns:
            DataReference 元数据
        """
        raw_output = result.raw_output

        # needs_user_input 状态不存储到 data_store
        if result.status == "needs_user_input":
            data_id = None
            summary = f"等待用户澄清: {raw_output.get('question', '未知问题')}"
            logger.info(
                "ExecutionEngine: 跳过存储 needs_user_input 状态 (step=%s)",
                result.call.step_id
            )
        else:
            # 正常数据：保存到 data_store
            data_id = self.data_store.save(raw_output)
            summary = self._generate_summary(raw_output, state)
            logger.info(
                "ExecutionEngine: 保存数据 step=%s tool=%s data_id=%s",
                result.call.step_id,
                result.call.plugin_id,
                data_id,
            )

        data_ref = DataReference(
            step_id=result.call.step_id,
            tool_name=result.call.plugin_id,
            data_id=data_id,
            summary=summary,
            status=result.status,
            error_message=result.error_message,
        )

        return data_ref

    def _generate_summary(self, raw_output: object, state: GraphState) -> str:
        """生成数据摘要（使用 LLM 或兜底方案）。"""
        if self.summarizer_llm is None:
            return _default_summary(raw_output, self.cheap_summary_max_chars)

        prompt = (
            f"原始查询: {state.get('original_query', '')}\n"
            f"数据:\n{_ensure_serializable(raw_output)}"
        )
        try:
            text = self.summarizer_llm.generate(prompt, temperature=0.2)
            text = text.strip()
            if not text:
                raise ValueError("empty summary")
            return text[: self.cheap_summary_max_chars]
        except Exception as exc:
            logger.warning("ExecutionEngine: 摘要生成失败，使用兜底摘要: %s", exc)
            return _default_summary(raw_output, self.cheap_summary_max_chars)

    def _resolve_value(
        self,
        value: any,
        state: GraphState,
        data_store: ResearchDataStore
    ) -> any:
        """
        递归解析值中的依赖引用（支持嵌套结构）。

        Args:
            value: 要解析的值（可能是 dict/list/其他）
            state: 当前状态
            data_store: 数据存储

        Returns:
            解析后的值
        """
        # 检测 $ref 引用格式
        if isinstance(value, dict) and "$ref" in value:
            ref_data = value["$ref"]
            try:
                stash_ref = StashReference(
                    step_id=ref_data["step_id"],
                    json_path=ref_data.get("json_path")
                )
                resolved_value = stash_ref.resolve(
                    state.get("data_stash", []),
                    data_store
                )
                logger.debug(
                    f"ExecutionEngine: 解析引用 -> "
                    f"step_id={stash_ref.step_id}, "
                    f"json_path={stash_ref.json_path}, "
                    f"value={resolved_value}"
                )
                return resolved_value
            except Exception as e:
                logger.error(
                    f"ExecutionEngine: 解析引用失败: {e}",
                    exc_info=True
                )
                # 解析失败，返回原始值
                return value

        # 递归处理 dict
        elif isinstance(value, dict):
            return {k: self._resolve_value(v, state, data_store) for k, v in value.items()}

        # 递归处理 list
        elif isinstance(value, list):
            return [self._resolve_value(item, state, data_store) for item in value]

        # 其他类型直接返回
        else:
            return value

    def _resolve_dependencies(
        self,
        call: ToolCall,
        state: GraphState,
        context: ToolExecutionContext
    ) -> ToolCall:
        """
        解析工具调用中的依赖引用（StashReference），支持嵌套结构。

        支持的引用格式：
        - 顶层引用: {"param": {"$ref": {"step_id": 1}}}
        - 嵌套引用: {"filter": {"field": {"$ref": {"step_id": 1, "json_path": "data.id"}}}}
        - 数组引用: {"source_refs": [{"$ref": {"step_id": 1}}, {"$ref": {"step_id": 2}}]}

        Args:
            call: 原始工具调用
            state: 当前状态
            context: 执行上下文

        Returns:
            解析后的工具调用
        """
        # 获取 data_store（优先从 context.extras，兜底使用 self.data_store）
        data_store = context.extras.get("data_store") or self.data_store
        if not data_store:
            logger.warning(
                "ExecutionEngine: data_store 不可用，跳过依赖解析"
            )
            return call

        # 递归解析所有参数
        resolved_args = self._resolve_value(call.args, state, data_store)

        # 如果参数发生变化，创建新的 ToolCall
        if resolved_args != call.args:
            logger.info(
                f"ExecutionEngine: 步骤 {call.step_id} 的依赖已解析"
            )
            return ToolCall(
                plugin_id=call.plugin_id,
                args=resolved_args,
                step_id=call.step_id,
                description=call.description
            )
        else:
            return call


def create_execution_engine_node(runtime):
    """
    创建 ExecutionEngine 节点（LangGraph 节点工厂）。

    Args:
        runtime: LangGraphRuntime 实例

    Returns:
        LangGraph 节点函数
    """
    engine = ExecutionEngine(
        registry=runtime.tool_registry,
        data_store=runtime.data_store,
        summarizer_llm=runtime.summarizer_llm,
        cheap_summary_max_chars=runtime.cheap_summary_max_chars
    )

    def node(state: GraphState) -> GraphState:
        """ExecutionEngine 节点函数。"""
        plan = state.get("execution_plan")

        if not plan:
            logger.warning("ExecutionEngine: 没有 execution_plan，跳过执行")
            return state

        # 创建执行上下文
        context = ToolExecutionContext(
            data_query_service=runtime.data_query_service,
            extras={
                "data_store": runtime.data_store,
                "planner_llm": runtime.planner_llm
            }
        )

        # 执行计划
        updated_state = engine.execute_plan(plan, state, context)

        return updated_state

    return node
