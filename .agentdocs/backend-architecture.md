# 后端架构与技术约束

## 概述
本文档记录后端（Integration/Service/Controller层）的架构设计、技术约束和可复用组件规范。修改任何后端代码时必读。

## Integration层组件

### DataExecutor - RSS数据获取
**位置**: `integration/data_executor.py`

**职责**:
- 调用RSSHub API（仅本地部署，失败直接返回错误）
- 健康检查和连接管理
- 数据标准化（FeedItem模型）
- 错误处理和重试

**使用规范**:
```python
from integration.data_executor import DataExecutor, create_data_executor_from_config

# 方式1：从配置文件创建（推荐）
executor = create_data_executor_from_config()

# 方式2：使用上下文管理器
with DataExecutor() as executor:
    result = executor.fetch_rss("/hupu/bbs/bxj/1")

# 方式3：手动管理
executor = DataExecutor()
try:
    result = executor.fetch_rss("/path")
finally:
    executor.close()
```

**关键特性**:
1. **本地优先** - 依赖自托管 RSSHub (`http://localhost:1200`)，失败会直接返回错误并记录日志
2. **URL编码安全** - 正确处理特殊字符（`#`、中文等），避免HTTP fragment截断
3. **万物皆可RSS** - FeedItem模型支持视频、社交动态、论坛、商品等多种数据类型
4. **媒体信息提取** - 自动从RSSHub的enclosure字段提取图片/视频/音频URL

**重要记忆**:
- 默认由调用方管理 DataQueryService 生命周期；若设置 manage_data_service=True，ChatService 会在关闭时一并释放资源
- 所有RSSHub路径必须通过DataExecutor访问，不允许直接拼接URL
- 特殊字符路径（如`/hupu/bbs/#步行街主干道/1`）会被正确编码
- 返回的FetchResult包含`source`字段（当前仅会是`local`），用于数据来源追踪
- `DATA_QUERY_SINGLE_ROUTE=1` 或 `prefer_single_route=True` 时，DataQueryService 仅执行 primary route；未显式开启时才会尝试 RAG 的其它候选

### CacheService - TTL缓存管理
**位置**: `integration/cache_service.py`

**职责**:
- 提供线程安全的TTL缓存
- 支持不同类型缓存（RSS/RAG/LLM）
- 缓存统计和命中率跟踪

**使用规范**:
```python
from integration.cache_service import get_cache_service

# 获取全局单例（推荐）
cache = get_cache_service()

# RSS数据缓存（TTL 10分钟）
cache.set_rss_cache("/hupu/bbs/bxj/1", rss_data)
data = cache.get_rss_cache("/hupu/bbs/bxj/1")

# RAG检索结果缓存（TTL 1小时）
cache.set_rag_cache("用户查询", rag_result, top_k=5)
result = cache.get_rag_cache("用户查询", top_k=5)

# LLM解析结果缓存（TTL 1小时）
cache.set_llm_cache("prompt", llm_result, model="gpt-4", temperature=0.1)
result = cache.get_llm_cache("prompt", model="gpt-4", temperature=0.1)

# 获取统计信息
stats = cache.get_stats()
print(f"RSS命中率: {stats['rss_hit_rate']:.2%}")
```

**关键特性**:
1. **线程安全** - 使用`threading.RLock()`保证并发访问安全
2. **自动TTL管理** - 基于`cachetools.TTLCache`，自动清理过期项
3. **参数敏感缓存** - RAG和LLM缓存支持kwargs，不同参数产生不同缓存键
4. **全局单例模式** - `get_cache_service()`保证全局唯一实例

**重要记忆**:
- 所有数据缓存统一走CacheService，不允许使用functools.lru_cache
- RAG和LLM缓存键会考虑所有参数（包括kwargs），参数顺序不影响缓存命中
- 测试时使用`reset_cache_service()`重置全局实例

## 同步/异步策略

**当前实现**: Integration层和Service层保持同步实现

**原因**:
- 现有`RAGInAction`和LLM客户端均为同步阻塞实现
- 避免大规模改写现有模块
- 简化测试与复用

**Controller层处理**:
- FastAPI控制器通过`run_in_threadpool`调度同步Service
- 避免阻塞事件循环
- 可选的async包装在Service层提供

## URL编码最佳实践

**问题**: RSSHub路径可能包含特殊字符（`#`、空格、中文等），直接拼接会被截断

**解决方案**: `DataExecutor._build_request_url()`三步处理
1. **拆分** - `_split_path_and_query()` 分离路径和查询参数
2. **编码** - `_encode_path()` 对路径逐段URL编码
3. **组装** - `_build_query_params()` 去重format参数并重组URL

**示例**:
```python
# 输入: "/hupu/bbs/#步行街主干道/1?order=hot"
# 输出: "http://localhost:1200/hupu/bbs/%23%E6%AD%A5%E8%A1%8C%E8%A1%97%E4%B8%BB%E5%B9%B2%E9%81%93/1?order=hot&format=json"
```

## 测试策略

### 单元测试与集成测试分离
**位置**: `tests/integration/`

**规范**:
1. **纯单元测试** - 默认运行，不依赖外部服务
2. **真实服务测试** - 需要设置`RSSHUB_TEST_REAL=1`环境变量
3. **健康检查失败跳过** - 本地RSSHub未启动时自动跳过真实请求测试

**实现方式**:
```python
# 方式1：pytest fixture自动跳过
@pytest.fixture
def real_executor():
    exec_ = DataExecutor()
    if not exec_.ensure_rsshub_alive():
        pytest.skip("本地RSSHub未启动")
    yield exec_
    exec_.close()

# 方式2：环境变量控制
if os.getenv("RSSHUB_TEST_REAL", "0") != "1":
    pytest.skip("需要RSSHUB_TEST_REAL=1", allow_module_level=True)
```

**重要记忆**:
- 所有需要真实RSSHub的测试必须隔离到`TestDataExecutorReal`类或独立脚本
- CI和离线环境默认跳过真实服务测试，保证测试可重复执行
- 手动测试脚本使用`pytest.skip(..., allow_module_level=True)`退出

## 配置管理

### 服务层配置（推荐使用）
**位置**: `services/config.py` - `DataQueryConfig`

**配置项**:
```python
DATA_QUERY_SINGLE_ROUTE = "0"          # 单路模式开关（1=启用，0=禁用）
DATA_QUERY_MULTI_ROUTE_LIMIT = "3"     # 多路查询时的最大路由数量
DATA_QUERY_ANALYSIS_PREVIEW_MAX_ITEMS = "20"  # 分析总结时的最大数据采样数
DATA_QUERY_DESCRIPTION_MAX_LENGTH = "120"     # 描述文本的最大长度
```

**使用规范**:
```python
from services.config import get_data_query_config

# 获取配置单例
config = get_data_query_config()

# 访问配置项
if config.single_route_default:
    # 启用单路模式
    pass

# 测试时重置配置
from services.config import reset_data_query_config
reset_data_query_config()
```

**关键特性**:
1. **Pydantic V2 兼容** - 使用 `SettingsConfigDict` 配置
2. **环境变量自动映射** - 支持 `.env` 文件和系统环境变量
3. **单例模式** - 全局唯一配置实例，避免重复初始化
4. **忽略额外字段** - `extra='ignore'` 避免与其他配置冲突
5. **类型安全** - 运行时自动类型转换和验证

**重要记忆**:
- **禁止硬编码环境变量** - 所有服务层配置必须通过 `get_data_query_config()` 获取，不允许使用 `os.getenv()`
- **配置优先级** - 环境变量 > `.env` 文件 > 代码默认值
- **测试隔离** - 测试中使用 `reset_data_query_config()` 重置单例，避免测试间干扰
- **布尔值解析** - 支持 "1"/"true"/"yes" -> True, "0"/"false"/"no" -> False

### RSSHub配置
**位置**: `query_processor/config.py` - `RSSHubSettings`

**配置项**:
```python
RSSHUB_BASE_URL = "http://localhost:1200"  # 本地RSSHub地址
RSSHUB_HEALTH_CHECK_TIMEOUT = 3  # 健康检查超时（秒）
RSSHUB_REQUEST_TIMEOUT = 30  # 请求超时（秒）
RSSHUB_MAX_RETRIES = 2  # 最大重试次数
```

**重要记忆**:
- 配置统一使用Pydantic Settings管理
- 不允许在代码中硬编码RSSHub URL
- `PathSettings.base_url`已废弃，统一使用`RSSHubSettings.base_url`

## 依赖管理

**位置**: 根目录`requirements.txt`

**重要记忆**:
- 所有Python依赖统一在根目录`requirements.txt`维护
- 子目录`rag_system/`和`query_processor/`的requirements.txt改为引用`-r ../requirements.txt`
- 新增依赖必须添加到根目录文件，不允许子目录独立维护
- pytest已取消注释，为必需依赖

## FeedItem通用数据模型

**背景**: RSSHub支持"万物皆可RSS"，不仅限于文章/博客

**支持的数据类型**:
- 视频（B站、YouTube）
- 社交动态（微博、推特）
- 论坛帖子（虎扑、V2EX）
- 商品、天气、股票、GitHub仓库等

**模型设计**:
```python
@dataclass
class FeedItem:
    title: str                      # 标题
    link: str                       # 链接
    description: str                # 描述/摘要
    pub_date: Optional[str] = None  # 发布时间
    author: Optional[str] = None    # 作者/发布者

    # 通用扩展字段
    category: Optional[List[str]] = None     # 分类/标签
    media_url: Optional[str] = None          # 媒体URL
    media_type: Optional[str] = None         # 媒体类型（image/video/audio）
    raw_data: Optional[Dict[str, Any]] = None  # 原始数据
```

**重要记忆**:
- 不要将FeedItem命名为Article或Post，它是通用数据容器
- `media_type`从RSSHub的`enclosure.type`提取，无媒体时为`None`
- `raw_data`保留RSSHub返回的所有原始字段，供后续扩展使用

## 错误处理规范

### DataExecutor错误处理
1. **健康检查失败** - 记录异常并提示“本地RSSHub不可用”，不再自动切换远端服务
2. **请求超时/失败** - 重试`max_retries`次
3. **失败记录** - 日志中写明失败原因，便于排查本地部署
4. **异常封装** - 返回`FetchResult`，`status="error"`，附带错误信息

### CacheService错误处理
1. **缓存键生成失败** - 降级到字符串哈希
2. **并发访问冲突** - RLock保证线程安全
3. **内存溢出** - TTLCache自动LRU淘汰

## 性能优化记忆

1. **缓存TTL设置**:
   - RSS数据: 10分钟（平衡实时性和请求压力）
   - RAG结果: 1小时（相同查询避免重复计算）
   - LLM结果: 1小时（避免重复LLM调用成本）

2. **线程池策略**（后续Controller层实现）:
   - FastAPI使用`run_in_threadpool`调度同步Service
   - 避免阻塞事件循环
   - 超时控制防止线程泄漏

3. **连接复用**:
   - DataExecutor使用`httpx.Client`复用连接
   - 必须通过上下文管理器或手动close()释放资源

## Service层组件

### IntentService - 意图识别
**位置**: `services/intent_service.py`

**职责**:
- 判断用户查询的意图类型（data_query/chitchat）
- 基于规则+关键词的轻量级识别
- 提供置信度评分

**使用规范**:
```python
from services.intent_service import get_intent_service

# 获取全局单例（推荐）
service = get_intent_service()

# 识别意图
result = service.recognize("虎扑步行街最新帖子")
if result.intent_type == "data_query":
    # 调用数据查询服务
    pass

# 快捷方法
if service.is_data_query("虎扑步行街最新帖子", threshold=0.5):
    # 数据查询逻辑
    pass
```

**关键特性**:
1. **关键词匹配** - 维护数据查询和闲聊关键词列表
2. **置信度计算** - 基于关键词匹配数量，范围[0.5, 0.99]
3. **默认策略** - 包含问号 -> 数据查询；短查询 -> 闲聊；其他 -> 数据查询
4. **全局单例** - `get_intent_service()`保证全局唯一

### DataQueryService - 数据查询服务
**位置**: `services/data_query_service.py`

**职责**:
- 整合RAG检索、路径生成、RSS数据获取
- 双层缓存管理（RAG结果 + RSS数据）
- 统一查询结果封装

**使用规范**:
```python
from services.data_query_service import DataQueryService
from orchestrator.rag_in_action import create_rag_in_action

# 创建服务
rag_in_action = create_rag_in_action()
service = DataQueryService(rag_in_action, single_route_default=True)

# 使用上下文管理器（推荐）
with DataQueryService(rag_in_action) as service:
    result = service.query("虎扑步行街最新帖子")
    if result.status == "success":
        for item in result.items:
            print(item.title)
```

**关键特性**:
1. **双层缓存** - RAG结果缓存（避免重复RAG）+ RSS数据缓存（避免重复请求）
2. **智能缓存键** - RAG缓存包含filter_datasource参数
3. **资源管理** - 自动创建和释放DataExecutor
4. **统一结果** - DataQueryResult包含status/items/cache_hit/source/datasets/retrieved_tools等信息
5. **多路由查询** - 默认尝试 RAG 检索到的前 3 个候选路由，必要时可开启单路模式
6. **RAG 检索透明化** - 返回 retrieved_tools 字段，前端可展示 AI 推理过程（2025-11 新增）

**DataQueryResult 核心字段**:
- `status` - 查询状态（success/error/not_found/needs_clarification）
- `items` - 主数据集的数据项列表（兼容旧版）
- `datasets` - 多数据集列表（QueryDataset 类型），每个数据集对应一张前端卡片
- `retrieved_tools` - RAG 检索到的候选工具列表（包含 route_id、name、score 等）
- `cache_hit` - 缓存命中状态（rag_cache/rss_cache/none）
- `reasoning` - 推理过程或错误信息

**流程**:
1. 检查RAG缓存 → 2. 调用RAGInAction → 3. 缓存RAG结果 → 4. 多路由规划 → 5. 并行拉取数据 → 6. 返回多数据集结果

### ChatService - 统一对话服务
**位置**: `services/chat_service.py`

**职责**:
- 统一的对话入口
- 自动意图识别和路由
- 格式化响应

**使用规范**:
```python
from services.chat_service import ChatService

# 创建服务
# manage_data_service=True 表示 ChatService 负责在关闭时释放 data_query_service
service = ChatService(data_query_service, manage_data_service=True)

# 处理对话
response = service.chat("虎扑步行街最新帖子")
print(response.message)
if response.data:
    for item in response.data:
        print(item['title'])

# 转换为字典（API响应）
response_dict = response.to_dict()
```

**关键特性**:
1. **自动路由** - 根据IntentService识别结果路由到数据查询或闲聊
2. **统一响应** - ChatResponse包含success/intent_type/message/data/metadata
3. **闲聊支持** - 简单的关键词匹配响应（可扩展为LLM）
4. **元数据丰富** - 包含cache_hit/source/intent_confidence/retrieved_tools/datasets等调试信息
5. **RAG 透明化** - `_format_retrieved_tools()` 方法格式化候选工具列表，提取 route_id、name、score 等关键信息供前端展示

**重要记忆**:
- 所有对话入口统一走ChatService，不要直接调用DataQueryService
- ChatService 仅在 `manage_data_service=True` 时负责关闭 DataQueryService，默认由调用方管理生命周期
- 通过环境变量 `CHAT_SERVICE_MODE` 控制服务初始化（auto/production/mock），auto 模式下依赖缺失会自动回退到 MockChatService
- ChatResponse.to_dict()用于API响应序列化
- 闲聊响应当前是规则+模板，后续可接入LLM

## Controller层 (api/)

### 设计原则
1. **线程池解耦** - 使用`run_in_threadpool`执行同步Service，避免阻塞FastAPI事件循环
2. **统一响应格式** - 所有接口返回ApiResponse[T]统一结构
3. **异常集中处理** - 中间件统一捕获并转换为标准错误响应
4. **依赖注入** - 通过Depends()管理服务生命周期

### 核心组件

#### 1. ChatController (api/controllers/chat_controller.py)
**职责**: 处理HTTP请求，调用Service层，返回标准响应

**关键接口**:
```python
POST /api/v1/chat
- 请求: ChatRequest (query, filter_datasource, use_cache)
- 响应: ChatResponse (success, message, data, metadata)
- 实现: await run_in_threadpool(chat_service.chat, ...)
```

```python
GET /api/v1/health
- 响应: 健康状态 (chat_service, rsshub, rag, cache)
- 检查: RSSHub本地可用状态
```

**生命周期管理**:
- `initialize_services()` - 应用启动时创建全局ChatService (manage_data_service=True)
  - 支持环境变量 `CHAT_SERVICE_MODE` 控制初始化模式：
    - `auto`（默认）- 尝试创建真实服务，失败时回退到MockChatService
    - `mock` - 直接使用MockChatService（测试/无依赖环境）
    - `production` - 必须创建真实服务，失败则抛出异常
  - MockChatService提供简单的模拟响应，无需RAG/LLM/向量索引依赖
- `shutdown_services()` - 应用关闭时调用ChatService.close()
- `get_chat_service()` - 依赖注入函数，向路由提供服务实例

#### 2. 异常处理中间件 (api/middleware/exception_handlers.py)
**统一错误格式**:
```python
{
  "success": false,
  "error_code": "HTTP_404" | "VALIDATION_ERROR" | "INTERNAL_ERROR",
  "message": "错误描述",
  "detail": [...] // 仅验证错误时包含
}
```

**处理器**:
- `exception_handler_middleware` - 捕获所有未处理异常，返回500错误
- `http_exception_handler` - 处理HTTPException，返回对应状态码
- `validation_exception_handler` - 处理Pydantic验证错误，返回422+详情
- `add_process_time_header_middleware` - **[async def]** 添加X-Process-Time响应头（关键修复：必须是async函数，否则请求链中断）

#### 3. 统一响应Schema (api/schemas/responses.py)
**核心模型**:
- `FeedItemSchema` - RSS数据项（title/link/description/pub_date/media_url等）
- `ResponseMetadata` - 元数据（intent/cache_hit/source/confidence/retrieved_tools等）
- `ApiResponse[T]` - 泛型响应容器（success/message/data/metadata）
- `ChatRequest` - 对话请求（query必填，filter_datasource/use_cache可选）
- `ChatResponse` - 对话响应（继承ApiResponse[List[FeedItemSchema]]）

**ResponseMetadata 关键字段**:
- `intent_type` - 意图类型（data_query/chitchat）
- `intent_confidence` - 意图识别置信度
- `generated_path` - 生成的 RSS 路径
- `source` - 数据来源（local/fallback）
- `cache_hit` - 缓存命中情况（rag_cache/rss_cache/none）
- `retrieved_tools` - **RAG 检索到的候选工具列表**（用于前端展示 AI 推理过程）
- `datasets` - 多数据集摘要（route/feed_title/item_count）
- `warnings` - 面板生成警告列表

#### 4. FastAPI应用 (api/app.py)
**配置项**:
- CORS中间件 - 允许跨域（生产应限制域名）
- 异常处理 - 注册全局异常处理器
- 路由注册 - `/api/v1/chat`, `/api/v1/health`
- 生命周期 - startup事件初始化服务，shutdown事件释放资源
- API文档 - `/docs` (Swagger UI), `/redoc` (ReDoc)

**关键实现**:
```python
@app.on_event("startup")
async def startup_event():
    initialize_services()  # 创建全局ChatService

@app.on_event("shutdown")
async def shutdown_event():
    shutdown_services()  # 关闭ChatService（级联关闭DataQueryService）
```

### 关键技术决策

#### 同步Service + 异步Controller
**问题**: Service层是同步实现，FastAPI是异步框架
**方案**: 使用`fastapi.concurrency.run_in_threadpool`
```python
response = await run_in_threadpool(
    chat_service.chat,
    user_query=request.query,
    filter_datasource=request.filter_datasource,
    use_cache=request.use_cache,
)
```
**优点**:
- Service层保持同步，简化测试和RAG集成
- FastAPI事件循环不被阻塞，支持高并发
- 后续可平滑迁移到async Service（通过asyncio.to_thread）

#### 元数据映射
**问题**: Service层返回dict，API需要Pydantic模型
**方案**: 显式映射所有字段到ResponseMetadata
```python
metadata = ResponseMetadata(
    intent_type=response.metadata.get("intent_type"),
    intent_confidence=response.metadata.get("intent_confidence"),
    generated_path=response.metadata.get("generated_path"),
    source=response.metadata.get("source"),
    cache_hit=response.metadata.get("cache_hit"),
    feed_title=response.metadata.get("feed_title"),
    status=response.metadata.get("status"),
    reasoning=response.metadata.get("reasoning"),
)
```
**注意**: 所有字段Optional，Service层返回None时API也返回null

### 测试策略
**集成测试** (tests/api/test_chat_controller.py):
- 使用FastAPI TestClient（同步测试客户端）
- module级别fixture共享客户端（避免重复启动）
- 覆盖范围：
  - 根路径和健康检查
  - 基本对话查询（数据查询/闲聊）
  - 缓存控制（use_cache=true/false）
  - 验证错误（空查询/缺失参数/无效类型）
  - 响应格式（必需字段/元数据结构/处理时间头）
  - 并发请求（10个并发请求全部成功）
  - 错误处理（404/405）

**当前状态**: 13个测试全部通过 ✅（使用Mock模式，无需RAG/LLM依赖）

### 重要记忆
- **线程池必须** - 所有同步Service调用都必须通过run_in_threadpool，禁止直接在async函数中调用同步代码
- **依赖注入模式** - 路由通过Depends(get_chat_service)获取服务实例，不要在路由内部创建服务
- **生命周期管理** - ChatService在startup时创建（manage_data_service=True），在shutdown时关闭（级联释放所有资源）
- **Mock模式测试** - 使用`CHAT_SERVICE_MODE=mock`运行测试，避免强依赖RAG/LLM/向量索引；auto模式会自动回退
- **中间件async要求** - HTTP中间件（如add_process_time_header_middleware）必须是`async def`，否则请求链中断返回500
- **元数据完整性** - 所有metadata字段都要显式映射，即使值为None也要传递
- **错误响应统一** - 所有异常都通过中间件转换为{success, error_code, message, detail}格式

## WebSocket流式接口 (api/controllers/chat_stream.py)

### 设计原则
1. **按阶段推送** - 将处理过程拆分为4个阶段，逐步推送进度和数据
2. **线程池执行** - 使用`asyncio.to_thread + 生成器`模式，避免阻塞事件循环
3. **stream_id追踪** - 每个流式请求生成唯一ID，所有日志和消息都包含该ID
4. **统一消息格式** - 所有WebSocket消息遵循StreamMessage基类规范

### 核心组件

#### 1. 流式消息Schema (api/schemas/stream_messages.py)
**消息类型**:
- `StreamMessage` - 基类（type/stream_id/timestamp）
- `StageMessage` - 阶段更新（stage/message/progress）
- `DataMessage` - 数据推送（stage/data）
- `ErrorMessage` - 错误通知（error_code/error_message）
- `CompleteMessage` - 完成通知（success/message/total_time）

**流式阶段定义**:
```python
class StreamStage:
    INTENT = "intent"      # 意图识别 (progress=0.25)
    RAG = "rag"            # RAG检索 (progress=0.50)
    FETCH = "fetch"        # 数据获取 (progress=0.75)
    SUMMARY = "summary"    # 结果总结 (progress=1.0)
```

#### 2. WebSocket端点
**连接地址**: `ws://host:port/api/v1/chat/stream`

**客户端发送**:
```json
{
  "query": "用户查询",
  "filter_datasource": null,  // 可选
  "use_cache": true          // 可选
}
```

**服务端推送**:
```python
# 阶段更新
{"type": "stage", "stream_id": "stream-abc123", "stage": "intent",
 "message": "正在识别意图...", "progress": 0.25}

# 数据推送
{"type": "data", "stream_id": "stream-abc123", "stage": "intent",
 "data": {"intent_type": "data_query", "confidence": 0.95}}

# 完成通知
{"type": "complete", "stream_id": "stream-abc123",
 "success": true, "message": "查询完成", "total_time": 2.5}
```

#### 3. 流式处理流程
```python
def stream_chat_processing(...) -> Generator[dict, None, None]:
    # 阶段1: 意图识别
    yield StageMessage(stage="intent", progress=0.25)
    yield DataMessage(stage="intent", data={...})

    # 阶段2: RAG检索（仅数据查询）
    if intent == "data_query":
        yield StageMessage(stage="rag", progress=0.50)
        yield DataMessage(stage="rag", data={...})

    # 阶段3: 数据获取
    yield StageMessage(stage="fetch", progress=0.75)
    response = chat_service.chat(...)
    yield DataMessage(stage="fetch", data={...})

    # 阶段4: 结果总结
    yield StageMessage(stage="summary", progress=1.0)
    yield DataMessage(stage="summary", data=response.to_dict())

    # 完成
    yield CompleteMessage(success=True, total_time=...)
```

#### 4. 异步执行策略
**问题**: 生成器是同步的，WebSocket端点是async的
**方案**: 使用`asyncio.to_thread`在线程池中逐个获取消息
```python
@router.websocket("/chat/stream")
async def chat_stream(websocket: WebSocket, chat_service=Depends(...)):
    await websocket.accept()
    stream_id = generate_stream_id()  # stream-{uuid[:12]}

    # 创建生成器
    message_generator = stream_chat_processing(
        chat_service, user_query, stream_id, ...
    )

    # 在线程池中逐个获取消息并发送
    while True:
        message = await asyncio.to_thread(next, message_generator, None)
        if message is None:
            break
        await websocket.send_json(message)
```

**优点**:
- WebSocket事件循环不被阻塞
- 支持真正的流式推送（不需要等待全部完成）
- 可以随时中断（客户端断开连接）

### 测试策略
**端到端测试** (tests/api/test_chat_stream.py):
- 使用FastAPI TestClient的`websocket_connect()`
- 13个测试覆盖所有场景：
  - WebSocket连接和stream_id生成
  - 消息类型序列验证（stage→data→complete）
  - 消息结构验证（所有字段存在且类型正确）
  - 流式阶段顺序验证（intent→rag→fetch→summary）
  - 错误处理（空查询、无效JSON、连接断开）
  - 缓存控制和数据源过滤
  - 进度值有效性（0.0-1.0递增）

**当前状态**: 13个测试全部通过 ✅

### 客户端示例
**Python客户端**:
```python
import asyncio
import websockets
import json

async def stream_query(query: str):
    uri = "ws://localhost:8000/api/v1/chat/stream"
    async with websockets.connect(uri) as ws:
        # 发送查询
        await ws.send(json.dumps({"query": query}))

        # 接收流式消息
        async for message in ws:
            data = json.loads(message)

            if data['type'] == 'stage':
                print(f"[{data['progress']*100:.0f}%] {data['message']}")
            elif data['type'] == 'data':
                print(f"数据: {data['data']}")
            elif data['type'] == 'complete':
                print(f"完成: {data['message']} (耗时{data['total_time']:.2f}s)")
                break
            elif data['type'] == 'error':
                print(f"错误: {data['error_message']}")
                break

asyncio.run(stream_query("虎扑步行街最新帖子"))
```

**JavaScript客户端**:
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/chat/stream');

ws.onopen = () => {
    ws.send(JSON.stringify({query: '虎扑步行街最新帖子'}));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'stage') {
        console.log(`[${data.progress*100}%] ${data.message}`);
    } else if (data.type === 'data') {
        console.log('数据:', data.data);
    } else if (data.type === 'complete') {
        console.log(`完成: ${data.message}`);
        ws.close();
    }
};
```

### 重要记忆
- **生成器 + asyncio.to_thread** - WebSocket流式接口必须使用此模式，禁止直接在async函数中调用同步生成器
- **stream_id必须** - 每个流式请求都必须生成唯一stream_id，所有日志和消息都包含该ID
- **阶段顺序** - 流式阶段必须按顺序推送：intent → rag（可选）→ fetch → summary
- **complete最后** - 每个流式请求最后必须发送complete消息，无论成功失败
- **错误即关闭** - 发送error消息后应立即发送complete并关闭连接

## RAG 检索结果展示（retrieved_tools）

### 功能说明
从 2025-11 版本开始，`metadata.retrieved_tools` 字段包含 RAG 检索到的候选工具列表，前端可利用此信息：
1. 展示 AI 推理过程（让用户了解系统考虑了哪些数据源）
2. 提供快速切换功能（点击候选工具重新查询）
3. 相关推荐（基于检索结果推荐相关数据源）
4. 调试信息（开发时查看 RAG 效果和评分）

此外，为了透明化 LLM 行为，`metadata.debug.llm_calls` 会记录本次请求涉及的所有 LLM 调用（意图分类、查询规划等），包含截断后的 prompt/response；`metadata.debug.rag` 则提供 RAG 解析轨迹（selected_tool、参数填充、retrieved_tools preview）。调试前端可以直接读取该字段渲染“模型推理过程”面板。

> **注意**：无论查询最终状态是 `success`、`needs_clarification`、`not_found` 还是 `error`，都会透出同一次 RAG 检索得到的候选工具，方便用户在失败场景下也能看到“系统已经考虑过什么”。

### 数据格式

```json
{
  "metadata": {
    "retrieved_tools": [
      {
        "route_id": "bilibili/hot-search",
        "name": "B站热搜",
        "provider": "bilibili",
        "description": "B站热搜榜单，包含当前最热门的话题和视频",
        "score": 0.92,
        "route": "/bilibili/hot-search"
      },
      {
        "route_id": "bilibili/ranking",
        "name": "B站排行榜",
        "provider": "bilibili",
        "description": "B站各分区排行榜",
        "score": 0.78,
        "route": "/bilibili/ranking/:rid/:day?",
        "example_path": "/bilibili/ranking/0/3"
      }
    ],
    "generated_path": "/bilibili/hot-search",
    ...
  }
}
```

### 前端使用示例

```typescript
// 获取 RAG 候选工具
const response = await chatApi.chat({
  query: '我想看bilibili热搜',
  mode: 'auto',
});

const retrievedTools = response.metadata?.retrieved_tools || [];

// 场景1: 展示 AI 推理过程
console.log(`系统考虑了 ${retrievedTools.length} 个数据源：`);
retrievedTools.forEach((tool, index) => {
  console.log(`${index + 1}. ${tool.name} (相似度: ${tool.score})`);
});

// 场景2: 实现快速切换
function switchToTool(toolRouteId: string) {
  const tool = retrievedTools.find(t => t.route_id === toolRouteId);
  if (tool) {
    // 重新查询该数据源
    chatApi.chat({
      query: `查询 ${tool.name}`,
      mode: 'simple',
    });
  }
}

// 场景3: 相关推荐
const recommendations = retrievedTools
  .filter(t => t.score > 0.7)
  .slice(1, 4) // 排除第一个（已使用），取接下来的3个
  .map(t => ({
    title: t.name,
    description: t.description,
    onClick: () => switchToTool(t.route_id),
  }));
```

### Vue 组件示例

```vue
<template>
  <div class="retrieved-tools">
    <h3>系统考虑的数据源</h3>
    <div v-for="tool in retrievedTools" :key="tool.route_id" class="tool-card">
      <div class="tool-header">
        <span class="tool-name">{{ tool.name }}</span>
        <span class="tool-score">{{ (tool.score * 100).toFixed(0) }}% 匹配</span>
      </div>
      <p class="tool-description">{{ tool.description }}</p>
      <button @click="switchToTool(tool.route_id)">查看此数据源</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { ChatResponse } from '@/types/api';

const props = defineProps<{
  response: ChatResponse;
}>();

const retrievedTools = computed(() =>
  props.response.metadata?.retrieved_tools || []
);

function switchToTool(routeId: string) {
  // 实现切换逻辑
}
</script>
```

### 重要记忆
- **description 已限制长度**：后端限制为 100 字符，前端可直接使用，无需再次截断
- **score 为相似度评分**：范围 0.0-1.0，越高表示与用户查询越相关
- **route 包含参数占位符**：如 `/bilibili/ranking/:rid/:day?`，需要根据实际需求填充参数
- **空列表是正常的**：某些情况下 RAG 可能只返回一个工具，retrieved_tools 可能为空数组

## 后续扩展规划

1. **Redis缓存** - CacheService设计支持替换为Redis，不改业务代码
2. **异步支持** - Service层可补充async包装方法，通过`asyncio.to_thread`调用同步实现
3. **监控指标** - RSSHub 可用性、缓存命中率、响应耗时等
4. **LLM闲聊** - ChatService的闲聊响应可接入真实LLM，提供更自然的对话
5. **流式优化** - 实现Service层回调机制，在RAG/数据获取阶段实时推送中间结果（目前是模拟）

