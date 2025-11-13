# 订阅系统 Phase 2: 智能解析实施任务

> **任务目标**：实现订阅系统的智能解析功能，让用户可以通过自然语言查询订阅内容
>
> **相关文档**：
> - Phase 1 任务：`.agentdocs/workflow/251113-subscription-system-implementation.md`
> - 订阅系统设计：`.agentdocs/subscription-system-design.md`
> - 后端架构：`.agentdocs/backend-architecture.md`
>
> **创建时间**：2025-11-14
> **预计工期**：3-5 天

---

## 一、现状分析

### 1.1 Phase 1 已完成的基础设施

✅ **数据层**：
- `Subscription` 模型（实体 + 标识符）
- `SubscriptionEmbedding` 模型（向量化记录表，但未实际使用）
- SubscriptionService（CRUD + resolve_entity）

✅ **配置层**：
- ActionRegistry（动作注册表，支持查询 supported_actions）
- action_registry_config.json（配置文件）

✅ **API 层**：
- RESTful CRUD 接口
- `/api/v1/subscriptions/resolve` - 解析实体接口

✅ **前端**：
- 订阅管理界面（手动添加、编辑、删除）
- 动作按钮（已集成 panelStore.requestPanel）

### 1.2 Phase 2 需要实现的功能

❌ **QueryParser（查询解析器）**
- 输入："科技美学的最新投稿"
- 输出：`{entity_name: "科技美学", action: "投稿视频"}`
- 使用 LLM 智能解析自然语言查询

❌ **SubscriptionVectorStore（向量检索服务）**
- 使用 bge-m3 模型向量化订阅信息
- 独立的 ChromaDB Collection：`subscription_embeddings`
- 支持语义搜索（"那岩" → "科技美学"）

❌ **SimpleChatNode 集成**
- 在对话中智能识别订阅查询
- 优先从订阅系统解析实体
- 失败时回退到实时搜索

❌ **fetch_public_data 工具增强**
- 检测查询是否涉及订阅实体
- 使用 resolve_entity + ActionRegistry 构建路径

---

## 二、方案设计

### 2.1 查询解析流程

```
用户输入："科技美学的最新投稿视频"
    ↓
┌─────────────────────────────────────────────┐
│ Step 1: QueryParser（LLM 解析）              │
├─────────────────────────────────────────────┤
│ 提取：                                        │
│ - entity_name: "科技美学"                     │
│ - action: "投稿视频"                          │
│ - platform: "bilibili" (可选推断)             │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ Step 2: SubscriptionVectorStore（语义搜索）  │
├─────────────────────────────────────────────┤
│ 搜索 "科技美学" 相似的订阅：                   │
│ - 精确匹配 display_name                      │
│ - 模糊匹配 aliases (["科技美学Official", "那岩"])│
│ - 向量语义搜索（容错）                         │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ Step 3: resolve_entity（获取标识符）           │
├─────────────────────────────────────────────┤
│ 返回：                                        │
│ - subscription_id: 1                         │
│ - identifiers: {"uid": "12345"}              │
│ - platform: "bilibili"                       │
│ - entity_type: "user"                        │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ Step 4: ActionRegistry（构建路径）            │
├─────────────────────────────────────────────┤
│ 映射动作：                                    │
│ - "投稿视频" → action="videos"               │
│ - 查询：(bilibili, user, videos)             │
│ - 路径模板："/bilibili/user/video/:uid"      │
│ - 填充标识符："/bilibili/user/video/12345"   │
└─────────────────────────────────────────────┘
    ↓
调用 RSSHub API 获取数据
```

### 2.2 核心组件设计

#### QueryParser（查询解析器）

```python
# services/subscription/query_parser.py
from pydantic import BaseModel
from typing import Optional
from services.llm.llm_service import LLMService

class ParsedQuery(BaseModel):
    """解析后的查询结果"""
    entity_name: str  # "科技美学"
    action: Optional[str] = None  # "投稿视频"
    platform: Optional[str] = None  # "bilibili"
    confidence: float  # 0.0-1.0

class QueryParser:
    """查询解析器（LLM 驱动）

    将自然语言查询解析为结构化信息。
    """

    SYSTEM_PROMPT = """你是一个订阅查询解析助手。

用户会输入对订阅内容的查询，你需要提取：
1. entity_name: 实体名称（UP主、专栏、仓库等）
2. action: 用户想查看的动作（投稿视频、关注列表、commits 等）
3. platform: 平台（可选，如果能推断出来）

示例：
- 输入："科技美学的最新投稿" → entity_name="科技美学", action="投稿视频", platform="bilibili"
- 输入："少数派专栏的文章" → entity_name="少数派", action="文章", platform="zhihu"
- 输入："langchain的最新commits" → entity_name="langchain", action="commits", platform="github"

以 JSON 格式返回结果。"""

    def __init__(self):
        self.llm = LLMService()

    async def parse(self, query: str) -> ParsedQuery:
        """解析查询

        Args:
            query: 用户输入的自然语言查询

        Returns:
            解析后的结构化查询
        """
        # 调用 LLM 解析
        response = await self.llm.chat(
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ],
            response_format={"type": "json_object"}
        )

        # 解析 JSON 响应
        result = json.loads(response)

        return ParsedQuery(
            entity_name=result["entity_name"],
            action=result.get("action"),
            platform=result.get("platform"),
            confidence=result.get("confidence", 0.8)
        )
```

#### SubscriptionVectorStore（向量检索服务）

```python
# services/subscription/vector_service.py
from typing import List, Optional, Tuple
import chromadb
from services.embedding.embedding_service import EmbeddingService
from services.database import SubscriptionService

class SubscriptionVectorStore:
    """订阅向量检索服务

    使用 ChromaDB 存储订阅的向量表示，支持语义搜索。
    """

    COLLECTION_NAME = "subscription_embeddings"

    def __init__(self):
        self.chroma_client = chromadb.PersistentClient(path="./runtime/chroma")
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "订阅实体向量"}
        )
        self.embedding_service = EmbeddingService()
        self.subscription_service = SubscriptionService()

    async def add_subscription(self, subscription_id: int) -> None:
        """向量化并添加订阅

        Args:
            subscription_id: 订阅 ID
        """
        # 获取订阅信息
        subscription = self.subscription_service.get_subscription(subscription_id)

        # 构建文本表示（用于向量化）
        text = self._build_text_representation(subscription)

        # 生成向量
        embedding = await self.embedding_service.embed(text)

        # 存储到 ChromaDB
        self.collection.add(
            ids=[str(subscription_id)],
            embeddings=[embedding],
            metadatas=[{
                "display_name": subscription.display_name,
                "platform": subscription.platform,
                "entity_type": subscription.entity_type,
            }],
            documents=[text]
        )

        # 更新 SubscriptionEmbedding 记录
        # TODO: 更新数据库记录

    async def search(
        self,
        query: str,
        platform: Optional[str] = None,
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """语义搜索订阅

        Args:
            query: 搜索查询（实体名称）
            platform: 平台过滤（可选）
            top_k: 返回数量

        Returns:
            [(subscription_id, similarity_score), ...]
        """
        # 生成查询向量
        query_embedding = await self.embedding_service.embed(query)

        # 构建过滤条件
        where = {"platform": platform} if platform else None

        # 向量检索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where
        )

        # 解析结果
        matches = []
        for i, subscription_id in enumerate(results["ids"][0]):
            similarity = 1 - results["distances"][0][i]  # 距离转相似度
            matches.append((int(subscription_id), similarity))

        return matches

    def _build_text_representation(self, subscription) -> str:
        """构建订阅的文本表示（用于向量化）

        包含：display_name, aliases, tags, description
        """
        parts = [subscription.display_name]

        if subscription.aliases:
            aliases = json.loads(subscription.aliases)
            parts.extend(aliases)

        if subscription.tags:
            tags = json.loads(subscription.tags)
            parts.extend(tags)

        if subscription.description:
            parts.append(subscription.description)

        return " | ".join(parts)
```

#### SubscriptionResolver（订阅解析器）

```python
# services/subscription/subscription_resolver.py
from typing import Optional, Dict, Any
from .query_parser import QueryParser, ParsedQuery
from .vector_service import SubscriptionVectorStore
from services.database import SubscriptionService
from services.subscription.action_registry import ActionRegistry

class SubscriptionResolver:
    """订阅解析器

    整合 QueryParser + VectorStore + ActionRegistry，
    实现从自然语言到 RSSHub 路径的完整解析。
    """

    def __init__(self):
        self.query_parser = QueryParser()
        self.vector_store = SubscriptionVectorStore()
        self.subscription_service = SubscriptionService()
        self.action_registry = ActionRegistry()

    async def resolve(self, query: str) -> Optional[Dict[str, Any]]:
        """解析查询并返回 RSSHub 路径

        Args:
            query: 用户输入的自然语言查询

        Returns:
            {
                "subscription_id": 1,
                "path": "/bilibili/user/video/12345",
                "display_name": "科技美学",
                "action_display_name": "投稿视频",
                "entity_name": "科技美学",
                "action": "videos"
            }
            或 None（解析失败）
        """
        # Step 1: 解析查询
        parsed = await self.query_parser.parse(query)

        # Step 2: 语义搜索订阅
        matches = await self.vector_store.search(
            query=parsed.entity_name,
            platform=parsed.platform,
            top_k=1
        )

        if not matches:
            return None

        subscription_id, similarity = matches[0]

        # 相似度阈值检查
        if similarity < 0.7:
            return None

        # Step 3: 获取订阅详情
        subscription = self.subscription_service.get_subscription(subscription_id)

        # Step 4: 解析动作
        action = self._resolve_action(parsed.action, subscription)

        if not action:
            # 如果未指定动作，返回默认动作
            supported_actions = json.loads(subscription.supported_actions)
            action = supported_actions[0] if supported_actions else None

        if not action:
            return None

        # Step 5: 构建路径
        action_def = self.action_registry.get_action(
            subscription.platform,
            subscription.entity_type,
            action
        )

        if not action_def:
            return None

        path = self.action_registry.build_path(
            subscription.platform,
            subscription.entity_type,
            action,
            json.loads(subscription.identifiers)
        )

        return {
            "subscription_id": subscription_id,
            "path": path,
            "display_name": subscription.display_name,
            "action_display_name": action_def.display_name,
            "entity_name": parsed.entity_name,
            "action": action,
            "similarity": similarity
        }

    def _resolve_action(self, action_text: Optional[str], subscription) -> Optional[str]:
        """解析动作名称

        将自然语言动作（如"投稿视频"）映射到动作名称（如"videos"）
        """
        if not action_text:
            return None

        supported_actions = json.loads(subscription.supported_actions)

        # 构建动作名称到显示名称的映射
        action_map = {}
        for action in supported_actions:
            action_def = self.action_registry.get_action(
                subscription.platform,
                subscription.entity_type,
                action
            )
            if action_def:
                action_map[action_def.display_name] = action

        # 模糊匹配
        action_text_lower = action_text.lower()
        for display_name, action_name in action_map.items():
            if action_text_lower in display_name.lower():
                return action_name

        return None
```

### 2.3 LangGraph 集成

#### 增强 SimpleChatNode

```python
# langgraph_agents/nodes/simple_chat_node.py（修改）

class SimpleChatNode:
    """简单对话节点（增强订阅支持）"""

    def __init__(self):
        # ... 现有初始化
        self.subscription_resolver = SubscriptionResolver()  # 新增

    async def execute(self, state: AgentState) -> AgentState:
        """执行节点逻辑（增强订阅检测）"""
        query = state["messages"][-1].content

        # 尝试从订阅系统解析
        subscription_result = await self.subscription_resolver.resolve(query)

        if subscription_result:
            # 找到订阅匹配，调用 fetch_public_data
            tool_result = await self._fetch_from_subscription(subscription_result)
            # ... 处理结果
        else:
            # 回退到原有逻辑
            # ... 现有处理
```

#### 增强 fetch_public_data 工具

```python
# langgraph_agents/tools/public_data_fetcher.py（修改）

class PublicDataFetcher:
    """公共数据获取工具（增强订阅支持）"""

    def __init__(self):
        # ... 现有初始化
        self.subscription_resolver = SubscriptionResolver()  # 新增

    async def fetch(
        self,
        query: str,
        datasource: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取数据（优先使用订阅）"""

        # 优先尝试从订阅系统解析
        if not datasource:  # 只有在未指定数据源时才尝试订阅
            subscription_result = await self.subscription_resolver.resolve(query)

            if subscription_result:
                # 使用订阅系统解析的路径
                return await self._fetch_from_rsshub(subscription_result["path"])

        # 回退到原有逻辑（实时搜索）
        # ... 现有处理
```

---

## 三、任务拆解

### Stage 1: QueryParser 实现（1天）✅

#### TODO
- [x] 创建 `services/subscription/query_parser.py`
- [x] 实现 `ParsedQuery` Pydantic 模型
- [x] 实现 `QueryParser` 类
  - [x] 设计 LLM Prompt（提取实体和动作）
  - [x] 集成现有 LLMService
  - [x] 支持 JSON 模式输出
- [x] 编写单元测试（`tests/services/test_query_parser.py`）
  - [x] 测试 B站查询解析
  - [x] 测试知乎查询解析
  - [x] 测试 GitHub 查询解析
  - [x] 测试边界情况

**验收标准**：
- ✅ 可以解析"科技美学的投稿视频"
- ✅ 可以解析"少数派的文章"
- ✅ 可以解析"langchain的commits"
- ✅ 单元测试全部通过（11/11）

---

### Stage 2: SubscriptionVectorStore 实现（1-2天）✅

#### TODO
- [x] 创建 `services/subscription/vector_service.py`
- [x] 实现 `SubscriptionVectorStore` 类
  - [x] 初始化 ChromaDB Collection
  - [x] 实现 `add_subscription()` 方法
  - [x] 实现 `search()` 方法
  - [x] 实现 `_build_text_representation()` 方法
- [x] 集成 bge-m3 模型（复用现有 EmbeddingModel）
  - [x] 延迟加载机制
  - [x] encode() 和 encode_queries() 方法
- [x] 实现订阅创建/更新时自动向量化
  - [x] 修改 `SubscriptionService.create_subscription()`
  - [x] 修改 `SubscriptionService.update_subscription()`
  - [x] 实现 `_trigger_embedding()` 方法
  - [x] 实现 `_semantic_search()` 方法
- [x] 编写单元测试（`tests/services/test_vector_service.py`）
  - [x] 测试向量化
  - [x] 测试语义搜索
  - [x] 测试别名匹配
  - [x] 测试批量操作

**验收标准**：
- ✅ 创建订阅时自动向量化
- ✅ 搜索"科技美学"能找到订阅
- ✅ 搜索"那岩"能找到"科技美学"订阅（别名匹配）
- ✅ 单元测试全部通过（17/17）

---

### Stage 3: SubscriptionResolver 实现（1天）✅

#### TODO
- [x] 创建 `services/subscription/subscription_resolver.py`
- [x] 实现 `SubscriptionResolver` 类
  - [x] 整合 QueryParser + VectorStore
  - [x] 实现 `resolve()` 方法
  - [x] 实现 `_resolve_action()` 方法
  - [x] 实现 `batch_resolve()` 方法（批量解析）
- [x] 编写集成测试（`tests/services/test_subscription_resolver.py`）
  - [x] 测试端到端解析流程
  - [x] 测试动作匹配
  - [x] 测试失败回退
  - [x] 测试批量解析
  - [x] 测试多平台支持（bilibili/github/zhihu）

**验收标准**：
- ✅ 输入"科技美学的投稿"返回正确的 RSSHub 路径
- ✅ 动作匹配支持自然语言（"视频" → videos, "动态" → dynamics）
- ✅ 集成测试全部通过（13/13）

---

### Stage 4: LangGraph 集成（1天）✅

#### TODO
- [x] 创建新工具 `fetch_subscription_data`（采用方案2：独立工具）
  - [x] 创建 `langgraph_agents/tools/subscription_data.py`
  - [x] 实现订阅查询工具
  - [x] 整合 SubscriptionResolver + DataQueryService
  - [x] 在 `bootstrap.py` 中注册工具
- [x] 编写单元测试（`tests/langgraph_agents/test_subscription_data_tool.py`）
  - [x] 测试工具注册
  - [x] 测试成功查询
  - [x] 测试订阅未找到
  - [x] 测试数据获取失败
  - [x] 测试参数验证
  - [x] 测试异常处理
  - [x] 测试依赖注入

**验收标准**：
- ✅ 新工具 `fetch_subscription_data` 成功注册
- ✅ LLM 可以智能选择订阅工具或实时搜索工具
- ✅ 支持自然语言查询："科技美学的投稿" → 正确解析
- ✅ 单元测试全部通过（8/8）
- ✅ 职责分离：订阅查询 vs 实时搜索

---

### Stage 5: 前端优化（可选，1天）

#### TODO
- [ ] 添加"智能查询"输入框（MainView）
- [ ] 订阅卡片显示向量化状态
- [ ] 添加"建议订阅"提示

**验收标准**：
- ✅ 前端可以直接使用智能查询
- ✅ 用户体验流畅

---

## 四、技术决策记录

### 4.1 为什么使用 LLM 而非规则匹配？

**决策**：使用 LLM 解析查询

**理由**：
1. **灵活性** - 用户输入方式多样，规则难以覆盖
2. **可扩展** - 新增平台或动作无需修改解析逻辑
3. **自然** - 符合用户自然语言习惯

**成本**：每次查询约 100-200 tokens（可接受）

### 4.2 为什么使用独立的 ChromaDB Collection？

**决策**：订阅向量使用独立的 Collection

**理由**：
1. **隔离性** - 与知识库向量分离，避免混淆
2. **性能** - 订阅数量少，检索速度快
3. **管理** - 可以单独管理向量版本

### 4.3 相似度阈值如何设定？

**决策**：相似度阈值 = 0.7

**理由**：
- < 0.7：匹配太宽泛，可能误匹配
- \>= 0.7：较高置信度，准确率高
- 后续可以根据用户反馈调整

---

## 五、风险与应对

### 5.1 风险：LLM 解析不准确

**应对**：
- 设计清晰的 Prompt，提供示例
- 使用 JSON Schema 约束输出格式
- 添加置信度评分，低置信度时提示用户

### 5.2 风险：向量化性能问题

**应对**：
- 异步向量化，不阻塞订阅创建
- 批量向量化（后台任务）
- 使用缓存机制

### 5.3 风险：与现有系统冲突

**应对**：
- 保持向后兼容，订阅系统为可选增强
- 失败时优雅降级到原有逻辑
- 添加开关控制是否启用智能解析

---

## 六、参考文档

- **Phase 1 任务**：`.agentdocs/workflow/251113-subscription-system-implementation.md`
- **订阅系统设计**：`.agentdocs/subscription-system-design.md`
- **后端架构**：`.agentdocs/backend-architecture.md`
- **LangGraph 架构**：`.agentdocs/langgraph-v4.4-architecture-design.md`

---

**任务状态**：⏳ 待开始
**创建日期**：2025-11-14
**预计完成**：2025-11-18
