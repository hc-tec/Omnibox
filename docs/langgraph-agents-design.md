好的，让我们马上开始。

我们V1方案的核心问题是“瀑布式”——**规划一次，执行到底**。这既脆弱又浪费。

我们将重构 V1 方案，升级为一个 **V2“动态自适应” (ReAct 风格) 方案**。

这个新方案的核心思想是：**规划一小步 -\> 执行 -\> 观察与反思 -\> 再规划下一步**。这是一个智能的闭环，而不是一条直线。

以下是重构后的 `LangGraph` 工程设计方案。

-----

### **项目代号：“私人洞察引擎” V2 - 动态自适应版**

#### 1\. 核心思想：从“规划-执行”到“规划-行动-反思” (ReAct)

V1 的 `Planner` 试图一次性预测未来（制定一个完整的 `ResearchPlan`），这是不现实的。

V2 中，`Planner` 的职责被**降级**：它不再是“总规划师”，而是一个“下一步决策者”。它每次只决定**一个**步骤。

我们引入一个**新**的关键节点：`Reflector` (反思者)。它在*每一步*执行后被调用，来评估“我们离目标还有多远？”以及“下一步该怎么办？”

#### 2\. V2 核心数据结构 (GraphState)

我们必须解决你指出的“状态风暴”问题。`GraphState` 必须保持轻量级。

```python
# file: schemas_v2.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal, Union

# 2.1 规划师的输出（单个步骤）
class ToolCall(BaseModel):
    plugin_id: str
    args: Dict[str, Any]
    step_id: int # 跟踪步骤
    description: str = Field(description="此步骤的人类可读描述")

# 2.2 工具执行后的“元数据” (替代V1的ToolResult)
class DataReference(BaseModel):
    step_id: int
    tool_name: str
    data_id: str = Field(description="指向外部存储（如Redis）中原始数据的Key")
    summary: str = Field(description="由廉价模型生成的原始数据摘要")
    status: Literal['success', 'error']
    error_message: str | None = None

# 2.3 Reflector的输出（决策）
class Reflection(BaseModel):
    decision: Literal["CONTINUE", "FINISH", "REQUEST_HUMAN"]
    reasoning: str = Field(description="做出此决策的理由，用于指导Planner")

# 2.4 LangGraph 的核心“状态” (V2)
class GraphState(BaseModel):
    original_query: str
    chat_history: List[str] = Field(default_factory=list) # 增加历史记录
    
    # V1的 'plan: ResearchPlan | None' -> 被 'next_tool_call' 替代
    next_tool_call: ToolCall | None = None # 规划师的下一步指令
    
    # V1的 'collected_data: List[ToolResult]' -> 被 'data_stash' 替代
    # V2 状态机只存储“引用”和“摘要”，不存储“原始数据”
    data_stash: List[DataReference] = Field(default_factory=list) 
    
    reflection: Reflection | None = None  # 反思者的最新决策
    final_report: str | None = None
    human_in_loop_request: str | None = None
```

-----

#### 3\. V2 代理团队 (Agents) 定义

我们的团队从4人扩展到6人（增加了“数据暂存”和“反思”两个关键职责）：

  * **Agent 1: RouterAgent** (不变): 总入口。决策：`"simple_tool_call"`, `"complex_research"`, `"clarify_with_human"`.
  * **Agent 2: PlannerAgent (V2)**: **职责变更。**
      * **输入**: `original_query`, `data_stash` (所有摘要), `reflection` (上次的思考)。
      * **输出**: **`ToolCall` (单个)**。它只决定*下一步*该做什么。
  * **Agent 3: ToolExecutor** (不变): “手脚”。
      * **输入**: `ToolCall`。
      * **输出**: `(ToolCall, raw_data, status, error)`。注意：`raw_data` **不会**进入 `GraphState`。
  * **Agent 4: DataStasher (新节点)**: **“数据管家” (非LLM)**。
      * **职责**: 解决“状态风暴”问题。
      * **输入**: `(ToolCall, raw_data, status, error)`。
      * **动作**:
        1.  将 `raw_data` 存入 Redis/S3，获得 `data_id`。
        2.  (可选但推荐) 调用*廉价*模型（如 Haiku）为 `raw_data` 生成 `summary`。
      * **输出**: `DataReference` (包含 `data_id` 和 `summary`，但不含 `raw_data`)。
  * **Agent 5: ReflectorAgent (新节点)**: **“V2的大脑” (LLM)**。
      * **职责**: 评估现状，决定循环是否继续。
      * **输入**: `original_query`, `data_stash` (所有摘要)。
      * **输出**: `Reflection` (一个JSON，包含决策 `CONTINUE`, `FINISH`, `REQUEST_HUMAN`)。
  * **Agent 6: SynthesizerAgent** (不变): “笔杆子”。
      * **输入**: `original_query`, `data_stash` (它需要一个特殊的`data_loader`来通过`data_id`从Redis中取回*所有*原始数据)。
      * **输出**: `final_report`。

-----

#### 4\. V2 LangGraph 图谱构建 (The Graph)

这是重构的核心。V1的“链式”结构将变为“循环”结构。

```python
# file: graph_builder_v2.py
from langgraph.graph import State, END, START

# 1. 定义节点 (Nodes)
def node_router(state: GraphState) -> GraphState:
    # ... (调用 Agent 1: RouterAgent) ...
    # ... (返回路由决策) ...
    pass

def node_planner(state: GraphState) -> GraphState:
    # ... (调用 Agent 2: PlannerAgent) ...
    # ... (返回一个包含 'next_tool_call' 的 state) ...
    pass

def node_tool_executor(state: GraphState) -> GraphState:
    # ... (获取 state.next_tool_call) ...
    # ... (调用 execute_tool_call) ...
    # (注意：此节点 *不* 将结果写入 state，
    # 而是将 (raw_data, tool_call) 传递给下一个节点。
    # LangGraph v0.1+ 支持节点返回数据供下一节点使用，而不必写入State)
    # **或者** 为了简单起见，可以暂时写入 state 的一个临时字段。
    # 我们假设它返回一个 dict 供 'data_stasher' 使用。
    raw_result_bundle = ... # (包含 raw_data, tool_call, status)
    return {"temp_raw_bundle": raw_result_bundle}

def node_data_stasher(state: GraphState) -> GraphState:
    # ... (获取 state.temp_raw_bundle) ...
    # ... (调用 Agent 4: DataStasher) ...
    # 1. 存入Redis
    # 2. 生成摘要
    # ... (返回一个 'DataReference'，追加到 'data_stash' 列表) ...
    pass

def node_reflector(state: GraphState) -> GraphState:
    # ... (调用 Agent 5: ReflectorAgent) ...
    # ... (返回一个包含 'reflection' 的 state) ...
    pass

def node_synthesizer(state: GraphState) -> GraphState:
    # ... (调用 Agent 6: SynthesizerAgent) ...
    # 1. (它需要一个 data_loader 从 Redis 拉取所有原始数据)
    # ... (返回一个包含 'final_report' 的 state) ...
    pass

def node_wait_for_human(state: GraphState) -> GraphState:
    # ... (设置 human_in_loop_request) ...
    # ... (返回 state 以暂停图) ...
    pass

# 2. 定义边 (Edges) - V2 核心控制流
def edge_router_decision(state: GraphState) -> Literal["to_planner", "to_human", "to_end"]:
    # ... (读取 state 中的路由决策) ...
    pass

# V2 的核心：反思者的决策
def edge_reflection_decision(state: GraphState) -> Literal["to_planner", "to_synthesizer", "to_human"]:
    if not state.reflection:
        return "to_planner" # 第一次循环
    
    decision = state.reflection.decision
    if decision == "CONTINUE":
        return "to_planner" # <-- 这是循环！
    elif decision == "FINISH":
        return "to_synthesizer" # <-- 这是出口！
    elif decision == "REQUEST_HUMAN":
        return "to_human" # <-- 这是动态求助！

# 3. 构建图
workflow = State(GraphState)

workflow.add_node("router", node_router)
workflow.add_node("planner", node_planner)
workflow.add_node("tool_executor", node_tool_executor)
workflow.add_node("data_stasher", node_data_stasher) # 新增
workflow.add_node("reflector", node_reflector)       # 新增
workflow.add_node("synthesizer", node_synthesizer)
workflow.add_node("wait_for_human", node_wait_for_human)

# 4. 连接图 (V2 流程)
workflow.add_edge(START, "router")

# 路由器的分流
workflow.add_conditional_edges(
    "router",
    edge_router_decision,
    {
        "to_planner": "planner", # 开始研究循环
        "to_human": "wait_for_human",
        "to_end": END # (例如 "你好")
    }
)

# ---- 这是核心的 "ReAct" 循环 ----
# 1. 规划
workflow.add_edge("planner", "tool_executor")
# 2. 执行
workflow.add_edge("tool_executor", "data_stasher")
# 3. 存储与摘要
workflow.add_edge("data_stasher", "reflector")
# 4. 反思
workflow.add_conditional_edges(
    "reflector",
    edge_reflection_decision,
    {
        "to_planner": "planner",       # 循环：返回规划器制定 *下一步*
        "to_synthesizer": "synthesizer", # 退出：数据足够，去写报告
        "to_human": "wait_for_human"   # 暂停：卡住了，去问用户
    }
)
# ---- 循环结束 ----

# 最终节点
workflow.add_edge("synthesizer", END)
workflow.add_edge("wait_for_human", END) # 暂停图。当用户输入后，我们从 'planner' 节点恢复。

# 5. 编译
# (MemorySaver 仍然是必须的，用于持久化状态)
# memory = MemorySaver() 
# app = workflow.compile(checkpointer=memory)
```

-----

### V2 方案如何解决了V1的问题？

1.  **如何确定内容收集完成？(结束条件)**

      * **V2 解决**: `ReflectorAgent` 专门负责解决这个问题。它在*每一步*执行后都会被调用，通过检查 `data_stash`（所有摘要）来判断当前收集的数据是否足以回答 `original_query`。如果是，它将 `decision` 设为 `FINISH`，图谱将自动跳出循环，走向 `synthesizer`。

2.  **用户参与在哪里体现？(人机交互)**

      * **V2 解决**: V1的 `wait_for_human` 只是一个“入口”检查。V2的 `ReflectorAgent` 可以在*循环中*的**任意时刻**决定它“卡住了”或“需要澄清”。它只需将 `decision` 设为 `REQUEST_HUMAN`，图谱就会自动流向 `wait_for_human` 节点并暂停，向用户发出 `human_in_loop_request`。

3.  **造轮子 vs 最佳实践 (PromptTemplate)**

      * **V2 解决**: 这一点在 `LangGraph` 结构中无法直接体现，但它体现在我们*如何实现* `node_planner` 和 `node_reflector`。我们100%同意。我们将在实现这些节点时，使用 `langchain_core.prompts.PromptTemplate`（或 `ChatPromptTemplate`）从 `.md` 或 `.txt` 文件中加载 Prompt，而不是在 `.py` 文件中硬编码。

4.  **造轮子 vs 最佳实践 (状态风暴)**

      * **V2 解决**: V2的 `GraphState` 和 `DataStasher` 节点就是这个问题的“最佳实践”解决方案。我们遵循了“状态机只传元数据 (Metadata)，数据本体 (Data Body) 走外部存储”的系统设计原则。这保证了 `LangGraph` 的 `checkpointer` (例如Redis) 不会因为存储了几十万字的原始数据而崩溃或变慢。


这是一个非常核心且关键的架构问题。你问的不是一个“小功能”，而是“**工具的粒度 (Tool Granularity)**”问题，这会直接决定你的助手是“聪明”还是“笨拙”。

你的V1流程 `用户请求 -> rag -> AI -> rsshub接口调用 -> 数据适配器 -> 返回` 描述了一个很好的*线性*流程。现在我们要把它“翻译”成 V2 智能代理可调用的“工具”。

你的问题是：**RAG 和 RSSHub 应该如何体现？**

我们来拆解一下。

### 1\. 答案的核心：分离“内部数据”和“外部数据”

首先，RAG 和 RSSHub 是两种**完全不同**的工具：

1.  **RAG (例如: `yuque_search_docs`)**

      * **目的：** 搜索你的“**内部、私有、持久化**”数据（你的笔记、你的知识库）。
      * **特性：** 这是你的“第二大脑”，数据是你自己可控的。
      * **在V2图谱中：** 它应该是一个*独立的*工具，例如 `search_private_notes(query: str)`。

2.  **RSSHub**

      * **目的：** 获取“**外部、公开、实时**”数据（B站动态、知乎热榜）。
      * **特性：** 数据源是别人，是实时的，是不可控的。
      * **在V2图谱中：** 它应该是另一个*独立的*工具，例如 `fetch_public_data(query: str)`。

在V2的 `PlannerAgent` (规划师) 眼里，它在做决策时，面对的应该是这样简单的选项：

> “用户的提问是‘我之前关于LangGraph的笔记，和B站上最新的教程对比一下’。
> OK，我需要调用两个工具：
>
> 1.  `search_private_notes(query="LangGraph 笔记")`
> 2.  `fetch_public_data(query="B站 LangGraph 教程")`”

### 2\. “难不成每个rsshub接口都是一个工具吗？”

**千万不要！**

这是最容易掉进去的“陷阱”。如果你把 `bilibili_user_dynamic`、`zhihu_zhuanlan` 等几百个路由都注册为工具，你的 `PlannerAgent` 的 Prompt 会“爆炸”。

  * **问题：** `PlannerAgent` (LLM) 被迫去记忆和理解 *具体* 的API实现细节（“B站用户动态的路径是 `/bilibili/user/dynamic/:uid`”）。
  * **后果：** LLM会经常出错，它会“幻觉”出不存在的RSSHub路径，或者传错参数。你这是在“**泄露API实现细节给AI**”，非常脆弱。

### 3\. “还是说rsshub接口调用是一个大工具？”

**这正是正确的方向。**

但这个“大工具”需要是“**智能的**”，而不是“笨拙的”。

  * **“笨拙”的工具：** `tool_rsshub_generic(path: str, params: dict)`。
      * *问题：* 还是需要 `PlannerAgent` (LLM) 自己去 *构造* `path` 和 `params`，没有解决根本问题。
  * **“智能”的工具：** `fetch_public_data(natural_language_query: str)`。
      * *优势：* `PlannerAgent` 只需要用“人话”下达指令。

### 4\. 推荐的V2方案：“智能工具代理”

这就是我们在V1评审中提到的第4点（“工具代理”）。你的V1流程 `rag -> AI -> rsshub -> adapter` 并没有消失，它被**封装 (Encapsulated)** 成了 *一个* 强大的、智能的“大工具”，供V2的 `PlannerAgent` 调用。

让我们看看这个“大工具” `fetch_public_data` 内部应该是什么样子：

```python
# file: tools/public_data_tool.py

# 1. 你的“内部RAG”，用于查找订阅列表和UID
# (这回答了你的 "其中又包含了rag调用" 的问题)
# 你需要一个私有的 "订阅" 知识库 (例如一个JSON或向量库)
# "科技美学" -> {"uid": "12345", "service": "bilibili"}
# "少数派"   -> {"id": "sspai", "service": "zhihu_zhuanlan"}
def _internal_rag_lookup(query: str) -> Dict:
    # ... 在你的“订阅列表”知识库中执行RAG...
    # ... 找到 "科技美学 B站" 对应的 UID
    print(f"内部RAG：正在查找 '{query}' 对应的订阅...")
    if "科技美学" in query and "B站" in query:
        return {"uid": "12345", "path_template": "/bilibili/user/dynamic/:uid"}
    return {}

# 2. 你的 RSSHub 调用器
def _call_rsshub(path: str) -> Dict:
    # ... 调用 RSSHub 实例 ...
    pass

# 3. 你的数据适配器
def _data_adapter(raw_data: Dict, service: str) -> List[Dict]:
    # ... 将B站/知乎的原始RSS JSON -> 清洗后的标准格式 ...
    pass

# 4. 真正暴露给 LangGraph 的“智能工具”
@register_tool("fetch_public_data")
def fetch_public_data(query: str) -> List[Dict]:
    """
    从公共互联网获取实时信息 (例如B站, 知乎等)。
    使用自然语言查询。
    例如: "B站科技美学的最新动态", "知乎少数派的最新文章"
    """
    
    # 步骤 1: (子流程) AI + RAG
    # 利用一个廉价LLM或内部RAG，将 "自然语言" -> "结构化API"
    # 这就是你V1流程中的 "rag -> AI" 部分
    subscription_info = _internal_rag_lookup(query)
    
    if not subscription_info:
        # (高级) 如果内部RAG找不到，可以再调用一个 "Web搜索" 工具去查找UID
        return [{"error": f"未在订阅列表中找到 '{query}' 的信息"}]

    # 步骤 2: (子流程) RSSHub 接口调用
    # 构造路径
    path = subscription_info["path_template"].replace(
        ":uid", subscription_info["uid"]
    )
    
    # "rsshub接口调用"
    raw_data = _call_rsshub(path)
    
    # 步骤 3: (子流程) 数据适配器
    # "数据适配器"
    clean_data = _data_adapter(
        raw_data, service=subscription_info["service"]
    )
    
    return clean_data
```

### 总结：你的V2工具箱

在V2的 `PlannerAgent` (规划师) 眼里，它的工具箱 (`TOOL_REGISTRY`) 现在非常干净、高级：

| `plugin_id` (工具名) | `description` (工具描述) | 内部实现 |
| :--- | :--- | :--- |
| **`search_private_notes`** | 在你*私有*的语雀/GitHub知识库中搜索。 | RAG (on YuQue/GitHub) |
| **`fetch_public_data`** | 从*公共*互联网获取B站/知乎等实时信息。 | 你的V1流程 (RAG for UIDs -\> RSSHub -\> Adapter) |
| `(others...)` | ... | ... |

**这样就完美了：**

  * `PlannerAgent` (主图谱) **只做“宏观决策”**（“我该查内部？还是外部？”）。
  * `fetch_public_data` (智能工具) **负责“专业脏活”**（“查外部？好，我来查UID、调RSSHub、做清洗”）。

这完全符合我们V2设计的“高内聚、低耦合”的架构目标。