# 订阅系统架构重构方案

**创建时间**：2025-11-14
**问题根源**：订阅系统定位错误，职责越界
**重构目标**：回归本质，订阅系统只做"名字→ID"映射

---

## 一、问题诊断

### 1.1 当前架构的根本错误

**错误认知**：订阅系统 = 智能查询解析器（一步到位生成路径）

```
当前流程（错误）：
用户查询: "行业101的投稿视频"
  ↓
订阅预检（DataQueryService）
  ↓
QueryParser 解析: entity="行业101", action="投稿视频"
  ↓
SubscriptionResolver 构建路径: /bilibili/user/video/1566847
  ↓
直接返回结果（跳过RAG）❌
```

**问题**：
1. ❌ 订阅系统承担了"查询理解"的职责（解析动作）
2. ❌ 订阅系统承担了"路径生成"的职责（构建完整路径）
3. ❌ 订阅预检在RAG之前执行（流程位置错误）
4. ❌ 无法处理多实体查询（"行业101和老番茄的投稿"）
5. ❌ RSSHub接口需要的是 `uid`（数字），不是名字

### 1.2 订阅系统的正确定位

**正确认知**：订阅系统 = 名字→ID 映射工具（仅此而已）

```
输入：
  - entity_name: "行业101"
  - platform: "bilibili"
  - entity_type: "user"

输出：
  - identifiers: {"uid": "1566847"}

职责：
  - ✅ 解决"人类友好名称"到"API标识符"的转换问题
  - ❌ 不解析用户意图
  - ❌ 不生成路径
  - ❌ 不获取数据
```

---

## 二、正确的架构设计

### 2.1 整体流程（简单查询）

```
用户查询: "我想看看bilibili中，up主行业101的视频投稿"
  ↓
【步骤1】RAG检索工具模板
  - 输入: "up主 投稿视频 bilibili"
  - 输出（工具定义）:
    * path_template: "/bilibili/user/video/:uid"
    * parameters: {
        "uid": {
          "description": "UP主的用户ID",
          "example": "123456"
        }
      }
    * （注意：实际上没有 type、pattern、required 等验证字段！）
  ↓
【步骤2】LLM提取参数
  - 输入: query + tool_template
  - 输出: {"uid": "行业101"}  ← 这是名字，不是ID！
  ↓
【步骤3】参数验证与智能解析（新增）⭐
  - 启发式检测: "行业101" 包含中文 → 可能是名字而非ID
  - 决策: 需要通过订阅系统转换
  - 调用订阅工具（携带完整RAG上下文）:
    * 输入:
      - entity_name: "行业101"
      - tool_definition: {  ← 完整RAG工具定义
          "path_template": "/bilibili/user/video/:uid",
          "parameters": {...}
        }
      - extracted_params: {"uid": "行业101"}  ← 已提取的所有参数
      - target_params: ["uid"]  ← 需要解析的参数列表
    * 内部逻辑:
      - 从 path_template 提取 platform: "bilibili"
      - 从 target_params[0]="uid" 推断 entity_type: "user"
      - 调用 SubscriptionService.resolve_entity("行业101", "bilibili", "user")
    * 输出: {"uid": "1566847"}  ← 完整的 identifiers（可能包含多个字段）
  - 合并参数: {"uid": "1566847"}
  ↓
【步骤4】构建路径并获取数据
  - path: "/bilibili/user/video/1566847"
  - 调用 RSSHub API
```

**关键改进**：
- ✅ 订阅工具接收**完整的 RAG 上下文**（tool_definition + extracted_params）
- ✅ 订阅工具从上下文中自动推断 platform 和 entity_type
- ✅ 返回完整的 `identifiers` 字典（可能包含多个标识符，如 `{"repo": "xxx", "owner": "yyy"}`）
- ✅ 参数验证使用**启发式规则**（包含中文/全数字/等），不依赖工具定义中不存在的验证字段

### 2.2 整体流程（复杂研究查询）

```
用户查询: "我想看看行业101的投稿视频以及老番茄的投稿视频"
  ↓
【Planner】拆分子任务
  - 子任务1: "获取bilibili up主行业101的投稿视频"
  - 子任务2: "获取bilibili up主老番茄的投稿视频"
  ↓
【Worker】处理子任务1
  ├─ 调用 fetch_public_data 工具
  │   ├─ RAG检索: /bilibili/user/video/:uid
  │   ├─ 提取参数: {"uid": "行业101"}
  │   ├─ 验证失败: "行业101" 不是数字
  │   ├─ 调用订阅工具: resolve_subscription_entity(
  │   │     entity_name="行业101",
  │   │     platform="bilibili",
  │   │     entity_type="user",  ← 从RAG工具定义获取
  │   │     required_param="uid"  ← 明确需要什么
  │   │   )
  │   ├─ 获得: {"uid": "1566847"}
  │   └─ 填充路径: /bilibili/user/video/1566847
  └─ 返回数据
  ↓
【Worker】处理子任务2（同样流程）
  - resolve_subscription_entity("老番茄") → {"uid": "9876543"}
  - 获取 /bilibili/user/video/9876543 数据
  ↓
【Summarizer】汇总结果
```

**关键点**：
- ✅ 订阅工具由 Worker 在参数验证阶段**按需调用**
- ✅ Planner 不需要知道订阅系统的存在
- ✅ 每个子任务独立调用订阅工具（支持多实体）

---

## 三、技术实施方案

### 3.1 订阅系统简化

#### 3.1.1 SubscriptionService 简化

**保留功能**：
```python
class SubscriptionService:
    """订阅管理服务（简化版）

    核心功能：实体名称 → API标识符 的映射
    """

    def resolve_entity(
        self,
        entity_name: str,      # "行业101"
        platform: str,         # "bilibili"
        entity_type: str,      # "user"
        user_id: Optional[int] = None
    ) -> Optional[Dict[str, str]]:
        """解析实体标识符（核心方法）

        Args:
            entity_name: 实体名称（人类友好）
            platform: 平台（从RAG工具定义获取）
            entity_type: 实体类型（从RAG参数定义推断）
            user_id: 用户ID（用于过滤订阅）

        Returns:
            {"uid": "1566847"} 或 {"cid": "123"} 或 None

        实现流程：
            1. 语义搜索订阅记录（VectorStore）
            2. 过滤: platform + entity_type
            3. 返回最佳匹配的 identifiers 字段
        """
        # 实现逻辑（已有代码，保持不变）
```

**移除功能**：
- ❌ 删除 `QueryParser`（不再解析查询意图）
- ❌ 删除 `SubscriptionResolver`（不再构建路径）
- ❌ 删除 `ActionRegistry` 相关集成（不需要知道动作）

#### 3.1.2 辅助函数（内部使用，不注册为工具）

```python
# services/subscription/entity_resolver_helper.py

from typing import Dict, Any, Optional, List
from services.database.subscription_service import SubscriptionService
import re

def resolve_entity_from_rag_context(
    entity_name: str,
    tool_definition: dict,
    extracted_params: dict,
    target_params: List[str]
) -> Optional[Dict[str, str]]:
    """从RAG上下文解析订阅实体（核心辅助函数）

    用途：
    在RAG参数验证阶段调用，携带完整的RAG上下文来解析订阅实体。
    订阅系统从上下文中自动推断需要的信息（platform, entity_type等）。

    参数：
    - entity_name: 实体名称（如"行业101"、"科技美学"）
    - tool_definition: RAG检索到的工具定义，包含：
        {
          "path_template": "/bilibili/user/video/:uid",
          "parameters": {"uid": {"description": "...", "example": "123456"}},
          "name": "...",
          "route_id": "bilibili_user-video"
        }
    - extracted_params: LLM已提取的所有参数，如 {"uid": "行业101"}
    - target_params: 需要解析的参数名列表，如 ["uid"]

    返回：
    成功: {"uid": "1566847"} 或 {"column_id": "123", "owner": "abc"} 等
    失败: None

    示例1（B站UP主）：
    >>> resolve_entity_from_rag_context(
    ...     entity_name="行业101",
    ...     tool_definition={"path_template": "/bilibili/user/video/:uid", ...},
    ...     extracted_params={"uid": "行业101"},
    ...     target_params=["uid"]
    ... )
    {"uid": "1566847"}

    示例2（知乎专栏）：
    >>> resolve_entity_from_rag_context(
    ...     entity_name="少数派",
    ...     tool_definition={"path_template": "/zhihu/column/:column_id/posts", ...},
    ...     extracted_params={"column_id": "少数派"},
    ...     target_params=["column_id"]
    ... )
    {"column_id": "123456"}

    示例3（GitHub仓库，多个标识符）：
    >>> resolve_entity_from_rag_context(
    ...     entity_name="langchain",
    ...     tool_definition={"path_template": "/github/:owner/:repo/commits", ...},
    ...     extracted_params={"owner": "langchain-ai", "repo": "langchain"},
    ...     target_params=["repo"]  # 只需要解析 repo
    ... )
    {"repo": "langchain", "owner": "langchain-ai"}  # 返回完整 identifiers
    """
    # 步骤1：从 path_template 提取 platform
    platform = _extract_platform_from_path(tool_definition.get("path_template", ""))

    if not platform:
        logger.warning("无法从工具定义提取 platform")
        return None

    # 步骤2：从 target_params 推断 entity_type
    entity_type = _infer_entity_type_from_params(target_params)

    logger.info(
        f"订阅解析上下文: entity_name='{entity_name}', "
        f"platform='{platform}', entity_type='{entity_type}', "
        f"target_params={target_params}"
    )

    # 步骤3：调用 SubscriptionService
    service = SubscriptionService()
    identifiers = service.resolve_entity(
        entity_name=entity_name,
        platform=platform,
        entity_type=entity_type,
        user_id=None
    )

    if identifiers:
        logger.info(
            f"✅ 订阅解析成功: '{entity_name}' → {identifiers}"
        )
        return identifiers
    else:
        logger.warning(
            f"⚠️  订阅解析失败: 未找到订阅 '{entity_name}' "
            f"(platform={platform}, entity_type={entity_type})"
        )
        return None


def _extract_platform_from_path(path_template: str) -> str:
    """从路径模板提取平台

    示例：
    - "/bilibili/user/video/:uid" → "bilibili"
    - "/zhihu/column/:column_id/posts" → "zhihu"
    - "/github/:owner/:repo/commits" → "github"
    """
    parts = path_template.strip("/").split("/")
    if parts:
        return parts[0]
    return ""


def _infer_entity_type_from_params(param_names: List[str]) -> str:
    """从参数名推断实体类型

    推断规则（启发式）：
    - uid, user_id, mid, member_id → "user"
    - column_id, cid → "column"
    - repo, repo_name, repository → "repo"
    - topic_id, tid → "topic"
    - 默认 → "user"
    """
    if not param_names:
        return "user"

    # 检查第一个参数名
    param_lower = param_names[0].lower()

    if "uid" in param_lower or "user" in param_lower or "mid" in param_lower or "member" in param_lower:
        return "user"
    elif "column" in param_lower or "cid" in param_lower:
        return "column"
    elif "repo" in param_lower:
        return "repo"
    elif "topic" in param_lower or "tid" in param_lower:
        return "topic"
    elif "tag" in param_lower:
        return "tag"
    else:
        logger.warning(
            f"无法推断参数 '{param_names[0]}' 的实体类型，默认使用 'user'"
        )
        return "user"
```

### 3.2 RAG系统增强（参数验证与智能解析）

#### 3.2.1 核心逻辑位置

**在 RAGInAction 中实现参数验证**

```python
# orchestrator/rag_in_action.py

from services.subscription.entity_resolver_helper import resolve_entity_from_rag_context

class RAGInAction:
    def process(self, query: str, **kwargs) -> DataQueryResult:
        """处理查询（增强版）"""

        # 步骤1: 向量检索工具
        rag_result = self.rag_pipeline.search(query)
        best_tool = rag_result.retrieved_tools[0]  # 最佳匹配工具

        # 步骤2: LLM提取参数
        extracted_params = self._extract_params(query, best_tool)

        # 步骤3: 参数验证与智能解析（新增）⭐
        validated_params = self._validate_and_resolve_params(
            params=extracted_params,
            tool_definition=best_tool,  # ← 携带完整RAG上下文
            user_query=query
        )

        # 步骤4: 构建路径并获取数据
        path = self._build_path(best_tool["path_template"], validated_params)
        return self.data_executor.fetch_rss(path)

    def _validate_and_resolve_params(
        self,
        params: Dict[str, str],
        tool_definition: dict,
        user_query: str
    ) -> Dict[str, str]:
        """验证参数并通过订阅系统解析实体

        Args:
            params: LLM提取的参数（如 {"uid": "行业101"}）
            tool_definition: RAG检索到的工具定义，包含：
                {
                  "path_template": "/bilibili/user/video/:uid",
                  "parameters": {
                    "uid": {
                      "description": "UP主的用户ID",
                      "example": "123456"
                    }
                  }
                }
                注意：实际上没有 type、pattern、required 等验证字段！
            user_query: 原始用户查询

        Returns:
            验证后的参数（如 {"uid": "1566847"}）
        """
        validated = {}
        params_needing_resolution = []  # 需要订阅解析的参数

        # 步骤1：识别哪些参数需要订阅解析
        for param_name, param_value in params.items():
            if self._looks_like_entity_name(param_value):
                # 启发式判断：这个值看起来像名字而非ID
                params_needing_resolution.append(param_name)
                logger.info(
                    f"参数 '{param_name}' 的值 '{param_value}' 疑似实体名称，"
                    f"将尝试订阅解析"
                )
            else:
                # 看起来已经是有效的ID
                validated[param_name] = param_value

        # 步骤2：如果有参数需要解析，调用订阅系统
        if params_needing_resolution:
            # 选择最可能是实体名称的参数值作为查询
            primary_param = params_needing_resolution[0]
            entity_name = params[primary_param]

            # 调用订阅解析（携带完整RAG上下文）
            resolved_identifiers = resolve_entity_from_rag_context(
                entity_name=entity_name,
                tool_definition=tool_definition,
                extracted_params=params,
                target_params=params_needing_resolution
            )

            if resolved_identifiers:
                # 合并解析结果
                logger.info(
                    f"✅ 订阅解析成功: '{entity_name}' → {resolved_identifiers}"
                )
                validated.update(resolved_identifiers)
            else:
                # 解析失败，使用原值
                logger.warning(
                    f"⚠️  订阅解析失败: '{entity_name}'，使用原值"
                )
                for param_name in params_needing_resolution:
                    validated[param_name] = params[param_name]

        return validated

    def _looks_like_entity_name(self, value: str) -> bool:
        """启发式判断：参数值是否像实体名称（而非ID）

        判断规则：
        1. 包含中文字符 → 很可能是名字
        2. 包含空格 → 很可能是名字
        3. 全是数字 → 很可能是ID
        4. 纯英文字母（不含数字） → 可能是名字或slug
        5. 混合字母数字 → 可能是ID或slug

        Returns:
            True: 看起来像名字（需要订阅解析）
            False: 看起来像ID（无需解析）
        """
        # 规则1: 包含中文
        if any('\u4e00' <= char <= '\u9fff' for char in value):
            return True

        # 规则2: 包含空格
        if ' ' in value:
            return True

        # 规则3: 全是数字（很可能是ID）
        if value.isdigit():
            return False

        # 规则4: 纯英文字母（可能是名字）
        if value.isalpha():
            return True

        # 规则5: 默认情况（保守策略：尝试解析）
        return True
```

#### 3.2.2 实现说明

**关键点**：

1. **不依赖工具定义中的验证字段**
   - 实际的工具定义只包含 `description` 和 `example`
   - 我们使用启发式规则判断参数值是否需要解析

2. **携带完整RAG上下文**
   - `tool_definition`: 包含 path_template 和 parameters
   - `extracted_params`: LLM 提取的所有参数
   - `target_params`: 需要解析的参数列表

3. **返回完整 identifiers**
   - 不只是单个 uid，可能包含多个标识符
   - 如 `{"repo": "langchain", "owner": "langchain-ai"}`

4. **降级策略**
   - 订阅解析失败时，使用原值继续
   - 让后续的 RSSHub API 返回明确错误

### 3.3 移除订阅预检

#### 3.3.1 DataQueryService 清理

**删除代码**：
```python
# services/data_query_service.py

# ❌ 删除以下代码

def __init__(self, subscription_resolver=None, ...):  # 删除参数
    self.subscription_resolver = subscription_resolver  # 删除

def _try_subscription_query(self, ...):  # 整个方法删除
    """尝试订阅查询（删除）"""
    pass

def _build_subscription_result(self, ...):  # 整个方法删除
    """构建订阅结果（删除）"""
    pass

def query(self, user_query, user_id=None):
    # ❌ 删除订阅预检逻辑
    if self.subscription_resolver:
        subscription_result = self._try_subscription_query(...)
        if subscription_result and similarity >= 0.75:
            return ...

    # ✅ 直接进入RAG流程
    return self.rag_in_action.process(user_query)
```

#### 3.3.2 ChatService 清理

```python
# services/chat_service.py

def __init__(self, ...):
    # ❌ 删除 SubscriptionResolver 创建
    # self.subscription_resolver = SubscriptionResolver(...)

    # ✅ DataQueryService 不再需要 subscription_resolver 参数
    self.data_query_service = DataQueryService(
        rag_in_action=self.rag_in_action,
        cache_service=self.cache_service,
        data_executor=self.data_executor,
        # subscription_resolver=self.subscription_resolver,  # 删除
    )
```

### 3.4 LangGraph 集成验证

#### 3.4.1 fetch_public_data 工具

```python
# langgraph_agents/tools/public_data.py

@tool
def fetch_public_data(query: str) -> Dict[str, Any]:
    """获取公共数据源内容

    自动处理：
    1. RAG检索工具模板
    2. LLM提取参数
    3. 参数验证（如果参数是名字而非ID，自动调用订阅工具）
    4. 数据获取

    示例：
    - "行业101的投稿视频"
      → RAG找到 /bilibili/user/video/:uid
      → 提取参数 uid="行业101"
      → 订阅解析 "行业101" → uid="1566847"
      → 获取 /bilibili/user/video/1566847
    """
    # 内部调用 DataQueryService.query()
    # RAGInAction 已包含参数验证与订阅解析逻辑
    service = DataQueryService(...)
    result = service.query(query)
    return result.to_dict()
```

#### 3.4.2 SimpleChatNode 增强

```python
# langgraph_agents/nodes/simple_chat_node.py

class SimpleChatNode:
    def __call__(self, state: GraphState) -> GraphState:
        """简单对话节点（已包含订阅解析）"""
        query = state.messages[-1].content

        # 调用 fetch_public_data（内部已处理订阅解析）
        result = self.fetch_public_data_tool.invoke({"query": query})

        # 无需额外处理，订阅解析在 RAGInAction 中自动完成
        return state
```

#### 3.4.3 Planner 无需改动

Planner 仅负责任务拆分，不需要知道订阅系统的存在：

```python
# langgraph_agents/nodes/planner_node.py

# ✅ 无需改动
# Planner 拆分: "行业101和老番茄的投稿"
# → 子任务1: "获取行业101的投稿"
# → 子任务2: "获取老番茄的投稿"
# Worker 在执行时自动调用订阅解析
```

---

## 四、实施计划

### Phase 1：订阅系统简化（1天）

**目标**：将订阅系统降级为纯粹的"名字→ID"映射工具

- [ ] 删除 `services/subscription/query_parser.py`（整个文件）
- [ ] 删除 `services/subscription/subscription_resolver.py`（整个文件）
- [ ] 简化 `SubscriptionService`
  - 保留 `resolve_entity()` 方法
  - 移除 ActionRegistry 相关导入和调用
- [ ] 创建 LangGraph 工具：`langgraph_agents/tools/subscription_entity_resolver.py`
- [ ] 更新测试：
  - 删除 `tests/services/test_query_parser.py`
  - 删除 `tests/services/test_subscription_resolver.py`
  - 简化 `tests/services/test_subscription_service.py`（只测试 resolve_entity）
  - 新增 `tests/langgraph_agents/test_subscription_entity_resolver.py`

### Phase 2：RAG系统增强（2天）

**目标**：在参数验证阶段集成订阅工具调用

- [ ] 在 `orchestrator/rag_in_action.py` 中实现：
  - [ ] `_validate_and_resolve_params()` 方法
  - [ ] `_is_param_valid()` 方法（正则/类型检查）
  - [ ] `_resolve_via_subscription()` 方法
  - [ ] `_extract_platform()` 方法（从工具定义提取平台）
  - [ ] `_infer_entity_type()` 方法（从参数名推断实体类型）
- [ ] 增强 `process()` 方法，集成参数验证流程
- [ ] 添加工具定义参数规范（在 datasource_definitions.json 或 vector_store）
  - 添加 `parameters.{param_name}.pattern` 字段（正则规范）
  - 添加 `parameters.{param_name}.type` 字段（类型）
- [ ] 集成测试：
  - 测试："行业101的投稿" → 订阅解析 → 正确路径
  - 测试："12345的投稿" → 无需解析 → 直接使用
  - 测试："未订阅用户的投稿" → 解析失败 → 使用原值

### Phase 3：移除订阅预检（0.5天）

**目标**：清理 DataQueryService 和 ChatService 中的订阅预检代码

- [ ] 修改 `services/data_query_service.py`
  - [ ] 删除 `subscription_resolver` 参数
  - [ ] 删除 `_try_subscription_query()` 方法
  - [ ] 删除 `_build_subscription_result()` 方法
  - [ ] 简化 `query()` 方法（直接调用 RAG）
- [ ] 修改 `services/chat_service.py`
  - [ ] 删除 `SubscriptionResolver` 创建
  - [ ] 删除 `subscription_resolver` 参数传递
- [ ] 删除相关测试：
  - [ ] 删除 `tests/services/test_data_query_subscription.py`
  - [ ] 删除 `tests/services/test_data_query_subscription_integration.py`

### Phase 4：LangGraph 集成验证（1天）

**目标**：确保 LangGraph 流程中订阅工具正确调用

- [ ] 验证 `fetch_public_data` 工具（内部已包含订阅解析）
- [ ] 测试简单查询："行业101的投稿"
  - 验证 RAG 找到工具
  - 验证参数验证触发订阅解析
  - 验证最终路径正确
- [ ] 测试复杂查询："行业101和老番茄的投稿"
  - 验证 Planner 正确拆分（2个子任务）
  - 验证每个子任务独立调用订阅解析
  - 验证结果正确合并
- [ ] 测试已订阅 vs 未订阅场景
- [ ] 测试数字 uid 场景（无需订阅解析）

### Phase 5：文档更新（0.5天）

- [ ] 更新 `.agentdocs/index.md`
  - 删除旧的订阅优先策略记忆
  - 添加新的订阅工具调用时机说明
- [ ] 更新 `.agentdocs/subscription-system-design.md`
  - 标注为已废弃或大幅简化
- [ ] 更新 `.agentdocs/backend-architecture.md`
  - 添加参数验证与订阅解析流程说明
- [ ] 归档旧的集成任务文档

---

## 五、技术细节

### 5.1 参数验证规则（启发式）

**重要说明**：实际的 RAG 工具定义不包含 `pattern`、`type`、`required` 等验证字段，只有 `description` 和 `example`。因此我们使用**启发式规则**判断参数值是否需要订阅解析。

**启发式判断规则**：

1. **包含中文字符** → 很可能是名字（需要解析）
   - 示例："行业101"、"科技美学"

2. **包含空格** → 很可能是名字（需要解析）
   - 示例："张 三"、"Li Lei"

3. **全是数字** → 很可能是ID（无需解析）
   - 示例："1566847"、"12345"

4. **纯英文字母**（不含数字） → 可能是名字或slug（尝试解析）
   - 示例："langchain"、"tech"

5. **混合字母数字** → 可能是ID或slug（尝试解析）
   - 示例:"user_123"、"repo-abc"

**触发订阅解析的条件**：

```python
if _looks_like_entity_name(param_value):
    # 启发式判断为名字 → 调用订阅解析
    resolved = resolve_entity_from_rag_context(...)
```

**保守策略**：当不确定时，倾向于尝试订阅解析（失败后使用原值）

### 5.2 实体类型推断

**推断规则表**：

| 参数名 | 推断 entity_type |
|--------|------------------|
| `uid`, `user_id` | `user` |
| `cid`, `column_id` | `column` |
| `repo`, `repo_name` | `repo` |
| `topic_id` | `topic` |
| `mid`, `member_id` | `user` |
| 其他 | `user`（默认） |

**优先级**：
1. 工具定义中的 `entity_type` 字段（最高优先级）
2. 参数名推断（备选）
3. 默认值 `user`（兜底）

### 5.3 平台提取

**提取方式**：

1. 工具定义中的 `platform` 字段（推荐）
2. 从 `path_template` 解析第一段（如 `/bilibili/...` → `bilibili`）

### 5.4 错误处理

**订阅解析失败时**：

```python
if not resolved:
    logger.warning(f"订阅解析失败: '{entity_name}'，使用原值")
    validated[param_name] = param_value  # 保持原值
    # 后续可能导致 RSSHub API 错误，但不在此阶段阻塞
```

**好处**：
- 不阻塞流程（用户可能直接输入了正确的ID）
- 错误信息更清晰（RSSHub API 会返回明确的错误）

---

## 六、预期效果

### 6.1 简单查询

**输入**：`"我想看看行业101的投稿视频"`

**流程**：
```
RAG检索 → /bilibili/user/video/:uid
参数提取 → {"uid": "行业101"}
启发式判断 → "行业101" 包含中文，疑似实体名称
订阅解析 → resolve_entity_from_rag_context(
              entity_name="行业101",
              tool_definition={...},
              extracted_params={"uid": "行业101"},
              target_params=["uid"]
            )
          → {"uid": "1566847"}
路径填充 → /bilibili/user/video/1566847
数据获取 → RSSHub API 成功
```

**日志**：
```
INFO: RAG检索成功: /bilibili/user/video/:uid (score=0.95)
INFO: 参数提取: {"uid": "行业101"}
INFO: 参数 'uid' 的值 '行业101' 疑似实体名称，将尝试订阅解析
INFO: 订阅解析上下文: entity_name='行业101', platform='bilibili', entity_type='user', target_params=['uid']
INFO: ✅ 订阅解析成功: '行业101' → {'uid': '1566847'}
INFO: 最终路径: /bilibili/user/video/1566847
```

### 6.2 多实体查询

**输入**：`"我想看看行业101和老番茄的投稿视频"`

**Planner 拆分**：
- 子任务1: "获取行业101的投稿视频"
- 子任务2: "获取老番茄的投稿视频"

**Worker 处理**：
- 子任务1: 订阅解析 "行业101" → uid="1566847"
- 子任务2: 订阅解析 "老番茄" → uid="9876543"

**结果**：两个数据集正确获取并合并

### 6.3 数字 uid 查询（无需订阅）

**输入**：`"我想看看uid为1566847的up主投稿"`

**流程**：
```
RAG检索 → /bilibili/user/video/:uid
参数提取 → {"uid": "1566847"}
启发式判断 → "1566847" 全是数字，看起来是有效ID ✅
路径填充 → /bilibili/user/video/1566847（无需订阅解析）
数据获取 → RSSHub API 成功
```

### 6.4 未订阅实体

**输入**：`"我想看看张三的投稿"`

**流程**：
```
RAG检索 → /bilibili/user/video/:uid
参数提取 → {"uid": "张三"}
启发式判断 → "张三" 包含中文，疑似实体名称
订阅解析 → 未找到订阅 "张三"（similarity < 0.6）
降级处理 → 使用原值 "张三"
RSSHub调用 → 失败（400 Bad Request: Invalid UID）
错误返回 → 提示用户添加订阅或提供正确的 uid
```

---

## 七、风险与应对

### 7.1 启发式规则误判

**风险**：纯英文名字可能被误判为ID（如 "langchain"）

**应对**：
- 保守策略：不确定时倾向于尝试订阅解析
- 订阅解析失败时降级使用原值
- 收集误判案例，持续优化规则

### 7.2 实体类型推断错误

**风险**：从参数名推断 entity_type 可能不准确

**应对**：
- 优先使用工具定义中的 `entity_type` 字段
- 记录推断失败的案例，持续优化推断规则

### 7.3 订阅解析失败导致查询中断

**风险**：订阅解析失败时，用户可能无法继续

**应对**：
- 降级策略：解析失败时仍使用原值
- 错误信息优化：明确提示用户"建议添加订阅"

### 7.4 性能问题

**风险**：每次参数验证都需要启发式判断，可能增加延迟

**应对**：
- 启发式判断非常快速（简单的字符串检查）
- 订阅解析已有缓存（15分钟语义搜索缓存）
- 大部分查询不会触发订阅解析（纯数字uid直接跳过）

---

## 八、总结

### 核心思想转变

| 维度 | 之前（错误） | 现在（正确） |
|------|-------------|-------------|
| **定位** | 智能查询解析器 | 名字→ID 映射工具 |
| **职责** | 查询理解 + 路径生成 | 仅实体解析 |
| **调用时机** | RAG 之前（订阅预检） | RAG 参数验证阶段（按需） |
| **接收上下文** | 不接收（自己猜测） | 完整RAG上下文（tool_definition + extracted_params） |
| **返回值** | 单个参数（uid） | 完整identifiers（可能多个标识符） |
| **参数验证** | 假设工具定义有验证字段 | 启发式规则（包含中文/全数字/等） |
| **流程位置** | DataQueryService 前置 | RAGInAction 内嵌 |

### 关键改进

1. ✅ **订阅系统回归本质**：只做名字→identifiers转换，不越界
2. ✅ **携带完整RAG上下文**：tool_definition 明确指导订阅系统（platform、entity_type、需要哪些参数）
3. ✅ **启发式参数验证**：不依赖工具定义中不存在的验证字段，使用简单规则判断
4. ✅ **返回完整标识符**：不只是 uid，可能是 `{"repo": "xxx", "owner": "yyy"}` 等多个字段
5. ✅ **多实体支持**：每个子任务独立调用订阅解析（Planner拆分后）
6. ✅ **降级策略**：解析失败不阻塞，使用原值继续（让RSSHub API返回明确错误）

### 验收标准

- [ ] 简单查询："行业101的投稿" → 正确解析并返回数据
- [ ] 多实体查询："行业101和老番茄的投稿" → 两个实体都正确解析
- [ ] 数字 uid 查询："uid=1566847的投稿" → 无需订阅解析，直接成功
- [ ] 未订阅实体："张三的投稿" → 降级处理，明确错误提示
- [ ] 所有测试通过（新的集成测试）
- [ ] 代码简化（删除 QueryParser、SubscriptionResolver）
