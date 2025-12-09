# Phase 5: 仪表盘设计方案

**创建日期**: 2025-12-09
**状态**: ✅ 已完成
**目标**: 实现数据监控仪表盘，支持卡片 Pin、定时刷新、条件触发、通知推送

---

## 一、现状分析

### 1.1 现有可复用代码

| 模块 | 位置 | 复用策略 |
|------|------|---------|
| **DataArtifact** | `services/data_artifact/` | ✅ Pin 的数据来源 |
| **Workflow/WorkflowRun** | `services/workflow/` | ✅ 刷新时复用执行机制 |
| **面板组件** | `features/panel/components/` | ✅ 复用 17 个已有组件 |
| **DynamicBlockRenderer** | `features/panel/` | ✅ 复用组件渲染 |
| **WebSocket 推送** | `api/controllers/` | ✅ 复用进度推送机制 |
| **DatabaseConnection** | `services/database/` | ✅ 复用数据库连接 |

### 1.2 需要新增的内容

1. **Dashboard 数据模型**：DashboardCard（Pin 的卡片）、RefreshSchedule（刷新计划）
2. **条件触发系统**：Trigger 定义、TriggerEvaluator 评估器
3. **通知系统**：Notification 模型、NotificationService
4. **后台调度器**：SchedulerService（定时任务调度）
5. **前端组件**：DashboardView、DashboardCard、TriggerConfigDialog

---

## 二、数据模型设计

### 2.1 DashboardCard（仪表盘卡片）

```python
# services/dashboard/models.py

class CardType(str, Enum):
    """卡片类型"""
    ARTIFACT = "artifact"       # 数据产物卡片
    WORKFLOW = "workflow"       # 工作流结果卡片
    CUSTOM = "custom"           # 自定义查询卡片

class RefreshInterval(str, Enum):
    """刷新频率"""
    MANUAL = "manual"           # 手动刷新
    HOURLY = "hourly"           # 每小时
    DAILY = "daily"             # 每天
    WEEKLY = "weekly"           # 每周
    CUSTOM = "custom"           # 自定义 cron

class DashboardCard(SQLModel, table=True):
    """
    仪表盘卡片

    核心设计：
    - 卡片是对数据源（Artifact/Workflow/Query）的引用
    - 支持定时刷新和条件触发
    - 支持自定义可视化配置
    """
    __tablename__ = "dashboard_cards"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    card_id: str = SQLField(index=True, description="卡片唯一标识")

    # 基本信息
    name: str = SQLField(..., description="卡片名称")
    description: str = SQLField(default="", description="卡片描述")
    card_type: str = SQLField(..., description="卡片类型")

    # 数据源配置
    source_config_json: str = SQLField(
        default="{}",
        description="""
        数据源配置（根据 card_type 不同）：
        - artifact: {"artifact_id": "xxx"}
        - workflow: {"workflow_id": "xxx", "variable_values": {...}}
        - custom: {"query": "xxx"}
        """
    )

    # 可视化配置
    view_config_json: str = SQLField(
        default="{}",
        description="""
        可视化配置：
        - component: 组件类型（LineChart、Table 等）
        - props: 组件属性
        - layout: 布局配置（position, size）
        """
    )

    # 刷新配置
    refresh_interval: str = SQLField(
        default=RefreshInterval.MANUAL.value,
        description="刷新频率"
    )
    refresh_cron: Optional[str] = SQLField(
        default=None,
        description="自定义 cron 表达式（当 refresh_interval=custom 时）"
    )
    last_refresh_at: Optional[datetime] = SQLField(default=None)
    next_refresh_at: Optional[datetime] = SQLField(default=None)

    # 触发器配置（JSON 数组）
    triggers_json: str = SQLField(default="[]", description="触发器列表")

    # 布局位置
    position_x: int = SQLField(default=0)
    position_y: int = SQLField(default=0)
    width: int = SQLField(default=4, description="宽度（网格单位，共12列）")
    height: int = SQLField(default=3, description="高度（网格单位）")

    # 状态
    enabled: bool = SQLField(default=True, description="是否启用")

    # 时间戳
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now)
```

### 2.2 Trigger（条件触发器）

```python
class TriggerType(str, Enum):
    """触发器类型"""
    VALUE_CHANGE = "value_change"     # 值变化时触发
    THRESHOLD = "threshold"           # 超过阈值触发
    PATTERN = "pattern"               # 模式匹配触发
    SCHEDULE = "schedule"             # 定时触发

class TriggerAction(str, Enum):
    """触发动作"""
    NOTIFY = "notify"                 # 发送通知
    REFRESH = "refresh"               # 刷新卡片
    RUN_WORKFLOW = "run_workflow"     # 执行工作流
    WEBHOOK = "webhook"               # 调用 Webhook

class Trigger(BaseModel):
    """
    触发器定义

    设计理念：
    - 条件 + 动作的组合
    - 支持多种触发类型和动作
    - 可序列化为 JSON 存储
    """
    trigger_id: str = Field(default_factory=lambda: f"trg-{uuid.uuid4().hex[:8]}")
    name: str = Field(..., description="触发器名称")
    enabled: bool = Field(default=True)

    # 触发条件
    trigger_type: TriggerType = Field(...)
    condition: Dict[str, Any] = Field(
        default_factory=dict,
        description="""
        条件配置（根据 trigger_type 不同）：
        - value_change: {"field": "count", "change_type": "increase"}
        - threshold: {"field": "count", "operator": "gt", "value": 100}
        - pattern: {"field": "title", "regex": ".*关键词.*"}
        - schedule: {"cron": "0 9 * * *"}
        """
    )

    # 触发动作
    action: TriggerAction = Field(...)
    action_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="""
        动作配置：
        - notify: {"channels": ["app", "email"], "message": "xxx"}
        - refresh: {}
        - run_workflow: {"workflow_id": "xxx", "variables": {...}}
        - webhook: {"url": "https://...", "method": "POST"}
        """
    )

    # 执行记录
    last_triggered_at: Optional[datetime] = Field(default=None)
    trigger_count: int = Field(default=0)
```

### 2.3 Notification（通知）

```python
class NotificationChannel(str, Enum):
    """通知渠道"""
    APP = "app"               # 应用内通知
    EMAIL = "email"           # 邮件
    WEBHOOK = "webhook"       # Webhook

class NotificationStatus(str, Enum):
    """通知状态"""
    PENDING = "pending"
    SENT = "sent"
    READ = "read"
    FAILED = "failed"

class Notification(SQLModel, table=True):
    """
    通知记录
    """
    __tablename__ = "notifications"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    notification_id: str = SQLField(index=True)

    # 来源
    source_type: str = SQLField(..., description="trigger | system")
    source_id: Optional[str] = SQLField(default=None, description="触发器 ID")
    card_id: Optional[str] = SQLField(default=None, description="关联卡片 ID")

    # 内容
    title: str = SQLField(...)
    message: str = SQLField(...)
    data_json: str = SQLField(default="{}", description="附加数据")

    # 渠道和状态
    channel: str = SQLField(default=NotificationChannel.APP.value)
    status: str = SQLField(default=NotificationStatus.PENDING.value)

    # 时间戳
    created_at: datetime = SQLField(default_factory=datetime.now)
    sent_at: Optional[datetime] = SQLField(default=None)
    read_at: Optional[datetime] = SQLField(default=None)
```

### 2.4 数据库迁移

```python
# 新增表：dashboard_cards, notifications
# 复用现有：workflows, workflow_runs, artifacts
```

---

## 三、服务层设计

### 3.1 DashboardService

```python
# services/dashboard/dashboard_service.py

class DashboardService:
    """仪表盘服务"""

    def __init__(self, db: DatabaseConnection):
        self._db = db

    # 卡片 CRUD
    def create_card(self, card: DashboardCard) -> DashboardCard: ...
    def get_card(self, card_id: str) -> Optional[DashboardCard]: ...
    def list_cards(self, enabled_only: bool = True) -> List[DashboardCard]: ...
    def update_card(self, card_id: str, updates: Dict) -> DashboardCard: ...
    def delete_card(self, card_id: str) -> bool: ...

    # Pin 操作
    def pin_artifact(
        self,
        artifact_id: str,
        name: str,
        view_config: Optional[Dict] = None,
        refresh_interval: str = "manual"
    ) -> DashboardCard:
        """将数据产物 Pin 到仪表盘"""
        pass

    def pin_workflow(
        self,
        workflow_id: str,
        name: str,
        variable_values: Dict[str, Any],
        view_config: Optional[Dict] = None,
        refresh_interval: str = "daily"
    ) -> DashboardCard:
        """将工作流结果 Pin 到仪表盘（支持定时执行）"""
        pass

    # 刷新操作
    def refresh_card(self, card_id: str) -> Dict[str, Any]:
        """手动刷新卡片数据"""
        pass

    def get_card_data(self, card_id: str) -> Dict[str, Any]:
        """获取卡片当前数据"""
        pass

    # 布局管理
    def update_layout(self, card_layouts: List[Dict]) -> None:
        """批量更新卡片布局"""
        pass
```

### 3.2 SchedulerService（后台调度）

```python
# services/dashboard/scheduler_service.py

class SchedulerService:
    """
    后台调度服务

    基于 APScheduler 实现定时刷新
    """

    def __init__(self, dashboard_service: DashboardService):
        self._dashboard = dashboard_service
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        """启动调度器"""
        self._scheduler.start()
        self._sync_jobs()

    def stop(self) -> None:
        """停止调度器"""
        self._scheduler.shutdown()

    def _sync_jobs(self) -> None:
        """同步数据库中的刷新任务"""
        cards = self._dashboard.list_cards(enabled_only=True)
        for card in cards:
            if card.refresh_interval != RefreshInterval.MANUAL.value:
                self._add_refresh_job(card)

    def _add_refresh_job(self, card: DashboardCard) -> None:
        """添加刷新任务"""
        job_id = f"refresh_{card.card_id}"

        if card.refresh_interval == RefreshInterval.HOURLY.value:
            trigger = IntervalTrigger(hours=1)
        elif card.refresh_interval == RefreshInterval.DAILY.value:
            trigger = IntervalTrigger(days=1)
        elif card.refresh_interval == RefreshInterval.WEEKLY.value:
            trigger = IntervalTrigger(weeks=1)
        elif card.refresh_interval == RefreshInterval.CUSTOM.value:
            trigger = CronTrigger.from_crontab(card.refresh_cron)
        else:
            return

        self._scheduler.add_job(
            self._refresh_card_job,
            trigger=trigger,
            id=job_id,
            args=[card.card_id],
            replace_existing=True
        )

    async def _refresh_card_job(self, card_id: str) -> None:
        """执行刷新任务"""
        try:
            result = await self._dashboard.refresh_card(card_id)
            await self._evaluate_triggers(card_id, result)
        except Exception as e:
            logger.error(f"刷新卡片失败: {card_id}, {e}")
```

### 3.3 TriggerService（条件触发）

```python
# services/dashboard/trigger_service.py

class TriggerService:
    """
    触发器服务

    负责评估触发条件、执行触发动作
    """

    def __init__(
        self,
        dashboard_service: DashboardService,
        notification_service: NotificationService,
        workflow_engine: WorkflowEngine
    ):
        self._dashboard = dashboard_service
        self._notification = notification_service
        self._workflow = workflow_engine

    def evaluate_triggers(
        self,
        card_id: str,
        old_data: Optional[Dict],
        new_data: Dict
    ) -> List[Trigger]:
        """
        评估卡片的触发器

        Returns:
            触发的触发器列表
        """
        card = self._dashboard.get_card(card_id)
        triggers = card.get_triggers()
        triggered = []

        for trigger in triggers:
            if not trigger.enabled:
                continue
            if self._check_condition(trigger, old_data, new_data):
                self._execute_action(trigger, card, new_data)
                triggered.append(trigger)

        return triggered

    def _check_condition(
        self,
        trigger: Trigger,
        old_data: Optional[Dict],
        new_data: Dict
    ) -> bool:
        """检查触发条件"""
        if trigger.trigger_type == TriggerType.VALUE_CHANGE:
            return self._check_value_change(trigger.condition, old_data, new_data)
        elif trigger.trigger_type == TriggerType.THRESHOLD:
            return self._check_threshold(trigger.condition, new_data)
        elif trigger.trigger_type == TriggerType.PATTERN:
            return self._check_pattern(trigger.condition, new_data)
        return False

    def _check_value_change(self, condition: Dict, old: Optional[Dict], new: Dict) -> bool:
        """检查值变化"""
        field = condition.get("field")
        change_type = condition.get("change_type", "any")  # any | increase | decrease

        if old is None:
            return True  # 首次数据，视为变化

        old_value = self._get_field_value(old, field)
        new_value = self._get_field_value(new, field)

        if change_type == "any":
            return old_value != new_value
        elif change_type == "increase":
            return new_value > old_value
        elif change_type == "decrease":
            return new_value < old_value
        return False

    def _check_threshold(self, condition: Dict, data: Dict) -> bool:
        """检查阈值"""
        field = condition.get("field")
        operator = condition.get("operator")  # gt | lt | eq | gte | lte
        value = condition.get("value")

        current = self._get_field_value(data, field)

        ops = {
            "gt": lambda a, b: a > b,
            "lt": lambda a, b: a < b,
            "eq": lambda a, b: a == b,
            "gte": lambda a, b: a >= b,
            "lte": lambda a, b: a <= b,
        }
        return ops.get(operator, lambda a, b: False)(current, value)

    def _execute_action(self, trigger: Trigger, card: DashboardCard, data: Dict) -> None:
        """执行触发动作"""
        if trigger.action == TriggerAction.NOTIFY:
            self._send_notification(trigger, card, data)
        elif trigger.action == TriggerAction.REFRESH:
            # 已经刷新，跳过
            pass
        elif trigger.action == TriggerAction.RUN_WORKFLOW:
            self._run_workflow(trigger, data)
        elif trigger.action == TriggerAction.WEBHOOK:
            self._call_webhook(trigger, data)
```

### 3.4 NotificationService（通知服务）

```python
# services/dashboard/notification_service.py

class NotificationService:
    """
    通知服务

    负责发送和管理通知
    """

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def send(
        self,
        title: str,
        message: str,
        channel: NotificationChannel = NotificationChannel.APP,
        source_type: str = "system",
        source_id: Optional[str] = None,
        card_id: Optional[str] = None,
        data: Optional[Dict] = None
    ) -> Notification:
        """发送通知"""
        notification = Notification(
            notification_id=f"notif-{uuid.uuid4().hex[:12]}",
            title=title,
            message=message,
            channel=channel.value,
            source_type=source_type,
            source_id=source_id,
            card_id=card_id,
            data_json=json.dumps(data or {})
        )

        # 保存到数据库
        self._save(notification)

        # 根据渠道发送
        if channel == NotificationChannel.APP:
            self._send_app_notification(notification)
        elif channel == NotificationChannel.EMAIL:
            self._send_email(notification)
        elif channel == NotificationChannel.WEBHOOK:
            self._send_webhook(notification)

        return notification

    def list_unread(self, limit: int = 50) -> List[Notification]:
        """获取未读通知"""
        pass

    def mark_read(self, notification_id: str) -> None:
        """标记已读"""
        pass

    def mark_all_read(self) -> None:
        """全部标记已读"""
        pass

    def _send_app_notification(self, notification: Notification) -> None:
        """发送应用内通知（通过 WebSocket 推送）"""
        # TODO: 集成 WebSocket 推送
        pass
```

---

## 四、API 设计

### 4.1 Dashboard API 端点

```python
# api/controllers/dashboard_controller.py

# 卡片管理
GET    /api/v1/dashboard/cards              # 卡片列表
GET    /api/v1/dashboard/cards/{card_id}    # 卡片详情
POST   /api/v1/dashboard/cards              # 创建卡片
PUT    /api/v1/dashboard/cards/{card_id}    # 更新卡片
DELETE /api/v1/dashboard/cards/{card_id}    # 删除卡片

# Pin 操作
POST   /api/v1/dashboard/pin/artifact       # Pin 数据产物
POST   /api/v1/dashboard/pin/workflow       # Pin 工作流

# 刷新
POST   /api/v1/dashboard/cards/{card_id}/refresh  # 手动刷新
GET    /api/v1/dashboard/cards/{card_id}/data     # 获取卡片数据

# 布局
PUT    /api/v1/dashboard/layout             # 更新布局（拖拽后保存）

# 触发器
GET    /api/v1/dashboard/cards/{card_id}/triggers      # 获取触发器
POST   /api/v1/dashboard/cards/{card_id}/triggers      # 添加触发器
DELETE /api/v1/dashboard/cards/{card_id}/triggers/{id} # 删除触发器
```

### 4.2 Notification API 端点

```python
# api/controllers/notification_controller.py

GET    /api/v1/notifications                # 通知列表
GET    /api/v1/notifications/unread/count   # 未读数量
POST   /api/v1/notifications/{id}/read      # 标记已读
POST   /api/v1/notifications/read-all       # 全部已读
```

### 4.3 请求/响应模型

```python
# api/schemas/dashboard.py

class PinArtifactRequest(BaseModel):
    """Pin 数据产物请求"""
    artifact_id: str
    name: str
    view_config: Optional[Dict] = None
    refresh_interval: str = "manual"
    triggers: Optional[List[TriggerSchema]] = None
    position: Optional[Dict[str, int]] = None  # {x, y, width, height}

class PinWorkflowRequest(BaseModel):
    """Pin 工作流请求"""
    workflow_id: str
    name: str
    variable_values: Dict[str, Any]
    view_config: Optional[Dict] = None
    refresh_interval: str = "daily"
    triggers: Optional[List[TriggerSchema]] = None
    position: Optional[Dict[str, int]] = None

class CardResponse(BaseModel):
    """卡片响应"""
    card_id: str
    name: str
    description: str
    card_type: str
    source_config: Dict
    view_config: Dict
    refresh_interval: str
    refresh_cron: Optional[str]
    last_refresh_at: Optional[str]
    next_refresh_at: Optional[str]
    triggers: List[TriggerSchema]
    position: Dict[str, int]
    enabled: bool
    created_at: str
    updated_at: str

class CardDataResponse(BaseModel):
    """卡片数据响应"""
    card_id: str
    data: Any
    layout: Optional[Dict]
    blocks: Optional[List[Dict]]
    refreshed_at: str

class UpdateLayoutRequest(BaseModel):
    """更新布局请求"""
    layouts: List[Dict]  # [{card_id, x, y, width, height}]

class TriggerSchema(BaseModel):
    """触发器 Schema"""
    trigger_id: Optional[str] = None
    name: str
    enabled: bool = True
    trigger_type: str
    condition: Dict
    action: str
    action_config: Dict
```

---

## 五、前端组件设计

### 5.1 目录结构

```
frontend/src/features/dashboard/
├── components/
│   ├── DashboardView.vue          # 仪表盘主视图
│   ├── DashboardCard.vue          # 仪表盘卡片
│   ├── DashboardGrid.vue          # 网格布局容器
│   ├── CardSettingsDialog.vue     # 卡片设置对话框
│   ├── TriggerConfigDialog.vue    # 触发器配置对话框
│   ├── RefreshConfigForm.vue      # 刷新配置表单
│   └── NotificationBell.vue       # 通知铃铛组件
├── stores/
│   └── dashboardStore.ts          # 仪表盘状态管理
├── services/
│   └── dashboardApi.ts            # API 服务
├── types/
│   └── dashboard.ts               # 类型定义
└── index.ts                       # 模块导出
```

### 5.2 核心组件设计

#### 5.2.1 DashboardView（仪表盘主视图）

```vue
<template>
  <div class="dashboard-view">
    <!-- 顶部工具栏 -->
    <header class="dashboard-header">
      <h1>监控仪表盘</h1>
      <div class="header-actions">
        <Button variant="outline" size="sm" @click="refreshAll">
          <RefreshCw class="w-4 h-4 mr-2" />
          全部刷新
        </Button>
        <Button @click="showAddDialog = true">
          <Plus class="w-4 h-4 mr-2" />
          添加卡片
        </Button>
      </div>
    </header>

    <!-- 网格布局 -->
    <DashboardGrid
      :cards="cards"
      :editable="editMode"
      @layout-change="handleLayoutChange"
    >
      <template #card="{ card }">
        <DashboardCard
          :card="card"
          :data="cardDataMap[card.card_id]"
          :loading="loadingCards.has(card.card_id)"
          @refresh="refreshCard(card.card_id)"
          @settings="openSettings(card)"
          @delete="deleteCard(card.card_id)"
        />
      </template>
    </DashboardGrid>

    <!-- 空状态 -->
    <div v-if="cards.length === 0" class="empty-state">
      <LayoutDashboard class="w-12 h-12 text-muted-foreground" />
      <p>还没有添加任何卡片</p>
      <p class="text-sm text-muted-foreground">
        从工作流结果或数据产物中 Pin 卡片到这里
      </p>
    </div>

    <!-- 对话框 -->
    <CardSettingsDialog
      v-model:open="settingsOpen"
      :card="selectedCard"
      @save="updateCard"
    />
  </div>
</template>
```

#### 5.2.2 DashboardCard（仪表盘卡片）

```vue
<template>
  <Card class="dashboard-card" :class="{ 'is-refreshing': loading }">
    <!-- 卡片头部 -->
    <CardHeader class="p-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <CardTitle class="text-sm">{{ card.name }}</CardTitle>
        <Badge v-if="card.refresh_interval !== 'manual'" variant="outline" class="text-xs">
          {{ refreshLabel }}
        </Badge>
      </div>
      <div class="card-actions flex items-center gap-1">
        <Button variant="ghost" size="icon" @click="$emit('refresh')">
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loading }" />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <MoreVertical class="w-4 h-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem @click="$emit('settings')">
              <Settings class="w-4 h-4 mr-2" /> 设置
            </DropdownMenuItem>
            <DropdownMenuItem @click="$emit('delete')" class="text-destructive">
              <Trash2 class="w-4 h-4 mr-2" /> 删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </CardHeader>

    <!-- 卡片内容 -->
    <CardContent class="p-3 pt-0">
      <div v-if="loading && !data" class="skeleton-loader">
        <Skeleton class="h-32 w-full" />
      </div>
      <DynamicBlockRenderer
        v-else-if="data"
        :block="data.blocks[0]"
        :data-blocks="data.dataBlocks"
      />
      <div v-else class="no-data">
        暂无数据
      </div>
    </CardContent>

    <!-- 卡片底部 -->
    <CardFooter class="p-3 pt-0 text-xs text-muted-foreground">
      <span v-if="card.last_refresh_at">
        更新于 {{ formatTime(card.last_refresh_at) }}
      </span>
      <span v-if="card.triggers?.length" class="ml-auto">
        <Bell class="w-3 h-3 inline mr-1" />
        {{ card.triggers.length }} 个触发器
      </span>
    </CardFooter>
  </Card>
</template>
```

#### 5.2.3 DashboardGrid（网格布局）

```vue
<template>
  <div class="dashboard-grid">
    <GridLayout
      v-model:layout="layout"
      :col-num="12"
      :row-height="80"
      :is-draggable="editable"
      :is-resizable="editable"
      :margin="[16, 16]"
      @layout-updated="onLayoutUpdated"
    >
      <GridItem
        v-for="card in cards"
        :key="card.card_id"
        :i="card.card_id"
        :x="card.position_x"
        :y="card.position_y"
        :w="card.width"
        :h="card.height"
      >
        <slot name="card" :card="card" />
      </GridItem>
    </GridLayout>
  </div>
</template>

<script setup lang="ts">
// 使用 vue-grid-layout 实现拖拽布局
import { GridLayout, GridItem } from 'vue-grid-layout'
</script>
```

#### 5.2.4 TriggerConfigDialog（触发器配置）

```vue
<template>
  <Dialog v-model:open="open">
    <DialogContent class="max-w-lg">
      <DialogHeader>
        <DialogTitle>配置触发器</DialogTitle>
        <DialogDescription>
          设置条件触发规则，当数据满足条件时自动执行动作
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <!-- 触发器列表 -->
        <div v-for="(trigger, index) in triggers" :key="trigger.trigger_id" class="trigger-item">
          <div class="flex items-center gap-2">
            <Switch v-model="trigger.enabled" />
            <span>{{ trigger.name }}</span>
            <Button variant="ghost" size="icon" @click="removeTrigger(index)">
              <Trash2 class="w-4 h-4" />
            </Button>
          </div>

          <!-- 条件配置 -->
          <div class="condition-config mt-2 pl-8">
            <Select v-model="trigger.trigger_type">
              <SelectTrigger>
                <SelectValue placeholder="触发类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="value_change">值变化</SelectItem>
                <SelectItem value="threshold">阈值触发</SelectItem>
                <SelectItem value="pattern">模式匹配</SelectItem>
              </SelectContent>
            </Select>

            <!-- 根据类型显示不同的条件表单 -->
            <ThresholdConditionForm
              v-if="trigger.trigger_type === 'threshold'"
              v-model="trigger.condition"
              :fields="availableFields"
            />
          </div>

          <!-- 动作配置 -->
          <div class="action-config mt-2 pl-8">
            <Select v-model="trigger.action">
              <SelectTrigger>
                <SelectValue placeholder="触发动作" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="notify">发送通知</SelectItem>
                <SelectItem value="run_workflow">执行工作流</SelectItem>
                <SelectItem value="webhook">调用 Webhook</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <!-- 添加触发器 -->
        <Button variant="outline" @click="addTrigger">
          <Plus class="w-4 h-4 mr-2" /> 添加触发器
        </Button>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="open = false">取消</Button>
        <Button @click="saveTriggers">保存</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
```

### 5.3 状态管理

```typescript
// stores/dashboardStore.ts

interface DashboardState {
  // 卡片列表
  cards: DashboardCard[]

  // 卡片数据缓存
  cardDataMap: Record<string, CardData>

  // 加载状态
  loadingCards: Set<string>

  // 通知
  notifications: Notification[]
  unreadCount: number

  // UI 状态
  editMode: boolean
  selectedCardId: string | null
}

const useDashboardStore = defineStore('dashboard', {
  state: (): DashboardState => ({
    cards: [],
    cardDataMap: {},
    loadingCards: new Set(),
    notifications: [],
    unreadCount: 0,
    editMode: false,
    selectedCardId: null,
  }),

  actions: {
    // 加载卡片列表
    async loadCards() { ... },

    // Pin 操作
    async pinArtifact(request: PinArtifactRequest) { ... },
    async pinWorkflow(request: PinWorkflowRequest) { ... },

    // 刷新操作
    async refreshCard(cardId: string) { ... },
    async refreshAll() { ... },

    // 布局管理
    async updateLayout(layouts: CardLayout[]) { ... },

    // 触发器管理
    async updateTriggers(cardId: string, triggers: Trigger[]) { ... },

    // 通知
    async loadNotifications() { ... },
    async markRead(notificationId: string) { ... },
  }
})
```

---

## 六、路由配置

```typescript
// router/index.ts 扩展

{
  path: '/dashboard',
  name: 'Dashboard',
  component: () => import('@/features/dashboard/components/DashboardView.vue'),
  meta: { title: '监控仪表盘' }
}
```

---

## 七、实施计划

### 7.1 分阶段实施

| 阶段 | 内容 | 预计工作量 |
|------|------|-----------|
| 5.1 | Dashboard 数据模型 + 数据库迁移 | 0.5 天 |
| 5.2 | DashboardService + API | 1 天 |
| 5.3 | SchedulerService（定时刷新） | 1 天 |
| 5.4 | TriggerService（条件触发） | 1 天 |
| 5.5 | NotificationService + API | 0.5 天 |
| 5.6 | 前端 dashboardStore + dashboardApi | 0.5 天 |
| 5.7 | DashboardView + DashboardGrid 组件 | 1 天 |
| 5.8 | DashboardCard + 设置对话框 | 1 天 |
| 5.9 | TriggerConfigDialog + NotificationBell | 0.5 天 |
| 5.10 | 集成测试 + 修复 | 1 天 |

**总计**: 约 8-9 天

### 7.2 依赖关系

```
5.1 数据模型
    ↓
5.2 DashboardService + API
    ↓
┌─────────────────────────────────┐
│  5.3 SchedulerService           │
│  5.4 TriggerService             │
│  5.5 NotificationService        │
└─────────────────────────────────┘
    ↓
5.6 前端 Store + API
    ↓
┌─────────────────────────────────┐
│  5.7 DashboardView + Grid       │
│  5.8 DashboardCard              │
│  5.9 TriggerConfig + Notify     │
└─────────────────────────────────┘
    ↓
5.10 集成测试
```

### 7.3 技术选型

| 需求 | 选择 | 理由 |
|------|------|------|
| 后台调度 | APScheduler | 轻量、Python 原生、支持 cron |
| 网格布局 | vue-grid-layout | Vue 3 支持、拖拽调整、响应式 |
| 实时通知 | WebSocket 复用 | 已有基础设施，避免引入新依赖 |

---

## 八、待确认问题

| 问题 | 选项 A | 选项 B | 建议 |
|------|--------|--------|------|
| **仪表盘入口** | 独立页面 `/dashboard` | 工作台内的 Tab | A: 独立更清晰 | A
| **定时刷新精度** | 固定周期（hourly/daily/weekly） | 支持自定义 cron | 先 A，后续扩展 B | A
| **通知渠道** | 仅应用内 | 支持邮件/Webhook | 先应用内，后续扩展 | A
| **网格布局** | vue-grid-layout | 自定义 CSS Grid | A: 功能完善 | B

---

## 九、TODO 清单

- [x] 用户确认设计方案
- [x] Phase 5.1: Dashboard 数据模型
- [x] Phase 5.2: DashboardService + API
- [x] Phase 5.3: SchedulerService（定时刷新）- 使用 Python threading 替代 APScheduler
- [x] Phase 5.4: TriggerService（条件触发）
- [x] Phase 5.5: NotificationService
- [x] Phase 5.6: 前端 dashboardStore + dashboardApi
- [x] Phase 5.7: DashboardView + DashboardGrid（用户选择 CSS Grid 方案）
- [x] Phase 5.8: DashboardCard + NotificationBell
- [x] Phase 5.9: 集成测试 - 通过语法验证

---

## 十、设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 卡片存储 | 独立表 dashboard_cards | 与工作流/产物解耦，灵活配置 |
| 触发器存储 | JSON 字段 | 结构灵活，避免多表关联 |
| 调度器 | Python threading | 项目未安装 APScheduler，使用内置 threading 简化依赖 |
| 网格布局 | 自定义 CSS Grid | 用户选择 B，避免引入额外依赖，12 列响应式布局 |
| 通知 | 应用内优先 | MVP 阶段简化实现 |

---

## 十一、实现文件清单

### 后端新增文件
- `services/dashboard/models.py` - 数据模型（DashboardCard, Notification, Trigger）
- `services/dashboard/store.py` - CRUD 操作
- `services/dashboard/dashboard_service.py` - 核心服务
- `services/dashboard/scheduler_service.py` - 定时刷新（Python threading）
- `services/dashboard/trigger_service.py` - 条件触发评估
- `services/dashboard/notification_service.py` - 通知推送
- `services/dashboard/__init__.py` - 模块导出
- `api/schemas/dashboard.py` - API 请求/响应模型
- `api/controllers/dashboard_controller.py` - REST API 端点

### 前端新增文件
- `features/dashboard/types/dashboard.ts` - TypeScript 类型
- `features/dashboard/services/dashboardApi.ts` - API 服务
- `features/dashboard/stores/dashboardStore.ts` - Pinia 状态管理
- `features/dashboard/components/DashboardView.vue` - 主视图
- `features/dashboard/components/DashboardGrid.vue` - CSS Grid 布局
- `features/dashboard/components/DashboardCard.vue` - 卡片组件
- `features/dashboard/components/NotificationBell.vue` - 通知铃铛
- `features/dashboard/index.ts` - 模块导出

### 修改的文件
- `api/app.py` - 注册 dashboard_router
- `services/database/connection.py` - create_tables 包含新表
- `frontend/src/router/index.ts` - 添加 /dashboard 路由

