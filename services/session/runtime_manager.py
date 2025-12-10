"""Session Runtime 管理器

核心组件，负责：
1. 管理 session_id → SessionState 的映射
2. 创建/恢复 LangGraphRuntime
3. 跨请求保持执行上下文
4. 记录执行步骤
5. 会话超时清理
"""

import logging
from threading import Lock, Thread
from datetime import datetime
from typing import Optional, Dict, Any, Callable, List
import time

from query_processor.llm_client import LLMClient
from services.data_query_service import DataQueryService

from langgraph_agents.sync_executor import (
    SyncLangGraphExecutor,
    LangGraphExecutionResult,
    create_sync_executor,
)
from langgraph_agents.state import GraphState, DataReference

from .models import SessionState, SessionStatus, RecordedStep, Session
from .store import SessionStore, get_session_store
from .config import get_session_config

logger = logging.getLogger(__name__)


class SessionRuntimeManager:
    """
    Session Runtime 管理器

    职责：
    1. 管理 session_id → SessionState 的映射
    2. 创建/恢复 LangGraphRuntime
    3. 跨请求保持执行上下文
    4. 记录执行步骤
    5. 会话超时清理
    """

    def __init__(
        self,
        session_store: Optional[SessionStore] = None,
        llm_client: Optional[LLMClient] = None,
        data_query_service: Optional[DataQueryService] = None,
    ):
        """
        初始化 SessionRuntimeManager

        Args:
            session_store: Session 存储层
            llm_client: LLM 客户端
            data_query_service: 数据查询服务
        """
        self.session_store = session_store or get_session_store()
        self.llm_client = llm_client
        self.data_query_service = data_query_service
        self.config = get_session_config()

        # 内存缓存：session_id → SessionState
        self._sessions: Dict[str, SessionState] = {}

        # Executor 缓存：session_id → SyncLangGraphExecutor
        self._executors: Dict[str, SyncLangGraphExecutor] = {}

        # 线程安全
        self._lock = Lock()

        # 清理线程
        self._cleanup_thread: Optional[Thread] = None
        self._cleanup_running = False

        logger.info("SessionRuntimeManager 初始化完成")

    def start_cleanup_thread(self):
        """启动后台清理线程"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return

        self._cleanup_running = True
        self._cleanup_thread = Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="session-cleanup"
        )
        self._cleanup_thread.start()
        logger.info("Session 清理线程已启动")

    def stop_cleanup_thread(self):
        """停止清理线程"""
        self._cleanup_running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
            self._cleanup_thread = None

    def _cleanup_loop(self):
        """清理循环"""
        interval = self.config.cleanup_interval_minutes * 60
        while self._cleanup_running:
            try:
                self.cleanup_expired_sessions()
            except Exception as e:
                logger.error(f"Session 清理失败: {e}")
            time.sleep(interval)

    def create_session(
        self,
        workspace_id: Optional[str] = None,
        source_workflow_id: Optional[str] = None,
        name: str = ""
    ) -> SessionState:
        """
        创建新 Session

        Args:
            workspace_id: 关联的 Workspace ID
            source_workflow_id: 来源 Workflow ID
            name: Session 名称

        Returns:
            SessionState
        """
        with self._lock:
            # 创建持久化记录
            session = self.session_store.create_session(
                workspace_id=workspace_id,
                source_workflow_id=source_workflow_id,
                name=name
            )

            # 获取状态（从持久化模型中）
            state = session.get_state()

            # 缓存到内存
            self._sessions[session.session_id] = state

            logger.info(f"SessionRuntimeManager: 创建 Session {session.session_id}")
            return state

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        获取 Session 状态

        优先从内存获取，否则从数据库恢复

        Args:
            session_id: Session ID

        Returns:
            SessionState，不存在或已过期返回 None
        """
        with self._lock:
            # 检查内存缓存
            if session_id in self._sessions:
                state = self._sessions[session_id]
                if not state.is_expired():
                    state.touch()
                    return state
                else:
                    # 过期，清理
                    self._cleanup_session(session_id)
                    return None

            # 从数据库恢复
            session = self.session_store.load_session(session_id)
            if not session:
                return None

            state = session.get_state()
            if state.is_expired():
                self._cleanup_session(session_id)
                return None

            state.touch()
            self._sessions[session_id] = state
            return state

    def execute_in_session(
        self,
        session_id: str,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        panel_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        reasoning_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        tool_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        tool_start_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> LangGraphExecutionResult:
        """
        在 Session 内执行查询（核心方法）

        与直接调用 SyncLangGraphExecutor.execute() 的区别：
        1. 恢复之前的 data_stash、chat_history、working_memory
        2. 执行完成后更新 Session 状态
        3. 记录执行步骤（渐进式 DAG）

        Args:
            session_id: Session ID
            query: 用户查询
            context: 额外上下文（如 artifact_refs）
            panel_callback: 面板预览回调
            reasoning_callback: Agent推理回调
            tool_callback: 工具调用完成回调

        Returns:
            LangGraphExecutionResult
        """
        # 获取 Session 状态
        state = self.get_session(session_id)
        if not state:
            raise ValueError(f"Session 不存在或已过期: {session_id}")

        # 获取或创建 Executor
        executor = self._get_or_create_executor(session_id)

        # 构建初始状态（从 Session 恢复）
        initial_state = self._build_initial_state(state, query, context)

        logger.info(
            f"SessionRuntimeManager: 执行查询 session={session_id} "
            f"query={query[:50]}... data_stash={len(state.data_stash)} chat_history={len(state.chat_history)}"
        )

        # 配置
        config = {
            "recursion_limit": executor.recursion_limit,
            "configurable": {"thread_id": session_id},
        }

        # 设置 callbacks
        tool_context = getattr(executor.runtime, "tool_context", None)
        extras = getattr(tool_context, "extras", None) if tool_context else None
        old_panel_callback = extras.get("emit_panel_preview") if extras else None
        old_reasoning_callback = extras.get("emit_agent_reasoning") if extras else None
        old_tool_callback = extras.get("emit_tool_result") if extras else None
        old_tool_start_callback = extras.get("emit_tool_start") if extras else None

        if panel_callback and extras is not None:
            extras["emit_panel_preview"] = panel_callback
        if reasoning_callback and extras is not None:
            extras["emit_agent_reasoning"] = reasoning_callback
        if tool_callback and extras is not None:
            extras["emit_tool_result"] = tool_callback
        if tool_start_callback and extras is not None:
            extras["emit_tool_start"] = tool_start_callback

        try:
            # 执行 LangGraph
            final_state = executor.app.invoke(initial_state, config)
            result = executor._extract_result(final_state)

            # 更新 Session 状态
            self._update_session_state(state, final_state, query, result)

            # 持久化
            if self.config.auto_persist:
                self._persist_session(session_id, state)

            return result

        except Exception as e:
            logger.error(f"SessionRuntimeManager: 执行失败 - {e}", exc_info=True)
            # 记录错误到 Session
            state.add_to_chat_history("user", query)
            state.add_to_chat_history("assistant", f"[错误] {str(e)}")
            if self.config.auto_persist:
                self._persist_session(session_id, state)
            raise

        finally:
            # 恢复原来的 callbacks
            if extras is not None:
                if panel_callback:
                    if old_panel_callback is None:
                        extras.pop("emit_panel_preview", None)
                    else:
                        extras["emit_panel_preview"] = old_panel_callback
                if reasoning_callback:
                    if old_reasoning_callback is None:
                        extras.pop("emit_agent_reasoning", None)
                    else:
                        extras["emit_agent_reasoning"] = old_reasoning_callback
                if tool_callback:
                    if old_tool_callback is None:
                        extras.pop("emit_tool_result", None)
                    else:
                        extras["emit_tool_result"] = old_tool_callback
                if tool_start_callback:
                    if old_tool_start_callback is None:
                        extras.pop("emit_tool_start", None)
                    else:
                        extras["emit_tool_start"] = old_tool_start_callback

    def close_session(self, session_id: str) -> bool:
        """
        关闭 Session

        Args:
            session_id: Session ID

        Returns:
            是否关闭成功
        """
        with self._lock:
            self._cleanup_session(session_id)
            return self.session_store.close_session(session_id)

    def get_recorded_steps(self, session_id: str) -> List[RecordedStep]:
        """
        获取 Session 记录的执行步骤

        Args:
            session_id: Session ID

        Returns:
            RecordedStep 列表
        """
        state = self.get_session(session_id)
        if not state:
            return []
        return state.recorded_steps

    def _get_or_create_executor(self, session_id: str) -> SyncLangGraphExecutor:
        """获取或创建 Executor"""
        if session_id not in self._executors:
            if not self.llm_client or not self.data_query_service:
                raise ValueError("LLM client 或 data_query_service 未配置")

            executor = create_sync_executor(
                llm_client=self.llm_client,
                data_query_service=self.data_query_service
            )
            self._executors[session_id] = executor
            logger.debug(f"SessionRuntimeManager: 创建 Executor for {session_id}")

        return self._executors[session_id]

    def _build_initial_state(
        self,
        session_state: SessionState,
        query: str,
        context: Optional[Dict[str, Any]]
    ) -> GraphState:
        """
        从 Session 状态构建 LangGraph 初始状态

        关键：恢复 data_stash、chat_history、working_memory
        """
        # 恢复 data_stash
        data_stash: List[DataReference] = []
        for ref_dict in session_state.data_stash:
            try:
                data_stash.append(DataReference(**ref_dict))
            except Exception as e:
                logger.warning(f"恢复 DataReference 失败: {e}")

        # 转换 chat_history 格式（SessionState 存储为 dict，GraphState 期望 str）
        chat_history_strs: List[str] = []
        for item in session_state.chat_history:
            if isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content", "")
                chat_history_strs.append(f"{role}: {content}")
            else:
                chat_history_strs.append(str(item))

        # 构建初始状态
        initial_state: GraphState = {
            "original_query": query,
            "chat_history": chat_history_strs,
            "data_stash": data_stash,
            "working_memory": session_state.working_memory.copy(),
            "next_tool_call": None,
            "reflection": None,
            "final_report": None,
            "human_in_loop_request": None,
            "router_decision": None,
            "pending_tool_result": None,
            "last_tool_result": None,
            "last_error": None,
            "execution_plan": None,
            "completed_step_ids": [],
            "knowledge_graph": None,
        }

        # 添加额外上下文
        if context:
            if "artifact_refs" in context:
                initial_state["working_memory"]["artifact_refs"] = context["artifact_refs"]
            if "filter_datasource" in context:
                initial_state["working_memory"]["filter_datasource"] = context["filter_datasource"]

        return initial_state

    def _update_session_state(
        self,
        session_state: SessionState,
        final_state: Dict[str, Any],
        query: str,
        result: LangGraphExecutionResult
    ):
        """
        更新 Session 状态

        1. 更新 data_stash（累积）
        2. 更新 chat_history
        3. 更新 working_memory
        4. 记录执行步骤
        """
        # 更新 data_stash（新增的，去重）
        new_refs = final_state.get("data_stash", [])
        existing_ids = {ref.get("data_id") for ref in session_state.data_stash if ref.get("data_id")}

        for ref in new_refs:
            ref_dict = ref.model_dump() if hasattr(ref, 'model_dump') else ref
            data_id = ref_dict.get("data_id")
            if data_id and data_id not in existing_ids:
                session_state.add_to_data_stash(ref_dict)
                existing_ids.add(data_id)

        # 更新 chat_history
        session_state.add_to_chat_history("user", query)
        if result.final_report:
            session_state.add_to_chat_history("assistant", result.final_report)

        # 更新 working_memory
        new_memory = final_state.get("working_memory", {})
        session_state.working_memory.update(new_memory)

        # 记录执行步骤
        for ref in new_refs:
            ref_dict = ref.model_dump() if hasattr(ref, 'model_dump') else ref
            tool_name = ref_dict.get("tool_name", "unknown")

            if tool_name and tool_name != "unknown":
                # 查找对应的执行参数
                params = {}
                for step in result.execution_steps:
                    if step.get("tool_name") == tool_name:
                        params = step.get("params", {})
                        break

                step = RecordedStep(
                    step_id=session_state.get_next_step_id(),
                    tool_id=tool_name,
                    tool_name=tool_name,
                    params=params,
                    artifact_id=ref_dict.get("artifact_id"),
                    data_id=ref_dict.get("data_id"),
                    summary=ref_dict.get("summary", ""),
                    status=ref_dict.get("status", "success"),
                    error_message=ref_dict.get("error_message"),
                    trigger_query=query,
                    depends_on=self._infer_dependencies(params, session_state),
                )
                session_state.add_recorded_step(step)

        session_state.touch()

    def _infer_dependencies(
        self,
        params: Dict[str, Any],
        session_state: SessionState
    ) -> List[int]:
        """
        自动推断依赖关系

        规则：如果参数中引用了某个 data_id，找到产生该 data_id 的步骤
        """
        depends_on = []

        # 构建 data_id → step_id 映射
        data_id_to_step: Dict[str, int] = {}
        for step in session_state.recorded_steps:
            if step.data_id:
                data_id_to_step[step.data_id] = step.step_id

        # 递归扫描参数，查找引用
        def scan_refs(value):
            if isinstance(value, str):
                if value in data_id_to_step:
                    depends_on.append(data_id_to_step[value])
            elif isinstance(value, dict):
                for v in value.values():
                    scan_refs(v)
            elif isinstance(value, list):
                for item in value:
                    scan_refs(item)

        scan_refs(params)
        return list(set(depends_on))

    def _persist_session(self, session_id: str, state: SessionState):
        """持久化 Session 状态"""
        try:
            self.session_store.update_state(session_id, state)
        except Exception as e:
            logger.error(f"SessionRuntimeManager: 持久化失败 - {e}")

    def _cleanup_session(self, session_id: str):
        """清理 Session（内存）"""
        self._sessions.pop(session_id, None)
        self._executors.pop(session_id, None)

    def cleanup_expired_sessions(self) -> int:
        """清理所有过期的 Sessions"""
        with self._lock:
            expired = []
            for session_id, state in list(self._sessions.items()):
                if state.is_expired():
                    expired.append(session_id)

            for session_id in expired:
                self._cleanup_session(session_id)

            # 同时清理数据库
            db_cleaned = self.session_store.cleanup_expired()

            if expired or db_cleaned:
                logger.info(
                    f"SessionRuntimeManager: 清理 {len(expired)} 个内存 Session，"
                    f"{db_cleaned} 个数据库 Session"
                )

            return len(expired) + db_cleaned


# 全局单例
_manager: Optional[SessionRuntimeManager] = None


def get_session_runtime_manager(
    llm_client: Optional[LLMClient] = None,
    data_query_service: Optional[DataQueryService] = None,
) -> SessionRuntimeManager:
    """
    获取 SessionRuntimeManager 单例

    Args:
        llm_client: LLM 客户端（首次调用时设置）
        data_query_service: 数据查询服务（首次调用时设置）

    Returns:
        SessionRuntimeManager 实例
    """
    global _manager
    if _manager is None:
        _manager = SessionRuntimeManager(
            llm_client=llm_client,
            data_query_service=data_query_service
        )
    elif llm_client or data_query_service:
        # 更新依赖
        if llm_client:
            _manager.llm_client = llm_client
        if data_query_service:
            _manager.data_query_service = data_query_service
    return _manager


def reset_session_runtime_manager():
    """重置管理器（测试用）"""
    global _manager
    if _manager:
        _manager.stop_cleanup_thread()
    _manager = None
