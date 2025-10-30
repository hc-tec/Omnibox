## 项目架构说明

本项目采用分层架构设计，遵循**单一职责原则**和**依赖倒置原则**，确保代码的可维护性和可扩展性。

## 架构图

```
用户查询 "虎扑步行街最新帖子"
    ↓
┌────────────────────────────────────────┐
│  Orchestrator (编排层)                 │
│  - rag_in_action.py                    │
│  职责：协调各模块，实现完整流程          │
└────────────────────────────────────────┘
    ↓                              ↓
┌─────────────────────┐    ┌───────────────────────────┐
│  RAG System         │    │  Query Processor          │
│  (向量检索层)       │    │  (查询解析层)             │
│                     │    │                           │
│  - embedding_model  │    │  - llm_client             │
│  - vector_store     │    │  - prompt_builder         │
│  - rag_pipeline     │    │  - parser                 │
│                     │    │  - path_builder           │
│  职责：向量检索      │    │  职责：LLM解析            │
└─────────────────────┘    └───────────────────────────┘
    ↓                              ↓
  相关路由定义              结构化API调用指令
    ↓                              ↓
    └──────────────┬───────────────┘
                   ↓
          最终API调用路径
        "/hupu/bbs/bxj/1"
```

## 目录结构

```
D:\AIProject\omni/
│
├── rag_system/              【模块1：向量检索】
│   ├── __init__.py
│   ├── config.py            # RAG配置
│   ├── embedding_model.py   # 向量化模型（bge-m3）
│   ├── vector_store.py      # 向量数据库（ChromaDB）
│   ├── semantic_doc_generator.py  # 语义文档生成
│   ├── rag_pipeline.py      # RAG检索管道
│   ├── example_usage.py     # 使用示例
│   ├── quick_start.py       # 快速开始
│   ├── requirements.txt     # 依赖
│   └── README.md            # 文档
│
├── query_processor/         【模块2：查询解析】
│   ├── __init__.py
│   ├── config.py            # 查询处理器配置
│   ├── llm_client.py        # LLM客户端抽象层
│   ├── prompt_builder.py    # Prompt构建器
│   ├── parser.py            # 查询解析器
│   └── path_builder.py      # URL路径构建器
│
├── orchestrator/            【模块3：流程编排】
│   ├── __init__.py
│   ├── rag_in_action.py     # 完整RAG-in-Action流程
│   └── example_usage.py     # 使用示例
│
├── route_process/           【数据层】
│   ├── datasource_definitions.json  # 路由定义数据
│   └── routes.json
│
└── api_service/             【可选：API服务】
    ├── server.py            # FastAPI服务器
    ├── routes.py            # API路由
    └── schemas.py           # 数据模型
```

## 模块职责

### 1. RAG System（向量检索层）

**职责**：将用户查询转换为向量，检索相关的路由定义

**输入**：
- 用户查询文本（如"虎扑步行街最新帖子"）

**输出**：
- 相关路由定义列表（Top-K）
- 每个路由包含完整的JSON定义

**核心组件**：
- `embedding_model.py`: 文本向量化（bge-m3模型）
- `vector_store.py`: 向量存储和检索（ChromaDB）
- `rag_pipeline.py`: 检索流程管理

**示例**：
```python
from rag_system.rag_pipeline import RAGPipeline

pipeline = RAGPipeline()
results = pipeline.search("虎扑步行街", top_k=3)
# 返回: [(route_id, similarity, route_definition), ...]
```

### 2. Query Processor（查询解析层）

**职责**：使用LLM将自然语言查询和路由定义解析为结构化的API调用指令

**输入**：
- 用户查询文本
- 路由定义（来自RAG System）

**输出**：
- 结构化的API调用指令（JSON格式）
- 包含：路径、参数、状态等

**核心组件**：
- `llm_client.py`: 统一的LLM调用接口（支持OpenAI、Anthropic等）
- `prompt_builder.py`: 构建给LLM的Prompt
- `parser.py`: 解析LLM返回的JSON
- `path_builder.py`: 根据参数构建URL路径

**示例**：
```python
from query_processor.llm_client import create_llm_client
from query_processor.prompt_builder import build_prompt
from query_processor.parser import QueryParser

# 创建LLM客户端
llm = create_llm_client("openai", model="gpt-4")

# 构建Prompt
prompt = build_prompt("虎扑步行街", retrieved_tools)

# 解析
parser = QueryParser(llm)
result = parser.parse(prompt)
# 返回: {"status": "success", "generated_path": "/hupu/bbs/...", ...}
```

### 3. Orchestrator（编排层）

**职责**：协调RAG System和Query Processor，实现完整的端到端流程

**输入**：
- 用户查询文本

**输出**：
- 完整的处理结果（可直接用于API调用）

**核心组件**：
- `rag_in_action.py`: 主流程编排

**示例**：
```python
from orchestrator.rag_in_action import create_rag_in_action

# 创建实例
ria = create_rag_in_action(
    llm_provider="openai",
    llm_config={"model": "gpt-4"}
)

# 处理查询
result = ria.process("虎扑步行街最新帖子")

# 使用结果
if result["status"] == "success":
    api_path = result["generated_path"]
    # 调用API: /hupu/bbs/bxj/1
```

## 数据流转

### 完整流程

```
1. 用户输入
   "帮我看看虎扑步行街今天最新发布的帖子"
   ↓

2. RAG System: 向量检索
   - 将查询向量化
   - 在向量数据库中检索
   - 返回Top-3相关路由定义
   ↓
   [
     {route_id: "hupu_bbs", name: "社区", ...},
     {route_id: "hupu_all", name: "首页", ...},
     ...
   ]
   ↓

3. Query Processor: Prompt构建
   - 将路由定义格式化为JSON
   - 组合用户查询
   - 生成完整Prompt
   ↓
   "你是API调用助手...工具定义：{...}...用户请求：{...}"
   ↓

4. Query Processor: LLM解析
   - 调用LLM（GPT-4等）
   - 提取意图和参数
   - 返回结构化结果
   ↓
   {
     "status": "success",
     "selected_tool": {"route_id": "hupu_bbs", ...},
     "parameters_filled": {"id": "bxj", "order": "1"},
     "generated_path": "/hupu/bbs/bxj/1"
   }
   ↓

5. 最终输出
   可执行的API调用路径和参数
```

## 设计原则

### 1. 单一职责原则（SRP）

每个模块只负责一件事：
- **RAG System**：只负责向量检索
- **Query Processor**：只负责查询解析
- **Orchestrator**：只负责流程协调

### 2. 依赖倒置原则（DIP）

高层模块不依赖低层模块，都依赖抽象：
- `LLMClient` 是抽象接口，可以有 `OpenAIClient`、`AnthropicClient` 等实现
- `Orchestrator` 依赖抽象的 `RAGPipeline` 和 `LLMClient`，不依赖具体实现

### 3. 开闭原则（OCP）

对扩展开放，对修改关闭：
- 添加新的LLM提供商：只需实现 `LLMClient` 接口
- 添加新的向量模型：只需修改 `embedding_model.py`
- 添加新的Prompt模板：只需在 `prompt_builder.py` 中添加

### 4. 接口隔离原则（ISP）

每个模块提供最小的接口：
- `RAGPipeline.search()` - 简单的检索接口
- `LLMClient.generate()` - 简单的生成接口
- `RAGInAction.process()` - 简单的处理接口

## 优势

### 1. 可维护性

- **职责清晰**：修改LLM调用不会影响RAG检索
- **代码独立**：每个模块可以独立开发和测试
- **易于理解**：新开发者可以快速理解架构

### 2. 可测试性

- **单元测试**：每个模块可以独立测试
- **Mock容易**：可以轻松Mock LLM或RAG组件
- **集成测试**：Orchestrator层进行集成测试

### 3. 可扩展性

- **替换LLM**：从OpenAI切换到Claude只需改配置
- **替换向量模型**：从bge-m3切换到其他模型只需改配置
- **添加功能**：如添加缓存、监控、多轮对话等

### 4. 可复用性

- **RAG System**：可以用于其他需要语义检索的场景
- **Query Processor**：可以用于其他需要LLM解析的场景
- **LLM Client**：可以在其他项目中复用

## 使用场景

### 场景1：快速原型

```python
from orchestrator.rag_in_action import create_rag_in_action

ria = create_rag_in_action("openai", {"model": "gpt-4"})
result = ria.process("虎扑步行街")
```

### 场景2：定制化流程

```python
from rag_system.rag_pipeline import RAGPipeline
from query_processor.llm_client import create_llm_client
from orchestrator.rag_in_action import RAGInAction

# 自定义RAG配置
rag = RAGPipeline()

# 自定义LLM配置
llm = create_llm_client("anthropic", model="claude-3-sonnet")

# 组合
ria = RAGInAction(rag_pipeline=rag, llm_client=llm)
```

### 场景3：集成自己的LLM

```python
def my_llm(prompt):
    # 调用你的本地大模型
    return generate_response(prompt)

from query_processor.llm_client import create_llm_client
llm = create_llm_client("custom", generate_func=my_llm)
```

## 扩展点

### 1. 添加新的LLM提供商

在 `query_processor/llm_client.py` 中添加新类：

```python
class MyLLMClient(LLMClient):
    def generate(self, prompt: str, **kwargs) -> str:
        # 实现你的LLM调用逻辑
        pass
```

### 2. 添加缓存层

在 `orchestrator/rag_in_action.py` 中添加缓存：

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_process(query):
    return self.process(query)
```

### 3. 添加多轮对话

创建 `orchestrator/conversation.py`：

```python
class ConversationManager:
    def __init__(self, rag_in_action):
        self.ria = rag_in_action
        self.history = []

    def chat(self, user_input):
        # 结合历史上下文处理
        pass
```

## 最佳实践

1. **使用环境变量**：API Key等敏感信息用环境变量
2. **日志记录**：每个模块都有详细的日志
3. **错误处理**：优雅地处理各种异常情况
4. **参数验证**：在Orchestrator层验证用户输入
5. **性能监控**：记录每个阶段的耗时

## 下一步

1. 运行示例：`python orchestrator/example_usage.py`
2. 阅读各模块文档：查看各模块的README
3. 集成到你的项目：根据需求选择合适的集成方式
