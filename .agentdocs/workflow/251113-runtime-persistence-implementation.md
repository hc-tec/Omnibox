# Runtime 持久化实施任务

**任务概述**：为项目引入数据库持久化能力，优先实现运行时配置（AI 模型、RSSHub）的可管理性，逐步扩展到会话历史和研究任务。

**开始时间**：2025-11-13
**当前状态**：**规划完成，待开始实施**

---

## 背景与动机

### 当前痛点
1. **配置无法持久化** - 所有 AI 模型/RSSHub 配置依赖环境变量，重启后丢失
2. **无多配置管理** - 无法快速切换不同的 LLM 服务或 RSSHub 实例
3. **无历史记录** - Panel 会话和研究任务无法查看历史，断线后无法恢复

### 核心需求
1. ✅ **Runtime 配置持久化**（AI 模型、RSSHub）- 最高优先级
2. ✅ **前端会话历史**（Panel 布局保存/恢复）- 中优先级
3. ⚠️ **研究任务持久化**（断线恢复）- 中优先级
4. ⚠️ **用户系统**（多用户隔离）- 可选，按需实施
5. ⚠️ **付费系统**（兑换码/Tier 控制）- 可选，商业化时实施

---

## 方案审视结果

### 原方案问题
由 Codex 生成的初始方案存在以下问题：
1. ❌ **严重过度设计** - 从无数据库跳跃到 4 张用户表 + Magic Link + MFA + PostgreSQL + Redis
2. ❌ **脱离现状** - 未考虑现有三层架构（Service/Integration）的集成路径
3. ❌ **优先级错乱** - 将用户/付费放在核心配置之前
4. ❌ **技术过重** - PostgreSQL + Redis 对早期单机部署过重

### 修正方案
采用**渐进式实施路径**：
- ✅ SQLite 统一开发/生产（后续可迁移 PostgreSQL）
- ✅ SQLModel（类型安全 + 与现有 Pydantic 风格一致）
- ✅ 单表 + JSON 字段（避免过度拆分）
- ✅ Fallback 机制（数据库不可用时回退到环境变量）
- ✅ 5 个阶段（MVP → 会话 → 研究 → 用户 → 付费）

详细方案见：`.agentdocs/runtime-persistence-plan.md`

---

## 阶段规划与 TODO

### 阶段 1：基础持久化 MVP（3-5 天）⏳

**目标**：引入数据库，实现 AI 模型和 RSSHub 配置的 CRUD 管理

#### TODO 清单

**Day 1：数据库基础搭建**
- [ ] 安装依赖 `sqlmodel`, `alembic`, `cryptography`
- [ ] 创建 `services/database/` 目录结构
- [ ] 创建数据模型 `models.py`（LLMProfile/RSSHubProfile/RuntimeConfig）
- [ ] 创建数据库连接管理 `connection.py`（单例模式）
- [ ] 初始化 Alembic，生成迁移脚本
- [ ] 编写单元测试（模型创建/查询/更新/删除）

**Day 2：配置服务层**
- [ ] 实现 `ConfigService`（CRUD 操作）
- [ ] 实现加密密钥管理（Fernet + .encryption_key）
- [ ] 实现 LLM Profile 管理（list/create/update/delete/activate）
- [ ] 实现 RSSHub Profile 管理（同上）
- [ ] 实现 API Key 加解密方法
- [ ] 编写 ConfigService 单元测试（覆盖所有 CRUD + 加密）

**Day 3：集成到现有架构**
- [ ] 修改 `query_processor/llm_client.py`，新增 `create_llm_client_auto()`
- [ ] 修改 `integration/data_executor.py`，新增 `create_data_executor_auto()`
- [ ] 更新 `orchestrator/rag_in_action.py`，使用 `create_llm_client_auto()`
- [ ] 更新 `services/data_query_service.py`，使用 `create_data_executor_auto()`
- [ ] 测试 Fallback 机制（数据库为空 → 环境变量）
- [ ] 编写集成测试（数据库配置 + 环境变量 fallback）

**Day 4：FastAPI CRUD 接口**
- [ ] 创建 `api/schemas/config.py`（Pydantic 请求/响应模型）
- [ ] 创建 `api/controllers/config_controller.py`（RESTful 接口）
- [ ] 实现 LLM Profile 接口（GET/POST/PATCH/DELETE + activate）
- [ ] 实现 RSSHub Profile 接口（同上）
- [ ] 编写 API 集成测试（使用 TestClient）
- [ ] 更新 OpenAPI 文档（tags + descriptions）

**Day 5：前端设置页面**
- [ ] 创建 `frontend/src/types/config.ts`（TypeScript 类型定义）
- [ ] 创建 `frontend/src/api/config.ts`（API 调用封装）
- [ ] 创建 `frontend/src/store/settingsStore.ts`（Pinia store）
- [ ] 创建 `frontend/src/views/SettingsView.vue`（Tabs 主容器）
- [ ] 创建 `frontend/src/components/settings/LLMProfileSettings.vue`（列表 + CRUD）
- [ ] 创建 `frontend/src/components/settings/LLMProfileForm.vue`（表单组件）
- [ ] 创建 `frontend/src/components/settings/RSSHubProfileSettings.vue`（同上）
- [ ] 端到端测试（创建配置 → 激活 → 验证生效）

#### 验收标准
- ✅ 可以通过前端界面添加/编辑/删除/激活 LLM 配置
- ✅ 可以通过前端界面添加/编辑/删除/激活 RSSHub 配置
- ✅ API Key 正确加密存储（查看数据库确认密文）
- ✅ 配置生效验证（使用数据库配置成功调用 LLM/RSSHub）
- ✅ Fallback 机制验证（删除数据库配置，回退到环境变量）
- ✅ 单元测试覆盖率 > 80%
- ✅ 集成测试全部通过

---

### 阶段 2：会话持久化（2-3 天）⏳

**目标**：保存 Panel 会话历史，支持"查看历史"和"恢复布局"

#### TODO 清单

**Day 1：数据模型与服务**
- [ ] 创建 `PanelSession` 模型（单表 + JSON 字段）
- [ ] 生成 Alembic 迁移脚本
- [ ] 创建 `PanelSessionService`（CRUD 操作）
- [ ] 编写单元测试

**Day 2：API 与前端 Store**
- [ ] 创建 `api/controllers/panel_session_controller.py`
- [ ] 实现 RESTful 接口（GET/POST/DELETE）
- [ ] 创建 `frontend/src/store/panelHistoryStore.ts`
- [ ] 实现 `saveCurrentSession()` 和 `restoreSession()`

**Day 3：前端历史页面**
- [ ] 创建 `frontend/src/views/HistoryView.vue`（列表 + 搜索）
- [ ] 实现点击历史项恢复布局
- [ ] 实现删除历史记录
- [ ] 端到端测试

#### 验收标准
- ✅ Panel 查询后自动保存会话
- ✅ 可以查看历史会话列表（按时间倒序）
- ✅ 点击历史项成功恢复布局
- ✅ 可以删除历史记录

---

### 阶段 3：研究任务持久化（3-4 天）⏳

**目标**：保存研究任务历史，支持断线恢复

#### TODO 清单

**Day 1：数据模型与服务**
- [ ] 创建 `ResearchTask` 模型（单表 + JSON 字段存储 plan/steps/panels/analyses）
- [ ] 生成 Alembic 迁移脚本
- [ ] 创建 `ResearchTaskService`（CRUD + append 方法）
- [ ] 编写单元测试

**Day 2：集成到流式推送**
- [ ] 修改 `services/chat_service.py`，新增 `stream_research_with_persistence()`
- [ ] 实时保存研究步骤到数据库
- [ ] 实现断线恢复逻辑（加载已有任务继续推送）
- [ ] 编写集成测试

**Day 3-4：API 与前端**
- [ ] 创建研究任务 API（GET/POST/PATCH）
- [ ] 前端实现研究历史页面
- [ ] 前端实现断线恢复（WebSocket 重连后从数据库加载状态）
- [ ] 端到端测试

#### 验收标准
- ✅ 研究任务自动保存到数据库
- ✅ WebSocket 断线重连后可以恢复任务状态
- ✅ 可以查看历史研究任务列表
- ✅ 可以重新打开已完成的研究任务查看结果

---

### 阶段 4：用户系统（可选，5-7 天）⏳

**触发条件**：需要多用户使用或团队协作时实现

#### TODO 清单
- [ ] 创建 `User` 模型（最简化，仅 email + password_hash）
- [ ] 实现认证服务（Argon2 密码哈希 + JWT）
- [ ] 为现有表添加 `user_id` 外键（Alembic 迁移）
- [ ] 实现鉴权中间件（验证 JWT token）
- [ ] 前端实现 `authStore` 和登录页面
- [ ] 测试多用户数据隔离

#### 验收标准
- ✅ 用户可以注册/登录
- ✅ 配置、会话、研究任务按用户隔离
- ✅ 未登录用户无法访问他人数据

**⚠️ 暂不实施**（当前不需要）

---

### 阶段 5：付费系统（可选，4-5 天）⏳

**触发条件**：商业化需求明确时实现

#### TODO 清单
- [ ] 创建 `RedeemCode` 和 `UserEntitlement` 模型
- [ ] 实现兑换服务
- [ ] 实现 Tier 控制中间件
- [ ] 前端实现兑换页面
- [ ] 测试 Tier 限制功能

**⚠️ 暂不实施**（当前不需要）

---

## 技术决策记录

### 为什么选择 SQLite 而非 PostgreSQL？
- ✅ 早期单机部署，SQLite 性能足够（支持并发读，写入排队）
- ✅ 零配置，无需独立数据库服务
- ✅ 文件数据库，方便备份和迁移
- ⚠️ 后续如需高并发写入，可用 Alembic 迁移到 PostgreSQL

### 为什么选择 SQLModel 而非纯 SQLAlchemy？
- ✅ 与现有 Pydantic 代码风格一致
- ✅ 类型安全，IDE 提示友好
- ✅ 代码量少 30-40%（同时作为 ORM 模型和 Pydantic 模型）
- ✅ FastAPI 官方推荐（作者同为 Sebastián Ramírez）

### 为什么用单表 + JSON 而非多表关系？
- ✅ 研究任务的 steps/panels/analyses 天然是一个整体
- ✅ 避免多表 JOIN 的性能开销和代码复杂度
- ✅ SQLite 3.38+ 支持 JSON 查询函数
- ⚠️ 如需复杂查询（如按步骤状态筛选），再考虑拆表

### 为什么继续用内存缓存而非 Redis？
- ✅ 单机部署，内存缓存足够
- ✅ CacheService 已实现 TTL 和统计功能
- ✅ 避免引入额外依赖和运维复杂度
- ⚠️ 后续如需多实例部署，可迁移到 Redis

### 为什么用 Fernet 而非 KMS？
- ✅ 标准库 `cryptography`，无需外部服务
- ✅ 对称加密，性能优于非对称加密
- ✅ 支持密钥轮转（存储多个密钥版本）
- ⚠️ 密钥需要妥善保管（丢失后无法解密历史数据）

---

## 风险与应对

### 风险 1：加密密钥丢失
**影响**：无法解密历史 API Key
**概率**：低（有备份机制）
**应对**：
- 开发环境：存储在 `.encryption_key` 文件（加入 `.gitignore`）
- 生产环境：使用环境变量 `ENCRYPTION_KEY`
- 备份：定期备份密钥文件

### 风险 2：数据库迁移失败
**影响**：数据丢失或应用无法启动
**概率**：中（Alembic 迁移有风险）
**应对**：
- 迁移前自动备份数据库文件
- 使用 Alembic 的 downgrade 功能回滚
- 在测试环境充分验证迁移脚本

### 风险 3：与现有代码集成出现 Bug
**影响**：部分功能失效
**概率**：中
**应对**：
- 保持 Fallback 机制（数据库不可用时回退环境变量）
- 充分的集成测试和端到端测试
- 灰度发布（先在部分功能启用）

---

## 参考文档

- 方案文档：`.agentdocs/runtime-persistence-plan.md`
- 后端架构：`.agentdocs/backend-architecture.md`
- 前端架构：`.agentdocs/frontend-architecture.md`
- SQLModel 官方文档：https://sqlmodel.tiangolo.com/
- Alembic 官方文档：https://alembic.sqlalchemy.org/

---

## 任务状态跟踪

| 阶段 | 状态 | 开始时间 | 完成时间 | 备注 |
|------|------|----------|----------|------|
| 阶段 1：基础持久化 MVP | ⏳ 待开始 | - | - | 3-5 天 |
| 阶段 2：会话持久化 | ⏳ 待开始 | - | - | 2-3 天 |
| 阶段 3：研究任务持久化 | ⏳ 待开始 | - | - | 3-4 天 |
| 阶段 4：用户系统 | ⏸️ 暂不实施 | - | - | 可选 |
| 阶段 5：付费系统 | ⏸️ 暂不实施 | - | - | 可选 |

---

## 阶段完成记录

### 阶段 1：基础持久化 MVP
- **开始时间**：待定
- **完成时间**：待定
- **实际工作量**：待定
- **遇到的问题**：待定
- **解决方案**：待定

### 阶段 2：会话持久化
- **开始时间**：待定
- **完成时间**：待定
- **实际工作量**：待定
- **遇到的问题**：待定
- **解决方案**：待定

### 阶段 3：研究任务持久化
- **开始时间**：待定
- **完成时间**：待定
- **实际工作量**：待定
- **遇到的问题**：待定
- **解决方案**：待定
