# Service层使用指南

## 概述
Service层是业务逻辑层，负责整合Integration层的组件，提供完整的业务功能。所有外部调用都应该通过Service层进行，不应直接调用Integration层组件。

## 架构层次
```
Controller层
    ↓
Service层 (IntentService → DataQueryService)
    ↓
Integration层 (DataExecutor + CacheService)
    ↓
基础设施层 (RAGInAction)
```

## 核心服务使用

### 1. IntentService - 意图识别

**位置**: `services/intent_service.py`

**职责**: 判断用户查询意图（数据查询 vs 闲聊）

**创建方式**:
```python
from services.intent_service import get_intent_service

# 推荐使用全局单例
service = get_intent_service()

# 或直接创建
from services.intent_service import IntentService
service = IntentService()
```

**基本使用**:
```python
# 意图识别
result = service.recognize("虎扑步行街最��帖子")
print(f"意图: {result.intent_type}")  # data_query/chitchat
print(f"置信度: {result.confidence}")  # 0.5-0.99
print(f"推理: {result.reasoning}")

# 快捷判断
if service.is_data_query("虎扑步行街最新帖子", threshold=0.5):
    print("这是数据查询意图")
```

**关键词列表**:
- 数据查询关键词：虎扑、微博、知乎、bilibili、帖子、文章、视频、最新、热门等
- 闲聊关键词：你好、您好、hi、hello、谢谢、再见等

### 2. DataQueryService - 数据查询

**位置**: `services/data_query_service.py`

**职责**: 整合RAG检索、RSS数据获取和缓存

**创建方式**:
```python
from services.data_query_service import DataQueryService
from orchestrator.rag_in_action import create_rag_in_action

# 创建RAG实例
rag_in_action = create_rag_in_action()

# 创建服务
service = DataQueryService(rag_in_action)

# 使用上下文管理器（推荐）
with DataQueryService(rag_in_action) as service:
    result = service.query("虎扑步行街最新帖子")
```

**基本使用**:
```python
# 查询数据
result = service.query(
    user_query="虎扑步行街最新帖子",
    filter_datasource=None,  # 可选：过滤特定数据源
    use_cache=True          # 可选：是否使用缓存
)

if result.status == "success":
    print(f"标题: {result.feed_title}")
    print(f"路径: {result.generated_path}")
    print(f"来源: {result.source}")  # local/fallback
    print(f"缓存命中: {result.cache_hit}")  # rag_cache/rss_cache/none

    for item in result.items:
        print(f"- {item.title}")
        print(f"  {item.link}")
        if item.media_url:
            print(f"  媒体: {item.media_url} ({item.media_type})")
```

**查询状态**:
- `success`: 成功获取数据
- `needs_clarification`: 需要澄清（查看`result.clarification_question`）
- `not_found`: 未找到匹配功能
- `error`: 处理失败（查看`result.reasoning`）

### 3. ChatService - 统一对话

**位置**: `services/chat_service.py`

**职责**: 统一的对话入口，自动意图识别和路由

**创建方式**:
```python
from services.chat_service import ChatService
from services.data_query_service import DataQueryService

# 先创建DataQueryService
data_service = DataQueryService(rag_in_action)

# 创建对话服务
# manage_data_service=True 表示 ChatService 会在关闭时一并释放 data_service
chat_service = ChatService(data_service, manage_data_service=True)
```
> 如需复用同一个 `DataQueryService` 实例（例如在多个入口共享），请保持 `manage_data_service=False`（默认值），并由调用方负责生命周期管理。

**基本使用**:
```python
# 处理对话
response = chat_service.chat("虎扑步行街最新帖子")

print(f"成功: {response.success}")
print(f"意图: {response.intent_type}")  # data_query/chitchat
print(f"消息: {response.message}")

if response.data:
    print(f"数据条数: {len(response.data)}")
    for item in response.data:
        print(f"- {item['title']}")

# 查看元数据
metadata = response.metadata
print(f"缓存命中: {metadata.get('cache_hit')}")
print(f"数据来源: {metadata.get('source')}")
print(f"意图置信度: {metadata.get('intent_confidence')}")

# 转换为字典（API响应用）
response_dict = response.to_dict()
```

## 典型使用场景

### 场景1：数据查询
```python
# 通过ChatService（推荐）
response = chat_service.chat("B站最新视频")
if response.success:
    for video in response.data:
        print(f"视频: {video['title']}")

# 直接通过DataQueryService
result = data_service.query("虎扑步行街最新帖子")
if result.status == "success":
    for item in result.items:
        print(f"帖子: {item.title}")
```

### 场景2：闲聊
```python
response = chat_service.chat("你好")
print(response.message)  # "你好！我是RSS数据聚合助手..."
```

### 场景3：缓存控制
```python
# 禁用缓存（强制重新查询）
result = data_service.query("虎扑最新帖子", use_cache=False)

# 查看缓存状态
metadata = chat_service.chat("虎扑").metadata
print(f"缓存命中: {metadata['cache_hit']}")
```

## 性能优化

### 缓存策略
- **RAG缓存**: TTL 1小时，相同查询避免重复RAG计算
- **RSS缓存**: TTL 10分钟，相同路径避免重复HTTP请求
- **缓存键**: RAG缓存包含filter_datasource参数，确保精确匹配

### 资源管理
- 使用上下文管理器确保资源释放
- DataQueryService会自动创建和关闭DataExecutor
- CacheService使用全局单例，无需手动管理

## 错误处理

### IntentService错误
- 基本不会出错，使用规则+关键词
- 空查询返回chitchat意图

### DataQueryService错误
- RAG失败: 返回`not_found`状态
- RSS获取失败: 返回`error`状态
- 网络问题: DataExecutor自动重试和降级

### ChatService错误
- 意图识别失败: fallback为data_query
- 数据查询失败: 返回错误消息
- 系统异常: 返回友好错误信息

## 扩展点

### IntentService扩展
- 可接入LLM进行更准确的意图识别
- 可添加更多意图类型（如情感分析）
- 可调整关键词列表和权重

### ChatService扩展
- 可接入真实LLM进行闲聊
- 可添加对话历史管理
- 可添加用户个性化设置

### DataQueryService扩展
- 可添加数据源过滤
- 可添加结果排序和分页
- 可添加数据聚合和分析

## 重要约束

1. **不要绕过Service层**: 所有业务调用必须通过Service层，不应直接调用Integration层组件
2. **��用全局单例**: IntentService和CacheService使用全局单例，避免重复创建
3. **资源管理**: DataQueryService使用上下文管理器或手动close()
4. **缓存策略**: 优先使用缓存，只有需要强制刷新时才禁用
5. **错误处理**: 统一使用Service层的错误处理，不要在调用层单独处理
