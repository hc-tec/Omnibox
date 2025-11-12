# LangGraph Agents 系统整合方案

## 整合目标

将 LangGraph Agents（复杂多轮研究系统）整合到现有的 Omni 项目中，使前端用户能够通过 UI 触发复杂研究任务并实时查看进展。

## 现有架构分析

### 当前数据流

```
前端 → API Controller (chat_controller.py)
                ↓
           ChatService
                ↓
      ┌────────┴────────┐
      ↓                  ↓
IntentService    DataQueryService
                        ↓
                   RAGInAction
                        ↓
                 (单轮查询完成)
```

### 关键组件

1. **ChatService** (`services/chat_service.py`)
   - 统一入口，负责意图识别和路由
   - 调用 DataQueryService 处理数据查询
   - 生成智能面板结构

2. **DataQueryService** (`services/data_query_service.py`)
   - 处理**单轮**数据查询
   - 调用 RAGInAction
   - 返回 DataQueryResult

3. **RAGInAction** (`orchestrator/rag_in_action.py`)
   - RAG 检索 + LLM 解析
   - 单次调用完成

4. **API Controller** (`api/controllers/chat_controller.py`)
   - REST API `/api/v1/chat`
   - WebSocket `/api/v1/chat/stream`

### LangGraph Agents 特性

- **多轮研究**：规划 → 执行 → 反思 → 再规划（ReAct 循环）
- **状态管理**：GraphState + CheckPointer
- **工具编排**：动态工具调用
- **复杂度高**：适合需要多步骤数据收集和分析的场景

---

## 整合方案：方案 C（推荐）

### 方案概述

创建新的 **ResearchService**，与 DataQueryService 平行，ChatService 根据需求智能路由。

### 架构图

```
前端 → API Controller
          ↓
     ChatService (统一入口)
          ↓
    ┌─────┴───────┐
    ↓             ↓
DataQueryService  ResearchService  ← 新增
    ↓             ↓
RAGInAction   LangGraph Agents
(单轮查询)    (多轮研究)
```

### 路由策略

ChatService 根据以下条件决定使用哪个服务：

1. **显式指定**（推荐初期方案）：
   - 前端请求中携带 `mode: "research"` 参数
   - ChatService 直接路由到 ResearchService

2. **自动识别**（后期优化）：
   - 基于用户查询复杂度
   - 例如：多个问题、需要对比分析、需要综合多个数据源

### 核心接口设计

#### ResearchService API

```python
class ResearchService:
    def research(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        callback: Optional[Callable] = None,  # 流式回调
    ) -> ResearchResult:
        """
        执行复杂研究任务

        Returns:
            ResearchResult 包含：
            - final_report: 最终报告
            - data_stash: 收集的数据引用
            - execution_steps: 执行步骤记录
            - metadata: 元数据
        """
```

#### ChatService 更新

```python
class ChatService:
    def chat(
        self,
        user_query: str,
        mode: Literal["auto", "simple", "research"] = "auto",
        ...
    ) -> ChatResponse:
        if mode == "research" or self._should_use_research(user_query, mode):
            return self._handle_research(user_query, ...)
        else:
            return self._handle_data_query(user_query, ...)
```

---

## 实施计划

### 阶段 1：创建 ResearchService（核心）

**目标**：封装 LangGraph Agents，提供简洁 API

**文件**: `services/research_service.py`

**职责**:
- 初始化 LangGraph 运行时（Runtime）
- 管理工具注册表（ToolRegistry）
- 执行研究工作流（create_langgraph_app）
- 返回结构化结果（ResearchResult）

**核心代码结构**:
```python
from langgraph_agents import (
    LangGraphRuntime,
    create_langgraph_app,
    InMemoryResearchDataStore,
)
from langgraph_agents.tools import ToolRegistry
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Callable

@dataclass
class ResearchStep:
    """单个研究步骤记录"""
    step_id: int
    action: str  # tool_call / reflection / synthesize
    description: str
    status: str  # success / error
    timestamp: str

@dataclass
class ResearchResult:
    """研究结果"""
    success: bool
    final_report: str
    data_stash: List[Dict[str, Any]]  # 数据引用列表
    execution_steps: List[ResearchStep]  # 执行步骤
    metadata: Dict[str, Any]
    error: Optional[str] = None

class ResearchService:
    def __init__(
        self,
        router_llm,
        planner_llm,
        reflector_llm,
        synthesizer_llm,
        data_query_service,  # 用于工具调用
    ):
        # 初始化 LangGraph 组件
        self.data_store = InMemoryResearchDataStore()
        self.tool_registry = self._init_tools(data_query_service)
        self.runtime = LangGraphRuntime(
            router_llm=router_llm,
            planner_llm=planner_llm,
            reflector_llm=reflector_llm,
            synthesizer_llm=synthesizer_llm,
            tool_registry=self.tool_registry,
            data_store=self.data_store,
        )
        self.app = create_langgraph_app(self.runtime)

    def _init_tools(self, data_query_service):
        """注册工具到 ToolRegistry"""
        registry = ToolRegistry()

        @registry.register_tool(
            plugin_id="query_data",
            description="查询数据源获取信息",
            schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "datasource": {"type": "string"},
                },
                "required": ["query"],
            }
        )
        def query_data_tool(query: str, datasource: Optional[str] = None):
            result = data_query_service.query(query, filter_datasource=datasource)
            return {
                "status": result.status,
                "data": result.feed_items[:10],  # 限制返回数量
                "feed_title": result.feed_title,
            }

        # 可以注册更多工具...

        return registry

    def research(
        self,
        user_query: str,
        filter_datasource: Optional[str] = None,
        callback: Optional[Callable] = None,
    ) -> ResearchResult:
        """执行研究任务"""
        try:
            # 准备初始状态
            initial_state = {
                "original_query": user_query,
                "chat_history": [],
            }

            # 执行 LangGraph 工作流
            config = {"configurable": {"thread_id": "research-1"}}

            execution_steps = []

            for event in self.app.stream(initial_state, config):
                # 记录每个步骤
                if callback:
                    callback(event)  # 实时回调给前端

                # 解析事件并记录
                step = self._parse_event(event)
                if step:
                    execution_steps.append(step)

            # 获取最终状态
            final_state = self.app.get_state(config).values

            return ResearchResult(
                success=True,
                final_report=final_state.get("final_report", ""),
                data_stash=self._format_data_stash(final_state.get("data_stash", [])),
                execution_steps=execution_steps,
                metadata={
                    "query": user_query,
                    "total_steps": len(execution_steps),
                    "datasource_filter": filter_datasource,
                },
            )

        except Exception as exc:
            logger.error(f"研究任务失败: {exc}", exc_info=True)
            return ResearchResult(
                success=False,
                final_report="",
                data_stash=[],
                execution_steps=[],
                metadata={},
                error=str(exc),
            )
```

---

### 阶段 2：更新 ChatService

**文件**: `services/chat_service.py`

**变更点**:

1. **初始化时注入 ResearchService**:
```python
class ChatService:
    def __init__(
        self,
        data_query_service: DataQueryService,
        research_service: Optional[ResearchService] = None,  # 新增
        ...
    ):
        self.research_service = research_service
```

2. **添加 `_handle_research` 方法**:
```python
def _handle_research(
    self,
    user_query: str,
    filter_datasource: Optional[str],
    intent_confidence: float,
) -> ChatResponse:
    """处理复杂研究意图"""
    logger.debug("处理复杂研究意图")

    research_result = self.research_service.research(
        user_query=user_query,
        filter_datasource=filter_datasource,
    )

    if research_result.success:
        return ChatResponse(
            success=True,
            intent_type="research",
            message=research_result.final_report,
            metadata={
                "mode": "research",
                "steps": len(research_result.execution_steps),
                "execution_steps": [
                    {
                        "step_id": step.step_id,
                        "action": step.action,
                        "description": step.description,
                    }
                    for step in research_result.execution_steps
                ],
            },
        )
    else:
        return ChatResponse(
            success=False,
            intent_type="research",
            message=f"研究任务失败：{research_result.error}",
            metadata={"error": research_result.error},
        )
```

3. **更新 `chat` 方法支持 mode 参数**:
```python
def chat(
    self,
    user_query: str,
    mode: Literal["auto", "simple", "research"] = "auto",
    ...
) -> ChatResponse:
    # 如果显式指定研究模式
    if mode == "research":
        if not self.research_service:
            return ChatResponse(
                success=False,
                intent_type="error",
                message="研究服务未启用",
            )
        return self._handle_research(user_query, filter_datasource, 1.0)

    # 原有逻辑...
    intent_result = self.intent_service.recognize(user_query)

    if intent_result.intent_type == "data_query":
        return self._handle_data_query(...)
    ...
```

---

### 阶段 3：API Controller 更新

**文件**: `api/controllers/chat_controller.py`

**变更点**:

1. **ChatRequest 增加 mode 参数**:
```python
# api/schemas/responses.py
class ChatRequest(BaseModel):
    query: str
    filter_datasource: Optional[str] = None
    use_cache: bool = True
    mode: Literal["auto", "simple", "research"] = "auto"  # 新增
```

2. **chat endpoint 传递 mode**:
```python
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    response = await run_in_threadpool(
        _chat_service.chat,
        user_query=request.query,
        filter_datasource=request.filter_datasource,
        use_cache=request.use_cache,
        mode=request.mode,  # 新增
    )
    ...
```

---

### 阶段 4：WebSocket 流式响应（可选）

**目标**：前端实时查看研究进展

**实现**：通过 WebSocket 推送每个步骤的事件

```python
@router.websocket("/research/stream")
async def research_stream(websocket: WebSocket):
    await websocket.accept()

    data = await websocket.receive_json()
    user_query = data.get("query")

    def callback(event):
        """LangGraph 事件回调"""
        # 解析事件并推送到前端
        message = {
            "type": "step",
            "node": event.get("node"),
            "data": event.get("data"),
        }
        asyncio.create_task(websocket.send_json(message))

    result = await run_in_threadpool(
        _research_service.research,
        user_query=user_query,
        callback=callback,
    )

    # 发送最终结果
    await websocket.send_json({
        "type": "complete",
        "data": {
            "final_report": result.final_report,
            "success": result.success,
        },
    })
```

---

### 阶段 5：前端集成

**UI 变更**:

1. **添加"研究模式"开关**:
   ```vue
   <Switch v-model="isResearchMode" label="复杂研究模式" />
   ```

2. **请求时携带 mode 参数**:
   ```typescript
   const response = await fetch('/api/v1/chat', {
     method: 'POST',
     body: JSON.stringify({
       query: userQuery,
       mode: isResearchMode ? 'research' : 'auto',
     }),
   });
   ```

3. **显示研究步骤**（可选）:
   - 如果后端返回 `execution_steps`，前端可以展示研究过程
   - 类似于"思考中..."的动画

---

## 测试策略

### 单元测试

1. **ResearchService 测试** (`tests/services/test_research_service.py`)
   - Mock LLM clients
   - 验证工具注册
   - 验证结果格式

2. **ChatService 测试更新** (`tests/services/test_chat_service.py`)
   - 测试 mode='research' 路径
   - 验证 ResearchService 被正确调用

### 集成测试

1. **API 测试** (`tests/api/test_chat_controller.py`)
   - 测试 `/api/v1/chat` with `mode='research'`
   - 验证响应格式

2. **端到端测试**
   - 手动测试前端发起研究请求
   - 验证实时反馈和最终结果

---

## 风险与缓解

### 风险 1：LangGraph 执行时间长

- **影响**：前端用户等待时间过长
- **缓解**：
  - 使用 WebSocket 提供实时进度反馈
  - 设置合理的超时时间
  - 提供"取消研究"功能

### 风险 2：LLM API 费用

- **影响**：复杂研究调用多次 LLM，成本高
- **缓解**：
  - 使用配置限制最大步骤数
  - 优先使用较便宜的模型（如 Reflector 用 Haiku）
  - 添加用户权限控制

### 风险 3：工具调用失败

- **影响**：研究中断
- **缓解**：
  - Reflector 有错误恢复逻辑
  - 提供降级方案（退回简单查询）

---

## 后续优化方向

1. **智能路由**：自动识别何时使用研究模式
2. **结果缓存**：相似研究任务复用结果
3. **可视化**：研究过程可视化（知识图谱）
4. **协作研究**：多用户共享研究会话

---

## 参考文档

- `.agentdocs/workflow/251111-langgraph-agents-refactor.md` - LangGraph Agents 重构文档
- `docs/langgraph-agents-design.md` - LangGraph 设计文档
- `docs/langgraph-agents-frontend-design.md` - 前端集成设计
