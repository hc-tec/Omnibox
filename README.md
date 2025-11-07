# 智能API调用系统

基于RAG + LLM的自然语言到API调用转换系统

## 快速开始

### 1. 安装依赖

**方式1：一次性安装（推荐）**

```bash
# 使用根目录统一的 requirements.txt
pip install -r requirements.txt

# 国内用户推荐使用清华镜像加速
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 启动本地RSSHub服务

**重要：本系统默认使用本地RSSHub，需先启动Docker服务**

```bash
# 进入部署目录
cd deploy

# 启动RSSHub服务（包含Redis和Browserless）
docker-compose up -d

# 验证RSSHub启动成功
curl http://localhost:1200/
# 看到欢迎页面表示成功

# 查看服务状态
docker-compose ps

# 停止服务（如需）
# docker-compose down
```

### 3. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件，至少填写 OPENAI_API_KEY
nano .env  # 或使用其他编辑器

# 主要配置项：
# - OPENAI_API_KEY: OpenAI API密钥（必填）
# - RSSHUB_BASE_URL: 本地RSSHub地址（默认 http://localhost:1200）
# - RSSHUB_FALLBACK_URL: 降级地址（默认 https://rsshub.app）
```

### 4. 构建向量索引

```bash
cd rag_system
python quick_start.py
```

### 5. 运行示例

```bash
cd ../orchestrator
python example_usage.py
```

**详细配置说明**：详见 [CONFIGURATION.md](CONFIGURATION.md)

## 架构说明

本项目采用**分层架构**，严格遵循单一职责原则：

```
用户查询 "虎扑步行街最新帖子"
    ↓
┌─────────────────────────────┐
│  Orchestrator (编排层)       │  协调所有模块
└─────────────────────────────┘
    ↓                    ↓
┌─────────────┐    ┌────────────────┐
│ RAG System  │    │ Query Processor│
│ 向量检索    │    │ LLM解析        │
└─────────────┘    └────────────────┘
    ↓                    ↓
  相关路由           结构化指令
    └────────┬────────┘
             ↓
    "/hupu/bbs/bxj/1"
```

### 模块职责

| 模块 | 职责 | 技术栈 |
|-----|------|--------|
| **rag_system** | 向量检索 | bge-m3 + ChromaDB |
| **query_processor** | 查询解析 | LLM (GPT-4/Claude) |
| **orchestrator** | 流程编排 | Python |

详细架构说明：[ARCHITECTURE.md](ARCHITECTURE.md)

## 使用示例

### 方式1：一键调用（推荐）

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
    print(f"API路径: {result['generated_path']}")
    print(f"参数: {result['parameters_filled']}")
```

### 方式2：分步调用（了解流程）

```python
from rag_system.rag_pipeline import RAGPipeline
from query_processor import *

# 步骤1: RAG检索
rag = RAGPipeline()
results = rag.search("虎扑步行街", top_k=3)

# 步骤2: 构建Prompt
from query_processor.prompt_builder import build_prompt
prompt = build_prompt("虎扑步行街", retrieved_tools)

# 步骤3: LLM解析
from query_processor.llm_client import create_llm_client
from query_processor.parser import QueryParser

llm = create_llm_client("openai", model="gpt-4")
parser = QueryParser(llm)
result = parser.parse(prompt)
```

### 方式3：使用自定义LLM

```python
def my_llm_generate(prompt: str) -> str:
    # 调用你自己的LLM服务
    return your_llm_service.generate(prompt)

from query_processor.llm_client import create_llm_client

llm = create_llm_client(
    provider="custom",
    generate_func=my_llm_generate
)
```

## 项目结构

```
D:\AIProject\omni/
│
├── rag_system/              # 向量检索模块
│   ├── embedding_model.py   # bge-m3向量化
│   ├── vector_store.py      # ChromaDB存储
│   ├── rag_pipeline.py      # 检索管道
│   └── README.md
│
├── query_processor/         # 查询解析模块
│   ├── llm_client.py        # LLM客户端抽象
│   ├── prompt_builder.py    # Prompt构建
│   ├── parser.py            # 结果解析
│   └── path_builder.py      # 路径构建
│
├── orchestrator/            # 编排模块
│   ├── rag_in_action.py     # 主流程
│   └── example_usage.py     # 使用示例
│
├── route_process/           # 数据源
│   └── datasource_definitions.json
│
├── ARCHITECTURE.md          # 架构文档
└── README.md                # 本文档
```

## 核心特性

### 1. 向量检索（RAG System）

- ✅ 使用bge-m3模型（最佳中英文性能）
- ✅ ModelScope国内镜像加速
- ✅ ChromaDB向量数据库
- ✅ 语义理解和相似度匹配

### 2. 查询解析（Query Processor）

- ✅ 支持多种LLM（OpenAI、Anthropic、自定义）
- ✅ 基于 LangChain 的成熟聊天模型封装
- ✅ 智能参数提取
- ✅ 自动路径构建
- ✅ 错误处理和重试机制

### 3. 流程编排（Orchestrator）

- ✅ 端到端处理
- ✅ 详细日志记录
- ✅ 多种状态处理（success/needs_clarification/not_found/error）

## 配置说明

### 环境变量配置（推荐方式 - Pydantic Settings）

**创建 .env 文件**：

```bash
cp .env.example .env
```

**编辑 .env**：

```env
# 最少只需要这一个
OPENAI_API_KEY=sk-your-key-here

# 可选配置
OPENAI_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.1
PROMPT_MAX_TOOLS=3
```

**优势**：
- ✅ 类型验证（Pydantic）
- ✅ 环境分离（开发/生产）
- ✅ 密钥安全（不提交到Git）
- ✅ 自动加载（无需手动读取）

详见：[CONFIGURATION.md](CONFIGURATION.md)

### RAG配置（rag_system/config.py）

```python
EMBEDDING_MODEL_CONFIG = {
    "model_name": "BAAI/bge-m3",
    "device": "cuda",
    "use_modelscope": True,  # 国内镜像
}
```

## 环境要求

- Python 3.8+
- 内存：16GB+ （推荐64GB）
- 显存：8GB （可选，CPU模式也可运行）
- LLM API Key（OpenAI或其他）

## 安装

```bash
# 安装RAG依赖
cd rag_system
pip install -r requirements.txt

# 安装查询解析模块依赖（包含 LangChain + OpenAI/Anthropic SDK）
cd ../query_processor
pip install -r requirements.txt
```

## 设计原则

1. **单一职责**：每个模块只负责一件事
2. **依赖倒置**：依赖抽象接口，不依赖具体实现
3. **开闭原则**：对扩展开放，对修改关闭
4. **接口隔离**：提供最小化的接口

## 扩展性

### 添加新的LLM提供商

```python
from query_processor.llm_client import LLMClient

class MyLLMClient(LLMClient):
    def generate(self, prompt: str, **kwargs) -> str:
        # 实现你的LLM调用逻辑
        pass
```

### 添加缓存

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_search(query):
    return ria.process(query)
```

### 添加监控

```python
import time

def process_with_metrics(query):
    start = time.time()
    result = ria.process(query)
    duration = time.time() - start
    log_metrics(query, duration, result["status"])
    return result
```

## 测试

```bash
# RAG系统测试
cd rag_system
python example_usage.py

# 完整流程测试
cd orchestrator
python example_usage.py
```

## 文档

- [架构设计](ARCHITECTURE.md) - 详细的架构说明
- [RAG系统文档](rag_system/README.md) - 向量检索详解
- [ModelScope指南](rag_system/MODELSCOPE_GUIDE.md) - 国内镜像使用

## 常见问题

### Q: 为什么要分这么多模块？

A: 遵循单一职责原则，每个模块独立开发、测试、维护。修改LLM不影响RAG，修改向量模型不影响查询解析。

### Q: 可以只用RAG不用LLM吗？

A: 可以。RAG System是独立的，可以单独使用进行语义检索。

### Q: 可以使用本地LLM吗？

A: 可以。使用自定义LLM客户端，集成任何LLM服务。

### Q: 性能如何？

A:
- RAG检索：<50ms
- LLM调用：1-3秒（取决于LLM服务）
- 总耗时：1-5秒

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

MIT License

## 致谢

- 向量模型：BAAI/bge-m3
- 向量数据库：ChromaDB
- LLM：OpenAI/Anthropic
