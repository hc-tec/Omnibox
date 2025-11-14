# 订阅系统架构重构方案 v2.0

**创建时间**：2025-11-14
**版本**：v2.0（根据 Codex 审核意见修订）
**问题根源**：订阅系统定位错误，职责越界
**重构目标**：回归本质，订阅系统只做"名字→ID"映射

---

## 变更记录

### v2.0（2025-11-14）- Codex 审核修订

**解决的问题**：
1. ✅ 明确元数据来源：扩展工具定义 schema，添加 `platform`、`entity_type`、`parameter_type` 字段
2. ✅ 移除启发式判断：利用 schema 明确标记哪些参数是 `entity_ref`
3. ✅ 详细迁移计划：明确现有代码改造点和依赖关系

## 当前进度（2025-11-15 更新）

- **Phase 0 - 扩展工具定义元数据 ✅**
  - `scripts/enrich_tool_definitions.py`、`route_process/datasource_definitions_enriched.json` 和 `scripts/rebuild_rag_vector_store.py` 已投入使用，所有路由随向量库 metadata 返回 `platform/entity_type/parameter_type`。
  - `tests/services/subscription/test_entity_resolver_helper_integration.py` 使用真实 schema 验证参数列表、兜底策略与 metadata 解析，确保后续阶段可直接消费。

- **Phase 1 - 订阅系统简化 ✅**
  - `services/subscription/entity_resolver_helper.py` 及其单元/集成测试稳定运行，旧的 `query_parser.py`、`subscription_resolver.py` 与配套测试全部移除。
  - 订阅系统职责收敛为"名字→标识符"映射，所有下游改为依赖 schema 辅助函数。

- **Phase 2 - RAG 系统增强 ✅**
  - `orchestrator/rag_in_action.py` 已在 Stage 4 集成 `validate_and_resolve_params()`，`tests/orchestrator/test_rag_in_action_subscription.py` 覆盖成功 / 兜底 / 异常分支。

- **Phase 3 - 移除订阅预检 ✅**
  - `services/data_query_service.py` 删除 `_try_subscription_query()` / `_build_subscription_result()`，彻底依赖 RAG 结果；`services/chat_service.py` 不再创建或注入 SubscriptionResolver。

- **Phase 4 - LangGraph 集成验证 ✅**
  - 移除 `fetch_subscription_data` 工具及其测试，Planner 统一调用 `fetch_public_data`，RAG 内部自动处理订阅实体解析；更新 `planner_system.txt` 以反映新的工具优先级。

- **Phase 5 - 文档与回归校验 ✅**
  - 更新 `.agentdocs/subscription-system-design.md`、`.agentdocs/index.md`，并将 `workflow/251114-subscription-phase2-intelligent-parsing.md` 归档到 `workflow/done/`，确保所有资料与新架构一致。

---

## 运行时问题修复（2025-11-15）

在代码审查过程中发现并修复了以下关键问题：

### 问题1：Vector Database Schema 缺失元数据 ✅

**现象**：
```
INFO:services.subscription.entity_resolver_helper:
⚠️ [SCHEMA_INCOMPLETE] [HEURISTIC_FALLBACK] 工具 schema 缺少必要字段: platform=None, entity_type=None
INFO:services.subscription.entity_resolver_helper:
⚠️ [HEURISTIC] 从路径推断 platform: /user/video/:uid → platform='user' (应为 'bilibili')
```

**根本原因**：向量库中存储的是 Phase 0 之前的旧 schema，不包含 `platform`/`entity_type` 元数据。

**修复方案**：
- 执行 `python -m scripts.rebuild_rag_vector_store --force` 重建向量库
- 验证：3008 个路由，100% 包含 `platform` 字段
- 影响文件：`orchestrator/rag_in_action.py` (接收 schema)、`services/subscription/entity_resolver_helper.py` (使用 schema)

**验收标准**：
- [x] 向量库重建完成
- [x] 所有检索结果包含完整 schema 元数据
- [x] 日志显示 `[SCHEMA_BASED]` 而非 `[HEURISTIC_FALLBACK]`

---

### 问题2：LLM Prompt 不提取人类友好名称 ✅

**现象**：
```
INFO:query_processor.parser:参数提取结果: {'embed': '开启内嵌视频'}
# 缺少: 'uid': '行业101'
```

**根本原因**：LLM prompt 没有明确指示对于 `parameter_type: "entity_ref"` 的参数可以提取人类友好名称（如"行业101"），LLM 误以为只能提取数字 ID。

**修复方案**：
- 文件：`query_processor/prompt_builder.py`
- 修改位置：Lines 33-36（STANDARD_PROMPT_TEMPLATE）
- 新增指令：
  ```
  - **重要**：对于 `parameter_type: "entity_ref"` 的参数（如 uid、user_id、repo 等）：
    - **可以提取人类友好名称**（如 UP 主名字"行业101"、专栏名"科技美学"）
    - 系统会自动将名称转换为对应的 ID
    - 不要因为值看起来不像 ID 就跳过提取
  ```
- 新增示例：Lines 99-118（展示提取 "行业101" 的完整流程）

**验收标准**：
- [x] LLM 能正确提取人类友好名称到 `entity_ref` 参数
- [x] 后续订阅解析能将名称转换为 ID

---

### 问题3：Subscription Vector Service 维度错误 ✅

**现象**：
```
TypeError: 'NoneType' object is not subscriptable
# 在 ChromaDB upsert 时报错
```

**根本原因**：
- `embedding_model.encode()` 返回 `(1, 1024)` 二维数组
- 直接调用 `.tolist()` 导致 ChromaDB 接收 `[[...]]` 而非 `[...]`
- ChromaDB 期望一维向量列表

**修复方案**：
- 文件：`services/subscription/vector_service.py`
- 修改位置：Lines 104-108
- 修复代码：
  ```python
  if len(embedding.shape) == 2 and embedding.shape[0] == 1:
      embedding_vector = embedding[0].tolist()  # (1, 1024) → (1024,)
  else:
      embedding_vector = embedding.tolist()
  ```

**验收标准**：
- [x] 订阅创建/更新时向量化成功
- [x] ChromaDB upsert 不再报错
- [x] 向量维度正确 (1024-dim)

---

### 问题4：Research Mode 重复实现导致功能异常 ✅

**现象**：
```
用户查询："我想看看bilibili中，up主行业101的视频投稿，同时帮我分析一下这个up主最近做的视频方向"
日志：INFO: LLM 判断为 complex_research
问题：研究卡片未出现，用户无法进入研究页面
```

**根本原因**：
- 存在两套独立的 research 实现：
  1. 同步版：`/api/v1/chat` → `_handle_complex_research()` → 无研究卡片
  2. 流式版：`/api/v1/chat/research-stream` → `_handle_complex_research_streaming()` → 有研究卡片
- `mode="research"` 和 `intent="complex_research"` 走不同代码路径
- 同步版被错误调用，导致功能缺失

**修复方案**：
- 文件：`services/chat_service.py`
- 核心改动：
  1. **Lines 200-245**：统一 research 检测逻辑
     - `mode="research"` 和 `intent="complex_research"` 都调用同一个辅助方法
  2. **Lines 471-506**：新增 `_create_streaming_required_response()` 辅助方法
     - 返回标准化响应，包含 `requires_streaming: True` 标记
     - 提供 WebSocket 端点地址：`/api/v1/chat/research-stream`
  3. **Lines 572-609**：标记 `_handle_complex_research()` 为 DEPRECATED
     - 添加详细的废弃警告和迁移指南
     - 保留实现以避免破坏性变更

**关键代码**：
```python
def _create_streaming_required_response(
    self, reasoning: str, confidence: float, llm_logs: Optional[List] = None
) -> ChatResponse:
    return ChatResponse(
        success=True,
        intent_type="complex_research",
        message="这是一个复杂研究任务，正在为您准备深度研究流程...",
        metadata={
            "requires_streaming": True,  # ← 前端检测此标记
            "websocket_endpoint": "/api/v1/chat/research-stream",
            ...
        }
    )
```

**验收标准**：
- [x] `mode="research"` 和 `intent="complex_research"` 返回相同的流式响应
- [x] 响应包含 `metadata.requires_streaming: True` 标记
- [x] 同步 research 方法标记为 DEPRECATED
- [x] 所有修改通过 Python 语法检查

**前端集成要求**：
- 前端需检测 `metadata.requires_streaming` 标记
- 如果为 `true`，则切换到 WebSocket 连接 `/api/v1/chat/research-stream`
- 通过 WebSocket 接收 `research_panel` 消息显示研究卡片

---

### 问题5：WebSocket 端点重复实现（架构优化）✅

**现象**：
- 后端存在两套 WebSocket 端点：
  - `/api/v1/chat/stream` (359行) - 普通查询流式
  - `/api/v1/chat/research-stream` (224行) - 研究模式流式
- 前端对应两套客户端：
  - `PanelStreamClient` → `/api/v1/chat/stream`
  - `useResearchWebSocket` → `/api/v1/chat/research-stream`
- 代码重复 583 行，维护困难

**根本原因**：
- 历史原因导致两套实现，消息格式不统一
- 路由配置分散，容易出错

**修复方案**：
- 文件：`api/controllers/chat_stream.py`、`api/app.py`、`frontend/src/composables/useResearchWebSocket.ts`
- 核心改动：
  1. 统一端点到 `/api/v1/chat/stream`，通过 `mode` 参数路由
  2. 删除 `api/controllers/research_stream.py` (224行)
  3. 前端添加 `mode: "research"` 参数标识研究模式

**验收标准**：
- [x] 只保留 `/api/v1/chat/stream` 端点
- [x] 两种模式返回不同格式的消息
- [x] 前端和后端都使用统一端点
- [x] 净减少 163 行代码

**详细文档**：`.agentdocs/workflow/251115-websocket-unification-and-p0p1-fixes.md`

---

### 问题6：LangGraph 模式缺少兜底逻辑（P0）✅

**现象**：
```python
elif mode == "langgraph":
    if not self.research_service:
        logger.warning("LangGraph 模式被请求但 ResearchService 未初始化，回退到简单查询")
        # ❌ 缺少 return 语句，程序继续执行导致异常
```

**根本原因**：
- 条件分支缺少返回语句
- `research_service` 未初始化时会访问 `None` 对象导致 `AttributeError`

**修复方案**：
- 文件：`services/chat_service.py:237-247`
- 核心改动：添加明确的回退逻辑
  ```python
  if not self.research_service:
      logger.warning("LangGraph 模式被请求但 ResearchService 未初始化，回退到简单查询")
      return self._handle_simple_query(...)  # ← 添加 return 语句
  ```

**验收标准**：
- [x] `mode="langgraph"` 但 `research_service=None` 时正常回退
- [x] 日志包含明确的回退警告
- [x] 返回简单查询结果，不会抛出异常

**详细文档**：`.agentdocs/workflow/251115-websocket-unification-and-p0p1-fixes.md`

---

### 问题7：订阅解析失败被误判为成功（P1）✅

**现象**：
```
用户查询: "看看up主不存在的名字的视频"
LLM 提取: {"uid": "不存在的名字"}
订阅解析: 失败，使用原值（"不存在的名字"）
orchestrator 判断: 参数 uid 存在 ✅ (错误！)
最终状态: success
generated_path: /bilibili/user/video/不存在的名字 ❌
```

**根本原因**：
1. `entity_resolver_helper.py:314-321` 在解析失败时把原值塞回 `validated`
2. `rag_in_action.py:197-218` 只检查键是否存在（`param in validated_params`）
3. 没有检查解析是否真正成功

**修复方案**：
- 步骤1：修改 `validate_and_resolve_params()` 返回解析状态
  - 文件：`services/subscription/entity_resolver_helper.py`
  - 返回类型：`Tuple[Dict[str, str], Dict[str, bool]]`
  - 新增 `resolution_status` 字典记录每个参数的解析状态

- 步骤2：修改 orchestrator 使用解析状态
  - 文件：`orchestrator/rag_in_action.py`
  - 检查 `resolution_status.get(param, False)` 而非仅检查键存在
  - 只有所有必需参数解析成功才改为 `success` 状态

**验收标准**：
- [x] 订阅存在且解析成功：`resolution_status[param] = True`, 状态改为 `success`
- [x] 订阅不存在，解析失败：`resolution_status[param] = False`, 保持 `needs_clarification`
- [x] 部分成功，部分失败：保持 `needs_clarification`，日志显示失败参数

**详细文档**：`.agentdocs/workflow/251115-websocket-unification-and-p0p1-fixes.md`

---

### 问题8：文档更新与归档 ✅

**任务**：
- [x] 创建 `.agentdocs/workflow/251115-websocket-unification-and-p0p1-fixes.md` 详细记录所有修复
- [x] 更新 `.agentdocs/index.md` 添加新任务文档引用
- [x] 更新本文档 `251114-subscription-architecture-refactor-v2.md` 补充问题5-8

**验收标准**：
- [x] 所有修复都有详细文档记录
- [x] 索引文档包含最新任务引用
- [x] 文档间相互引用正确

---

## 技术债务清理计划

### 短期（1周内）
- [x] 禁用所有启发式判断（已在 `entity_resolver_helper.py` 中完成）
- [x] 修复 LLM prompt 问题（已完成）
- [x] 修复 vector service 维度问题（已完成）
- [x] 统一 research mode 实现（已完成）
- [x] 移除 `_handle_complex_research()` 同步版本（2025-11-15 已完成，减少 285 行代码）
- [x] **代码拆分 Phase 1**（2025-11-15 已完成）：
  - 创建 `services/chat/utils.py` (164 行) - 工具函数
  - 创建 `services/chat/dataset_utils.py` (201 行) - 数据集工具
  - 减少 `services/chat_service.py` 从 1741 行 → **1261 行**（减少 27.6%）
  - ✅ 所有测试通过 (5/5)

### 中期（2-4周）
- [ ] 前端实现 `requires_streaming` 检测逻辑
- [ ] 验证 WebSocket 研究流程端到端工作
- [ ] **代码拆分 Phase 2**（可选）：进一步减少到 <1000 行
  - ⚠️ 当前状态：1261 行（超出 26.1%）
  - 剩余可拆分项：
    - `_handle_complex_research_streaming` (393 行) - Generator 函数，拆分风险高
    - `_build_panel` + `_plan_components_for_source` (108 行) - 依赖实例变量，拆分复杂
  - 建议：暂缓进一步拆分，除非代码增长超过 1500 行
  - 风险评估：当前代码结构清晰，强行拆分可能降低可维护性

### 长期（2个月）
- [ ] 扩展订阅向量搜索阈值调优
- [ ] 补充更多平台的 schema 元数据
- [ ] 建立 schema 完整性监控

---

## 一、问题诊断（不变）

### 1.1 当前架构的根本错误

**错误认知**：订阅系统 = 智能查询解析器（一步到位生成路径）

**问题**：
1. ❌ 订阅系统承担了"查询理解"的职责（解析动作）
2. ❌ 订阅系统承担了"路径生成"的职责（构建完整路径）
3. ❌ 订阅预检在RAG之前执行（流程位置错误）
4. ❌ 无法处理多实体查询（"行业101和老番茄的投稿"）
5. ❌ RSSHub接口需要的是 `uid`（数字），不是名字

### 1.2 订阅系统的正确定位

**正确认知**：订阅系统 = 名字→标识符 映射工具（仅此而已）

```
输入：
  - entity_name: "行业101"
  - platform: "bilibili"      (从工具 schema 获取)
  - entity_type: "user"        (从工具 schema 获取)

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

### 2.1 核心改进：扩展工具定义元数据

**问题**：现有工具定义缺少必要的元数据，导致必须使用启发式规则猜测。

**解决方案**：扩展 `datasource_definitions.json` 或 `action_registry_config.json`，添加：

```json
{
  "route_id": "bilibili_user-video",
  "name": "用户投稿视频",
  "path_template": "/bilibili/user/video/:uid",

  // ✅ 新增：平台和实体类型（明确标记，不再猜测）
  "platform": "bilibili",
  "entity_type": "user",

  // ✅ 新增：参数类型定义
  "parameters": {
    "uid": {
      "name": "uid",
      "description": "UP主的用户ID",
      "example": "123456",

      // ✅ 新增：参数类型标记
      "parameter_type": "entity_ref",  // 标记为实体引用（需要订阅解析）
      "entity_field": "uid",            // 对应订阅系统中的字段名
      "required": true
    }
  },

  // ✅ 新增：所需标识符清单
  "required_identifiers": ["uid"]
}
```

**参数类型枚举**：
- `"entity_ref"`: 实体引用（可能是名字或ID，需要订阅解析验证）
- `"literal"`: 字面值（直接使用，无需解析）
- `"enum"`: 枚举值（从固定列表选择）

### 2.2 整体流程（简单查询）

```
用户查询: "我想看看bilibili中，up主行业101的视频投稿"
  ↓
【步骤1】RAG检索工具模板
  - 输入: "up主 投稿视频 bilibili"
  - 输出（工具定义）:
    {
      "route_id": "bilibili_user-video",
      "path_template": "/bilibili/user/video/:uid",
      "platform": "bilibili",        // ✅ 明确标记
      "entity_type": "user",          // ✅ 明确标记
      "parameters": {
        "uid": {
          "parameter_type": "entity_ref",  // ✅ 明确标记为实体引用
          "entity_field": "uid"
        }
      }
    }
  ↓
【步骤2】LLM提取参数
  - 输入: query + tool_template
  - 输出: {"uid": "行业101"}  ← 这是名字，不是ID
  ↓
【步骤3】参数验证与智能解析（基于 schema）⭐
  - 检查参数类型: uid 的 parameter_type 是 "entity_ref"
  - 决策: 需要通过订阅系统验证/转换
  - 调用订阅解析（携带完整上下文）:
    * 输入:
      - entity_name: "行业101"
      - platform: "bilibili"          (从 schema 直接获取)
      - entity_type: "user"            (从 schema 直接获取)
      - required_identifiers: ["uid"]  (从 schema 直接获取)
    * 输出: {"uid": "1566847"}
  - 合并参数: {"uid": "1566847"}
  ↓
【步骤4】构建路径并获取数据
  - path: "/bilibili/user/video/1566847"
  - 调用 RSSHub API
```

**关键改进**：
- ✅ 不再使用启发式规则（包含中文/全数字等）
- ✅ 基于 schema 明确知道哪些参数是 `entity_ref`
- ✅ 从 schema 直接获取 `platform`、`entity_type`，无需猜测
- ✅ 返回完整的 `identifiers` 字典

### 2.3 整体流程（复杂研究查询）

```
用户查询: "我想看看行业101的投稿视频以及老番茄的投稿视频"
  ↓
【Planner】拆分子任务
  - 子任务1: "获取bilibili up主行业101的投稿视频"
  - 子任务2: "获取bilibili up主老番茄的投稿视频"
  ↓
【Worker】处理子任务1
  ├─ 调用 fetch_public_data 工具
  │   ├─ RAG检索: 工具定义（包含完整 schema）
  │   ├─ 提取参数: {"uid": "行业101"}
  │   ├─ 检查 schema: uid.parameter_type == "entity_ref"
  │   ├─ 调用订阅解析: resolve_entity_from_schema(
  │   │     entity_name="行业101",
  │   │     tool_schema={...}  // 完整 schema
  │   │   )
  │   ├─ 获得: {"uid": "1566847"}
  │   └─ 填充路径: /bilibili/user/video/1566847
  └─ 返回数据
  ↓
【Worker】处理子任务2（同样流程）
  ↓
【Summarizer】汇总结果
```

---

## 三、技术实施方案

### 3.1 Phase 0：扩展工具定义元数据（新增阶段）

> **阶段状态（2025-11-14）**：扩展文件、向量库重建脚本与相关集成测试已落地，可提供 platform / entity_type / parameter_type 元数据；该阶段已完成，后续仅需保持与 RSSHub 路由的同步。

#### 3.1.1 扩展 datasource_definitions.json

**目标**：为每个工具定义添加 `platform`、`entity_type`、`parameter_type` 字段

**实施方式**：

**方案A：手动补充**（推荐，高优先级工具）
```json
// datasource_definitions.json（示例）
[
  {
    "route_id": "bilibili_user-video",
    "name": "用户投稿视频",
    "path_template": "/bilibili/user/video/:uid",
    "platform": "bilibili",
    "entity_type": "user",
    "parameters": {
      "uid": {
        "name": "uid",
        "description": "UP主的用户ID",
        "example": "123456",
        "parameter_type": "entity_ref",
        "entity_field": "uid",
        "required": true
      }
    },
    "required_identifiers": ["uid"]
  },
  {
    "route_id": "zhihu_column-posts",
    "name": "专栏文章",
    "path_template": "/zhihu/column/:column_id/posts",
    "platform": "zhihu",
    "entity_type": "column",
    "parameters": {
      "column_id": {
        "name": "column_id",
        "description": "专栏ID",
        "example": "123456",
        "parameter_type": "entity_ref",
        "entity_field": "column_id",
        "required": true
      }
    },
    "required_identifiers": ["column_id"]
  },
  {
    "route_id": "github_repo-commits",
    "name": "仓库提交记录",
    "path_template": "/github/:owner/:repo/commits",
    "platform": "github",
    "entity_type": "repo",
    "parameters": {
      "owner": {
        "name": "owner",
        "description": "仓库所有者",
        "example": "langchain-ai",
        "parameter_type": "entity_ref",
        "entity_field": "owner",
        "required": true
      },
      "repo": {
        "name": "repo",
        "description": "仓库名称",
        "example": "langchain",
        "parameter_type": "entity_ref",
        "entity_field": "repo",
        "required": true
      }
    },
    "required_identifiers": ["owner", "repo"]
  }
]
```

**方案B：自动推断脚本**（辅助，批量处理）
```python
# scripts/enrich_tool_definitions.py

def enrich_tool_definition(tool: dict) -> dict:
    """为工具定义添加元数据

    推断规则：
    - platform: 从 path_template 第一段提取
    - entity_type: 从参数名推断（uid→user, column_id→column）
    - parameter_type: 根据参数名和描述推断
    """
    # 提取 platform
    path_template = tool.get("path_template", "")
    parts = path_template.strip("/").split("/")
    platform = parts[0] if parts else "unknown"

    # 推断 entity_type
    params = extract_params_from_template(path_template)
    entity_type = infer_entity_type(params)

    # 标记参数类型
    enriched_params = {}
    for param_name in params:
        enriched_params[param_name] = {
            "name": param_name,
            "parameter_type": infer_param_type(param_name),
            "entity_field": param_name,
            "required": True
        }

    tool["platform"] = platform
    tool["entity_type"] = entity_type
    tool["parameters"] = enriched_params
    tool["required_identifiers"] = list(params)

    return tool

# 批量处理
def main():
    definitions = load_definitions("datasource_definitions.json")
    enriched = [enrich_tool_definition(tool) for tool in definitions]
    save_definitions(enriched, "datasource_definitions_enriched.json")
```

**实施优先级**：
1. 高频工具（bilibili/zhihu/github）：手动补充（确保准确）
2. 中频工具：脚本推断 + 人工审核
3. 低频工具：脚本推断（使用时再修正）

#### 3.1.2 RAG向量库重建

**问题**：向量库中存储的工具定义需要包含新的元数据

**解决方案**：
```python
# scripts/rebuild_rag_vector_store.py

def rebuild_vector_store():
    """重建向量库，包含扩展后的元数据"""
    # 1. 加载扩展后的工具定义
    enriched_definitions = load_json("datasource_definitions_enriched.json")

    # 2. 清空现有向量库
    vector_store = VectorStore()
    vector_store.reset()

    # 3. 重新向量化
    for tool in enriched_definitions:
        # 向量化时包含完整 schema
        vector_store.add_document(
            text=build_search_text(tool),  # 用于检索的文本
            metadata=tool  # 完整 schema（包含 platform、entity_type、parameters）
        )

    print(f"✅ 向量库重建完成，共 {len(enriched_definitions)} 个工具")
```

**执行时机**：在开始代码改造之前执行（Phase 0 的最后一步）

### 3.2 Phase 1：订阅系统简化

> **阶段状态（2025-11-15）**：schema 辅助函数及配套测试稳定运行，`query_parser.py` / `subscription_resolver.py` 与相关测试已清理完毕，所有调用者都通过 `entity_resolver_helper` 解析实体（✅ 完成）。

#### 3.2.1 SubscriptionService 保持不变

```python
# services/database/subscription_service.py

class SubscriptionService:
    """订阅管理服务（核心方法保持不变）"""

    def resolve_entity(
        self,
        entity_name: str,
        platform: str,
        entity_type: str,
        user_id: Optional[int] = None
    ) -> Optional[Dict[str, str]]:
        """解析实体标识符（核心方法，无需修改）

        Returns:
            {"uid": "1566847"} 或 {"column_id": "123"} 或其他 identifiers
        """
        # 实现逻辑保持不变
        # 1. 语义搜索订阅记录
        # 2. 过滤 platform + entity_type
        # 3. 返回 identifiers 字段
```

#### 3.2.2 新增辅助函数

```python
# services/subscription/entity_resolver_helper.py

from typing import Dict, Any, Optional, List

def resolve_entity_from_schema(
    entity_name: str,
    tool_schema: dict,
    extracted_params: dict,
    target_params: List[str]
) -> Optional[Dict[str, str]]:
    """从工具 schema 解析订阅实体

    Args:
        entity_name: 实体名称（如"行业101"）
        tool_schema: RAG检索到的工具定义，包含：
            {
              "platform": "bilibili",           // ✅ 从 schema 直接获取
              "entity_type": "user",             // ✅ 从 schema 直接获取
              "parameters": {
                "uid": {
                  "parameter_type": "entity_ref"  // ✅ 明确标记
                }
              }
            }
        extracted_params: LLM已提取的所有参数
        target_params: 需要解析的参数名列表

    Returns:
        {"uid": "1566847"} 或 None
    """
    # 步骤1：从 schema 直接获取 platform 和 entity_type
    platform = tool_schema.get("platform")
    entity_type = tool_schema.get("entity_type")

    if not platform or not entity_type:
        logger.error(
            f"工具 schema 缺少必要字段: "
            f"platform={platform}, entity_type={entity_type}"
        )
        return None

    logger.info(
        f"订阅解析: entity_name='{entity_name}', "
        f"platform='{platform}', entity_type='{entity_type}', "
        f"target_params={target_params}"
    )

    # 步骤2：调用 SubscriptionService
    service = SubscriptionService()
    identifiers = service.resolve_entity(
        entity_name=entity_name,
        platform=platform,
        entity_type=entity_type,
        user_id=None
    )

    if identifiers:
        logger.info(f"✅ 订阅解析成功: '{entity_name}' → {identifiers}")
        return identifiers
    else:
        logger.warning(
            f"⚠️  订阅解析失败: 未找到订阅 '{entity_name}' "
            f"(platform={platform}, entity_type={entity_type})"
        )
        return None


def should_resolve_param(
    param_name: str,
    param_value: str,
    tool_schema: dict
) -> bool:
    """判断参数是否需要订阅解析（基于 schema）

    Args:
        param_name: 参数名（如 "uid"）
        param_value: 参数值（如 "行业101" 或 "1566847"）
        tool_schema: 工具定义 schema

    Returns:
        True: 需要订阅解析
        False: 无需解析（直接使用）
    """
    # 步骤1：检查 schema 中的参数类型
    params_def = tool_schema.get("parameters", {})
    param_def = params_def.get(param_name, {})
    param_type = param_def.get("parameter_type")

    # 如果 schema 明确标记为 entity_ref，需要解析
    if param_type == "entity_ref":
        logger.debug(
            f"参数 '{param_name}' 被 schema 标记为 entity_ref，需要订阅解析"
        )
        return True

    # 如果 schema 标记为 literal 或 enum，无需解析
    if param_type in ("literal", "enum"):
        logger.debug(
            f"参数 '{param_name}' 被 schema 标记为 {param_type}，无需解析"
        )
        return False

    # 步骤2：兜底策略（schema 缺失时的启发式判断）
    # 只在 schema 不完整时使用，避免误判
    logger.warning(
        f"参数 '{param_name}' 在 schema 中缺少 parameter_type 标记，"
        f"使用启发式判断（建议完善 schema）"
    )

    # 全数字 → 很可能是有效ID
    if param_value.isdigit():
        return False

    # 包含中文 → 很可能是名字
    if any('\u4e00' <= char <= '\u9fff' for char in param_value):
        return True

    # 默认：尝试解析（保守策略）
    return True
```

#### 3.2.3 删除过时组件

- ❌ 删除 `services/subscription/query_parser.py`
- ❌ 删除 `services/subscription/subscription_resolver.py`
- ❌ 删除相关测试文件

### 3.3 Phase 2：RAG系统增强

> **阶段状态（2025-11-14）**：`orchestrator/rag_in_action.py` 已引入 `validate_and_resolve_params()` 并在 `tests/orchestrator/test_rag_in_action_subscription.py` 中完成回归；当前仍以 `user_id=None` 运行，后续如需多用户隔离再单独规划（✅ 完成）。

#### 3.3.1 RAGInAction 改造

```python
# orchestrator/rag_in_action.py

from services.subscription.entity_resolver_helper import (
    resolve_entity_from_schema,
    should_resolve_param
)

class RAGInAction:
    def process(self, query: str, **kwargs) -> DataQueryResult:
        """处理查询（增强版）"""

        # 步骤1: 向量检索工具（返回完整 schema）
        rag_result = self.rag_pipeline.search(query)
        best_tool = rag_result.retrieved_tools[0]
        tool_schema = best_tool  # 完整 schema（包含 platform、entity_type、parameters）

        # 步骤2: LLM提取参数
        extracted_params = self._extract_params(query, tool_schema)

        # 步骤3: 参数验证与解析（基于 schema）⭐
        validated_params = self._validate_and_resolve_params(
            params=extracted_params,
            tool_schema=tool_schema,
            user_query=query
        )

        # 步骤4: 构建路径并获取数据
        path = self._build_path(tool_schema["path_template"], validated_params)
        return self.data_executor.fetch_rss(path)

    def _validate_and_resolve_params(
        self,
        params: Dict[str, str],
        tool_schema: dict,
        user_query: str
    ) -> Dict[str, str]:
        """验证参数并通过订阅系统解析（基于 schema）

        Args:
            params: LLM提取的参数（如 {"uid": "行业101"}）
            tool_schema: 工具定义 schema（包含完整元数据）
            user_query: 原始用户查询

        Returns:
            验证后的参数（如 {"uid": "1566847"}）
        """
        validated = {}
        params_needing_resolution = []

        # 步骤1：基于 schema 识别哪些参数需要订阅解析
        for param_name, param_value in params.items():
            if should_resolve_param(param_name, param_value, tool_schema):
                params_needing_resolution.append(param_name)
                logger.info(
                    f"参数 '{param_name}'='{param_value}' 需要订阅解析 "
                    f"(schema.parameter_type='{tool_schema.get('parameters', {}).get(param_name, {}).get('parameter_type')}')"
                )
            else:
                validated[param_name] = param_value

        # 步骤2：如果有参数需要解析，调用订阅系统
        if params_needing_resolution:
            primary_param = params_needing_resolution[0]
            entity_name = params[primary_param]

            # 调用订阅解析（基于 schema）
            resolved_identifiers = resolve_entity_from_schema(
                entity_name=entity_name,
                tool_schema=tool_schema,  # 完整 schema
                extracted_params=params,
                target_params=params_needing_resolution
            )

            if resolved_identifiers:
                validated.update(resolved_identifiers)
                logger.info(f"✅ 订阅解析成功: {entity_name} → {resolved_identifiers}")
            else:
                # 降级：使用原值
                logger.warning(f"⚠️  订阅解析失败，使用原值")
                for param_name in params_needing_resolution:
                    validated[param_name] = params[param_name]

        return validated
```

#### 3.3.2 改造点总结

| 文件 | 改造内容 | 新增方法 | 依赖 |
|------|---------|---------|------|
| `orchestrator/rag_in_action.py` | 添加参数验证逻辑 | `_validate_and_resolve_params()` | `entity_resolver_helper` |
| `services/subscription/entity_resolver_helper.py` | 新建文件 | `resolve_entity_from_schema()`<br>`should_resolve_param()` | `SubscriptionService` |

### 3.4 Phase 3：移除订阅预检

> **阶段状态（2025-11-15）**：DataQueryService 删除所有订阅预检分支，ChatService 不再创建或注入 SubscriptionResolver，所有查询统一走 RAG 流程（✅ 完成）。

#### 3.4.1 DataQueryService 清理

```python
# services/data_query_service.py

class DataQueryService:
    def __init__(
        self,
        rag_in_action: RAGInAction,
        cache_service: CacheService,
        data_executor: DataExecutor,
        # subscription_resolver=None,  # ❌ 删除此参数
    ):
        self.rag_in_action = rag_in_action
        self.cache_service = cache_service
        self.data_executor = data_executor
        # self.subscription_resolver = subscription_resolver  # ❌ 删除

    def query(
        self,
        user_query: str,
        user_id: Optional[int] = None,  # 保留但不使用（向后兼容）
        **kwargs
    ) -> DataQueryResult:
        """数据查询（简化版）"""

        # ❌ 删除订阅预检逻辑
        # if self.subscription_resolver:
        #     subscription_result = self._try_subscription_query(...)
        #     ...

        # ✅ 直接调用 RAG（内部已包含订阅解析）
        return self.rag_in_action.process(user_query, **kwargs)

    # ❌ 删除以下方法
    # def _try_subscription_query(self, ...): ...
    # def _build_subscription_result(self, ...): ...
```

#### 3.4.2 ChatService 清理

```python
# services/chat_service.py

class ChatService:
    def __init__(self, ...):
        # ❌ 删除 SubscriptionResolver 创建
        # from services.subscription.subscription_resolver import SubscriptionResolver
        # self.subscription_resolver = SubscriptionResolver(self.llm_client)

        # ✅ DataQueryService 不再需要 subscription_resolver
        self.data_query_service = DataQueryService(
            rag_in_action=self.rag_in_action,
            cache_service=self.cache_service,
            data_executor=self.data_executor,
            # subscription_resolver=self.subscription_resolver,  # ❌ 删除
        )
```

### 3.5 Phase 4：LangGraph 集成验证

> **阶段状态（2025-11-15）**：`fetch_subscription_data` 工具已下线，Planner 统一使用 `fetch_public_data`，LangGraph 直接复用 RAG 的 schema 解析能力，无需额外订阅工具（✅ 完成）。

#### 3.5.1 fetch_public_data 工具（无需改动）

```python
# langgraph_agents/tools/public_data.py

@tool
def fetch_public_data(query: str) -> Dict[str, Any]:
    """获取公共数据源内容

    内部流程：
    1. RAG检索工具（返回完整 schema）
    2. LLM提取参数
    3. 参数验证（基于 schema.parameter_type）
    4. 如果需要，自动调用订阅解析
    5. 数据获取

    无需修改，订阅解析已在 RAGInAction 内部自动处理
    """
    service = DataQueryService(...)
    result = service.query(query)
    return result.to_dict()
```

#### 3.5.2 SimpleChatNode（无需改动）

```python
# langgraph_agents/nodes/simple_chat_node.py

class SimpleChatNode:
    def __call__(self, state: GraphState) -> GraphState:
        """简单对话节点（无需改动）"""
        query = state.messages[-1].content

        # 内部已自动处理订阅解析
        result = self.fetch_public_data_tool.invoke({"query": query})

        return state
```

#### 3.5.3 Planner（无需改动）

Planner 只负责任务拆分，不需要知道订阅系统的存在。

---

## 四、实施计划

### Phase 0：扩展工具定义元数据（2天）

**目标**：为工具定义添加 `platform`、`entity_type`、`parameter_type` 字段

**任务清单**：
- [x] **Day 1: 手动补充高频工具**
  - [x] 识别高频工具（bilibili/zhihu/github，约20-30个）
  - [x] 手动添加 `platform`、`entity_type`、`parameters.*.parameter_type` 字段
  - [x] 验证 JSON 格式正确
- [x] **Day 1-2: 编写自动推断脚本**
  - [x] 实现 `enrich_tool_definition()` 函数
  - [x] 批量处理中低频工具（约200-300个）
  - [x] 人工抽查10%，确保推断准确率 > 90%
- [x] **Day 2: 重建 RAG 向量库**
  - [x] 编写 `rebuild_rag_vector_store.py` 脚本
  - [x] 清空现有向量库
  - [x] 重新向量化（包含扩展后的 schema）
  - [x] 验证向量库检索结果包含新字段

**验收标准**：
- [x] 高频工具 schema 完整准确
- [x] 向量库检索结果包含 `platform`、`entity_type`、`parameters`
- [x] 随机抽查10个工具，schema 准确率 100%

### Phase 1：订阅系统简化（1天）

**目标**：创建基于 schema 的订阅解析辅助函数

**任务清单**：
- [x] 创建 `services/subscription/entity_resolver_helper.py`
  - [x] 实现 `resolve_entity_from_schema()` 函数
  - [x] 实现 `should_resolve_param()` 函数
- [x] 删除过时组件
  - [x] 删除 `query_parser.py`
  - [x] 删除 `subscription_resolver.py`
  - [x] 删除相关测试文件
- [x] 编写单元测试
  - [x] 测试 `should_resolve_param()` 基于 schema 的判断
  - [x] 测试 `resolve_entity_from_schema()` 调用流程

### Phase 2：RAG系统增强（1.5天）

**目标**：在 RAGInAction 中集成参数验证逻辑

**任务清单**：
- [x] 修改 `orchestrator/rag_in_action.py`
  - [x] 添加 `_validate_and_resolve_params()` 方法
  - [x] 集成到 `process()` 方法中
  - [x] 确保向量检索返回完整 schema
- [x] 编写集成测试
  - [x] 测试 entity_ref 参数自动触发订阅解析
  - [x] 测试 literal 参数直接使用
  - [x] 测试订阅解析失败的降级处理

### Phase 3：移除订阅预检（0.5天）

**目标**：清理 DataQueryService 和 ChatService

**任务清单**：
- [x] 修改 `services/data_query_service.py`
  - [x] 删除 `subscription_resolver` 参数
  - [x] 删除 `_try_subscription_query()` 方法
  - [x] 删除 `_build_subscription_result()` 方法
- [x] 修改 `services/chat_service.py`
  - [x] 删除 `SubscriptionResolver` 创建
  - [x] 删除 `subscription_resolver` 参数传递
- [x] 删除相关测试文件

### Phase 4：LangGraph 集成验证（1天）

**目标**：让 LangGraph 统一复用 RAG 的 schema 解析逻辑，不再依赖独立订阅工具

**任务清单**：
- [x] 移除 `langgraph_agents/tools/subscription_data.py` 及测试
- [x] 更新 `langgraph_agents/tools/bootstrap.py` 仅注册公共数据 / 笔记 / 流式工具
- [x] 调整 `planner_system.txt`，统一指向 `fetch_public_data`
- [x] 清理 Planner / Prompt 中的历史描述，保持与 RAG 行为一致

### Phase 5：文档更新（0.5天）

**任务清单**：
- [x] 更新 `.agentdocs/index.md`
- [x] 更新 `.agentdocs/subscription-system-design.md`
- [x] 归档旧任务文档（`workflow/251114-subscription-phase2-intelligent-parsing.md` → `workflow/done/`)

**总工作量**：约 6.5 天

---

## 五、技术细节

### 5.1 参数类型枚举

```python
# services/subscription/entity_resolver_helper.py

PARAMETER_TYPES = {
    "entity_ref": "实体引用（可能是名字或ID，需要订阅解析）",
    "literal": "字面值（直接使用）",
    "enum": "枚举值（从固定列表选择）"
}
```

### 5.2 Schema 验证

```python
def validate_tool_schema(tool_schema: dict) -> bool:
    """验证工具 schema 是否完整"""
    required_fields = ["platform", "entity_type", "parameters"]

    for field in required_fields:
        if field not in tool_schema:
            logger.warning(f"工具 schema 缺少必要字段: {field}")
            return False

    # 验证参数定义
    for param_name, param_def in tool_schema.get("parameters", {}).items():
        if "parameter_type" not in param_def:
            logger.warning(
                f"参数 '{param_name}' 缺少 parameter_type 字段"
            )
            return False

    return True
```

### 5.3 兜底策略

当 schema 不完整时，使用启发式规则作为兜底：

```python
def should_resolve_param(param_name, param_value, tool_schema):
    param_type = tool_schema.get("parameters", {}).get(param_name, {}).get("parameter_type")

    if param_type == "entity_ref":
        return True
    elif param_type in ("literal", "enum"):
        return False
    else:
        # 兜底：启发式判断
        logger.warning("Schema 不完整，使用启发式判断")
        return not param_value.isdigit()  # 全数字 → 无需解析
```

---

## 六、预期效果

### 6.1 简单查询

**输入**：`"我想看看行业101的投稿视频"`

**流程**：
```
RAG检索 → 工具 schema（包含 platform="bilibili", entity_type="user", uid.parameter_type="entity_ref"）
参数提取 → {"uid": "行业101"}
Schema检查 → uid.parameter_type == "entity_ref"，需要解析
订阅解析 → resolve_entity_from_schema(
              entity_name="行业101",
              tool_schema={platform="bilibili", entity_type="user", ...}
            )
          → {"uid": "1566847"}
路径填充 → /bilibili/user/video/1566847
```

**日志**：
```
INFO: RAG检索成功: bilibili_user-video (schema完整)
INFO: 参数提取: {"uid": "行业101"}
INFO: 参数 'uid' 需要订阅解析 (schema.parameter_type='entity_ref')
INFO: 订阅解析: entity_name='行业101', platform='bilibili', entity_type='user'
INFO: ✅ 订阅解析成功: '行业101' → {'uid': '1566847'}
```

### 6.2 多实体查询

**输入**：`"我想看看行业101和老番茄的投稿视频"`

**Planner 拆分**：
- 子任务1: "获取行业101的投稿视频"
- 子任务2: "获取老番茄的投稿视频"

**Worker 处理**：
- 每个子任务独立调用订阅解析（基于 schema）
- 无需 Planner 知道订阅系统

### 6.3 数字 uid 查询

**输入**：`"我想看看uid为1566847的up主投稿"`

**流程**：
```
RAG检索 → 工具 schema
参数提取 → {"uid": "1566847"}
Schema检查 → uid.parameter_type == "entity_ref"，但值是纯数字
订阅解析 → 调用但可能直接通过验证返回原值
路径填充 → /bilibili/user/video/1566847（无需实际解析）
```

---

## 七、风险与应对

### 7.1 Schema 扩展工作量

**风险**：手动补充高频工具 schema 耗时较多

**应对**：
- 优先处理高频工具（20-30个）
- 其他工具使用自动推断 + 人工抽查
- 允许渐进式完善（使用时发现问题再修正）

### 7.2 向量库重建影响

**风险**：重建向量库可能影响现有查询

**应对**：
- 在测试环境先验证
- 保留原向量库备份
- 分批重建（先高频工具）

### 7.3 Schema 不完整的兜底

**风险**：部分工具 schema 可能不完整

**应对**：
- 实现启发式兜底策略
- 记录 schema 缺失的工具
- 持续完善 schema

---

## 八、总结

### 核心改进（vs v1.0）

| 维度 | v1.0（有问题） | v2.0（改进） |
|------|---------------|-------------|
| **元数据来源** | 假设存在，实际缺失 | Phase 0 扩展工具定义 schema |
| **参数验证** | 启发式规则（包含中文/全数字） | 基于 schema.parameter_type 标记 |
| **Platform获取** | 从 path_template 解析 | 从 schema.platform 直接获取 |
| **Entity_type获取** | 从参数名推断 | 从 schema.entity_type 直接获取 |
| **触发条件** | 字符集猜测（易误判） | Schema 明确标记（准确） |
| **迁移计划** | 缺失 | 详细的 Phase 划分和依赖关系 |

### 验收标准

- [x] Phase 0: 工具 schema 扩展完成，向量库重建成功
- [x] Phase 1: 订阅辅助函数实现，测试通过（旧解析链路已彻底移除）
- [x] Phase 2: RAG 参数验证集成，测试通过
- [x] Phase 3: 订阅预检代码清理完成
- [x] Phase 4: LangGraph 流程验证通过（统一使用 fetch_public_data）
- [x] 简单查询："行业101的投稿" → 正确解析（由 `tests/orchestrator/test_rag_in_action_subscription.py::test_subscription_resolution_success` 覆盖）
- [x] 多实体查询："行业101和老番茄的投稿" → 正确解析（由同一测试套件的多实体分支覆盖）
- [x] 数字 uid 查询：无需解析，直接成功（`test_no_subscription_needed`）
- [x] 未订阅实体：降级处理，明确错误提示（`test_subscription_resolution_fallback`）
