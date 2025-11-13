# 订阅管理系统实施任务

> **任务目标**：实现订阅管理系统 Phase 1 - 基础订阅管理（1-2周）
>
> **相关文档**：
> - 设计方案：`.agentdocs/subscription-system-design.md`（v2.2 修订版）
> - 持久化方案：`.agentdocs/runtime-persistence-plan.md`
> - 后端架构：`.agentdocs/backend-architecture.md`
>
> **创建时间**：2025-11-13
> **预计工期**：7-10 天

---

## 一、现状分析

### 1.1 已实现的组件

✅ **ActionRegistry**（`services/subscription/action_registry.py`）
- 动作注册表，配置驱动设计
- 支持从 `action_registry_config.json` 加载配置
- 提供 `get_action()`, `build_path()`, `get_supported_actions()` 等方法
- 单例模式，全局唯一实例

✅ **RouteAnalyzer**（`services/subscription/route_analyzer.py`）
- 路由分析器，从 RSSHub 路由定义自动推断 entity_type 和 action
- 支持自动生成 ActionRegistry 配置文件

### 1.2 待实现的核心组件

❌ **数据库层**（新增 `services/database/` 目录）
- `models.py` - 数据模型（Subscription + SubscriptionEmbedding）
- `connection.py` - 数据库连接管理（单例模式）
- `subscription_service.py` - 订阅管理服务（CRUD + ID映射）

❌ **订阅服务层**（扩展 `services/subscription/` 目录）
- `query_parser.py` - 查询解析器（LLM驱动，分离实体和动作）
- `vector_service.py` - 向量检索服务（ChromaDB 独立 Collection）

❌ **API 层**（新增 `api/controllers/subscription_controller.py`）
- RESTful CRUD 接口
- 订阅搜索接口
- 动作列表接口

❌ **前端界面**（新增 `frontend/src/views/SubscriptionsView.vue`）
- 订阅列表展示
- 添加/编辑/删除订阅
- 按动作查询数据

### 1.3 架构集成点

**与现有架构的集成**：
1. **持久化集成** - 复用 `runtime-persistence-plan.md` 的数据库架构（SQLite + SQLModel + Alembic）
2. **Service 层集成** - 遵循现有 Service 层模式（单例/上下文管理器/依赖注入）
3. **LangGraph 集成** - 增强 `fetch_public_data` 工具支持订阅系统

---

## 二、方案设计

### 2.1 Phase 1 核心功能

#### 目标

实现基础订阅管理功能，用户可以：
1. **手动添加订阅**（B站UP主、知乎专栏、GitHub仓库等）
2. **查看订阅列表**（显示实体信息、支持的动作）
3. **通过订阅查询数据**（点击动作按钮触发查询）
4. **删除订阅**（取消不再关注的实体）

#### 不包含的功能（后续 Phase）

- ❌ 智能查询解析（Phase 2）
- ❌ URL 一键导入（Phase 3）
- ❌ 与知识库集成（Phase 4）
- ❌ 多用户隔离（按需实施）

### 2.2 数据模型设计

#### Subscription（订阅实体）

```python
class Subscription(SQLModel, table=True):
    """订阅管理（实体 + 动作分离架构）"""
    __tablename__ = "subscriptions"

    id: Optional[int] = Field(default=None, primary_key=True)

    # 显示信息
    display_name: str = Field(index=True, description="显示名称，如 '科技美学'")
    avatar_url: Optional[str] = Field(default=None, description="头像URL")
    description: Optional[str] = Field(default=None, description="简介")

    # 实体标识
    platform: str = Field(index=True, description="平台：bilibili/zhihu/github/...")
    entity_type: str = Field(description="实体类型：user/column/repo（不是 user_video!）")

    # API标识（JSON存储）
    identifiers: str = Field(description="JSON 格式 API 标识")

    # 搜索优化
    aliases: str = Field(default="[]", description="JSON 格式别名列表")
    tags: str = Field(default="[]", description="JSON 格式标签列表")

    # 支持的动作
    supported_actions: str = Field(default="[]", description="JSON 格式支持的动作列表")

    # 元数据
    subscribe_count: int = Field(default=0, description="订阅人数（多用户场景）")
    last_fetched_at: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 多用户支持（Stage 4 之前为 NULL）
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
```

#### SubscriptionEmbedding（向量化记录）

```python
class SubscriptionEmbedding(SQLModel, table=True):
    """订阅向量化记录（实际向量存储在 ChromaDB）"""
    __tablename__ = "subscription_embeddings"

    subscription_id: int = Field(foreign_key="subscriptions.id", primary_key=True)
    embedding_version: str = Field(description="向量模型版本")
    last_embedded_at: datetime = Field(description="最后向量化时间")
    is_stale: bool = Field(default=False, description="内容是否已过时")
```

### 2.3 API 接口设计

#### CRUD 接口

```
GET    /api/v1/subscriptions                 # 列出订阅（支持过滤）
POST   /api/v1/subscriptions                 # 创建订阅
GET    /api/v1/subscriptions/:id             # 获取订阅详情
PATCH  /api/v1/subscriptions/:id             # 更新订阅
DELETE /api/v1/subscriptions/:id             # 删除订阅
```

#### 功能接口

```
GET    /api/v1/subscriptions/:id/actions     # 获取支持的动作列表
POST   /api/v1/subscriptions/resolve         # 解析实体并构建路径
```

### 2.4 前端界面设计

#### 订阅管理页面（SubscriptionsView.vue）

```
┌────────────────────────────────────────────┐
│  我的订阅                    [ + 添加订阅 ]  │
├────────────────────────────────────────────┤
│  ┌──────────────────────────────────────┐  │
│  │  [头像]  科技美学                    │  │
│  │          专注数码产品测评             │  │
│  │          bilibili · user             │  │
│  │                                      │  │
│  │  支持的操作：                         │  │
│  │  [ 投稿视频 ] [ 关注列表 ] [ 收藏 ]   │  │
│  │                                      │  │
│  │  [ 编辑 ] [ 删除 ]                   │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │  [头像]  少数派                      │  │
│  │          高效工具和生活方式           │  │
│  │          zhihu · column              │  │
│  │                                      │  │
│  │  支持的操作：                         │  │
│  │  [ 专栏文章 ]                        │  │
│  │                                      │  │
│  │  [ 编辑 ] [ 删除 ]                   │  │
│  └──────────────────────────────────────┘  │
└────────────────────────────────────────────┘
```

---

## 三、任务拆解（Phase 1）

### Stage 1: 数据库基础（2天）✅

#### TODO
- [x] 安装依赖（`sqlmodel`, `alembic`, `cryptography`）
- [x] 创建 `services/database/` 目录
- [x] 实现 `models.py`（Subscription + SubscriptionEmbedding）
- [x] 实现 `connection.py`（DatabaseConnection 单例）
- [x] 实现 `subscription_service.py`（CRUD + resolve_entity）
- [x] 初始化 Alembic 迁移工具
- [x] 生成初始迁移脚本
- [x] 执行迁移，创建数据库表
- [x] 编写数据库连接测试（9个测试用例全部通过）

**验收标准**：
- ✅ 可以连接到 SQLite 数据库（`omni.db`）
- ✅ `subscriptions` 和 `subscription_embeddings` 表创建成功
- ✅ 数据库连接单例模式正常工作
- ✅ 所有 CRUD 方法正常工作
- ✅ `resolve_entity()` 可以正确返回 API 标识符
- ✅ 单元测试全部通过（9/9 passed）

**技术亮点**：
- 实现了实体/动作分离架构（entity_type vs resource_type）
- 使用 JSON 字段存储灵活的标识符、别名、标签
- 支持通过别名解析实体（如"那岩" -> uid=12345）
- 自动从 ActionRegistry 获取 supported_actions
- 测试覆盖全面（CRUD + 搜索 + 解析 + 边界情况）

---

### Stage 2: 订阅管理服务 ✅（已与 Stage 1 合并完成）

#### TODO
- [x] 实现 `services/database/subscription_service.py`
  - [x] `list_subscriptions()` - 列出订阅（支持过滤）
  - [x] `get_subscription()` - 获取订阅详情
  - [x] `create_subscription()` - 创建订阅
  - [x] `update_subscription()` - 更新订阅
  - [x] `delete_subscription()` - 删除订阅
  - [x] `resolve_entity()` - 解析实体标识符
  - [x] `search_subscriptions()` - 搜索订阅（模糊匹配）
- [x] 编写单元测试（`tests/services/test_subscription_service.py`）
- [x] 测试 CRUD 操作
- [x] 测试 `resolve_entity()` 的 ID 映射功能

**验收标准**：
- ✅ 所有 CRUD 方法正常工作
- ✅ `resolve_entity()` 可以正确返回 API 标识符
- ✅ 单元测试全部通过

**说明**：Stage 2 的内容已在 Stage 1 实施过程中一并完成。

---

### Stage 3: API 接口（2天）

#### TODO
- [ ] 创建 `api/schemas/subscription.py`（Pydantic 模型）
  - [ ] `SubscriptionCreate` - 创建请求
  - [ ] `SubscriptionUpdate` - 更新请求
  - [ ] `SubscriptionResponse` - 响应模型
  - [ ] `ActionInfo` - 动作信息
  - [ ] `ResolveResponse` - 解析响应
- [ ] 实现 `api/controllers/subscription_controller.py`
  - [ ] `GET /subscriptions` - 列出订阅
  - [ ] `POST /subscriptions` - 创建订阅
  - [ ] `GET /subscriptions/:id` - 获取详情
  - [ ] `PATCH /subscriptions/:id` - 更新订阅
  - [ ] `DELETE /subscriptions/:id` - 删除订阅
  - [ ] `GET /subscriptions/:id/actions` - 获取动作列表
  - [ ] `POST /subscriptions/resolve` - 解析实体
- [ ] 在 `api/app.py` 中注册路由
- [ ] 编写 API 集成测试（`tests/api/test_subscription_controller.py`）

**验收标准**：
- ✅ 所有 API 接口正常工作
- ✅ 可以通过 Swagger UI 测试接口
- ✅ API 集成测试全部通过

---

### Stage 4: 前端界面（3天）

#### TODO
- [ ] 创建 `frontend/src/types/subscription.ts`（TypeScript 类型定义）
- [ ] 创建 `frontend/src/api/subscription.ts`（API 调用封装）
- [ ] 创建 `frontend/src/store/subscriptionStore.ts`（Pinia Store）
- [ ] 创建 `frontend/src/views/SubscriptionsView.vue`（订阅管理页面）
- [ ] 创建 `frontend/src/components/subscription/SubscriptionCard.vue`（订阅卡片）
- [ ] 创建 `frontend/src/components/subscription/SubscriptionForm.vue`（添加/编辑表单）
- [ ] 在路由中注册 `/subscriptions` 路径
- [ ] 添加导航菜单项
- [ ] 实现订阅列表加载
- [ ] 实现添加订阅功能
- [ ] 实现编辑订阅功能
- [ ] 实现删除订阅功能
- [ ] 实现点击动作按钮查询数据

**验收标准**：
- ✅ 可以查看订阅列表
- ✅ 可以添加新订阅（手动输入信息）
- ✅ 可以编辑订阅信息
- ✅ 可以删除订阅
- ✅ 点击动作按钮可以触发数据查询并展示在面板中

---

## 四、技术决策记录

### 4.1 为什么使用单表 + JSON 字段？

**决策**：Subscription 表使用 JSON 字段存储 `identifiers`、`aliases`、`tags`、`supported_actions`

**理由**：
1. **灵活性** - 不同平台的标识符字段不同（B站用 uid，GitHub 用 owner+repo）
2. **简化查询** - 查询订阅时总是需要完整信息，不需要 JOIN
3. **SQLite 支持** - SQLite 3.38+ 提供完善的 JSON 函数支持
4. **代码简洁** - 避免创建多张关联表，减少 ORM 复杂度

### 4.2 为什么 Phase 1 不实现智能解析？

**决策**：Phase 1 只实现手动添加订阅，不实现 QueryParser

**理由**：
1. **验证核心架构** - 先验证数据模型和 ActionRegistry 的设计是否合理
2. **降低复杂度** - QueryParser 依赖 LLM，需要额外的提示词工程和测试
3. **快速迭代** - 手动添加足以验证订阅系统的价值
4. **渐进式演进** - Phase 2 再实现智能解析，可以基于 Phase 1 的反馈优化

### 4.3 为什么不先实现向量检索？

**决策**：Phase 1 使用 SQL 模糊匹配，Phase 2 再实现向量检索

**理由**：
1. **依赖简化** - Phase 1 不依赖 bge-m3 模型和 ChromaDB
2. **性能够用** - 早期订阅数量少，SQL `LIKE` 查询足够快
3. **避免过度设计** - 先验证需求，再优化性能

---

## 五、风险与应对

### 5.1 风险：数据库迁移失败

**应对**：
- 使用 Alembic 版本控制，支持 rollback
- 在测试环境先执行迁移
- 备份现有数据库（如果有）

### 5.2 风险：ActionRegistry 配置文件不存在

**应对**：
- ActionRegistry 已实现自动生成配置文件的逻辑（`_auto_generate_config()`）
- 首次运行时自动调用 RouteAnalyzer 生成配置
- 如果生成失败，记录详细错误日志

### 5.3 风险：前端与后端数据契约不一致

**应对**：
- 使用 Pydantic 模型定义 API 接口
- 前端 TypeScript 类型与后端 Pydantic 模型保持一致
- 编写 API 集成测试验证契约

---

## 六、完成记录

### Stage 1: 数据库基础 ✅

**开始时间**：2025-11-13 19:00
**完成时间**：2025-11-13 21:00
**实际工时**：约 2 小时
**状态**：✅ 已完成

**交付物**：
- `services/database/__init__.py` - 包初始化文件
- `services/database/models.py` - 数据模型（Subscription + SubscriptionEmbedding）
- `services/database/connection.py` - 数据库连接管理（单例模式）
- `services/database/subscription_service.py` - 订阅管理服务（完整 CRUD + resolve_entity）
- `alembic/versions/b6fd3989812d_init_subscription_tables.py` - 数据库迁移脚本
- `tests/services/test_subscription_service.py` - 完整测试套件（9个测试用例）
- `omni.db` - SQLite 数据库文件

**测试结果**：
```
tests/services/test_subscription_service.py::TestSubscriptionService::test_create_subscription PASSED
tests/services/test_subscription_service.py::TestSubscriptionService::test_list_subscriptions PASSED
tests/services/test_subscription_service.py::TestSubscriptionService::test_get_subscription PASSED
tests/services/test_subscription_service.py::TestSubscriptionService::test_update_subscription PASSED
tests/services/test_subscription_service.py::TestSubscriptionService::test_delete_subscription PASSED
tests/services/test_subscription_service.py::TestSubscriptionService::test_search_subscriptions_fuzzy PASSED
tests/services/test_subscription_service.py::TestSubscriptionService::test_resolve_entity PASSED
tests/services/test_subscription_service.py::TestSubscriptionService::test_resolve_entity_by_alias PASSED
tests/services/test_subscription_service.py::TestSubscriptionService::test_resolve_entity_not_found PASSED

============================== 9 passed in 0.38s ==============================
```

**关键技术决策**：
1. **延迟外键约束**：`user_id` 字段不添加外键约束（Stage 4 再通过 Alembic 迁移添加）
2. **JSON 字段设计**：使用 JSON 字段存储灵活的结构化数据（identifiers, aliases, tags, supported_actions）
3. **单例模式**：DatabaseConnection 使用单例模式确保全局唯一实例
4. **测试隔离**：通过环境变量 `DATABASE_URL` 实现测试数据库隔离

**代码审查修复（2025-11-13 20:00-21:00）**：
1. ✅ **唯一约束生效** - 标准化 JSON（sort_keys=True）确保相同数据生成相同字符串
2. ✅ **别名列表副作用** - 复制列表避免修改调用方数据（`list(kwargs.get("aliases", []))`）
3. ✅ **动作清单同步** - update_subscription 检测 platform/entity_type 变更自动刷新 supported_actions
4. ✅ **JSON 字段搜索** - 改为在 Python 层解析 JSON 并精确匹配（更可靠）
5. ✅ **级联删除约束** - SubscriptionEmbedding 添加 `ondelete="CASCADE"` 外键约束
6. ✅ **数据库路径配置** - 新增 `services/config.py:DatabaseConfig`，数据库文件放到 `runtime/` 目录
7. ✅ **迁移脚本更新** - 重新生成迁移脚本应用所有修复（`067cc4ef0945_init_subscription_tables_with_cascade_.py`）

**新增文件**：
- `services/config.py:DatabaseConfig` - 数据库配置类（统一管理数据库路径）
- `alembic/versions/067cc4ef0945_*.py` - 新的迁移脚本（包含级联删除约束）
- `runtime/omni.db` - 数据库文件新位置（已添加到 `.gitignore`）

### Stage 2: API 接口（待开始）

**开始时间**：
**完成时间**：
**实际工时**：

### Stage 3: API 接口（待开始）

**开始时间**：
**完成时间**：
**实际工时**：

### Stage 4: 前端界面（待开始）

**开始时间**：
**完成时间**：
**实际工时**：

---

## 七、参考文档

- **设计方案**：`.agentdocs/subscription-system-design.md`（v2.2 修订版）
- **持久化方案**：`.agentdocs/runtime-persistence-plan.md`
- **后端架构**：`.agentdocs/backend-architecture.md`
- **ActionRegistry 自动化**：`.agentdocs/subscription-action-registry-automation.md`
- **SQLModel 文档**：https://sqlmodel.tiangolo.com/
- **Alembic 文档**：https://alembic.sqlalchemy.org/

---

**任务状态**：🚧 进行中（已完成 Stage 1-2，进入 Stage 3）
**预计完成日期**：2025-11-23
**当前进度**：40%（2/4 阶段完成）
