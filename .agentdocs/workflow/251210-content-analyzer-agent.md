# ContentAnalyzer Agent 设计文档

## 背景

### 核心矛盾

- **铁律**：LLM 禁止使用原始数据（防止 token 爆炸，如 RSS 全文可能 5MB+）
- **现实**：内容分析任务必须查看原始内容，仅凭 summary 无法完成深度分析
- **问题**：当前没有安全、可控的方式让 LLM 访问原始数据的子集

### 用户需求

用户提出："分析一下前三个热搜的内容"时：
- 需要分析标题、描述等实际内容
- 仅凭 summary（如"bilibili热搜获取10条数据..."）无法完成
- 但也不应该加载全部原始数据（可能包含无关字段、全文等）

## 现状分析

### 当前架构

```
ResearchAgent（V6.0 单Agent）
  ↓
  可用工具：
  - fetch_public_data  → 获取原始数据，存入 DataStore
  - data_operator      → 数据转换（不访问原始数据，只执行 transform）
  - extract_insights   → 洞察提取（已废弃，未使用）
  - aggregate_data     → 聚合统计（不访问原始数据）

  data_stash 中存储：
  - DataReference.summary  → ResearchAgent 用于决策
  - DataReference.data_id  → 指向 DataStore 中的原始数据
```

### 已有资源可复用

1. **schema_registry** - 已记录每个 data_id 的字段结构
   - `raw_schema`: 字段类型定义
   - `samples`: 字段值示例
   - 可用于让 AI 了解数据结构

2. **DataStore** - 已支持按 data_id 加载原始数据
   - 可扩展为支持字段过滤加载

3. **LangGraph 工具机制** - 已支持工具调用
   - 可新增 `analyze_content` 工具

## 改造方案

### 方案：ContentAnalyzer Agent（两阶段分析）

#### 核心思路

1. **ResearchAgent** 负责规划，决定需要内容分析时，调用 `analyze_content` 工具
2. **ContentAnalyzer Agent** 负责执行分析：
   - **阶段1**：查看 schema，AI 自主选择需要的字段
   - **阶段2**：加载选定字段的数据，执行分析

#### 架构图

```
ResearchAgent（规划层，只用 summary）
  ↓ 调用 analyze_content 工具
  ↓
ContentAnalyzer Agent（分析层，访问原始数据）
  ├─ 步骤1：inspect_schema()
  │   - 查看 schema_registry，了解数据有哪些字段
  │   - 根据分析任务，决定需要哪些字段（AI 自主选择）
  │   - 输出：{"selected_fields": ["title", "description"], "limit": 3}
  │
  ├─ 步骤2：load_filtered_data()
  │   - 从 DataStore 加载原始数据
  │   - 只提取选定的字段
  │   - 限制记录数（最多10条）
  │   - 字段值截断（每个字段最多1000字符）
  │
  └─ 步骤3：analyze()
      - 基于过滤后的数据执行分析
      - 返回分析结果
```

### 接口设计

#### 新增工具：analyze_content

```python
def analyze_content(
    source_ref: str,      # 数据引用，如 "$step.2" 或 "lg-xxx"
    task: str,            # 分析任务描述，如 "分析前三个热搜的主题和情感"
    limit: Optional[int] = None  # 限制记录数，默认从 task 中推断
) -> Dict[str, Any]:
    """
    内容分析工具（唯一可访问原始数据的工具）

    这个工具会启动 ContentAnalyzer Agent 执行分析。

    返回：
    {
        "type": "content_analysis",
        "analysis_result": {...},  # 分析结果
        "records_analyzed": 3,     # 分析的记录数
        "fields_used": ["title", "description"]  # 使用的字段
    }
    """
```

#### ContentAnalyzer Agent 接口

```python
class ContentAnalyzerAgent:
    """
    内容分析 Agent

    唯一可以访问 DataStore 原始数据的 Agent。
    通过两阶段设计确保 token 安全。
    """

    def __init__(self, runtime: LangGraphRuntime):
        self.runtime = runtime
        self.data_store = runtime.data_store
        self.schema_registry = runtime.schema_registry
        self.llm = runtime.planner_llm  # 复用现有 LLM

    def analyze(
        self,
        source_ref: str,
        task: str,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """执行内容分析（两阶段）"""

        # 阶段1：字段选择
        field_selection = self._select_fields(source_ref, task, limit)
        # 返回：{"selected_fields": [...], "limit": N, "reasoning": "..."}

        # 阶段2：加载数据并分析
        analysis_result = self._execute_analysis(
            source_ref,
            field_selection["selected_fields"],
            field_selection["limit"],
            task
        )

        return analysis_result
```

### 数据模型

#### schema_registry 已有结构（复用）

```python
{
  "schema": {
    "title": {"type": "string", "sample": "2026总台春晚..."},
    "description": {"type": "string", "sample": "央视官宣..."},
    "author": {"type": "string", "sample": "央视新闻"},
    "content": {"type": "string", "sample": "完整文章内容..."}  # 高token字段
  },
  "samples": [...],
  "metadata": {
    "sample_count": 10,
    "total_records": 10
  }
}
```

#### 字段选择决策（AI 输出）

```json
{
  "selected_fields": ["title", "description", "author"],
  "reasoning": "分析主题和情感需要标题和描述，作者信息有助于判断来源可信度",
  "limit": 3,
  "excluded_fields": ["content", "link"],
  "excluded_reason": "content 全文过长，link 对分析无用"
}
```

#### 分析结果

```json
{
  "type": "content_analysis",
  "task": "分析前三个热搜的主题和情感",
  "records_analyzed": 3,
  "fields_used": ["title", "description"],
  "analysis": {
    "items": [
      {
        "index": 0,
        "title": "2026总台春晚主题主标识发布",
        "theme": "文化/娱乐",
        "sentiment": "中性/正面",
        "key_points": ["官方发布", "春晚", "主题标识"]
      },
      ...
    ],
    "summary": "前三个热搜主要集中在..."
  }
}
```

### 安全保障机制

#### Token 控制（多层防护）

```python
# 1. 数量限制
MAX_RECORDS = 10  # 硬限制，绝对不能超过

# 2. 字段黑名单（在 prompt 中约束）
FORBIDDEN_FIELDS = ["content", "full_text", "body", "html"]

# 3. 字段值截断
MAX_FIELD_LENGTH = 1000  # 单个字段最多1000字符

# 4. 总 token 预估
def estimate_tokens(filtered_data):
    """预估 token 数，如果超过阈值则拒绝"""
    estimated = len(json.dumps(filtered_data)) * 1.5  # 粗略估算
    if estimated > 50000:  # 50K token 阈值
        raise ValueError(f"数据量过大，预估 {estimated} tokens")
```

#### Prompt 约束

```
重要约束：
1. 禁止选择以下字段：content, full_text, body, html（全文字段）
2. 字段数量：建议 3-6 个字段，不超过 8 个
3. 记录数量：最多 10 条（硬限制）
4. 如果发现某个字段的 sample 值超过 500 字符，应排除该字段
```

### 实施计划

#### Phase 1：ContentAnalyzer Agent 基础实现

- [x] 1.1 创建 `langgraph_agents/agents/content_analyzer.py`
- [x] 1.2 实现两阶段分析流程：
  - `_select_fields()` - 字段选择阶段
  - `_execute_analysis()` - 分析执行阶段
- [x] 1.3 实现安全保障：数量限制、字段黑名单、值截断
- [x] 1.4 添加 token 预估检查

#### Phase 2：工具集成

- [x] 2.1 创建 `langgraph_agents/tools/content_analysis.py`
- [x] 2.2 实现 `analyze_content` 工具
- [x] 2.3 在 ResearchAgent 的可用工具列表中注册
- [x] 2.4 更新 ResearchAgent prompt，说明何时使用该工具

#### Phase 3：Prompt 工程

- [x] 3.1 创建 `langgraph_agents/prompts/content_analyzer_system.txt`
- [x] 3.2 设计字段选择 prompt（引导 AI 智能选择）
- [x] 3.3 设计分析执行 prompt
- [x] 3.4 添加安全约束说明

#### Phase 4：测试

- [x] 4.1 编译检查和后端启动测试
- [x] 4.2 单元测试：字段选择逻辑
- [x] 4.3 单元测试：token 限制检查
- [x] 4.4 集成测试：完整分析流程
- [ ] 4.5 端到端测试：从 ResearchAgent 调用（待实际使用时测试）

## 实施进展（2025-12-10）

### 已完成

1. ✅ **ContentAnalyzer Agent** - `langgraph_agents/agents/content_analyzer.py`
   - 两阶段分析流程完整实现
   - 安全保障机制（数量、字段、值截断、token 预估）

2. ✅ **analyze_content 工具** - `langgraph_agents/tools/content_analysis.py`
   - 工具实现完成
   - 成功注册到 ResearchService

3. ✅ **Prompt 文件** - `langgraph_agents/prompts/content_analyzer_system.txt`
   - 字段选择引导
   - 分析执行引导
   - 安全约束说明

4. ✅ **工具注册** - `langgraph_agents/tools/bootstrap.py`
   - 成功集成到工具链

5. ✅ **单元测试** - `tests/langgraph_agents/test_content_analyzer.py`
   - 18/18 测试全部通过
   - 覆盖字段选择、记录提取、过滤截断、token 安全检查、工具执行兜底等核心逻辑

6. ✅ **数据引用 & Schema 集成**
   - 支持通过 DataRefResolver 解析 `$step.N` 引用并使用 data_stash 数据
   - SchemaRegistry 补充 `get_schema` 标准化输出，缺失时自动基于原始数据兜底
   - 工具级/Agent 级集成测试覆盖（resolver + schema_registry + data_store）

### 验证状态

**后端启动验证**：✅ 成功
```
INFO:langgraph_agents.tools.registry:注册工具: analyze_content - 对数据进行深度内容分析...
INFO:     Application startup complete.
```

**单元测试验证**：✅ 18/18 通过
```
tests/langgraph_agents/test_content_analyzer.py::TestContentAnalyzer::test_create_content_analyzer PASSED
...
============================= 18 passed in 0.23s ==============================
```

**已知问题**：
- ChatService 的工具注册兼容性尚需端到端验证（曾出现 `ToolRegistry.register() missing arguments` 警告），需要在运行时回归中确认是否仍存在

### 使用说明

⚠️ **当前状态**：由于工具注册框架兼容性问题，`analyze_content` 工具暂时未集成到生产环境。

代码和测试已完成，一旦修复注册问题即可启用。ResearchAgent 将可以调用：

```python
{
  "plugin_id": "analyze_content",
  "args": {
    "source_ref": "$step.2",  # 引用已获取的数据
    "task": "分析前三个热搜的主题和情感",  # 分析任务描述
    "limit": 3  # 可选：限制记录数
  }
}
```

工具执行流程：
1. ContentAnalyzer 查看 data_id 的 schema
2. AI 根据任务智能选择需要的字段（如 title, description）
3. 加载选定字段的数据（最多10条，字段值截断到1000字符）
4. 执行分析并返回结构化结果

### 下一步

- [ ] **P0**: 调查并修复工具注册框架兼容性问题
- [ ] 端到端功能测试（ResearchAgent 调用链 + Playwright MCP 端到端验证）
- [ ] 性能和 token 消耗监控
- [ ] 根据实际使用反馈优化 prompt

### 替代方案对比

#### 方案A：在 data_operator 中添加 analyze 模式（已否决）

**缺点**：
- data_operator 语义混乱（既是数据转换，又是内容分析）
- 字段选择由硬编码规则决定，不够智能

#### 方案B：使用 extract_insights 工具（已存在但未使用）

**缺点**：
- extract_insights 目前的实现可能不支持字段选择
- 需要查看现有实现，评估是否可复用

**需要调研**：
- 查看 `langgraph_agents/tools/insight_extraction.py` 的实现
- 如果 extract_insights 已经支持类似功能，可考虑扩展它而非新建 Agent

### 迁移计划

由于这是新增功能，无需迁移。

但需要确保：
1. ResearchAgent 在适当的时候调用 `analyze_content` 而非 `data_operator`
2. 更新 prompt，明确工具选择策略

### 风险评估

#### 高风险：Token 爆炸

**缓解措施**：
- 多层防护（数量、字段、值截断）
- token 预估检查
- 监控日志，记录每次分析的 token 消耗

#### 中风险：AI 选择不当的字段

**缓解措施**：
- Prompt 中明确禁止全文字段
- 提供字段 sample，让 AI 判断字段大小
- 兜底机制：如果选择的字段导致 token 超限，降级为只用 title

#### 低风险：性能影响

**缓解措施**：
- 只在真正需要分析时才调用
- 异步执行，不阻塞主流程

## 下一步

1. 用户确认方案
2. 调研 extract_insights 现有实现（决定是新建还是扩展）
3. 按 Phase 顺序实施

## 创建日期
2025-12-10
