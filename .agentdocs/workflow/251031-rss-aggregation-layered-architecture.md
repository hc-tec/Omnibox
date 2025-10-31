# RSS聚合系统分层架构实施

## 任务概述
为智能RSS聚合系统补充完整的分层架构，实现从自然语言查询到RSS数据获取的端到端流程。

## 一、现状分析

### 已完成模块（可直接复用）

#### 1. RAG System（向量检索层）✅
- `rag_system/embedding_model.py` - bge-m3向量化模型
- `rag_system/vector_store.py` - ChromaDB向量数据库
- `rag_system/rag_pipeline.py` - 完整RAG检索管道
- `rag_system/semantic_doc_generator.py` - 语义文档生成器
- **状态**：功能完整，无需修改

#### 2. Query Processor（查询解析层）✅
- `query_processor/llm_client.py` - LLM客户端抽象（支持OpenAI/Anthropic）
- `query_processor/prompt_builder.py` - Prompt构建器
- `query_processor/parser.py` - LLM响应解析器
- `query_processor/path_builder.py` - API路径构建器
- **状态**：功能完整，无需修改

#### 3. Orchestrator（编排层）✅
- `orchestrator/rag_in_action.py` - RAG+LLM完整流程编排
- **状态**：功能完整，无需修改

#### 4. 基础设施✅
- 数据源定义（`route_process/datasource_definitions.json`）
- 配置管理（Pydantic Settings + .env）
- 基础API框架（`rag_system/api_server.py`）

### 缺失模块（需要新增）

根据分层架构设计，以下模块需要补充：

#### 1. Service层（业务逻辑层）❌ 完全缺失
- 意图识别服务 - 区分数据查询、闲聊、澄清
- 闲聊处理服务 - 处理非数据查询的对话
- 数据查询服务 - 协调RAG检索和数据获取
- 结果总结服务 - LLM总结数据结果

#### 2. Integration层扩展（数据访问层）❌ 部分缺失
- **数据执行器（Data Executor）** - RSSHub调用和RSS解析 ⭐核心
- 会话存储服务 - 管理多轮对话上下文
- 缓存服务 - RSS数据和查询结果缓存

#### 3. Controller层（API层）⚠️ 需要重构
- 现有的 `rag_system/api_server.py` 仅是RAG检索API
- 需要统一的对话式API接口
- 需要会话管理和决策路由
- 需要WebSocket支持流式响应

## 二、架构设计

### 分层架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Controller 层（API层）                    │
│  职责：接收请求、会话管理、决策路由、响应格式化               │
│  文件：api/controllers/chat_controller.py                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Service 层（业务逻辑层）                   │
│  职责：意图识别、闲聊处理、数据查询、结果总结                 │
│  - services/intent_service.py     意图识别                   │
│  - services/chat_service.py       闲聊处理                   │
│  - services/data_query_service.py 数据查询                   │
│  - services/summary_service.py    结果总结                   │
└─────────────────────────────────────────────────────────────┘
                    ↓                           ↓
         ┌──────────────────┐         ┌──────────────────┐
         │  Orchestrator层   │         │  Orchestrator层   │
         │  (已存在)         │         │  (已存在)         │
         │  rag_in_action    │         │  rag_in_action    │
         └──────────────────┘         └──────────────────┘
                    ↓                           ↓
    ┌───────────────────────┐      ┌─────────────────────────┐
    │   RAG System (已存在)  │      │ Query Processor (已存在) │
    │   向量检索             │      │ LLM解析                 │
    └───────────────────────┘      └─────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Integration 层（数据访问层）                     │
│  - integration/data_executor.py   ⭐核心：RSSHub调用+RSS解析  │
│  - integration/session_store.py   会话存储                   │
│  - integration/cache_service.py   缓存服务                   │
└─────────────────────────────────────────────────────────────┘
```

### 核心工作流程

#### 场景1：数据查询
```
用户："虎扑步行街最新帖子"
  ↓
[Controller] 接收请求、提取session_id
  ↓
[Service-Intent] 意图识别 → data_query
  ↓
[Service-DataQuery]
  ↓
  [Orchestrator-RAG] RAG检索相关路由
  ↓
  [Orchestrator-LLM] LLM生成API路径
  ↓
[Integration-DataExecutor] ⭐执行RSSHub调用
  - 构造URL: https://rsshub.app/hupu/bbs/bxj/1
  - httpx异步请求
  - feedparser解析RSS
  ↓
[Integration-Cache] 缓存结果
  ↓
[Service-Summary] 可选：LLM总结
  ↓
[Controller] 格式化响应
```

#### 场景2：闲聊
```
用户："今天天气真好"
  ↓
[Controller] 接收请求
  ↓
[Service-Intent] 意图识别 → chat
  ↓
[Service-Chat] LLM生成友好回复
  ↓
[Controller] 返回响应
```

## 三、目录结构设计

```
D:\AIProject\omni/
│
├── api/                         【新增 - Controller层】
│   ├── __init__.py
│   ├── server.py                # FastAPI主服务器
│   ├── controllers/
│   │   ├── __init__.py
│   │   └── chat_controller.py   # 对话控制器
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── session_middleware.py # 会话管理中间件
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── request.py           # 请求数据模型
│   │   └── response.py          # 响应数据模型
│   └── config.py                # API配置
│
├── services/                    【新增 - Service层】
│   ├── __init__.py
│   ├── intent_service.py        # 意图识别服务
│   ├── chat_service.py          # 闲聊服务
│   ├── data_query_service.py    # 数据查询服务
│   └── summary_service.py       # 总结服务
│
├── integration/                 【新增 - Integration层】
│   ├── __init__.py
│   ├── data_executor.py         # RSS数据执行器 ⭐核心
│   ├── session_store.py         # 会话存储
│   └── cache_service.py         # 缓存服务
│
├── (其余已存在模块保持不变)
```

## 四、技术选型

| 层级 | 功能 | 技术选型 | 说明 |
|-----|------|---------|------|
| Controller | API框架 | FastAPI | 异步高性能，自动文档 |
| Controller | WebSocket | FastAPI WebSocket | 流式响应 |
| Service | 意图识别 | 规则引擎 + LLM (可选) | 初期用规则，后期升级 |
| Service | LLM调用 | 复用 `query_processor/llm_client.py` | 已有抽象层 |
| Integration | HTTP客户端 | `httpx` | 异步，现代化 |
| Integration | RSS解析 | `feedparser` | 成熟稳定 |
| Integration | 会话存储 | 内存dict（初期）→ Redis（生产） | 渐进式 |
| Integration | 缓存 | functools.lru_cache（初期）→ Redis（生产） | 渐进式 |

## 五、关键决策

### 决策1：意图识别策略

**问题**：如何快速区分"数据查询"和"闲聊"？

**方案对比**：
- A. 关键词规则：快速、无成本，准确率有限
- B. 小模型分类：较准确、需训练数据
- C. LLM判断：最准确但慢、有成本

**决策**：阶段3使用方案A（关键词规则），积累数据后考虑方案B

**理由**：符合CLAUDE.md "不过度设计"原则，先简单后复杂

### 决策2：会话存储方案

**问题**：使用内存还是Redis？

**决策**：
- 初期（单机测试）：内存存储（dict）
- 生产环境：Redis
- 代码使用抽象接口设计，方便切换

**理由**：渐进式架构，避免过早优化

### 决策3：缓存策略

**决策**：
- 缓存RSS数据：TTL 5-15分钟（根据数据源更新频率）
- 缓存RAG检索结果：TTL 1小时
- 缓存LLM解析结果：TTL 1小时

## 六、实施阶段及TODO

### 阶段0：任务文档准备 ✅
- [x] 创建任务文档
- [x] 更新索引文档

### 阶段1：Integration层 - 数据执行器（核心功能）
**目标**：能够调用RSSHub并解析RSS数据

- [ ] 创建 `integration/` 目录结构
- [ ] 实现 `integration/data_executor.py`
  - [ ] DataExecutor类定义
  - [ ] fetch_rss() 方法（httpx + feedparser）
  - [ ] 错误处理和重试机制
  - [ ] 标准化数据模型（Article类）
- [ ] 编写单元测试
- [ ] 验收测试：能成功获取并解析RSS数据

**验收标准**：
```python
executor = DataExecutor()
articles = await executor.fetch_rss("/hupu/bbs/bxj/1")
assert len(articles) > 0
assert articles[0].title is not None
```

### 阶段2：Service层 - 数据查询服务
**目标**：打通完整的数据查询流程

- [ ] 创建 `services/` 目录结构
- [ ] 实现 `services/data_query_service.py`
  - [ ] 集成 `orchestrator/rag_in_action.py`（获取路径）
  - [ ] 集成 `integration/data_executor.py`（执行获取）
  - [ ] 错误处理和降级策略
  - [ ] 返回标准化数据结构
- [ ] 编写单元测试
- [ ] 验收测试：端到端数据查询成功

**验收标准**：
```python
service = DataQueryService()
result = await service.query("虎扑步行街")
assert result["status"] == "success"
assert "articles" in result["data"]
```

### 阶段3：Service层 - 意图识别
**目标**：区分数据查询和闲聊

- [ ] 实现 `services/intent_service.py`
  - [ ] 定义意图枚举（data_query, chat, clarification）
  - [ ] 实现基于关键词规则的分类器
  - [ ] 定义查询关键词库
  - [ ] 定义闲聊关键词库
- [ ] 编写测试用例（至少30个典型case）
- [ ] 验收测试：意图识别准确率 > 85%

### 阶段4：Service层 - 闲聊服务
**目标**：处理非数据查询的对话

- [ ] 实现 `services/chat_service.py`
  - [ ] 复用 `query_processor/llm_client.py`
  - [ ] 设计闲聊Prompt模板
  - [ ] 支持上下文注入（可选）
- [ ] 编写单元测试
- [ ] 验收测试：能生成友好的闲聊回复

### 阶段5：Controller层 - 统一API
**目标**：提供前后端对接的REST API

- [ ] 创建 `api/` 目录结构
- [ ] 定义数据模型 `api/schemas/`
  - [ ] request.py：ChatRequest, QueryRequest等
  - [ ] response.py：ChatResponse, QueryResponse等
- [ ] 实现 `api/controllers/chat_controller.py`
  - [ ] POST /api/v1/chat 接口
  - [ ] 整合IntentService
  - [ ] 根据意图路由到不同Service
  - [ ] 统一响应格式
- [ ] 实现 `api/server.py`（FastAPI主服务器）
  - [ ] CORS配置
  - [ ] 异常处理中间件
  - [ ] 日志中间件
- [ ] API文档生成（Swagger）
- [ ] 验收测试：使用curl/Postman测试API

**验收标准**：
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "虎扑步行街最新帖子"}'
# 返回正确的RSS数据
```

### 阶段6：Integration层 - 会话管理
**目标**：支持多轮对话

- [ ] 实现 `integration/session_store.py`
  - [ ] SessionStore抽象接口
  - [ ] MemorySessionStore实现
  - [ ] 会话数据模型（history, context等）
  - [ ] TTL管理
- [ ] Controller层集成会话管理
  - [ ] 会话创建和加载
  - [ ] 会话上下文注入Service层
- [ ] 验收测试：多轮对话上下文正确

### 阶段7：集成与优化
**目标**：完善系统，提升稳定性和性能

- [ ] 实现缓存服务 `integration/cache_service.py`
  - [ ] 缓存RSS数据
  - [ ] 缓存RAG检索结果
  - [ ] TTL管理
- [ ] 完善错误处理
  - [ ] 统一异常类定义
  - [ ] 优雅降级策略
  - [ ] 详细错误日志
- [ ] 性能优化
  - [ ] 异步并发优化
  - [ ] 连接池配置
  - [ ] 超时控制
- [ ] 日志完善
  - [ ] 结构化日志
  - [ ] 关键节点耗时统计
- [ ] 文档完善
  - [ ] API使用文档
  - [ ] 部署文档
  - [ ] 架构文档更新

## 七、设计思考

### 为什么不使用微服务？

**原因**：
1. 项目初期，快速迭代更重要
2. 微服务运维复杂度高（容器编排、服务发现、网络通信）
3. 单体应用通过分层架构同样可以保持代码解耦
4. 符合CLAUDE.md "不过度设计"原则

### 为什么分这些层？

**Controller层**：
- 职责单一：接收请求、返回响应
- 不包含业务逻辑，只做"交通警察"

**Service层**：
- 核心业务逻辑：意图判断、数据查询、闲聊处理
- 可复用：不依赖HTTP框架，可用于其他入口（CLI、定时任务等）

**Integration层**：
- 所有"脏活累活"（I/O操作）集中在这里
- 易于Mock和测试
- 易于切换底层实现（内存→Redis）

### 渐进式架构理念

不一次性实现所有功能，而是：
1. 先实现核心路径（阶段1-2）
2. 再补充完整功能（阶段3-5）
3. 最后优化和完善（阶段6-7）

每个阶段都有明确的验收标准，确保质量。

## 八、风险与缓解

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| RSSHub不稳定或限流 | 数据获取失败 | 重试机制、错误降级、缓存 |
| 意图识别准确率低 | 用户体验差 | 积累数据逐步优化，提供澄清选项 |
| 会话管理复杂 | 多轮对话不准确 | 先实现简单版，逐步增强 |
| LLM调用慢 | 响应延迟 | 异步处理、流式返回、缓存 |

## 九、与CLAUDE.md规范的对齐

- ✅ 单个代码文件不超过1000行
- ✅ 优先复用现有代码（RAG、Query Processor、Orchestrator完全复用）
- ✅ 架构设计让边界情况自然融入常规逻辑
- ✅ 代码注释使用中文
- ✅ 不过度设计（单体应用、渐进式架构）
- ✅ 复杂任务创建任务文档
- ✅ 分阶段实施，每阶段使用TodoWrite跟踪进度

## 十、参考资料

- 项目架构文档：`../ARCHITECTURE.md`
- RAG系统文档：`../rag_system/README.md`
- 配置说明：`../CONFIGURATION.md`
- 环境变量模板：`../.env.example`
