# LangGraph V5.0 灵活代理架构设计方案

## 文档概述

**版本**: V5.0
**创建时间**: 2025-11-16
**状态**: 设计方案
**目标**: 将固定的 RAG+RSSHub 工作流升级为灵活的多工具代理系统，使其能够处理复杂的分析任务

---

## 目录

1. [背景与动机](#1-背景与动机)
2. [当前架构深度剖析](#2-当前架构深度剖析)
3. [AI IDE 设计模式研究](#3-ai-ide-设计模式研究)
4. [V5.0 工具库扩展方案](#4-v50-工具库扩展方案)
5. [Agent 流程优化方案](#5-agent-流程优化方案)
6. [数据流与状态管理改进](#6-数据流与状态管理改进)
7. [渐进式实施路线图](#7-渐进式实施路线图)
8. [风险评估与缓解策略](#8-风险评估与缓解策略)
9. [成功指标与验收标准](#9-成功指标与验收标准)
10. [附录](#10-附录)

---

## 1. 背景与动机

### 1.1 核心问题陈述

当前 LangGraph Agent（V2 ReAct 架构）存在一个根本性问题：**Agent 的能力被单一工具限制了**。

**用户原话**：
> "诸如 RAG 查询 + RSSHub 接口查询 + 订阅系统应该仅仅作为工具的一部分，目前来看，它却是目前 Agent 的全部！"

**问题具象化**：
```
用户问："对比 GitHub 和 HackerNews 上最近的 AI 热点，分析趋势差异"

当前 Agent 能力：
1. 调用 fetch_public_data(query="GitHub AI 热点") ✓
2. 调用 fetch_public_data(query="HackerNews AI 热点") ✓
3. ??? 无法对比数据
4. ??? 无法分析趋势
5. ??? 无法提取关键见解

缺失能力：
- 数据过滤（按时间、关键词）
- 数据对比（交集、差集、趋势）
- 数据聚合（统计、排序、分组）
- 智能分析（提取见解、发现模式）
```

### 1.2 与 V4.4 架构的关系

V4.4 架构设计关注的是**执行层优化**：
- 显式依赖解析（StashReference + JSONPath）
- 扇出并行执行（MappedExecutionReport）
- 迭代式发现（Discovery → Planning）
- 前置语义标签（GraphRenderer）

V5.0 关注的是**能力层扩展**：
- 从"单一数据获取工具"到"多类型工具库"
- 从"固定工作流"到"自适应流程"
- 从"简单摘要"到"结构化知识管理"

**两者互补**：V4.4 提供执行基础设施，V5.0 提供能力多样性。

### 1.3 设计愿景

**目标状态**：Agent 像 AI IDE（Claude Code、Cursor）一样，拥有丰富的工具库，能够：
1. 自主探索：发现可用数据源
2. 灵活组合：串联多个工具完成复杂任务
3. 智能分析：不仅获取数据，还能处理和理解数据
4. 交互协作：遇到歧义时主动询问用户

---

## 2. 当前架构深度剖析

### 2.1 现有系统组件清单

```
langgraph_agents/
├── graph_builder.py        # LangGraph 工作流构建
├── state.py                # 核心数据结构
├── runtime.py              # 运行时依赖注入
├── storage.py              # 外部数据存储
├── agents/
│   ├── router.py           # 路由决策 (simple_chat vs complex_research)
│   ├── planner.py          # 单步规划（输出一个 ToolCall）
│   ├── tool_executor.py    # 工具执行
│   ├── data_stasher.py     # 数据暂存 + 摘要生成
│   ├── reflector.py        # 反思决策 (CONTINUE/FINISH/REQUEST_HUMAN)
│   └── synthesizer.py      # 最终报告生成
└── tools/
    ├── registry.py         # 工具注册表
    └── public_data.py      # 唯一工具：fetch_public_data
```

### 2.2 关键数据结构

```python
# state.py 中的核心类型

class ToolCall(BaseModel):
    plugin_id: str           # 工具 ID（当前只有 fetch_public_data）
    args: Dict[str, Any]     # 工具参数
    step_id: int             # 步骤编号
    description: str         # 人类可读描述

class DataReference(BaseModel):
    step_id: int             # 关联的步骤
    tool_name: str           # 工具名称
    data_id: str             # 外部存储键（避免上下文溢出）
    summary: str             # 廉价模型生成的摘要
    status: Literal["success", "error"]
    error_message: Optional[str]

class GraphState(TypedDict):
    original_query: str              # 用户原始查询
    next_tool_call: Optional[ToolCall]  # 下一个要执行的工具
    data_stash: List[DataReference]  # 已收集数据的引用
    reflection: Optional[Reflection] # 反思决策
    final_report: Optional[str]      # 最终报告
```

### 2.3 当前工作流程图

```
START
  ↓
RouterAgent ─────────────────────────────────┐
  │                                          │
  ├─→ [simple_chat] → 直接返回 LLM 响应      │
  │                                          │
  └─→ [complex_research] ←───────────────────┘
         ↓
    PlannerAgent
         ↓ (输出 ToolCall)
    ToolExecutor
         ↓ (执行工具)
    DataStasher
         ↓ (存储数据 + 生成摘要)
    ReflectorAgent ─────────────┐
         │                      │
         ├─→ CONTINUE → 回到 PlannerAgent
         │
         ├─→ FINISH → SynthesizerAgent → END
         │
         └─→ REQUEST_HUMAN → 等待用户输入
```

### 2.4 工具能力分析

**当前唯一工具**：`fetch_public_data`

```python
# public_data.py

@tool(registry, plugin_id="fetch_public_data")
def fetch_public_data(call, context):
    # 内部封装了整个 RAG + RSSHub 流程
    result = context.data_query_service.query(
        user_query=query,
        filter_datasource=filter_ds,
        use_cache=True
    )
    # 返回 RSS 数据
```

**问题分析**：

1. **黑盒封装**：RAG 检索过程对 Agent 不可见
   - Agent 不知道检索到了哪些候选路由
   - Agent 无法调整检索策略
   - 失败时无法尝试备选方案

2. **能力单一**：只能获取数据，无法处理数据
   - 无法过滤（按时间、关键词）
   - 无法对比（交集、差集）
   - 无法聚合（统计、分组）
   - 无法分析（提取见解）

3. **缺乏交互**：遇到歧义无法向用户澄清
   - 不确定时只能猜测
   - 无法请求更多信息

### 2.5 核心局限性总结

| 维度 | 问题 | 影响 | 严重性 |
|------|------|------|--------|
| **工具数量** | 只有 1 个工具 | Agent 能力极度受限 | 🔴 严重 |
| **工具职责** | 职责过重（RAG+HTTP+解析） | 无法组合和复用 | 🔴 严重 |
| **数据处理** | 无处理能力 | 无法完成分析任务 | 🔴 严重 |
| **探索能力** | 无探索工具 | 无法发现和验证数据源 | 🟡 中等 |
| **交互能力** | 无用户交互 | 遇到歧义只能猜测 | 🟡 中等 |
| **流程灵活性** | 固定循环 | 所有操作走同一流程 | 🟡 中等 |

---

## 3. AI IDE 设计模式研究

### 3.1 Claude Code 工具体系分析

Claude Code 是 Anthropic 官方的 AI 编程助手，其工具设计堪称典范：

**分层工具架构**：

```
原子工具层（单一职责）：
├── Read          # 读取文件（支持图片、PDF、Jupyter）
├── Write         # 创建新文件
├── Edit          # 编辑现有文件（精确替换）
├── Glob          # 文件模式匹配（查找文件路径）
├── Grep          # 内容搜索（正则表达式）
└── Bash          # 执行系统命令

复合工具层（组合能力）：
├── Task          # 启动子 Agent（并行处理复杂任务）
├── WebFetch      # 获取网页内容并用 LLM 处理
└── WebSearch     # 搜索引擎查询

元工具层（流程控制）：
├── AskUserQuestion  # 向用户提问（多选题形式）
├── TodoWrite        # 任务规划与跟踪
└── ExitPlanMode     # 退出规划模式
```

**关键设计原则**：

1. **单一职责**
   - Read 只读，不搜索
   - Grep 只搜，不修改
   - Edit 只改，不创建
   - 每个工具专注于一件事，做到极致

2. **原子可组合**
   ```
   任务："修复 src/utils.py 中的 bug"

   Claude Code 的执行流程：
   1. Glob("src/**/*.py") → 确认文件存在
   2. Read("src/utils.py") → 查看当前代码
   3. Grep("error pattern") → 定位问题
   4. Edit(old_string, new_string) → 修复 bug
   5. Bash("python -m pytest") → 验证修复
   ```

3. **并行执行**
   - 当多个工具调用无依赖时，一次性发起
   - 减少往返延迟，提升效率

4. **交互式协作**
   - AskUserQuestion 提供结构化选项
   - 用户可以选择预设答案或自定义输入
   - 避免猜测，确保理解正确

### 3.2 Cursor / Kiro / Trae-agent 模式

这些 AI IDE 共享类似的设计理念：

**工具多样性**：
- 文件操作（CRUD）
- 代码搜索（符号查找、引用查找）
- 终端执行（编译、测试、部署）
- 版本控制（Git 操作）
- 语言服务（LSP 集成）

**自适应流程**：
- 不是固定的 Plan → Execute → Reflect
- 而是根据任务类型动态调整
- 简单任务直接执行，复杂任务迭代探索

**上下文感知**：
- 保留完整的执行历史
- 能够"回看"之前的结果
- 支持跨步骤的数据引用

### 3.3 对比分析：AI IDE vs 当前 Agent

| 维度 | AI IDE (Claude Code) | 当前 LangGraph Agent |
|------|---------------------|---------------------|
| **工具数量** | 10+ 个专用工具 | 1 个万能工具 |
| **工具职责** | 单一明确 | 复合臃肿 |
| **组合性** | 高度可组合 | 无法组合 |
| **并行能力** | 支持并行调用 | 只能串行 |
| **用户交互** | 结构化提问 | 无交互能力 |
| **任务管理** | TodoWrite 跟踪 | 无任务管理 |
| **探索能力** | Glob/Grep 发现 | 无探索工具 |
| **数据处理** | Edit/Bash 变换 | 只能获取 |

### 3.4 可借鉴的核心模式

1. **工具分层**：原子 → 复合 → 元工具
2. **单一职责**：每个工具专注一个功能
3. **探索验证**：先发现，再决策
4. **交互协作**：遇到歧义主动询问
5. **任务跟踪**：可视化进度管理
6. **并行执行**：无依赖任务同时进行

---

## 4. V5.0 工具库扩展方案

### 4.1 工具分类体系

基于 AI IDE 模式，为 LangGraph Agent 设计以下工具分类：

```
数据获取层（Source Tools）：
├── fetch_public_data      # 现有：RSSHub 数据获取
├── search_data_sources    # 新增：发现可用数据源
├── preview_data           # 新增：快速预览数据样本
└── fetch_web_content      # 新增：通用网页抓取

数据处理层（Transform Tools）：
├── filter_data            # 新增：条件过滤
├── aggregate_data         # 新增：聚合统计
├── compare_datasets       # 新增：数据集对比
├── extract_insights       # 新增：LLM 驱动的见解提取
└── sort_and_rank          # 新增：排序和排名

私有数据层（Private Tools）：
├── fetch_private_data     # 新增：通用私有数据获取（80% 场景）
├── search_user_notes      # 新增：搜索用户笔记（高频专用）
└── get_user_favorites     # 新增：跨平台收藏聚合（高频专用）

交互控制层（Control Tools）：
├── ask_user_clarification # 新增：向用户提问
├── save_research_result   # 新增：保存研究结果
└── create_subscription    # 新增：创建订阅配置
```

**私有数据架构说明**：
- **通用工具**（fetch_private_data）：处理大部分私有数据场景（B站收藏、GitHub Starred、观看历史等）
- **专用工具**：仅针对高频复杂场景（笔记搜索、跨平台收藏）
- **避免工具爆炸**：不为每个平台每个接口创建独立工具
```

### 4.2 核心工具详细设计

#### 4.2.1 search_data_sources（数据源发现）

**目的**：让 Agent 知道有哪些数据源可用（区分公开/私有），而不是盲目尝试

```python
@tool(registry, plugin_id="search_data_sources")
def search_data_sources(call: ToolCall, context: ToolExecutionContext):
    """
    通过 RAG 检索可用的数据源（公开 + 私有）

    Args:
        query: 自然语言查询（如"B站用户视频"或"我的B站收藏"）
        top_k: 返回候选数量（默认 10）

    Returns:
        {
            "public_sources": [
                {
                    "route_id": "bilibili/user/video",
                    "name": "UP 主投稿",
                    "description": "获取指定 UP 主的视频列表",
                    "access_type": "public",
                    "required_params": ["uid"],
                    "score": 0.95
                }
            ],
            "private_sources": [
                {
                    "route_id": "bilibili/user/favorites",
                    "name": "用户收藏夹",
                    "description": "获取当前用户的收藏夹列表",
                    "access_type": "private",
                    "auth_required": true,
                    "auth_status": "connected",  # connected | not_connected
                    "score": 0.88
                }
            ],
            "query": "B站收藏"
        }
    """
    # 使用现有 RAG 系统，但只返回候选列表，不执行
    retriever = context.rag_retriever
    results = retriever.retrieve(call.args["query"], top_k=call.args.get("top_k", 10))

    # 按 access_type 分组
    public_sources = []
    private_sources = []

    for r in results:
        source_info = {
            "route_id": r.route_id,
            "name": r.name,
            "description": r.description,
            "required_params": r.params,
            "score": r.score,
            "access_type": r.access_type  # 从 RAG Schema 读取
        }

        if r.access_type == "private":
            # 检查用户授权状态
            source_info["auth_required"] = True
            source_info["auth_status"] = _check_auth_status(
                platform=r.platform,
                user_id=context.user_id
            )
            private_sources.append(source_info)
        else:
            public_sources.append(source_info)

    return {
        "public_sources": public_sources,
        "private_sources": private_sources,
        "query": call.args["query"]
    }

def _check_auth_status(platform: str, user_id: Optional[str]) -> str:
    """检查用户是否已授权平台访问"""
    if not user_id:
        return "not_connected"
    # 查询授权服务
    # ...
    return "connected"  # 或 "not_connected"
```

**价值**：
- RAG 检索过程对 Agent 可见
- **区分公开/私有数据源**，Agent 可以据此决策
- **显示授权状态**，未授权时可以提示用户
- Agent 可以从多个候选中智能选择
- 失败时可以尝试备选路由

**关键改进**：
- 返回结果分为 `public_sources` 和 `private_sources`
- 私有数据源包含 `auth_status`，Agent 可以判断是否可用
- 支持提示用户"需要授权 B 站账号"

#### 4.2.2 filter_data（数据过滤）

**目的**：对已获取的数据进行条件筛选

```python
@tool(registry, plugin_id="filter_data")
def filter_data(call: ToolCall, context: ToolExecutionContext):
    """
    根据条件过滤数据

    Args:
        source_ref: 数据引用（指向 data_stash 中的数据）
        conditions: 过滤条件
            - time_range: {"start": "2024-01-01", "end": "2024-01-31"}
            - keywords: ["AI", "机器学习"]
            - exclude_keywords: ["广告"]
            - min_score: 10 (阅读数/点赞数等)

    Returns:
        {
            "filtered_items": [...],
            "original_count": 100,
            "filtered_count": 25,
            "filter_summary": "从 100 条中筛选出 25 条（关键词: AI, 时间: 2024-01）"
        }
    """
    # 从外部存储加载数据
    source_data = context.data_store.load(call.args["source_ref"])
    items = source_data.get("items", [])

    # 应用过滤条件
    filtered = items
    conditions = call.args.get("conditions", {})

    # 时间过滤
    if "time_range" in conditions:
        filtered = _filter_by_time(filtered, conditions["time_range"])

    # 关键词过滤
    if "keywords" in conditions:
        filtered = _filter_by_keywords(filtered, conditions["keywords"])

    # 排除关键词
    if "exclude_keywords" in conditions:
        filtered = _exclude_keywords(filtered, conditions["exclude_keywords"])

    return {
        "filtered_items": filtered,
        "original_count": len(items),
        "filtered_count": len(filtered),
        "filter_summary": _build_filter_summary(conditions, len(items), len(filtered))
    }
```

**价值**：
- 精确筛选感兴趣的数据
- 减少噪声，聚焦核心内容
- 支持多维度过滤

#### 4.2.3 compare_datasets（数据集对比）

**目的**：对比两个或多个数据集的异同

```python
@tool(registry, plugin_id="compare_datasets")
def compare_datasets(call: ToolCall, context: ToolExecutionContext):
    """
    对比多个数据集

    Args:
        dataset_refs: 数据集引用列表
        comparison_type: "intersection" | "difference" | "union" | "trend"
        key_field: 用于匹配的字段（如 "title"、"id"）

    Returns:
        {
            "comparison_type": "difference",
            "results": {
                "only_in_first": [...],   # 只在第一个数据集中
                "only_in_second": [...],  # 只在第二个数据集中
                "common": [...]           # 两者共有
            },
            "statistics": {
                "first_total": 50,
                "second_total": 45,
                "common_count": 20,
                "unique_first": 30,
                "unique_second": 25
            },
            "insights": "第一个数据集有 30 个独特条目，第二个有 25 个，重叠率为 40%"
        }
    """
    datasets = []
    for ref in call.args["dataset_refs"]:
        data = context.data_store.load(ref)
        datasets.append(data.get("items", []))

    comparison_type = call.args.get("comparison_type", "difference")
    key_field = call.args.get("key_field", "title")

    if comparison_type == "difference":
        results = _compute_difference(datasets, key_field)
    elif comparison_type == "intersection":
        results = _compute_intersection(datasets, key_field)
    elif comparison_type == "trend":
        results = _compute_trend(datasets, key_field)

    return {
        "comparison_type": comparison_type,
        "results": results,
        "statistics": _compute_statistics(results),
        "insights": _generate_insights(results, comparison_type)
    }
```

**价值**：
- 发现数据集之间的差异和共性
- 支持趋势分析（时间序列对比）
- 自动生成统计摘要

#### 4.2.4 extract_insights（智能见解提取）

**目的**：使用 LLM 从数据中提取关键见解

```python
@tool(registry, plugin_id="extract_insights")
def extract_insights(call: ToolCall, context: ToolExecutionContext):
    """
    使用 LLM 从数据中提取见解

    Args:
        source_ref: 数据引用
        analysis_type: "summary" | "trends" | "anomalies" | "recommendations"
        focus_areas: 关注的领域（可选）

    Returns:
        {
            "insights": [
                {
                    "type": "trend",
                    "title": "AI Agent 成为热点",
                    "description": "过去一周，AI Agent 相关内容增长 150%",
                    "evidence": ["条目1", "条目2"],
                    "confidence": 0.85
                },
                ...
            ],
            "overall_summary": "...",
            "next_actions": ["建议深入研究 X", "关注 Y 领域"]
        }
    """
    data = context.data_store.load(call.args["source_ref"])
    analysis_type = call.args.get("analysis_type", "summary")

    # 构建 LLM 提示
    prompt = _build_analysis_prompt(
        data=data,
        analysis_type=analysis_type,
        focus_areas=call.args.get("focus_areas", [])
    )

    # 调用 LLM 进行分析
    response = context.analysis_llm.generate(prompt, temperature=0.3)

    # 解析结果
    insights = _parse_insights_response(response)

    return insights
```

**价值**：
- 不仅获取数据，还能理解数据
- 自动发现趋势、异常、模式
- 提供可行动的建议

#### 4.2.5 ask_user_clarification（用户交互）

**目的**：遇到歧义时向用户澄清

```python
@tool(registry, plugin_id="ask_user_clarification")
def ask_user_clarification(call: ToolCall, context: ToolExecutionContext):
    """
    向用户提出澄清问题

    Args:
        question: 要问的问题
        options: 可选答案列表（2-4 个）
        context_info: 为什么需要澄清

    Returns:
        {
            "user_response": "选项2",
            "clarification_received": true
        }

    注意：此工具会触发 REQUEST_HUMAN 状态，等待用户输入
    """
    # 构造澄清请求
    clarification = {
        "question": call.args["question"],
        "options": call.args.get("options", []),
        "context": call.args.get("context_info", ""),
        "tool_call_id": call.step_id
    }

    # 返回特殊标记，触发人类介入
    return ToolExecutionPayload(
        call=call,
        raw_output=clarification,
        status="waiting_for_human",
        requires_human_input=True
    )
```

**价值**：
- 避免猜测，确保理解正确
- 提供结构化选项，降低用户负担
- 支持自定义输入

#### 4.2.6 私有数据工具架构

**核心问题**：如何避免工具爆炸？

每个平台有多个私有数据接口：
- B站：收藏夹、观看历史、关注列表、投币记录、点赞列表、稍后再看...
- GitHub：Starred、Watching、Issues、PRs、Commits、Activity...
- 微信读书：书架、笔记、划线、想法...

如果为每个接口创建独立工具 → **50+ 个工具，无法管理**

**解决方案**：混合架构

```
┌─────────────────────────────────────────────────┐
│ 层次1：通用工具（80% 场景）                     │
│   fetch_private_data(platform, data_type, ...)  │
│                                                  │
│ 层次2：专用工具（15% 高频场景）                 │
│   search_user_notes（知识库）                   │
│   get_user_favorites（跨平台收藏）              │
│                                                  │
│ 层次3：RAG 辅助（5% 长尾场景）                  │
│   search_data_sources → 发现私有数据源          │
└─────────────────────────────────────────────────┘
```

**工具1：fetch_private_data（通用私有数据）**

```python
@tool(registry, plugin_id="fetch_private_data")
def fetch_private_data(call: ToolCall, context: ToolExecutionContext):
    """
    通用私有数据获取工具

    Args:
        platform: 平台名称（bilibili, github, weread...）
        data_type: 数据类型（favorites, history, starred, watching...）
        params: 额外参数（可选）

    适用场景（80%）：
    - B站收藏夹：platform="bilibili", data_type="favorites"
    - GitHub Starred：platform="github", data_type="starred"
    - 观看历史：platform="bilibili", data_type="history"
    - 微信读书书架：platform="weread", data_type="shelf"

    Returns:
        {
            "type": "private_data",
            "platform": "bilibili",
            "data_type": "favorites",
            "items": [...],
            "metadata": {
                "total": 50,
                "cached": true,
                "fetched_at": "2025-01-16T10:00:00Z"
            }
        }
    """
    platform = call.args["platform"]
    data_type = call.args["data_type"]
    params = call.args.get("params", {})

    # 1. 检查用户授权
    auth_service = context.auth_service
    if not auth_service.is_authorized(platform, context.user_id):
        return ToolExecutionPayload(
            call=call,
            status="error",
            error_message=f"需要授权访问 {platform}",
            raw_output={
                "type": "auth_required",
                "platform": platform,
                "auth_url": auth_service.get_auth_url(platform),
                "instructions": f"请先在设置中连接 {platform} 账号"
            }
        )

    # 2. 获取访问凭证
    credentials = auth_service.get_credentials(platform, context.user_id)

    # 3. 调用私有数据服务
    private_data_service = context.private_data_service
    result = private_data_service.fetch(
        platform=platform,
        data_type=data_type,
        credentials=credentials,
        params=params
    )

    return ToolExecutionPayload(
        call=call,
        status="success",
        raw_output={
            "type": "private_data",
            "platform": platform,
            "data_type": data_type,
            "items": result.items,
            "metadata": {
                "total": len(result.items),
                "cached": result.from_cache,
                "fetched_at": result.timestamp.isoformat()
            }
        }
    )
```

**工具2：search_user_notes（高频专用）**

```python
@tool(registry, plugin_id="search_user_notes")
def search_user_notes(call: ToolCall, context: ToolExecutionContext):
    """
    搜索用户笔记（高频场景，独立工具）

    为什么独立：
    1. 高频使用（几乎每次私有数据查询都会用到）
    2. 复杂逻辑（语义搜索 + 全文搜索 + 双向链接）
    3. 特殊处理（标签、时间、层级）

    Args:
        query: 搜索关键词
        top_k: 返回数量（默认 5）
        filters: 可选过滤条件（tags, date_range）
    """
    # 对接知识库系统
    note_backend = context.note_backend
    if not note_backend:
        raise RuntimeError("知识库系统未初始化")

    query = call.args["query"]
    top_k = call.args.get("top_k", 5)
    filters = call.args.get("filters", {})

    # 混合搜索：语义 + 全文
    results = note_backend.search(
        query=query,
        top_k=top_k,
        filters=filters
    )

    return {
        "notes": [
            {
                "note_id": r.id,
                "title": r.title,
                "excerpt": r.excerpt,
                "tags": r.tags,
                "backlinks": r.backlinks,  # 双向链接
                "created_at": r.created_at.isoformat(),
                "relevance_score": r.score
            }
            for r in results
        ],
        "total": len(results)
    }
```

**工具3：get_user_favorites（跨平台聚合）**

```python
@tool(registry, plugin_id="get_user_favorites")
def get_user_favorites(call: ToolCall, context: ToolExecutionContext):
    """
    获取用户收藏（跨平台聚合）

    为什么独立：
    1. 跨平台聚合（B站 + GitHub + 微信读书 + ...）
    2. 统一格式返回
    3. 高频场景（"我最近收藏了什么"）

    Args:
        platform: 平台筛选（all | bilibili | github | weread）
        time_range: 时间范围（可选）
        limit: 数量限制（默认 50）
    """
    platform = call.args.get("platform", "all")
    time_range = call.args.get("time_range")
    limit = call.args.get("limit", 50)

    favorites_service = context.favorites_service

    if platform == "all":
        # 聚合所有平台
        results = favorites_service.get_all_favorites(
            user_id=context.user_id,
            time_range=time_range,
            limit=limit
        )
    else:
        # 单个平台
        results = favorites_service.get_platform_favorites(
            platform=platform,
            user_id=context.user_id,
            time_range=time_range,
            limit=limit
        )

    return {
        "favorites": results.items,
        "grouped_by_platform": results.group_by_platform(),
        "statistics": {
            "total": len(results.items),
            "by_platform": results.count_by_platform(),
            "time_range": time_range
        }
    }
```

**RAG Schema 扩展**

为了支持公私数据区分，需要在 `datasource_definitions.json` 中增加字段：

```json
{
    "route_id": "bilibili/user/favorites",
    "name": "用户收藏夹",
    "description": "获取当前用户的收藏夹列表",
    "platform": "bilibili",
    "access_type": "private",      // 新增：public | private | hybrid
    "auth_required": true,          // 新增：是否需要登录
    "data_category": "favorites",   // 新增：数据类别（用于通用工具）
    "params": []
}

{
    "route_id": "bilibili/user/video",
    "name": "UP 主投稿",
    "description": "获取指定 UP 主的视频列表",
    "platform": "bilibili",
    "access_type": "public",        // 公开数据
    "auth_required": false,
    "params": [
        {"name": "uid", "type": "string", "parameter_type": "entity_ref"}
    ]
}
```

**工具选择逻辑**

```
用户查询："我最近收藏了哪些 AI 相关的内容？"

1. Planner 识别关键词："我的" → 私有数据查询
2. 调用 search_data_sources(query="收藏")
3. 返回：
   - private_sources: [bilibili/favorites (connected), github/starred (not_connected)]
4. Planner 决策：
   - 优先使用高频工具：get_user_favorites(platform="all")
   - 备选：fetch_private_data(platform="bilibili", data_type="favorites")
5. 执行 get_user_favorites → 获取跨平台收藏
6. filter_data(keywords=["AI"]) → 过滤 AI 相关
7. Synthesizer 生成报告
```

**工具设计原则总结**

| 场景 | 工具类型 | 示例 | 理由 |
|------|---------|------|------|
| **高频 + 复杂** | 专用工具 | search_user_notes, get_user_favorites | 优化体验、复杂逻辑 |
| **通用场景** | 通用工具 | fetch_private_data | 覆盖 80% 长尾场景 |
| **探索发现** | RAG 辅助 | search_data_sources | 动态发现可用接口 |

**价值**：
- **避免工具爆炸**：不需要为每个接口创建工具
- **灵活扩展**：新增平台只需更新 Schema + 实现数据服务
- **智能决策**：Agent 知道哪些数据需要授权，可以提示用户
- **高频优化**：常用场景（笔记、收藏）有专用工具

### 4.3 工具实现优先级

| 优先级 | 工具 | 价值 | 复杂度 | 预计工时 |
|--------|------|------|--------|----------|
| 🔴 P0 | search_data_sources | 让 RAG 可见、可调、区分公私 | 低 | 0.5天 |
| 🔴 P0 | filter_data | 基础数据处理 | 低 | 0.5天 |
| 🔴 P0 | ask_user_clarification | 交互式协作 | 中 | 1天 |
| 🟡 P1 | compare_datasets | 多源对比分析 | 中 | 1天 |
| 🟡 P1 | extract_insights | 智能分析 | 中 | 1天 |
| 🟡 P1 | aggregate_data | 统计聚合 | 低 | 0.5天 |
| 🟡 P1 | fetch_private_data | 通用私有数据获取 | 中 | 1.5天 |
| 🟡 P1 | search_user_notes | 笔记搜索（高频专用） | 中 | 1天 |
| 🟢 P2 | get_user_favorites | 跨平台收藏聚合 | 中 | 1天 |
| 🟢 P2 | preview_data | 快速预览 | 低 | 0.5天 |
| 🟢 P2 | fetch_web_content | 通用网页 | 中 | 1天 |

**P0 优先理由**：
- search_data_sources：解决 RAG 黑盒问题 + 公私数据区分
- filter_data：解决数据处理缺失问题
- ask_user_clarification：解决交互缺失问题

**P1 新增私有数据工具**：
- fetch_private_data：通用私有数据工具（80% 场景）
- search_user_notes：知识库检索（高频场景）
- 这两个工具完成后，Agent 可以访问用户私有数据

**工具数量控制**：
- 总计 11 个工具（避免工具爆炸）
- 私有数据采用混合架构：1 个通用工具 + 2 个专用工具
- 长尾场景通过 RAG 辅助发现

完成 P0 后，Agent 能力将质变。完成 P1 后，支持私有数据分析。

### 4.4 工具注册与 Prompt 集成

**更新 PlannerAgent Prompt**：

```python
def create_planner_node_v5(runtime):
    # 动态获取所有可用工具
    tool_specs = runtime.tool_registry.list_tools()

    # 构建工具描述
    tools_description = """
你可以使用以下工具：

**数据获取类**：
- search_data_sources(query, top_k=5): 发现可用的数据源，返回候选路由列表
- fetch_public_data(query, filter_datasource=None): 从 RSSHub 获取数据

**数据处理类**：
- filter_data(source_ref, conditions): 过滤数据（按时间、关键词等）
- compare_datasets(dataset_refs, comparison_type): 对比多个数据集
- aggregate_data(source_ref, group_by, metrics): 聚合统计数据
- extract_insights(source_ref, analysis_type): 使用 AI 提取见解

**交互控制类**：
- ask_user_clarification(question, options): 向用户提问澄清

**重要原则**：
1. 先探索再行动：不确定时先用 search_data_sources 发现可用数据源
2. 渐进式处理：获取数据后，根据需要进行过滤、对比、分析
3. 主动澄清：遇到歧义时使用 ask_user_clarification
4. 关注结果质量：不满意时可以尝试其他数据源或过滤条件
"""

    # ... 构建完整 Prompt
```

---

## 5. Agent 流程优化方案

### 5.1 当前流程的问题

**问题1：所有操作走同一重流程**

```
当前：每个工具调用都走完整循环
Planner → ToolExecutor → DataStasher → Reflector

问题：
- 轻量探索（search_data_sources）也要存储+摘要
- 简单查询（preview_data）也要反思决策
- 增加延迟，浪费资源
```

**问题2：每次只能规划一步**

```
当前：Planner 每次输出一个 ToolCall

问题：
- 无法表达"先获取 A，再过滤 A"的依赖链
- 无法并行执行多个独立任务
- 无法提前规划多步策略
```

**问题3：反思逻辑过于简单**

```
当前：Reflector 只看摘要，决定 CONTINUE/FINISH/REQUEST_HUMAN

问题：
- 无法判断数据质量是否满意
- 无法决定是否尝试其他数据源
- 无法识别部分失败需要重试
```

### 5.2 优化方案：引入轻量模式

**核心思路**：区分探索类工具和执行类工具，不同流程

```
探索类工具（轻量模式）：
- search_data_sources
- preview_data
- ask_user_clarification

特点：
- 不经过 DataStasher（结果直接返回给 Planner）
- 不触发 Reflector（继续规划）
- 快速迭代，低延迟

执行类工具（完整模式）：
- fetch_public_data
- filter_data
- extract_insights

特点：
- 经过 DataStasher（存储 + 摘要）
- 触发 Reflector（决策下一步）
- 确保数据质量和可追溯性
```

**实现方案**：

```python
# 在 ToolSpec 中添加模式标记
class ToolSpec(BaseModel):
    plugin_id: str
    description: str
    schema: Dict[str, Any]
    execution_mode: Literal["lightweight", "full"] = "full"  # 新增

# 工具注册时指定模式
@tool(
    registry,
    plugin_id="search_data_sources",
    execution_mode="lightweight"  # 轻量模式
)
def search_data_sources(...):
    ...

# 工作流中根据模式路由
def _after_tool_execution(state: GraphState) -> str:
    tool_call = state.get("next_tool_call")
    tool_spec = registry.get_spec(tool_call.plugin_id)

    if tool_spec.execution_mode == "lightweight":
        # 轻量模式：直接返回 Planner，跳过 Stasher 和 Reflector
        return "to_planner_with_result"
    else:
        # 完整模式：走标准流程
        return "to_data_stasher"
```

### 5.3 优化方案：支持多步规划

**核心思路**：PlannerAgent 可以输出多个 ToolCall，支持依赖链

**方案1：执行图（Execution Graph）**

```python
# 新的规划输出格式
class ExecutionPlan(BaseModel):
    steps: List[ToolCallV5] = []
    dependencies: Dict[str, List[str]] = {}  # step_id -> [dependency_ids]

# PlannerAgent 输出示例
{
    "steps": [
        {
            "step_id": "A",
            "plugin_id": "search_data_sources",
            "args": {"query": "GitHub trending"},
            "description": "发现 GitHub 趋势数据源"
        },
        {
            "step_id": "B",
            "plugin_id": "fetch_public_data",
            "args": {"query": "GitHub trending", "route_hint": "${A.candidates[0]}"},
            "description": "获取 GitHub 趋势数据"
        },
        {
            "step_id": "C",
            "plugin_id": "filter_data",
            "args": {"source_ref": "${B}", "conditions": {"keywords": ["AI"]}},
            "description": "过滤 AI 相关内容"
        }
    ],
    "dependencies": {
        "B": ["A"],  # B 依赖 A
        "C": ["B"]   # C 依赖 B
    }
}
```

**方案2：结合 V4.4 的 StashReference**

```python
# 利用 V4.4 已设计的显式依赖
class ToolCallV5(BaseModel):
    step_id: str
    plugin_id: str
    args: Dict[str, Union[Any, StashReference]]  # 支持依赖引用
    human_readable_label: str

# 执行引擎根据依赖关系调度
def execute_plan(plan: ExecutionPlan, context):
    completed = {}

    while len(completed) < len(plan.steps):
        # 找到所有依赖已满足的步骤
        ready_steps = [
            step for step in plan.steps
            if step.step_id not in completed
            and all(dep in completed for dep in plan.dependencies.get(step.step_id, []))
        ]

        # 并行执行就绪步骤
        results = parallel_execute(ready_steps, context, completed)
        completed.update(results)

    return completed
```

### 5.4 优化方案：增强反思能力

**核心思路**：Reflector 不仅看摘要，还要检查数据质量和任务完成度

```python
def create_reflector_node_v5(runtime):
    def node(state: GraphState) -> GraphState:
        # 1. 检查数据质量
        quality_check = _check_data_quality(state["data_stash"])

        # 2. 检查任务完成度
        completion_check = _check_task_completion(
            original_query=state["original_query"],
            collected_data=state["data_stash"]
        )

        # 3. 检查是否有部分失败需要重试
        retry_needed = _check_retry_needed(state["data_stash"])

        # 4. 构建反思 Prompt
        prompt = f"""
        原始查询: {state["original_query"]}

        已收集数据:
        {_format_data_summaries(state["data_stash"])}

        数据质量评估:
        - 数据完整性: {quality_check["completeness"]}
        - 数据新鲜度: {quality_check["freshness"]}
        - 数据相关性: {quality_check["relevance"]}

        任务完成度:
        - 已完成子任务: {completion_check["completed"]}
        - 未完成子任务: {completion_check["pending"]}

        需要重试的步骤: {retry_needed}

        请决策:
        1. CONTINUE_FETCH: 继续获取更多数据
        2. CONTINUE_ANALYZE: 对现有数据进行分析
        3. RETRY_FAILED: 重试失败的步骤
        4. CLARIFY_USER: 需要用户澄清
        5. FINISH: 数据足够，生成报告
        """

        # 5. 调用 LLM 决策
        decision = runtime.reflector_llm.generate(prompt)

        return {"reflection": _parse_reflection_v5(decision)}

    return node
```

### 5.5 新工作流程图

```
START
  ↓
RouterAgent
  ├─→ [simple_chat] → LLM 响应 → END
  │
  └─→ [complex_research]
         ↓
    PlannerAgent (输出多步计划)
         ↓
    ExecutionEngine ─────────────────┐
         │                           │
         ├─→ [轻量工具] → 直接返回   │
         │       结果给 Planner      │
         │                           │
         └─→ [完整工具] → DataStasher
                             ↓
                      ReflectorAgent ─────┐
                           │              │
                           ├─→ CONTINUE_FETCH → 回到 Planner
                           │
                           ├─→ CONTINUE_ANALYZE → 回到 Planner
                           │
                           ├─→ RETRY_FAILED → 回到 Executor
                           │
                           ├─→ CLARIFY_USER → 等待用户
                           │
                           └─→ FINISH → SynthesizerAgent → END
```

---

## 6. 数据流与状态管理改进

### 6.1 当前数据流问题

**问题1：数据结构过于扁平**

```python
# 当前：data_stash 是线性列表
data_stash: List[DataReference] = [
    DataReference(step_id=1, tool_name="fetch_public_data", ...),
    DataReference(step_id=2, tool_name="fetch_public_data", ...),
    DataReference(step_id=3, tool_name="filter_data", ...),
]

# 问题：无法表达数据之间的关系
# - 哪些数据集可以对比？
# - 哪些是原始数据，哪些是处理后的？
# - 如何追踪数据血缘？
```

**问题2：摘要丢失细节**

```python
# 当前：DataStasher 生成简短摘要
summary = "获取了 50 条 B 站视频数据"

# 问题：
# - Agent 无法知道具体有哪些字段
# - 无法判断数据是否满足需求
# - 无法进行精确的后续处理
```

**问题3：小数据也走外部存储**

```python
# 当前：所有数据都存到外部
data_id = runtime.data_store.save(raw_output)

# 问题：
# - 探索结果（如候选路由列表）也要存储
# - 增加 IO 延迟
# - 摘要过程丢失信息
```

### 6.2 改进方案：分层数据存储

**核心思路**：区分工作记忆（快速访问）和外部存储（持久化）

```python
class GraphStateV5(TypedDict):
    # 原有字段
    original_query: str
    data_stash: List[DataReference]  # 外部存储引用
    reflection: Optional[Reflection]
    final_report: Optional[str]

    # 新增：工作记忆（直接在状态中）
    working_memory: Dict[str, Any]  # 小数据直接存储
    knowledge_graph: KnowledgeGraph  # 语义化数据组织

# 工作记忆示例
working_memory = {
    "discovered_sources": [  # 轻量工具结果
        {"route_id": "github/trending", "score": 0.95},
        {"route_id": "hackernews/best", "score": 0.88}
    ],
    "user_clarifications": {  # 用户澄清结果
        "time_range": "last_week",
        "focus_area": "AI"
    },
    "current_step": 3,
    "total_planned_steps": 5
}
```

**存储策略**：

| 数据类型 | 大小阈值 | 存储位置 | 原因 |
|----------|----------|----------|------|
| 探索结果 | <1KB | 工作记忆 | 需要快速访问，频繁引用 |
| 用户澄清 | <1KB | 工作记忆 | 影响后续所有决策 |
| 元数据 | <10KB | 工作记忆 | Schema、统计信息 |
| RSS 数据 | >10KB | 外部存储 | 避免上下文溢出 |
| 分析结果 | 视情况 | 混合 | 摘要在工作记忆，详情在外部 |

### 6.3 改进方案：语义化知识图谱

**核心思路**：用图结构组织数据关系，而不是扁平列表

```python
class KnowledgeNode(BaseModel):
    node_id: str
    node_type: Literal["dataset", "analysis", "insight", "source"]
    metadata: Dict[str, Any]
    created_at: datetime
    source_step: int

class KnowledgeEdge(BaseModel):
    from_node: str
    to_node: str
    relation: str  # "derived_from", "compared_with", "filtered_from"

class KnowledgeGraph(BaseModel):
    nodes: Dict[str, KnowledgeNode] = {}
    edges: List[KnowledgeEdge] = []

    def add_dataset(self, data_ref: DataReference, metadata: Dict):
        node = KnowledgeNode(
            node_id=data_ref.data_id,
            node_type="dataset",
            metadata=metadata,
            source_step=data_ref.step_id
        )
        self.nodes[node.node_id] = node

    def add_derivation(self, source_id: str, derived_id: str, operation: str):
        edge = KnowledgeEdge(
            from_node=source_id,
            to_node=derived_id,
            relation=f"derived_from_{operation}"
        )
        self.edges.append(edge)

    def find_comparable_datasets(self) -> List[Tuple[str, str]]:
        """找到可以对比的数据集（同类型、同时间范围）"""
        ...

    def trace_data_lineage(self, node_id: str) -> List[str]:
        """追踪数据血缘"""
        ...
```

**使用示例**：

```python
# 场景：用户问"对比 GitHub 和 HackerNews 上的 AI 热点"

# 步骤1：获取 GitHub 数据
kg.add_dataset(
    data_ref=github_ref,
    metadata={
        "source": "github",
        "topic": "AI",
        "time_range": "last_week",
        "item_count": 50
    }
)

# 步骤2：获取 HackerNews 数据
kg.add_dataset(
    data_ref=hn_ref,
    metadata={
        "source": "hackernews",
        "topic": "AI",
        "time_range": "last_week",
        "item_count": 45
    }
)

# 步骤3：Planner 查询知识图谱
comparable = kg.find_comparable_datasets()
# 返回: [("github_data_id", "hackernews_data_id")]

# 步骤4：执行对比
kg.add_analysis(
    analysis_id="comparison_1",
    source_datasets=[github_ref.data_id, hn_ref.data_id],
    analysis_type="difference"
)
kg.add_derivation(github_ref.data_id, "comparison_1", "compared")
kg.add_derivation(hn_ref.data_id, "comparison_1", "compared")

# 步骤5：Reflector 检查
# - 有 2 个数据集
# - 已执行对比分析
# - 知识图谱显示完整的处理链路
# → 决策：FINISH
```

### 6.4 改进方案：智能摘要增强

**核心思路**：摘要不仅是文本，还包含结构化元数据

```python
class EnhancedDataReference(DataReference):
    # 原有字段
    step_id: int
    tool_name: str
    data_id: str
    summary: str
    status: Literal["success", "error"]

    # 新增：结构化元数据
    schema_info: Dict[str, str] = {}  # 字段名 -> 类型
    statistics: Dict[str, Any] = {}   # 统计信息
    sample_items: List[Dict] = []     # 样本数据（前3条）
    quality_score: float = 0.0        # 数据质量评分

# DataStasher 增强
def create_data_stasher_node_v5(runtime):
    def node(state: GraphState):
        pending = state.get("pending_tool_result")

        # 1. 存储原始数据
        data_id = runtime.data_store.save(pending.raw_output)

        # 2. 提取结构化元数据
        schema_info = _extract_schema(pending.raw_output)
        statistics = _compute_statistics(pending.raw_output)
        sample_items = _get_sample_items(pending.raw_output, n=3)

        # 3. 计算数据质量评分
        quality_score = _assess_data_quality(
            pending.raw_output,
            state["original_query"]
        )

        # 4. 生成智能摘要
        summary = _generate_smart_summary(
            raw_output=pending.raw_output,
            schema=schema_info,
            stats=statistics,
            quality=quality_score
        )

        # 5. 创建增强引用
        data_ref = EnhancedDataReference(
            step_id=pending.call.step_id,
            tool_name=pending.call.plugin_id,
            data_id=data_id,
            summary=summary,
            status=pending.status,
            schema_info=schema_info,
            statistics=statistics,
            sample_items=sample_items,
            quality_score=quality_score
        )

        # 6. 更新知识图谱
        state["knowledge_graph"].add_dataset(data_ref, {
            "source": pending.call.args.get("source", "unknown"),
            "query": pending.call.args.get("query", ""),
            **statistics
        })

        return {"data_stash": [..., data_ref]}

    return node

def _generate_smart_summary(raw_output, schema, stats, quality):
    """
    生成结构化摘要，包含关键信息
    """
    return f"""
数据摘要:
- 来源: {raw_output.get("source", "unknown")}
- 记录数: {stats.get("count", 0)}
- 字段: {", ".join(schema.keys())}
- 时间范围: {stats.get("time_range", "unknown")}
- 质量评分: {quality:.2f}

示例数据:
{_format_sample_items(raw_output.get("items", [])[:3])}

统计信息:
{_format_statistics(stats)}
"""
```

### 6.5 数据访问模式优化

**优化1：懒加载外部数据**

```python
# 当前：每次都加载完整数据
data = runtime.data_store.load(data_id)

# 优化：按需加载
class LazyDataLoader:
    def __init__(self, data_store, data_id):
        self.data_store = data_store
        self.data_id = data_id
        self._cache = None

    def get_metadata(self) -> Dict:
        """只获取元数据，不加载完整数据"""
        return self.data_store.get_metadata(self.data_id)

    def get_items(self, start=0, limit=10) -> List:
        """分页加载"""
        return self.data_store.get_items(self.data_id, start, limit)

    def get_full(self) -> Any:
        """加载完整数据（必要时使用）"""
        if self._cache is None:
            self._cache = self.data_store.load(self.data_id)
        return self._cache
```

**优化2：数据过期策略**

```python
# 工作记忆清理
def cleanup_working_memory(state: GraphState):
    """清理不再需要的工作记忆"""
    memory = state.get("working_memory", {})

    # 保留最近 10 步的探索结果
    # 清理过期的临时数据
    # 保留所有用户澄清（重要）

    return filtered_memory
```

---

## 7. 渐进式实施路线图

### 7.1 阶段划分总览

| 阶段 | 目标 | 核心改动 | 预计工时 | 风险等级 |
|------|------|----------|----------|----------|
| **Phase 1** | P0 工具扩展 | 新增 3 个核心工具 | 2 天 | 🟢 低 |
| **Phase 2** | 轻量模式支持 | 工具分类 + 流程分流 | 1.5 天 | 🟡 中 |
| **Phase 3** | P1 工具扩展 | 新增 3 个分析工具 | 2.5 天 | 🟢 低 |
| **Phase 4** | 多步规划 | 执行图 + 依赖解析 | 3 天 | 🟡 中 |
| **Phase 5** | 数据流优化 | 知识图谱 + 智能摘要 | 3 天 | 🟡 中 |
| **Phase 6** | 私有数据接入 | 用户笔记搜索 | 2 天 | 🟡 中 |

**总工时**：约 14 天（3 周）

### 7.2 Phase 1：P0 工具扩展（2 天）

**目标**：实现最小可行改进，立即提升 Agent 能力

**Day 1：探索与过滤工具**

```bash
# 新增文件
langgraph_agents/tools/
├── source_discovery.py    # search_data_sources 实现
└── data_filter.py         # filter_data 实现

# 修改文件
langgraph_agents/tools/registry.py  # 添加工具注册
langgraph_agents/agents/planner.py  # 更新 Prompt 包含新工具
```

**任务清单**：

1. [ ] 实现 `search_data_sources` 工具
   - 复用现有 RAG 检索器
   - 只返回候选列表，不执行获取
   - 返回格式包含 route_id, name, description, score

2. [ ] 实现 `filter_data` 工具
   - 从外部存储加载数据
   - 支持时间过滤、关键词过滤
   - 返回过滤统计信息

3. [ ] 更新工具注册表
   - 注册新工具到 ToolRegistry
   - 添加工具描述和 Schema

4. [ ] 更新 PlannerAgent Prompt
   - 列出所有可用工具
   - 提供使用指南和示例

**Day 2：用户交互工具**

5. [ ] 实现 `ask_user_clarification` 工具
   - 构造澄清请求
   - 返回特殊状态触发人类介入
   - 支持多选项结构化提问

6. [ ] 修改 Reflector 支持 CLARIFY_USER 决策
   - 新增决策类型
   - 路由到等待用户输入节点

7. [ ] 单元测试
   - 每个工具独立测试
   - 集成测试验证完整流程

**验收标准**：
- [ ] 3 个新工具注册成功
- [ ] PlannerAgent 能够选择使用新工具
- [ ] 用户澄清流程可以正常运行
- [ ] 所有测试通过

### 7.3 Phase 2：轻量模式支持（1.5 天）

**目标**：探索类工具跳过数据存储，提升效率

**任务清单**：

1. [ ] 扩展 ToolSpec 数据结构
   ```python
   class ToolSpec(BaseModel):
       execution_mode: Literal["lightweight", "full"] = "full"
   ```

2. [ ] 标记工具执行模式
   - search_data_sources → lightweight
   - ask_user_clarification → lightweight
   - filter_data → full
   - fetch_public_data → full

3. [ ] 修改工作流路由逻辑
   - ToolExecutor 后根据模式分流
   - lightweight → 直接返回 Planner
   - full → 进入 DataStasher

4. [ ] 扩展 GraphState
   ```python
   class GraphState(TypedDict):
       working_memory: Dict[str, Any]  # 存储轻量工具结果
   ```

5. [ ] 修改 PlannerAgent 读取工作记忆
   - 访问 `state["working_memory"]`
   - 利用探索结果规划下一步

6. [ ] 集成测试
   - 验证轻量模式跳过存储
   - 验证工作记忆正确传递

**验收标准**：
- [ ] 轻量工具不触发 DataStasher
- [ ] 工作记忆正确维护
- [ ] 端到端流程测试通过

### 7.4 Phase 3：P1 工具扩展（2.5 天）

**目标**：实现数据分析能力，让 Agent 不仅获取数据还能理解数据

**任务清单**：

1. [ ] 实现 `compare_datasets` 工具
   - 支持交集、差集、并集、趋势分析
   - 自动生成统计摘要
   - 返回结构化对比结果

2. [ ] 实现 `extract_insights` 工具
   - 使用 LLM 提取见解
   - 支持趋势、异常、推荐分析
   - 返回带置信度的见解列表

3. [ ] 实现 `aggregate_data` 工具
   - 支持分组统计
   - 计算平均值、最大值、最小值等
   - 返回聚合结果

4. [ ] 更新 PlannerAgent Prompt
   - 添加分析工具使用指南
   - 提供复杂分析任务示例

5. [ ] 端到端测试
   - 测试"对比两个数据源"场景
   - 测试"提取 AI 趋势"场景

**验收标准**：
- [ ] 3 个分析工具实现完成
- [ ] 能够完成简单的对比分析任务
- [ ] 所有测试通过

### 7.5 Phase 4：多步规划（3 天）

**目标**：PlannerAgent 能输出多步计划，支持依赖链

**任务清单**：

1. [ ] 定义 ExecutionPlan 数据结构
   ```python
   class ExecutionPlan(BaseModel):
       steps: List[ToolCallV5]
       dependencies: Dict[str, List[str]]
   ```

2. [ ] 修改 PlannerAgent 输出格式
   - 从单个 ToolCall 改为 ExecutionPlan
   - 支持依赖声明

3. [ ] 实现 ExecutionEngine
   - 解析依赖关系
   - 调度就绪任务
   - 支持并行执行（基于 V4.4 的 asyncio）

4. [ ] 实现依赖解析（StashReference）
   - 参考 V4.4 的 ArgumentValue 设计
   - 支持 JSONPath 提取

5. [ ] 修改工作流图
   - Planner → ExecutionEngine → DataStasher
   - 支持批量处理

6. [ ] 全面测试
   - 测试依赖链执行
   - 测试并行任务
   - 性能测试

**验收标准**：
- [ ] Planner 能输出多步计划
- [ ] ExecutionEngine 正确调度任务
- [ ] 依赖关系正确解析
- [ ] 并行执行正常工作

### 7.6 Phase 5：数据流优化（3 天）

**目标**：引入知识图谱和智能摘要，提升数据组织能力

**任务清单**：

1. [ ] 实现 KnowledgeGraph 数据结构
   - 节点：数据集、分析、见解
   - 边：衍生关系、对比关系

2. [ ] 实现 EnhancedDataReference
   - 添加 schema_info、statistics、sample_items
   - 添加 quality_score

3. [ ] 增强 DataStasher
   - 提取结构化元数据
   - 生成智能摘要
   - 更新知识图谱

4. [ ] 增强 Reflector
   - 访问知识图谱
   - 检查数据血缘
   - 更智能的决策

5. [ ] 实现 GraphRenderer（可选）
   - 可视化知识图谱
   - 前端展示执行过程

6. [ ] 集成测试
   - 验证知识图谱正确构建
   - 验证智能摘要包含关键信息

**验收标准**：
- [ ] 知识图谱正确记录数据关系
- [ ] 智能摘要包含 Schema 和统计信息
- [ ] Reflector 能利用知识图谱决策

### 7.7 Phase 6：私有数据接入（2 天）

**目标**：连接用户私有数据，实现个性化分析

**任务清单**：

1. [ ] 实现 `search_user_notes` 工具
   - 对接知识库系统（knowledge-base-design.md）
   - 支持语义搜索
   - 返回相关笔记片段

2. [ ] 更新 ToolExecutionContext
   ```python
   @dataclass
   class ToolExecutionContext:
       note_backend: Optional[NoteSearchBackend]  # 已有接口
   ```

3. [ ] 更新 PlannerAgent
   - 在私有数据相关查询时优先考虑笔记搜索
   - 示例："结合我的笔记，分析 AI Agent 趋势"

4. [ ] 端到端测试
   - 公共数据 + 私有笔记联合分析
   - 验证数据融合正确

**验收标准**：
- [ ] 能搜索用户笔记
- [ ] 公私数据可以联合分析
- [ ] 测试通过

### 7.8 里程碑与检查点

```
Week 1:
├── Day 1-2: Phase 1 - P0 工具扩展 ✓
├── Day 3-4: Phase 2 - 轻量模式 ✓
└── Day 5: Phase 3 开始 - P1 工具

Week 2:
├── Day 6-7: Phase 3 完成 - P1 工具 ✓
├── Day 8-10: Phase 4 - 多步规划 ✓

Week 3:
├── Day 11-13: Phase 5 - 数据流优化 ✓
└── Day 14-15: Phase 6 - 私有数据 ✓

检查点:
- Phase 1 后: Agent 能使用探索和过滤工具
- Phase 2 后: 轻量工具执行更快
- Phase 3 后: Agent 能进行数据分析
- Phase 4 后: 支持复杂多步任务
- Phase 5 后: 数据组织更智能
- Phase 6 后: 私有数据可访问
```

---

## 8. 风险评估与缓解策略

### 8.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **LLM 理解新工具困难** | 高 | 中 | 提供详细使用示例；渐进式添加工具；Few-shot 提示 |
| **多步规划过于复杂** | 中 | 中 | 先支持简单依赖链；分阶段实现；保留单步回退能力 |
| **知识图谱性能问题** | 中 | 低 | 限制图大小；使用高效数据结构；定期清理 |
| **向后兼容性破坏** | 高 | 低 | 保留旧接口；添加兼容层；充分测试 |
| **工具调用失败率上升** | 中 | 中 | 增强错误处理；自动重试；备选方案 |

### 8.2 架构风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **状态膨胀** | 中 | 中 | 工作记忆定期清理；大数据外部存储；压缩策略 |
| **循环依赖** | 高 | 低 | 严格的依赖检查；DAG 验证；超时保护 |
| **上下文溢出** | 高 | 低 | 摘要优化；选择性信息包含；Token 计数监控 |

### 8.3 项目风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **工期延长** | 中 | 高 | 优先完成 P0；可选功能后移；增量交付 |
| **需求变化** | 中 | 中 | 模块化设计；接口抽象；文档同步 |
| **测试覆盖不足** | 高 | 中 | 每个 Phase 必须包含测试；CI 集成；代码审查 |

### 8.4 缓解策略详解

**策略1：保持向后兼容**

```python
# 保留旧的单步规划能力
def create_planner_node_v5(runtime):
    def node(state):
        # 检查配置：是否启用多步规划
        if runtime.config.get("enable_multi_step_planning", False):
            return _plan_multi_step(state)
        else:
            return _plan_single_step(state)  # 回退到 V2 行为
```

**策略2：渐进式工具添加**

```
Week 1: 只启用 search_data_sources, filter_data
Week 2: 添加 compare_datasets, extract_insights
Week 3: 添加私有数据工具

每次添加新工具后：
1. 更新 Prompt
2. 添加使用示例
3. 运行集成测试
4. 观察 Agent 行为
5. 根据需要调整
```

**策略3：监控与告警**

```python
# 添加性能监控
class AgentMetrics:
    def record_tool_call(self, tool_id, duration, success):
        ...

    def record_planning_time(self, num_steps, duration):
        ...

    def record_state_size(self, working_memory_kb, data_stash_count):
        ...

# 告警阈值
ALERTS = {
    "planning_time_max": 30,  # 秒
    "working_memory_max": 100,  # KB
    "data_stash_max": 50,  # 条目数
    "tool_failure_rate_max": 0.3
}
```

---

## 9. 成功指标与验收标准

### 9.1 功能指标

| 指标 | 基线（V2） | 目标（V5） | 验证方法 |
|------|------------|------------|----------|
| **可用工具数** | 1 | 8+ | 工具注册表计数 |
| **支持任务类型** | 数据获取 | 获取+过滤+分析+对比 | 端到端测试用例 |
| **多步任务支持** | 否 | 是 | 执行包含依赖的任务 |
| **用户交互** | 无 | 结构化提问 | 交互流程测试 |
| **数据处理能力** | 无 | 过滤/聚合/对比 | 数据处理测试 |

### 9.2 性能指标

| 指标 | 基线 | 目标 | 测量方法 |
|------|------|------|----------|
| **轻量工具延迟** | N/A | <500ms | 计时测量 |
| **多步任务总时长** | 串行累加 | 并行优化 30%+ | 端到端计时 |
| **工作记忆大小** | 0 | <100KB | 状态大小监控 |
| **摘要信息完整度** | 仅文本 | 文本+Schema+统计 | 人工评审 |

### 9.3 质量指标

| 指标 | 目标 | 验证方法 |
|------|------|----------|
| **测试覆盖率** | ≥80% | pytest-cov |
| **代码规范** | 符合 CLAUDE.md | 人工审查 |
| **文档完整性** | 所有新组件有文档 | 文档审查 |
| **向后兼容** | 现有测试 100% 通过 | CI 测试 |

### 9.4 业务指标

| 场景 | V2 能力 | V5 预期能力 |
|------|---------|-------------|
| "获取 B 站热门视频" | ✓ 可以 | ✓ 可以 |
| "获取并过滤 AI 相关内容" | ✗ 不行 | ✓ 获取 → 过滤 |
| "对比 GitHub 和 HN 热点" | ✗ 不行 | ✓ 获取两者 → 对比 |
| "分析近期 AI 趋势" | ✗ 不行 | ✓ 获取 → 过滤 → 提取见解 |
| "不确定时询问用户" | ✗ 不行 | ✓ ask_user_clarification |
| "结合我的笔记分析" | ✗ 不行 | ✓ 公共数据 + 私有笔记 |

### 9.5 验收测试用例

**用例1：探索性查询**

```
用户: "有哪些关于 AI Agent 的数据源？"

预期行为:
1. Planner 调用 search_data_sources(query="AI Agent")
2. 返回候选路由列表（GitHub、HackerNews、知乎等）
3. Agent 向用户展示可用选项

验收标准:
- [ ] RAG 检索结果对 Agent 可见
- [ ] 返回结构化候选列表
- [ ] 用户可以看到选项
```

**用例2：过滤分析**

```
用户: "获取 GitHub trending 的 AI 项目，只要过去一周的"

预期行为:
1. Planner: fetch_public_data → filter_data
2. 获取 GitHub trending
3. 按时间过滤
4. 返回过滤后的结果

验收标准:
- [ ] 成功获取数据
- [ ] 正确应用时间过滤
- [ ] 返回过滤统计信息
```

**用例3：多源对比**

```
用户: "对比 GitHub 和 HackerNews 上最近的 AI 热点"

预期行为:
1. Planner 输出多步计划:
   - A: fetch_public_data(GitHub)
   - B: fetch_public_data(HackerNews)
   - C: compare_datasets([A, B])
2. ExecutionEngine 调度执行（A、B 可并行）
3. Reflector 检查结果，决定 FINISH
4. Synthesizer 生成对比报告

验收标准:
- [ ] 多步计划正确生成
- [ ] 依赖关系正确解析
- [ ] 对比结果包含统计信息
- [ ] 最终报告清晰呈现差异
```

**用例4：歧义澄清**

```
用户: "获取热门内容"

预期行为:
1. Planner 识别查询模糊
2. 调用 ask_user_clarification:
   - 问题: "您希望获取哪个平台的热门内容？"
   - 选项: ["GitHub", "HackerNews", "知乎", "全部"]
3. 等待用户选择
4. 根据选择继续执行

验收标准:
- [ ] Agent 主动识别歧义
- [ ] 提供结构化选项
- [ ] 用户响应正确处理
- [ ] 后续执行符合用户选择
```

---

## 10. 附录

### 10.1 关键文件清单

**新增文件**：

```
langgraph_agents/
├── state_v5.py                       # V5 状态定义（GraphStateV5, KnowledgeGraph）
├── tools/
│   ├── source_discovery.py          # search_data_sources 工具
│   ├── data_filter.py               # filter_data 工具
│   ├── data_compare.py              # compare_datasets 工具
│   ├── data_aggregate.py            # aggregate_data 工具
│   ├── insight_extractor.py         # extract_insights 工具
│   └── user_interaction.py          # ask_user_clarification 工具
├── execution/
│   ├── plan.py                      # ExecutionPlan 数据结构
│   ├── engine.py                    # ExecutionEngine 实现
│   └── dependency_resolver.py       # 依赖解析逻辑
├── knowledge/
│   ├── graph.py                     # KnowledgeGraph 实现
│   └── enhanced_reference.py        # EnhancedDataReference
└── utils/
    ├── smart_summary.py             # 智能摘要生成
    └── data_quality.py              # 数据质量评估

tests/langgraph_agents/
├── test_source_discovery.py
├── test_data_filter.py
├── test_data_compare.py
├── test_execution_engine.py
├── test_knowledge_graph.py
├── test_integration_v5.py
└── test_e2e_scenarios.py
```

**修改文件**：

```
langgraph_agents/
├── state.py                          # 添加 GraphStateV5 兼容
├── runtime.py                        # 扩展 ToolExecutionContext
├── graph_builder.py                  # 工作流路由逻辑
├── tools/registry.py                 # 工具模式标记
├── agents/
│   ├── planner.py                    # 多步规划支持
│   ├── reflector.py                  # 增强反思逻辑
│   └── data_stasher.py               # 智能摘要
└── prompts/
    ├── planner_system.txt            # 更新工具描述
    └── reflector_system.txt          # 新增决策类型
```

### 10.2 依赖库

**新增依赖**（可选）：

```
# requirements.txt 追加

# V5.0 - 数据处理增强
jsonpath-ng>=1.6.1       # JSONPath 解析（V4.4 已引入）
python-dateutil>=2.8.2   # 时间解析
```

**无需新增依赖**：
- 过滤逻辑：纯 Python 实现
- 知识图谱：Python dict + list
- 并行执行：内置 asyncio
- LLM 调用：复用现有 LLMClient

### 10.3 与 V4.4 的集成关系

V5.0 建立在 V4.4 的执行基础设施之上：

| V4.4 特性 | V5.0 使用方式 |
|-----------|--------------|
| StashReference | 多步规划的依赖表达 |
| MappedExecutionReport | 批量任务执行结果 |
| GraphRenderer | 可视化执行图谱 |
| JSONPath 解析 | 数据过滤和提取 |

**集成顺序建议**：
1. 先实现 V5.0 Phase 1-2（独立于 V4.4）
2. 在 Phase 4 集成 V4.4 的依赖解析
3. Phase 5 利用 V4.4 的 GraphRenderer

### 10.4 参考资料

- **当前架构**：`docs/langgraph-agents-design.md`（V2 ReAct）
- **V4.4 设计**：`.agentdocs/langgraph-v4.4-architecture-design.md`
- **私有数据愿景**：`docs/private-data-vision.md`
- **知识库设计**：`.agentdocs/knowledge-base-design.md`
- **Claude Code 文档**：https://docs.claude.com/en/docs/claude-code

### 10.5 术语表

| 术语 | 定义 |
|------|------|
| **轻量模式** | 探索类工具跳过数据存储的执行模式 |
| **执行图** | 包含多个步骤和依赖关系的计划 |
| **工作记忆** | 存储在 GraphState 中的临时数据 |
| **知识图谱** | 语义化组织数据关系的图结构 |
| **智能摘要** | 包含结构化元数据的数据摘要 |
| **数据血缘** | 追踪数据从原始到衍生的变换过程 |

---

## 11. 下一步行动

### 11.1 立即行动

1. [ ] **评审本文档**
   - 确认技术方案可行性
   - 确认工时估算合理性
   - 确认优先级排序

2. [ ] **创建任务文档**
   - `.agentdocs/workflow/YYMMDD-langgraph-v5.0-implementation.md`
   - 详细 TODO 清单
   - 进度跟踪

3. [ ] **更新索引文档**
   - 添加本文档到 `.agentdocs/index.md`
   - 标记状态为"设计方案"

4. [ ] **技术验证**
   - 验证 RAG 检索器可以独立调用
   - 验证工作流支持条件路由
   - 验证 asyncio 并行执行

### 11.2 评审问题清单

请在评审时回答以下问题：

1.  **是否认可当前问题分析**？ 
   - Agent 能力被单一工具限制
   - 缺乏数据处理能力
   - 流程过于固定
是

2. ❓ **P0 工具选择是否正确**？
   - search_data_sources（探索）
   - filter_data（处理）
   - ask_user_clarification（交互）
是
   - 
3. ❓ **轻量模式是否必要**？
   - 提升探索效率
   - 减少不必要的存储
是
4. ❓ **多步规划复杂度是否可接受**？
   - 依赖解析
   - 并行执行
   - 错误处理
是
5. ❓ **知识图谱是否过度设计**？
   - 数据关系组织
   - 血缘追踪
   - 智能决策支持
否
6. ❓ **14 天工期是否合理**？
   - 包含测试和文档
   - 分阶段交付
   - 风险缓冲
是
---

**文档版本**: V1.0
**最后更新**: 2025-11-16
**维护者**: AI Agent
**审核状态**: 已评审

