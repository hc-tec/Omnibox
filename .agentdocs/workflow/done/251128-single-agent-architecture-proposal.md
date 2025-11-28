# V6.0 单Agent架构重构提案

**创建日期**: 2025-11-28
**状态**: ✅ 已完成

---

## 一、背景与问题分析

### 1.1 当前多Agent架构（V5.0）

当前系统采用多Agent协作架构：

```
Router → Planner → ToolExecutor → Reflector → (循环) → Synthesizer
```

- **Router**: 路由决策（complex_research / simple / chitchat）
- **Planner**: 工具规划（选择下一个工具）
- **Reflector**: 反思决策（CONTINUE / FINISH / REQUEST_HUMAN_CLARIFICATION）
- **Synthesizer**: 总结生成（最终报告）

### 1.2 已修复的问题（2025-11-27/28）

| 问题 | 原因 | 修复方案 |
|------|------|----------|
| Reflector过早返回FINISH | 无法看到完整任务要求，prompt缺少明确判断规则 | 增强system prompt，添加显式判断规则（规则1-3） |
| 所有LLM调用role显示"synthesizer" | 多Agent共享同一LLMClient实例，最后一次set_tracker()覆盖了所有role | 改为在generate()调用时传入role参数 |
| 重复LLM调试事件 | start_call和complete_call都调用callback | 只在complete_call/fail_call时调用callback |

### 1.3 根本性问题

尽管上述问题已修复，多Agent架构存在**根本性缺陷**：

1. **上下文割裂** - 每个Agent只能看到压缩后的摘要
2. **冗余LLM调用** - 每次循环需要2次LLM调用
3. **协调复杂度** - Agent间状态传递容易丢失细节
4. **上下文膨胀风险** - 每个Agent都需要包含完整历史摘要

---

## 二、架构重构方案

### 2.1 核心理念

**单Agent + 复杂工具层**：借鉴 Claude Code、Cursor 等成熟AI IDE的设计

### 2.2 关键设计原则

1. **复杂度下沉到工具层** - Agent只说"做什么"，工具负责"怎么做"
2. **上下文保持紧凑** - LLM只看摘要，原始数据存储在外部
3. **动态意图分解** - 不预先规划所有步骤，而是逐步执行

### 2.3 用户评审决策

| 问题 | 选择 |
|------|------|
| 是否完全废弃多Agent架构？ | ✅ A：完全重写为单Agent |
| Synthesizer是否保留？ | ✅ A：融入Agent的最终思考步骤 |
| Router是否保留？ | ✅ B：保留作为前置分流 |
| 实施优先级？ | ✅ 优先级最高 |

---

## 三、实施记录

### 3.1 完成的工作

| 任务 | 状态 | 文件 |
|------|------|------|
| 创建单Agent核心执行循环 | ✅ | `langgraph_agents/agents/research_agent.py` |
| 设计统一Agent Prompt | ✅ | `langgraph_agents/prompts/research_agent_system.txt` |
| 修改graph_builder.py集成单Agent节点 | ✅ | `langgraph_agents/graph_builder.py` |
| 更新agents/__init__.py导出新模块 | ✅ | `langgraph_agents/agents/__init__.py` |
| 更新state.py添加新状态字段 | ✅ | `langgraph_agents/state.py` |
| 编写单Agent单元测试 | ✅ | `tests/langgraph_agents/test_research_agent.py` |
| 更新相关测试适配新架构 | ✅ | 多个测试文件 |
| 标记废弃代码 | ✅ | planner.py, reflector.py, synthesizer.py |

### 3.2 测试结果

- **单Agent测试**: 18 个测试通过
- **完整测试套件**: 278 个测试通过，1 个跳过

### 3.3 新架构工作流

```
START → router → (条件分支)
         ├── simple_chat → END
         ├── research_agent → (条件分支)
         │        ├── tool_executor → (条件分支)
         │        │        ├── lightweight_handler → research_agent
         │        │        └── data_stasher → research_agent
         │        ├── END (FINISH)
         │        └── wait_for_human → END
         ├── wait_for_human → END
         └── END
```

### 3.4 关键代码变更

**新增文件**：
- `langgraph_agents/agents/research_agent.py` - 单Agent核心实现
- `langgraph_agents/prompts/research_agent_system.txt` - 统一Prompt
- `tests/langgraph_agents/test_research_agent.py` - 单Agent测试

**修改文件**：
- `langgraph_agents/graph_builder.py` - V6.0工作流
- `langgraph_agents/state.py` - 新增 `agent_decision`、`agent_reasoning` 字段
- `langgraph_agents/agents/__init__.py` - 导出 research_agent
- `tests/langgraph_agents/test_integration.py` - MockLLMClient 支持 role 参数
- `tests/langgraph_agents/test_lightweight_mode.py` - 边名称更新
- `tests/langgraph_agents/test_lightweight_mode_e2e.py` - 节点名称更新

**标记废弃**：
- `langgraph_agents/agents/planner.py` - 被 ResearchAgent 取代
- `langgraph_agents/agents/reflector.py` - 被 ResearchAgent 取代
- `langgraph_agents/agents/synthesizer.py` - 被 ResearchAgent 取代

---

## 四、后续工作（已完成）

### 阶段2：工具层增强 ✅
- [x] 增强工具返回摘要质量 (`data_stasher.py`: `_smart_default_summary()`)
- [x] 实现工具间data_id引用机制 (`tools/data_ref_resolver.py`)
- [x] 添加工具执行超时和容错 (`tools/execution_wrapper.py`)

### 阶段3：上下文管理 ✅
- [x] 实现分层记忆系统（L1-L4）(`context_manager.py`: `HierarchicalMemoryManager`)
- [x] 添加历史压缩机制 (`context_manager.py`: `_compress_content()`)
- [x] 实现上下文使用监控 (`context_manager.py`: `ContextUsageMonitor`)

### 新增文件清单

**阶段2**:
- `langgraph_agents/tools/data_ref_resolver.py` - 统一数据引用解析器
- `langgraph_agents/tools/execution_wrapper.py` - 工具执行保护（超时、重试）
- `tests/langgraph_agents/test_data_ref_resolver.py` - 解析器测试（25个）
- `tests/langgraph_agents/tools/test_execution_wrapper.py` - 包装器测试（23个）

**阶段3**:
- `langgraph_agents/context_manager.py` - 分层记忆与上下文管理
- `tests/langgraph_agents/test_context_manager.py` - 上下文管理测试（22个）

---

## 五、参考资料

- Claude Code架构分析：单Agent + Tool Use模式
- Cursor架构分析：Agent Loop + Context Management
- 当前V5.0代码：`langgraph_agents/agents/*.py`
- LLM调用追踪：`.agentdocs/llm-call-tracking-integration-guide.md`
