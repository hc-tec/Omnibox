# Runtime 持久化渐进式实施方案

> **目标**：在保持现有 FastAPI + Service 层架构不变的前提下，渐进式引入持久化能力，优先实现核心运行时配置（AI 模型、RSSHub）的可管理性，避免过度设计。

---

## 设计原则

### 1. 渐进式演进
- ✅ **先实现核心需求**（AI 模型/RSSHub 配置持久化）
- ✅ **与现有架构无缝集成**（复用 Service 层/DataExecutor/LLM 客户端）
- ✅ **保持向后兼容**（数据库不可用时 fallback 到环境变量）
- ⚠️ **后续按需扩展**（用户系统/付费等级等商业化需求）

### 2. 技术选型务实
- **数据库**：SQLite 统一开发/生产（早期单机部署足够，后续可迁移 PostgreSQL）
- **ORM**：SQLModel（结合 Pydantic + SQLAlchemy，与现有代码风格一致）
- **迁移**：Alembic（标准工具，支持版本控制）
- **加密**：Fernet（标准库 cryptography，避免引入 KMS）
- **缓存**：继续使用现有 CacheService（单机场景无需 Redis）

### 3. 最小化复杂度
- **能用 1 张表不用 4 张表**（避免过度拆分）
- **能用 JSON 字段不新增关系表**（减少 JOIN 复杂度）
- **能复用现有组件不重复造轮子**（如 CacheService、Service 层模式）

---

## 阶段规划

### 阶段 0：当前状态分析

**现有架构优势**：
- ✅ 成熟的三层架构（Controller → Service → Integration）
- ✅ 完善的配置管理（`services/config.py` + Pydantic Settings）
- ✅ 高效的内存缓存（`CacheService` 全局单例）
- ✅ 统一的 LLM 客户端抽象（`query_processor/llm_client.py`）
- ✅ 统一的数据获取层（`DataExecutor`）

**当前限制**：
- ❌ 完全无持久化（重启后配置丢失）
- ❌ 无多配置管理（无法切换不同 LLM/RSSHub 配置）
- ❌ 无历史记录（Panel 会话、研究任务无法查看历史）

---

### 阶段 1：基础持久化 MVP（3-5 天）

**目标**：引入数据库，实现运行时配置持久化，不涉及用户系统

#### 1.1 依赖安装

```bash
pip install sqlmodel alembic cryptography
```

**技术选型理由**：
- `sqlmodel`：结合 Pydantic 和 SQLAlchemy，类型安全，代码量少 30-40%
- `alembic`：标准迁移工具，支持版本控制和 rollback
- `cryptography`：提供 Fernet 对称加密，用于保护 API Key

#### 1.2 核心数据模型

```python
# services/database/models.py
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class LLMProfile(SQLModel, table=True):
    """AI 模型配置

    用于存储不同的 LLM 服务配置（OpenAI、Anthropic、本地模型等），
    支持快速切换和多配置管理。
    """
    __tablename__ = "llm_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, description="显示名称，如 'GPT-4 生产环境'")
    provider: str = Field(description="提供商：openai/anthropic/ollama/custom")
    base_url: Optional[str] = Field(default=None, description="自定义 API 地址")
    api_key_encrypted: Optional[str] = Field(default=None, description="Fernet 加密后的 API Key")
    model: str = Field(description="模型名称，如 gpt-4-turbo/claude-3-sonnet")
    extra_config: str = Field(default="{}", description="JSON 格式额外配置（temperature、max_tokens 等）")
    is_active: bool = Field(default=True, description="是否为当前激活配置")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class RSSHubProfile(SQLModel, table=True):
    """RSSHub 配置

    支持多个 RSSHub 实例配置，可为不同路由指定不同的 headers/cookies。
    """
    __tablename__ = "rsshub_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, description="配置名称，如 '默认配置'/'带认证配置'")
    base_url: str = Field(default="http://localhost:1200", description="RSSHub 实例地址")
    default_headers: str = Field(default="{}", description="JSON 格式默认请求头")
    default_cookies_encrypted: Optional[str] = Field(default=None, description="Fernet 加密后的 Cookies")
    rate_limit: Optional[int] = Field(default=None, description="每分钟请求限制")
    is_active: bool = Field(default=True, description="是否为当前激活配置")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class RSSHubRouteOverride(SQLModel, table=True):
    """RSSHub 路由级配置覆盖

    为特定路由（如 /bilibili/user）指定特殊的 headers/cookies，
    覆盖 profile 的默认配置。
    """
    __tablename__ = "rsshub_route_overrides"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="rsshub_profiles.id", description="所属 RSSHub 配置")
    route_pattern: str = Field(index=True, description="路由模式，如 '/bilibili/*'")
    extra_headers: str = Field(default="{}", description="JSON 格式额外请求头")
    extra_cookies_encrypted: Optional[str] = Field(default=None, description="Fernet 加密后的额外 Cookies")
    notes: Optional[str] = Field(default=None, description="备注说明")
    created_at: datetime = Field(default_factory=datetime.now)


class RuntimeConfig(SQLModel, table=True):
    """通用运行时配置（键值对存储）

    存储系统级别的简单配置项，如默认激活的 profile ID。
    """
    __tablename__ = "runtime_configs"

    key: str = Field(primary_key=True, description="配置键，如 'default_llm_profile_id'")
    value: str = Field(description="配置值（JSON 字符串）")
    description: Optional[str] = Field(default=None, description="配置说明")
    updated_at: datetime = Field(default_factory=datetime.now)
```

#### 1.3 数据库服务层

```python
# services/database/connection.py
from sqlmodel import SQLModel, Session, create_engine
from typing import Optional

class DatabaseConnection:
    """数据库连接管理（单例模式）"""
    _instance: Optional['DatabaseConnection'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        db_path = "omni.db"  # 可通过环境变量配置
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)

    def create_tables(self):
        """创建所有表（开发环境用，生产环境用 Alembic）"""
        SQLModel.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """获取数据库会话"""
        return Session(self.engine)


# services/database/config_service.py
from sqlmodel import select
from cryptography.fernet import Fernet
from typing import Optional, List
import json
import os

class ConfigService:
    """配置管理服务

    负责 LLM 和 RSSHub 配置的 CRUD 操作，以及 API Key 的加解密。
    """

    def __init__(self):
        self.db = DatabaseConnection()
        self.cipher = self._load_or_create_cipher()

    def _load_or_create_cipher(self) -> Fernet:
        """加载或生成加密密钥"""
        key_path = ".encryption_key"
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(key_path, "wb") as f:
                f.write(key)
            print(f"⚠️  已生成新的加密密钥：{key_path}（请妥善保管）")
        return Fernet(key)

    # ========== LLM Profile 管理 ==========

    def get_active_llm_profile(self) -> Optional[LLMProfile]:
        """获取当前激活的 LLM 配置"""
        with self.db.get_session() as session:
            statement = select(LLMProfile).where(LLMProfile.is_active == True)
            return session.exec(statement).first()

    def list_llm_profiles(self) -> List[LLMProfile]:
        """列出所有 LLM 配置"""
        with self.db.get_session() as session:
            return list(session.exec(select(LLMProfile)).all())

    def create_llm_profile(
        self,
        name: str,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        **kwargs
    ) -> LLMProfile:
        """创建新的 LLM 配置"""
        with self.db.get_session() as session:
            profile = LLMProfile(
                name=name,
                provider=provider,
                model=model,
                api_key_encrypted=self._encrypt(api_key) if api_key else None,
                **kwargs
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)
            return profile

    def set_active_llm_profile(self, profile_id: int):
        """设置激活的 LLM 配置（单例模式）"""
        with self.db.get_session() as session:
            # 取消所有激活状态
            session.exec(select(LLMProfile)).all()
            for p in session.exec(select(LLMProfile)).all():
                p.is_active = False
            # 激活指定配置
            profile = session.get(LLMProfile, profile_id)
            if profile:
                profile.is_active = True
                session.commit()

    def decrypt_api_key(self, encrypted: str) -> str:
        """解密 API Key"""
        return self.cipher.decrypt(encrypted.encode()).decode()

    def _encrypt(self, plain_text: str) -> str:
        """加密文本"""
        return self.cipher.encrypt(plain_text.encode()).decode()

    # ========== RSSHub Profile 管理 ==========
    # （类似 LLM Profile，省略具体实现）
```

#### 1.4 集成到现有架构

**1.4.1 修改 LLM 客户端工厂**

```python
# query_processor/llm_client.py（新增函数）
from services.database.config_service import ConfigService
import logging

logger = logging.getLogger(__name__)

def create_llm_client_auto():
    """自动选择配置源：数据库 → 环境变量

    优先从数据库读取激活的 LLM 配置，如果数据库不可用或没有配置，
    则 fallback 到环境变量（保持向后兼容）。
    """
    try:
        config_service = ConfigService()
        profile = config_service.get_active_llm_profile()

        if profile:
            logger.info(f"使用数据库 LLM 配置：{profile.name}")
            api_key = config_service.decrypt_api_key(profile.api_key_encrypted) if profile.api_key_encrypted else None
            extra_config = json.loads(profile.extra_config)

            return create_llm_client(
                provider=profile.provider,
                base_url=profile.base_url,
                api_key=api_key,
                model=profile.model,
                **extra_config
            )
    except Exception as e:
        logger.warning(f"数据库配置读取失败，fallback 到环境变量：{e}")

    # Fallback 到环境变量
    return create_llm_client_from_env()
```

**1.4.2 修改 DataExecutor 工厂**

```python
# integration/data_executor.py（新增函数）
from services.database.config_service import ConfigService
import logging

logger = logging.getLogger(__name__)

def create_data_executor_auto():
    """自动选择配置源：数据库 → 环境变量"""
    try:
        config_service = ConfigService()
        profile = config_service.get_active_rsshub_profile()

        if profile:
            logger.info(f"使用数据库 RSSHub 配置：{profile.name}")
            default_headers = json.loads(profile.default_headers)
            default_cookies = config_service.decrypt_cookies(profile.default_cookies_encrypted) if profile.default_cookies_encrypted else None

            return DataExecutor(
                base_url=profile.base_url,
                default_headers=default_headers,
                default_cookies=default_cookies
            )
    except Exception as e:
        logger.warning(f"数据库配置读取失败，fallback 到环境变量：{e}")

    # Fallback 到环境变量
    return create_data_executor_from_config()
```

**1.4.3 更新 Service 层调用**

```python
# orchestrator/rag_in_action.py（修改）
# 将 create_llm_client() 改为 create_llm_client_auto()

# services/data_query_service.py（修改）
# 将 create_data_executor_from_config() 改为 create_data_executor_auto()
```

#### 1.5 RESTful API 设计

```python
# api/controllers/config_controller.py
from fastapi import APIRouter, HTTPException, Depends
from services.database.config_service import ConfigService
from api.schemas.config import LLMProfileCreate, LLMProfileUpdate, LLMProfileResponse

router = APIRouter(prefix="/api/v1/config", tags=["runtime-config"])

def get_config_service() -> ConfigService:
    """依赖注入"""
    return ConfigService()

# ========== LLM 配置管理 ==========

@router.get("/llm-profiles", response_model=List[LLMProfileResponse])
def list_llm_profiles(service: ConfigService = Depends(get_config_service)):
    """列出所有 LLM 配置"""
    return service.list_llm_profiles()

@router.post("/llm-profiles", response_model=LLMProfileResponse, status_code=201)
def create_llm_profile(
    data: LLMProfileCreate,
    service: ConfigService = Depends(get_config_service)
):
    """创建新的 LLM 配置"""
    return service.create_llm_profile(**data.dict())

@router.patch("/llm-profiles/{profile_id}", response_model=LLMProfileResponse)
def update_llm_profile(
    profile_id: int,
    data: LLMProfileUpdate,
    service: ConfigService = Depends(get_config_service)
):
    """更新 LLM 配置"""
    return service.update_llm_profile(profile_id, **data.dict(exclude_unset=True))

@router.post("/llm-profiles/{profile_id}/activate")
def activate_llm_profile(
    profile_id: int,
    service: ConfigService = Depends(get_config_service)
):
    """激活指定的 LLM 配置"""
    service.set_active_llm_profile(profile_id)
    return {"success": True, "message": f"已激活配置 #{profile_id}"}

@router.delete("/llm-profiles/{profile_id}")
def delete_llm_profile(
    profile_id: int,
    service: ConfigService = Depends(get_config_service)
):
    """删除 LLM 配置"""
    service.delete_llm_profile(profile_id)
    return {"success": True, "message": "配置已删除"}

# ========== RSSHub 配置管理 ==========
# （类似 LLM 配置，省略具体实现）
```

#### 1.6 前端集成（Vue 3 + shadcn-vue）

```typescript
// frontend/src/store/settingsStore.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { LLMProfile, RSSHubProfile } from '@/types/config'
import * as configApi from '@/api/config'

export const useSettingsStore = defineStore('settings', () => {
  const llmProfiles = ref<LLMProfile[]>([])
  const rsshubProfiles = ref<RSSHubProfile[]>([])
  const isLoading = ref(false)

  // 加载所有配置
  async function loadConfigs() {
    isLoading.value = true
    try {
      llmProfiles.value = await configApi.listLLMProfiles()
      rsshubProfiles.value = await configApi.listRSSHubProfiles()
    } finally {
      isLoading.value = false
    }
  }

  // 创建 LLM 配置
  async function createLLMProfile(data: Partial<LLMProfile>) {
    const profile = await configApi.createLLMProfile(data)
    llmProfiles.value.push(profile)
    return profile
  }

  // 激活配置
  async function activateLLMProfile(id: number) {
    await configApi.activateLLMProfile(id)
    await loadConfigs() // 重新加载以更新激活状态
  }

  return {
    llmProfiles,
    rsshubProfiles,
    isLoading,
    loadConfigs,
    createLLMProfile,
    activateLLMProfile,
  }
})
```

```vue
<!-- frontend/src/views/SettingsView.vue -->
<template>
  <div class="settings-container">
    <Tabs default-value="llm">
      <TabsList>
        <TabsTrigger value="llm">AI 模型</TabsTrigger>
        <TabsTrigger value="rsshub">RSSHub</TabsTrigger>
      </TabsList>

      <TabsContent value="llm">
        <LLMProfileSettings />
      </TabsContent>

      <TabsContent value="rsshub">
        <RSSHubProfileSettings />
      </TabsContent>
    </Tabs>
  </div>
</template>

<!-- frontend/src/components/settings/LLMProfileSettings.vue -->
<template>
  <div class="llm-profiles">
    <div class="profiles-header">
      <h2>AI 模型配置</h2>
      <Button @click="showCreateDialog = true">
        <Plus class="w-4 h-4 mr-2" />
        添加配置
      </Button>
    </div>

    <div class="profiles-list">
      <Card v-for="profile in llmProfiles" :key="profile.id">
        <CardHeader>
          <CardTitle>
            {{ profile.name }}
            <Badge v-if="profile.is_active" variant="default">当前激活</Badge>
          </CardTitle>
          <CardDescription>
            {{ profile.provider }} - {{ profile.model }}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div class="profile-info">
            <div v-if="profile.base_url">Base URL: {{ profile.base_url }}</div>
            <div>创建时间: {{ formatDate(profile.created_at) }}</div>
          </div>
        </CardContent>
        <CardFooter class="gap-2">
          <Button
            v-if="!profile.is_active"
            variant="outline"
            @click="activateProfile(profile.id)"
          >
            激活
          </Button>
          <Button variant="ghost" @click="editProfile(profile)">编辑</Button>
          <Button variant="destructive" @click="deleteProfile(profile.id)">删除</Button>
        </CardFooter>
      </Card>
    </div>

    <!-- 创建/编辑对话框 -->
    <Dialog v-model:open="showCreateDialog">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ isEditing ? '编辑配置' : '添加 AI 模型配置' }}</DialogTitle>
        </DialogHeader>
        <LLMProfileForm
          :initial-data="editingProfile"
          @submit="handleSubmit"
          @cancel="showCreateDialog = false"
        />
      </DialogContent>
    </Dialog>
  </div>
</template>
```

#### 1.7 里程碑检查清单

- [ ] **Day 1**: 安装依赖，搭建 SQLModel + Alembic，创建基础表结构
- [ ] **Day 2**: 实现 `ConfigService`，编写 CRUD 方法，编写单元测试
- [ ] **Day 3**: 集成到 `create_llm_client_auto()` 和 `create_data_executor_auto()`，验证 fallback 机制
- [ ] **Day 4**: 实现 FastAPI CRUD 接口，编写 API 集成测试
- [ ] **Day 5**: 前端"设置"页面（shadcn-vue Form + Tabs），端到端测试

---

### 阶段 2：会话持久化（2-3 天）

**目标**：保存 Panel 历史会话，支持"查看历史"和"恢复布局"

#### 2.1 数据模型

```python
class PanelSession(SQLModel, table=True):
    """Panel 会话历史

    存储用户查询和对应的面板布局，支持历史回顾和恢复。
    采用单表设计 + JSON 字段存储完整布局，避免过度拆分。
    """
    __tablename__ = "panel_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    query: str = Field(description="用户查询文本")
    mode: str = Field(description="查询模式：auto/simple/research")
    layout_snapshot: str = Field(description="JSON 格式完整布局（nodes/edges/blocks/data）")
    datasource_filter: Optional[str] = Field(default=None, description="数据源过滤")
    created_at: datetime = Field(default_factory=datetime.now)
```

**为什么单表 + JSON？**
- Panel 的 blocks/data_blocks/layout 是一个整体，拆分会增加查询复杂度
- SQLite 3.38+ 支持 JSON 函数，可以在需要时提取字段
- 简化实现，减少关联查询

#### 2.2 API 设计

```python
# RESTful API
GET    /api/v1/panel-sessions?limit=20&offset=0
POST   /api/v1/panel-sessions
GET    /api/v1/panel-sessions/:id
DELETE /api/v1/panel-sessions/:id
```

#### 2.3 前端集成

```typescript
// frontend/src/store/panelHistoryStore.ts
export const usePanelHistoryStore = defineStore('panelHistory', () => {
  const sessions = ref<PanelSession[]>([])

  async function saveCurrentSession(query: string) {
    const panelStore = usePanelStore()
    const layoutSnapshot = {
      nodes: panelStore.nodes,
      edges: panelStore.edges,
      blocks: panelStore.blocks,
      dataBlocks: panelStore.dataBlocks,
    }

    const session = await api.post('/api/v1/panel-sessions', {
      query,
      mode: panelStore.mode,
      layout_snapshot: JSON.stringify(layoutSnapshot),
    })

    sessions.value.unshift(session)
  }

  async function restoreSession(id: number) {
    const session = await api.get(`/api/v1/panel-sessions/${id}`)
    const panelStore = usePanelStore()
    const layout = JSON.parse(session.layout_snapshot)

    panelStore.restoreLayout(layout)
  }
})
```

---

### 阶段 3：研究任务持久化（3-4 天）

**目标**：保存研究任务历史，支持"查看历史研究"和"断线恢复"

#### 3.1 数据模型（简化为单表）

```python
class ResearchTask(SQLModel, table=True):
    """研究任务

    存储完整的研究任务状态，包括计划、步骤、面板、分析等。
    采用单表 + JSON 字段设计，避免 4 张表的复杂关系。
    """
    __tablename__ = "research_tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    query: str = Field(description="研究查询")
    status: str = Field(description="pending/processing/completed/failed/cancelled")
    mode: str = Field(default="auto", description="研究模式")

    # JSON 字段存储完整状态
    plan: str = Field(default="{}", description="JSON 格式研究计划")
    steps: str = Field(default="[]", description="JSON 格式步骤列表")
    panels: str = Field(default="[]", description="JSON 格式面板数据")
    analyses: str = Field(default="[]", description="JSON 格式分析结果")
    summary: Optional[str] = Field(default=None, description="最终总结")

    auto_detected: bool = Field(default=False, description="是否由系统自动触发")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = Field(default=None)
```

**为什么简化为单表？**
- 研究任务的步骤、面板、分析是强关联的，查询时总是需要全部数据
- 拆分为 4 张表会增加 JOIN 复杂度和代码量
- JSON 字段足够灵活，SQLite 支持 JSON 查询

#### 3.2 WebSocket 推送时自动保存

```python
# services/chat_service.py（修改）
def stream_research_with_persistence(self, query: str, task_id: Optional[int] = None):
    """流式研究，自动持久化到数据库"""
    from services.database.research_service import ResearchTaskService

    task_service = ResearchTaskService()

    # 创建或加载任务
    if task_id:
        task = task_service.get_task(task_id)
    else:
        task = task_service.create_task(query)

    # 流式推送并实时更新数据库
    for message in self._stream_research_internal(query):
        if message['type'] == 'step':
            task_service.append_step(task.id, message['data'])
        elif message['type'] == 'panel':
            task_service.append_panel(task.id, message['data'])
        elif message['type'] == 'analysis':
            task_service.append_analysis(task.id, message['data'])
        elif message['type'] == 'complete':
            task_service.complete_task(task.id, message['data'])

        yield message
```

---

### 阶段 4：用户系统（可选，5-7 天）

**触发条件**：需要多用户使用或团队协作时实现

#### 4.1 最简单的用户模型

```python
class User(SQLModel, table=True):
    """用户账户（最简化版本）"""
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, description="邮箱（登录用）")
    password_hash: str = Field(description="Argon2 哈希密码")
    display_name: Optional[str] = Field(default=None, description="显示名称")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
```

**不实现的功能（早期不需要）**：
- ❌ Magic Link 登录（过度设计）
- ❌ MFA 多因素认证（早期不需要）
- ❌ auth_sessions 设备管理（早期不需要）
- ❌ user_profiles 独立表（字段可以直接放在 users 表）

#### 4.2 为现有表添加 user_id

```python
# 使用 Alembic 迁移添加外键
class LLMProfile(SQLModel, table=True):
    # ...
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", description="所属用户（NULL 表示全局配置）")

class PanelSession(SQLModel, table=True):
    # ...
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")

class ResearchTask(SQLModel, table=True):
    # ...
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
```

---

### 阶段 5：兑换码与付费（可选，4-5 天）

**触发条件**：商业化需求明确时实现

**实现方案**：参考原方案的兑换码表设计，在此不展开。

---

## 技术细节

### 1. 数据库迁移（Alembic）

```bash
# 初始化 Alembic
alembic init migrations

# 配置 alembic.ini
sqlalchemy.url = sqlite:///omni.db

# 配置 env.py 导入所有模型
from services.database.models import *

# 生成迁移脚本
alembic revision --autogenerate -m "init tables"

# 执行迁移
alembic upgrade head

# 回滚（如果需要）
alembic downgrade -1
```

### 2. API Key 加密最佳实践

```python
from cryptography.fernet import Fernet

# 密钥管理
# 1. 开发环境：存储在 .encryption_key 文件（加入 .gitignore）
# 2. 生产环境：使用环境变量 ENCRYPTION_KEY
# 3. 备份：定期备份密钥，丢失后无法解密历史数据

def _load_or_create_cipher(self) -> Fernet:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        key_path = ".encryption_key"
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                key = f.read().decode()
        else:
            key = Fernet.generate_key().decode()
            with open(key_path, "w") as f:
                f.write(key)
            logger.warning(f"⚠️  已生成新的加密密钥，请妥善保管：{key_path}")

    return Fernet(key.encode())
```

### 3. 配置优先级与 Fallback

```
数据库激活配置 → 环境变量 → 代码默认值
```

**实现示例**：
```python
def create_llm_client_auto():
    # 1. 尝试数据库
    try:
        profile = ConfigService().get_active_llm_profile()
        if profile:
            return create_llm_client_from_profile(profile)
    except Exception as e:
        logger.warning(f"数据库不可用：{e}")

    # 2. 尝试环境变量
    if os.getenv("OPENAI_API_KEY"):
        return create_llm_client_from_env()

    # 3. 使用默认值
    raise ValueError("未配置 LLM，请通过界面或环境变量配置")
```

### 4. 前端缓存策略

```typescript
// 设置页面：每次进入时刷新
onMounted(async () => {
  await settingsStore.loadConfigs()
})

// 主界面：启动时加载一次，缓存 5 分钟
const configCache = ref<LLMProfile | null>(null)
const configCacheTime = ref(0)

async function getLLMConfig() {
  const now = Date.now()
  if (configCache.value && now - configCacheTime.value < 5 * 60 * 1000) {
    return configCache.value
  }

  configCache.value = await api.get('/api/v1/config/llm-profiles/active')
  configCacheTime.value = now
  return configCache.value
}
```

---

## 实施检查清单

### 阶段 1：基础持久化 MVP
- [ ] 安装 sqlmodel/alembic/cryptography
- [ ] 创建数据库模型（LLMProfile/RSSHubProfile/RuntimeConfig）
- [ ] 实现 ConfigService（CRUD + 加解密）
- [ ] 集成到 create_llm_client_auto() / create_data_executor_auto()
- [ ] 实现 FastAPI CRUD 接口
- [ ] 前端"设置"页面（Tabs + Form + Card）
- [ ] 编写单元测试和集成测试
- [ ] 更新文档（README/backend-architecture.md）

### 阶段 2：会话持久化
- [ ] 创建 PanelSession 模型
- [ ] 实现 PanelSessionService
- [ ] 实现 FastAPI 接口
- [ ] 前端 panelHistoryStore
- [ ] 前端"历史记录"页面
- [ ] 测试保存和恢复功能

### 阶段 3：研究任务持久化
- [ ] 创建 ResearchTask 模型
- [ ] 实现 ResearchTaskService
- [ ] 修改 stream_research 支持持久化
- [ ] 前端断线恢复逻辑
- [ ] 前端"研究历史"页面
- [ ] 测试断线恢复功能

### 阶段 4：用户系统（可选）
- [ ] 创建 User 模型
- [ ] 实现认证服务（Argon2 + JWT）
- [ ] 为现有表添加 user_id
- [ ] 实现鉴权中间件
- [ ] 前端 authStore + 登录页面
- [ ] 测试多用户隔离

### 阶段 5：付费系统（可选）
- [ ] 创建 RedeemCode/UserEntitlement 模型
- [ ] 实现兑换服务
- [ ] 实现 Tier 控制中间件
- [ ] 前端兑换页面
- [ ] 测试 Tier 限制功能

---

## 重要记忆

### 设计原则
- ✅ **渐进式演进** - 先核心功能，再扩展功能
- ✅ **与现有架构集成** - 复用 Service 层模式
- ✅ **保持向后兼容** - 数据库不可用时 fallback
- ✅ **最小化复杂度** - 能用 1 张表不用 4 张表

### 技术选型
- 🗄️ **数据库** - SQLite（统一开发/生产）
- 🔧 **ORM** - SQLModel（类型安全 + Pydantic 风格）
- 🔄 **迁移** - Alembic（标准工具）
- 🔐 **加密** - Fernet（标准库）
- 💾 **缓存** - 继续用 CacheService（无需 Redis）

### 避免的过度设计
- ❌ PostgreSQL + Redis（早期不需要）
- ❌ 4 张用户表 + Magic Link + MFA（早期不需要）
- ❌ 4 张研究任务表（单表 + JSON 足够）
- ❌ audit_logs 审计表（早期不需要）
- ❌ KMS 秘钥管理（Fernet 足够）

### 实施顺序
1. **优先** - AI 模型/RSSHub 配置（解决核心痛点）
2. **其次** - Panel 会话历史（提升用户体验）
3. **再次** - 研究任务持久化（完善功能）
4. **可选** - 用户系统（多用户需求时）
5. **可选** - 付费系统（商业化时）

---

## 参考资料

- [SQLModel 官方文档](https://sqlmodel.tiangolo.com/)
- [Alembic 迁移指南](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Fernet 加密文档](https://cryptography.io/en/latest/fernet/)
- [FastAPI 依赖注入](https://fastapi.tiangolo.com/tutorial/dependencies/)
- 项目现有架构文档：`.agentdocs/backend-architecture.md`
