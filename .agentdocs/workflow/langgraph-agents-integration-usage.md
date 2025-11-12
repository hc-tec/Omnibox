# LangGraph Agents 集成使用指南

## 快速开始

LangGraph Agents 已成功集成到 Omni 项目中，提供复杂多轮研究能力。本文档介绍如何使用新功能。

## 架构概览

```
前端
  ↓ (POST /api/v1/chat with mode="research")
API Controller
  ↓
ChatService (路由)
  ├─→ DataQueryService (简单查询，单轮)
  └─→ ResearchService (复杂研究，多轮) ← 新增
         ↓
      LangGraph Agents
```

---

## 后端集成

### 1. 初始化 ResearchService

在应用启动时初始化 ResearchService（例如在 `api/controllers/chat_controller.py` 的启动逻辑中）：

```python
from services.research_service import ResearchService
from query_processor.llm_client import create_llm_client

# 初始化 LLM 客户端
router_llm = create_llm_client(model="gpt-4")
planner_llm = create_llm_client(model="gpt-4")
reflector_llm = create_llm_client(model="gpt-4")
synthesizer_llm = create_llm_client(model="gpt-4")

# 初始化 ResearchService
research_service = ResearchService(
    router_llm=router_llm,
    planner_llm=planner_llm,
    reflector_llm=reflector_llm,
    synthesizer_llm=synthesizer_llm,
    data_query_service=data_query_service,  # 复用现有的查询服务
)

# 初始化 ChatService 时注入 ResearchService
chat_service = ChatService(
    data_query_service=data_query_service,
    research_service=research_service,  # 新增参数
)
```

### 2. API 调用示例

前端可以通过在请求中设置 `mode` 参数来触发研究模式：

**请求**：
```json
POST /api/v1/chat

{
  "query": "分析最近一周GitHub上最热门的Python项目的特点和趋势",
  "mode": "research"
}
```

**响应**：
```json
{
  "success": true,
  "message": "根据对最近一周GitHub热门Python项目的研究...",
  "metadata": {
    "mode": "research",
    "total_steps": 8,
    "execution_steps": [
      {
        "step_id": 1,
        "node": "router",
        "action": "路由决策: complex_research",
        "status": "success"
      },
      {
        "step_id": 2,
        "node": "planner",
        "action": "规划下一步: 调用工具 query_data",
        "status": "success"
      },
      ...
    ],
    "data_stash_count": 3,
    "query": "...",
    "storage_stats": {...}
  }
}
```

---

## 前端集成

### 1. UI 控制

添加模式选择器：

```vue
<template>
  <div class="chat-interface">
    <!-- 查询模式选择 -->
    <div class="mode-selector">
      <RadioGroup v-model="queryMode">
        <RadioGroupItem value="auto">自动</RadioGroupItem>
        <RadioGroupItem value="simple">简单查询</RadioGroupItem>
        <RadioGroupItem value="research">复杂研究</RadioGroupItem>
      </RadioGroup>
    </div>

    <!-- 查询输入 -->
    <Textarea v-model="userQuery" placeholder="输入您的问题..." />

    <!-- 提交按钮 -->
    <Button @click="submitQuery">发送</Button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const userQuery = ref('');
const queryMode = ref<'auto' | 'simple' | 'research'>('auto');

async function submitQuery() {
  const response = await fetch('/api/v1/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: userQuery.value,
      mode: queryMode.value,  // 传递模式参数
    }),
  });

  const data = await response.json();

  if (data.success) {
    // 显示结果
    console.log('研究报告:', data.message);

    // 如果是研究模式，可以显示执行步骤
    if (data.metadata?.mode === 'research') {
      console.log('执行步骤:', data.metadata.execution_steps);
    }
  }
}
</script>
```

### 2. 显示研究进度（推荐 WebSocket）

- 端点：`GET /api/v1/research/stream?task_id=xxx`
- 前端：`ResearchStreamClient`（`frontend/src/features/research/services/researchStream.ts`）在 `researchStore.createTask()` 时自动连接
- 事件类型：`step`、`human_in_loop`、`human_response_ack`、`complete`、`error`、`cancelled`
- 如果无法使用 WebSocket，可退化为轮询任务状态接口（需自行实现）

---

## 配置管理

### 环境变量配置

LangGraph Agents 支持通过环境变量配置参数：

```bash
# LLM 重试配置
LANGGRAPH_RETRY_MAX=3
LANGGRAPH_RETRY_INITIAL_DELAY=1.0
LANGGRAPH_RETRY_BACKOFF=2.0
LANGGRAPH_RETRY_MAX_DELAY=10.0

# 数据存储配置
LANGGRAPH_STORE_MAX_ITEMS=1000
LANGGRAPH_STORE_TTL=3600
LANGGRAPH_SUMMARY_MAX_CHARS=320

# 笔记搜索配置
LANGGRAPH_SNIPPET_RADIUS=120
LANGGRAPH_NOTE_TOP_K=5
```

### 代码配置

```python
from langgraph_agents.config import LangGraphConfig

# 自定义配置
config = LangGraphConfig(
    llm_retry=LLMRetryConfig(max_retries=5),
    data_store=DataStoreConfig(ttl_seconds=7200),
    note_search=NoteSearchConfig(default_top_k=10),
)

# 使用自定义配置初始化 ResearchService
research_service = ResearchService(
    ...,
    config=config,
)
```

---

## 工具扩展

### 添加自定义工具

ResearchService 默认注册了 `query_data` 工具。您可以扩展更多工具：

```python
class ResearchService:
    def _init_tools(self) -> ToolRegistry:
        registry = ToolRegistry()

        # 工具 1: 查询数据（已有）
        @registry.register_tool(...)
        def query_data_tool(...):
            ...

        # 工具 2: 搜索笔记（新增示例）
        @registry.register_tool(
            plugin_id="search_notes",
            description="在本地笔记中搜索相关内容",
            schema={
                "type": "object",
                "properties": {
                    "keywords": {"type": "string"},
                    "top_k": {"type": "integer"},
                },
                "required": ["keywords"],
            },
        )
        def search_notes_tool(keywords: str, top_k: int = 5):
            # 实现笔记搜索逻辑
            results = note_search_service.search(keywords, top_k)
            return {
                "status": "success",
                "results": results,
            }

        # 工具 3: Web 搜索（新增示例）
        @registry.register_tool(
            plugin_id="web_search",
            description="在互联网上搜索信息",
            schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        )
        def web_search_tool(query: str):
            # 调用搜索 API
            results = web_search_api.search(query)
            return {
                "status": "success",
                "results": results[:5],  # 限制返回数量
            }

        return registry
```

---

## 测试

### 单元测试

```python
# tests/services/test_research_service.py
from services.research_service import ResearchService
from tests.mocks import MockLLMClient, MockDataQueryService

def test_research_service_initialization():
    """测试 ResearchService 初始化"""
    mock_llm = MockLLMClient()
    mock_dqs = MockDataQueryService()

    service = ResearchService(
        router_llm=mock_llm,
        planner_llm=mock_llm,
        reflector_llm=mock_llm,
        synthesizer_llm=mock_llm,
        data_query_service=mock_dqs,
    )

    assert service.tool_registry is not None
    assert service.runtime is not None
    assert service.app is not None

def test_research_service_basic_query():
    """测试基础研究查询"""
    # Mock LLM 返回预设的决策
    mock_llm = MockLLMClient(
        responses={
            "router": '{"route": "complex_research"}',
            "planner": '{"plugin_id": "query_data", "args": {...}}',
            "reflector": '{"decision": "FINISH"}',
            "synthesizer": "研究报告内容",
        }
    )

    service = ResearchService(...)
    result = service.research("测试查询")

    assert result.success
    assert result.final_report != ""
    assert len(result.execution_steps) > 0
```

### 集成测试

```python
# tests/api/test_research_integration.py
from fastapi.testclient import TestClient

def test_chat_with_research_mode(client: TestClient):
    """测试研究模式 API"""
    response = client.post(
        "/api/v1/chat",
        json={
            "query": "分析GitHub上的Python项目趋势",
            "mode": "research",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"]
    assert data["metadata"]["mode"] == "research"
    assert "execution_steps" in data["metadata"]
```

---

## 故障排查

### 常见问题

**Q1: 研究模式请求但返回错误 "研究服务未启用"**

**A**: 检查 ChatService 初始化时是否注入了 ResearchService：
```python
chat_service = ChatService(
    data_query_service=...,
    research_service=research_service,  # 确保传递了这个参数
)
```

**Q2: 研究执行时间过长**

**A**: 可以设置 `max_steps` 参数限制步骤数：
```python
result = research_service.research(
    user_query="...",
    max_steps=10,  # 限制最大步骤数
)
```

**Q3: LLM API 调用失败**

**A**: 检查：
1. LLM 客户端配置是否正确
2. API Key 是否有效
3. 网络连接是否正常
4. 查看日志中的重试记录

**Q4: 研究结果不理想**

**A**: 调整以下参数：
1. 使用更强大的 LLM 模型（如 GPT-4）
2. 修改 Prompt 模板（`langgraph_agents/prompts/` 目录）
3. 增加工具种类和质量
4. 调整 Reflector 的决策逻辑

---

## 性能优化

### 1. 使用更便宜的模型

对于非核心节点，可以使用较便宜的模型：

```python
research_service = ResearchService(
    router_llm=create_llm_client(model="gpt-4-turbo"),  # 路由用快速模型
    planner_llm=create_llm_client(model="gpt-4"),       # 规划用强模型
    reflector_llm=create_llm_client(model="gpt-4-turbo"),  # 反思用快速模型
    synthesizer_llm=create_llm_client(model="gpt-4"),   # 综合用强模型
    ...
)
```

### 2. 启用缓存

```python
result = research_service.research(
    user_query="...",
    # DataQueryService 内部会使用缓存
)
```

### 3. 限制数据返回量

在工具中限制返回的数据量：

```python
def query_data_tool(...):
    result = data_query_service.query(...)
    items = result.feed_items[:10]  # 只返回前 10 条
    return {"items": items}
```

---

## 下一步

1. **实现 WebSocket 流式响应**（参考 `langgraph-agents-integration-plan.md` 阶段 4）
2. **添加更多工具**（笔记搜索、Web 搜索等）
3. **优化 Prompt 模板**
4. **添加结果可视化**（研究过程图谱）

---

## 相关文档

- `.agentdocs/workflow/langgraph-agents-integration-plan.md` - 详细集成方案
- `.agentdocs/workflow/251111-langgraph-agents-refactor.md` - LangGraph Agents 重构文档
- `docs/langgraph-agents-design.md` - LangGraph 设计文档
- `docs/langgraph-agents-frontend-design.md` - 前端集成设计
