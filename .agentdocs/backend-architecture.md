# 后端架构与技术约束

## 概述
本文档记录后端（Integration/Service/Controller层）的架构设计、技术约束和可复用组件规范。修改任何后端代码时必读。

## Integration层组件

### DataExecutor - RSS数据获取
**位置**: `integration/data_executor.py`

**职责**:
- 调用RSSHub API（本地优先，支持降级到公共服务）
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
1. **本地优先降级机制** - 优先使用`http://localhost:1200`，失败后降级到`https://rsshub.app`
2. **URL编码安全** - 正确处理特殊字符（`#`、中文等），避免HTTP fragment截断
3. **万物皆可RSS** - FeedItem模型支持视频、社交动态、论坛、商品等多种数据类型
4. **媒体信息提取** - 自动从RSSHub的enclosure字段提取图片/视频/音频URL

**重要记忆**:\n- 默认由调用方管理 DataQueryService 生命周期；若设置 manage_data_service=True，ChatService 会在关闭时一并释放资源
- 所有RSSHub路径必须通过DataExecutor访问，不允许直接拼接URL
- 特殊字符路径（如`/hupu/bbs/#步行街主干道/1`）会被正确编码
- 返回的FetchResult包含`source`字段（local/fallback），用于监控降级情况

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

### RSSHub配置
**位置**: `query_processor/config.py` - `RSSHubSettings`

**配置项**:
```python
RSSHUB_BASE_URL = "http://localhost:1200"  # 本地RSSHub地址
RSSHUB_FALLBACK_URL = "https://rsshub.app"  # 降级地址
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
1. **健康检查失败** - 自动切换到fallback URL
2. **请求超时/失败** - 重试`max_retries`次
3. **降级记录** - 日志中写明降级原因
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
service = DataQueryService(rag_in_action)

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
4. **统一结果** - DataQueryResult包含status/items/cache_hit/source等信息

**流程**:
1. 检查RAG缓存 → 2. 调用RAGInAction → 3. 缓存RAG结果 → 4. 检查RSS缓存 → 5. 调用DataExecutor → 6. 缓存RSS数据 → 7. 返回结果

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
4. **元数据丰富** - 包含cache_hit/source/intent_confidence等调试信息

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
- 检查: RSSHub本地/降级状态
```

**生命周期管理**:
- `initialize_services()` - 应用启动时创建全局ChatService (manage_data_service=True)
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
- `add_process_time_header_middleware` - 添加X-Process-Time响应头

#### 3. 统一响应Schema (api/schemas/responses.py)
**核心模型**:
- `FeedItemSchema` - RSS数据项（title/link/description/pub_date/media_url等）
- `ResponseMetadata` - 元数据（intent/cache_hit/source/confidence等）
- `ApiResponse[T]` - 泛型响应容器（success/message/data/metadata）
- `ChatRequest` - 对话请求（query必填，filter_datasource/use_cache可选）
- `ChatResponse` - 对话响应（继承ApiResponse[List[FeedItemSchema]]）

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

**当前状态**: 12个测试全部通过 ✅

### 重要记忆
- **线程池必须** - 所有同步Service调用都必须通过run_in_threadpool，禁止直接在async函数中调用同步代码
- **依赖注入模式** - 路由通过Depends(get_chat_service)获取服务实例，不要在路由内部创建服务
- **生命周期管理** - ChatService在startup时创建（manage_data_service=True），在shutdown时关闭（级联释放所有资源）
- **元数据完整性** - 所有metadata字段都要显式映射，即使值为None也要传递
- **错误响应统一** - 所有异常都通过中间件转换为{success, error_code, message, detail}格式

## 后续扩展规划

1. **Redis缓存** - CacheService设计支持替换为Redis，不改业务代码
2. **异步支持** - Service层可补充async包装方法，通过`asyncio.to_thread`调用同步实现
3. **监控指标** - 降级次数、缓存命中率、响应耗时等
4. **LLM闲聊** - ChatService的闲聊响应可接入真实LLM，提供更自然的对话
5. **WebSocket流式** - 阶段5将实现按阶段推送的流式接口（意图识别→检索→数据→总结）

