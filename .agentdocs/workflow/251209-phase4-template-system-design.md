# Phase 4: 模板系统设计方案

**创建日期**: 2025-12-09
**状态**: ✅ 已完成
**目标**: 实现工作流模板化，支持模板创建、分享、市场发现

---

## 一、现状分析

### 1.1 现有可复用代码

| 模块 | 位置 | 复用策略 |
|------|------|---------|
| **Workflow 模型** | `services/workflow/models.py` | ✅ 已有 `is_template`、`template_source_id`、`variables_json`、`tags_json` |
| **WorkflowStore** | `services/workflow/store.py` | ✅ 已有 `list_workflows(is_template=True)` 查询 |
| **Variable 模型** | `services/workflow/models.py` | ✅ 支持 string/number/boolean/datasource/list 类型 |
| **WorkflowPanel** | `features/workspace/components/` | 🔄 扩展支持模板操作按钮 |
| **workspaceStore** | `features/workspace/stores/` | 🔄 扩展支持模板市场状态 |
| **workspaceApi** | `features/workspace/services/` | 🔄 扩展模板相关 API |

### 1.2 现有 Workflow 模型字段

```python
class Workflow(SQLModel, table=True):
    # 基础字段（已有）
    workflow_id: str
    name: str
    description: str
    status: str  # draft | ready | template

    # 模板字段（已有）
    is_template: bool = False
    template_source_id: Optional[str] = None  # 来源模板 ID

    # 变量与标签（已有）
    variables_json: str  # Dict[name, Variable]
    tags_json: str  # List[str]
```

### 1.3 需要扩展的内容

1. **模板元数据**：分类、作者、使用统计、预览图
2. **模板服务**：创建/实例化/导出/导入
3. **模板市场 API**：列表/搜索/统计
4. **前端组件**：模板市场页面、模板卡片、变量表单

---

## 二、数据模型设计

### 2.1 扩展 Workflow 模型（模板元数据）

```python
class Workflow(SQLModel, table=True):
    # ... 现有字段 ...

    # 模板元数据（新增）
    category: Optional[str] = SQLField(default=None, description="模板分类")
    author: Optional[str] = SQLField(default=None, description="模板作者")
    usage_count: int = SQLField(default=0, description="使用次数")
    preview_image: Optional[str] = SQLField(default=None, description="预览图 URL")
    version: str = SQLField(default="1.0.0", description="模板版本")
```

### 2.2 模板分类枚举

```python
class TemplateCategory(str, Enum):
    """模板分类"""
    DATA_ANALYSIS = "data_analysis"     # 数据分析
    CONTENT_RESEARCH = "content_research"  # 内容研究
    COMPETITIVE = "competitive"         # 竞品分析
    SOCIAL_MONITORING = "social_monitoring"  # 社交监控
    REPORT_GENERATION = "report_generation"  # 报告生成
    CUSTOM = "custom"                   # 自定义
```

### 2.3 模板导出格式

```typescript
interface WorkflowTemplate {
  // 元信息
  meta: {
    version: string           // 模板格式版本
    exported_at: string       // 导出时间
    source_workflow_id: string
  }

  // 模板内容
  template: {
    name: string
    description: string
    category: string
    tags: string[]

    // 步骤定义
    steps: WorkflowStep[]

    // 变量定义（模板化的核心）
    variables: Record<string, Variable>
  }

  // 预设值（可选）
  presets?: {
    name: string
    variable_values: Record<string, unknown>
  }[]
}
```

---

## 三、服务层设计

### 3.1 TemplateService

**文件**: `services/workflow/template_service.py`

```python
class TemplateService:
    """模板服务 - 负责模板的创建、实例化、导出导入"""

    def __init__(self, workflow_store: WorkflowStore):
        self._store = workflow_store

    def create_template_from_workflow(
        self,
        workflow_id: str,
        category: str,
        author: str = "anonymous",
        preview_image: Optional[str] = None
    ) -> Workflow:
        """从现有工作流创建模板"""
        pass

    def instantiate_template(
        self,
        template_id: str,
        variable_values: Dict[str, Any],
        new_name: Optional[str] = None
    ) -> Workflow:
        """从模板创建工作流实例"""
        pass

    def export_template(self, template_id: str) -> WorkflowTemplate:
        """导出模板为 JSON"""
        pass

    def import_template(
        self,
        template_data: WorkflowTemplate,
        author: str = "imported"
    ) -> Workflow:
        """从 JSON 导入模板"""
        pass

    def validate_variable_values(
        self,
        template_id: str,
        values: Dict[str, Any]
    ) -> List[str]:
        """校验变量值是否满足模板要求"""
        pass

    def increment_usage(self, template_id: str) -> None:
        """增加使用计数"""
        pass
```

### 3.2 模板市场查询扩展

在 `WorkflowStore` 中扩展：

```python
def list_templates(
    self,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    search: Optional[str] = None,
    sort_by: str = "usage_count",  # usage_count | created_at | name
    limit: int = 20,
    offset: int = 0
) -> Tuple[List[Workflow], int]:
    """
    查询模板市场

    Returns:
        (模板列表, 总数)
    """
    pass

def get_template_stats(self) -> Dict[str, int]:
    """
    获取模板统计

    Returns:
        {
            "total": 总数,
            "by_category": { "data_analysis": 5, ... }
        }
    """
    pass
```

---

## 四、API 设计

### 4.1 模板 API 端点

```python
# api/controllers/template_controller.py

# 模板市场
GET    /api/v1/templates                  # 模板列表（支持分类、搜索、分页）
GET    /api/v1/templates/{template_id}    # 模板详情
GET    /api/v1/templates/categories       # 分类列表及统计
GET    /api/v1/templates/stats            # 模板市场统计

# 模板操作
POST   /api/v1/templates                  # 从工作流创建模板
POST   /api/v1/templates/{id}/instantiate # 从模板创建工作流
POST   /api/v1/templates/import           # 导入模板
GET    /api/v1/templates/{id}/export      # 导出模板

# 变量校验
POST   /api/v1/templates/{id}/validate    # 校验变量值
```

### 4.2 请求/响应模型

```python
# api/schemas/template.py

class TemplateListQuery(BaseModel):
    """模板列表查询参数"""
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    search: Optional[str] = None
    sort_by: str = "usage_count"
    limit: int = 20
    offset: int = 0

class TemplateResponse(BaseModel):
    """模板响应"""
    template_id: str
    name: str
    description: str
    category: str
    author: str
    tags: List[str]
    usage_count: int
    preview_image: Optional[str]
    version: str

    # 变量定义
    variables: Dict[str, VariableSchema]

    # 步骤概要
    step_count: int
    step_types: List[str]  # ["fetch", "process", "analyze"]

    created_at: str
    updated_at: str

class CreateTemplateRequest(BaseModel):
    """创建模板请求"""
    workflow_id: str
    category: str
    author: str = "anonymous"
    preview_image: Optional[str] = None

class InstantiateRequest(BaseModel):
    """实例化模板请求"""
    variable_values: Dict[str, Any]
    new_name: Optional[str] = None

class TemplateListResponse(BaseModel):
    """模板列表响应"""
    templates: List[TemplateResponse]
    total: int
    categories: Dict[str, int]  # 分类统计
```

---

## 五、前端组件设计

### 5.1 目录结构扩展

```
frontend/src/features/workspace/
├── components/
│   ├── template/                    # 新增：模板相关组件
│   │   ├── TemplateMarket.vue       # 模板市场页面
│   │   ├── TemplateCard.vue         # 模板卡片
│   │   ├── TemplateDetail.vue       # 模板详情弹窗
│   │   ├── VariableForm.vue         # 变量填写表单
│   │   ├── SaveAsTemplateDialog.vue # 保存为模板对话框
│   │   └── TemplateImportDialog.vue # 导入模板对话框
│   └── workflow/
│       └── WorkflowPanel.vue        # 扩展：添加模板操作按钮
├── stores/
│   └── templateStore.ts             # 新增：模板市场状态管理
└── services/
    └── templateApi.ts               # 新增：模板 API
```

### 5.2 核心组件设计

#### 5.2.1 TemplateMarket（模板市场）

```vue
<template>
  <div class="template-market">
    <!-- 顶部筛选栏 -->
    <header class="market-header">
      <div class="search-box">
        <Search class="w-4 h-4" />
        <Input v-model="searchQuery" placeholder="搜索模板..." />
      </div>

      <div class="category-tabs">
        <Button
          v-for="cat in categories"
          :key="cat.value"
          :variant="selectedCategory === cat.value ? 'default' : 'ghost'"
          @click="selectedCategory = cat.value"
        >
          {{ cat.label }}
          <Badge variant="secondary">{{ cat.count }}</Badge>
        </Button>
      </div>
    </header>

    <!-- 模板网格 -->
    <div class="template-grid">
      <TemplateCard
        v-for="template in templates"
        :key="template.template_id"
        :template="template"
        @use="openInstantiateDialog(template)"
        @view="openDetailDialog(template)"
      />
    </div>

    <!-- 分页 -->
    <Pagination :total="total" v-model:page="page" />

    <!-- 对话框 -->
    <TemplateDetail
      v-model:open="detailOpen"
      :template="selectedTemplate"
      @use="openInstantiateDialog"
    />

    <VariableFormDialog
      v-model:open="instantiateOpen"
      :template="selectedTemplate"
      @submit="instantiateTemplate"
    />
  </div>
</template>
```

#### 5.2.2 TemplateCard（模板卡片）

```vue
<template>
  <Card class="template-card" @click="$emit('view', template)">
    <!-- 预览图 -->
    <div class="card-preview">
      <img v-if="template.preview_image" :src="template.preview_image" />
      <div v-else class="preview-placeholder">
        <FileText class="w-8 h-8" />
      </div>
    </div>

    <!-- 内容 -->
    <CardHeader class="p-3">
      <div class="flex items-center justify-between">
        <CardTitle class="text-sm">{{ template.name }}</CardTitle>
        <Badge variant="outline">{{ template.category }}</Badge>
      </div>
      <CardDescription class="text-xs line-clamp-2">
        {{ template.description }}
      </CardDescription>
    </CardHeader>

    <!-- 底部信息 -->
    <CardFooter class="p-3 pt-0 flex justify-between">
      <div class="text-xs text-muted-foreground">
        <span>{{ template.step_count }} 步骤</span>
        <span class="mx-1">·</span>
        <span>{{ template.usage_count }} 次使用</span>
      </div>
      <Button size="xs" @click.stop="$emit('use', template)">
        使用
      </Button>
    </CardFooter>
  </Card>
</template>
```

#### 5.2.3 VariableForm（变量填写表单）

```vue
<template>
  <div class="variable-form">
    <div
      v-for="(variable, name) in variables"
      :key="name"
      class="form-field"
    >
      <Label :for="name">
        {{ variable.description || name }}
        <span v-if="variable.required" class="text-destructive">*</span>
      </Label>

      <!-- 字符串输入 -->
      <Input
        v-if="variable.var_type === 'string'"
        :id="name"
        v-model="values[name]"
        :placeholder="variable.default"
      />

      <!-- 数字输入 -->
      <Input
        v-else-if="variable.var_type === 'number'"
        :id="name"
        type="number"
        v-model.number="values[name]"
      />

      <!-- 布尔开关 -->
      <Switch
        v-else-if="variable.var_type === 'boolean'"
        :id="name"
        v-model="values[name]"
      />

      <!-- 数据源选择 -->
      <DatasourceSelector
        v-else-if="variable.var_type === 'datasource'"
        :id="name"
        v-model="values[name]"
      />

      <!-- 列表/枚举选择 -->
      <Select
        v-else-if="variable.enum_values"
        :id="name"
        v-model="values[name]"
      >
        <SelectTrigger>
          <SelectValue :placeholder="`选择 ${name}`" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem
            v-for="opt in variable.enum_values"
            :key="opt"
            :value="opt"
          >
            {{ opt }}
          </SelectItem>
        </SelectContent>
      </Select>
    </div>
  </div>
</template>
```

#### 5.2.4 SaveAsTemplateDialog（保存为模板）

```vue
<template>
  <Dialog v-model:open="open">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>保存为模板</DialogTitle>
        <DialogDescription>
          将当前工作流保存为可复用的模板
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <!-- 分类选择 -->
        <div class="form-field">
          <Label>分类</Label>
          <Select v-model="category">
            <SelectTrigger>
              <SelectValue placeholder="选择分类" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="data_analysis">数据分析</SelectItem>
              <SelectItem value="content_research">内容研究</SelectItem>
              <SelectItem value="competitive">竞品分析</SelectItem>
              <SelectItem value="social_monitoring">社交监控</SelectItem>
              <SelectItem value="report_generation">报告生成</SelectItem>
              <SelectItem value="custom">自定义</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <!-- 作者 -->
        <div class="form-field">
          <Label>作者</Label>
          <Input v-model="author" placeholder="你的名字" />
        </div>

        <!-- 变量提取预览 -->
        <div class="variable-preview">
          <Label>已识别的变量</Label>
          <div class="text-sm text-muted-foreground">
            以下参数将作为模板变量，使用时需要填写：
          </div>
          <div class="mt-2 space-y-1">
            <div
              v-for="(variable, name) in extractedVariables"
              :key="name"
              class="flex items-center gap-2 text-sm"
            >
              <Badge variant="outline">{{ variable.var_type }}</Badge>
              <span>{{ name }}</span>
              <span class="text-muted-foreground">
                {{ variable.description }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="open = false">取消</Button>
        <Button @click="saveTemplate">保存模板</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
```

### 5.3 状态管理扩展

```typescript
// stores/templateStore.ts

interface TemplateState {
  // 模板市场
  templates: TemplateResponse[]
  total: number
  categories: Record<string, number>

  // 筛选条件
  filters: {
    category: string | null
    search: string
    sortBy: 'usage_count' | 'created_at' | 'name'
  }

  // 分页
  page: number
  pageSize: number

  // UI 状态
  loading: boolean
  error: string | null

  // 当前操作
  selectedTemplate: TemplateResponse | null
}

// Actions
- loadTemplates(): 加载模板列表
- loadCategories(): 加载分类统计
- setFilter(filter): 设置筛选条件
- createTemplate(request): 创建模板
- instantiateTemplate(templateId, values): 实例化模板
- importTemplate(file): 导入模板
- exportTemplate(templateId): 导出模板
```

---

## 六、路由配置

```typescript
// router/index.ts 扩展

{
  path: '/workspace/templates',
  name: 'template-market',
  component: () => import('@/features/workspace/components/template/TemplateMarket.vue'),
  meta: { title: '模板市场' }
}
```

---

## 七、实施计划

### 7.1 分阶段实施

| 阶段 | 内容 | 预计工作量 |
|------|------|-----------|
| 4.1 | 扩展 Workflow 模型（模板元数据字段） | 0.5 天 |
| 4.2 | 实现 TemplateService | 1 天 |
| 4.3 | 实现 Template API | 0.5 天 |
| 4.4 | 前端 templateStore + templateApi | 0.5 天 |
| 4.5 | TemplateMarket + TemplateCard 组件 | 1 天 |
| 4.6 | VariableForm + 实例化流程 | 1 天 |
| 4.7 | SaveAsTemplate + 导出导入 | 0.5 天 |
| 4.8 | 集成测试 + 修复 | 0.5 天 |

**总计**: 约 5-6 天

### 7.2 依赖关系

```
4.1 Workflow 模型扩展
    ↓
4.2 TemplateService
    ↓
4.3 Template API
    ↓
┌───────────────────────┐
│  4.4 templateStore    │
│  4.5 TemplateMarket   │
│  4.6 VariableForm     │
│  4.7 SaveAsTemplate   │
└───────────────────────┘
    ↓
4.8 集成测试
```

---

## 八、待确认问题

| 问题 | 选项 A | 选项 B | 建议 |
|------|--------|--------|------|
| **模板市场入口** | 独立页面 `/workspace/templates` | 工作流面板内的 Tab | A: 独立更清晰 |
| **模板预览图** | 自动截图（复杂） | 手动上传/默认图标 | B: 先简单实现 |
| **变量默认值** | 从原工作流参数提取 | 用户手动定义 | A: 更智能 |
| **模板版本管理** | 支持多版本 | 单版本（覆盖更新） | B: 先简单 |

---

## 九、TODO 清单

- [x] 用户确认设计方案 (2025-12-09)
- [x] Phase 4.1: 扩展 Workflow 模型 (2025-12-09)
- [x] Phase 4.2: 实现 TemplateService (2025-12-09)
- [x] Phase 4.3: 实现 Template API (2025-12-09)
- [x] Phase 4.4: 前端 templateStore + templateApi (2025-12-09)
- [x] Phase 4.5: TemplateMarket + TemplateCard 组件 (2025-12-09)
- [x] Phase 4.6: VariableForm + 实例化流程 (2025-12-09)
- [x] Phase 4.7: SaveAsTemplate + 导出导入 (2025-12-09)
- [x] Phase 4.8: 集成测试 (2025-12-09)

---

## 十、设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 模板存储 | 复用 Workflow 表 + is_template 标记 | 已有基础，避免新建表 |
| 变量系统 | 复用现有 Variable 模型 | 已支持多种类型，功能完善 |
| 导出格式 | JSON | 通用、易于版本控制 |
| 分类体系 | 预定义枚举 + custom | 平衡规范性和灵活性 |

---

## 十一、实施记录

### 后端实现

| 文件 | 说明 |
|------|------|
| `services/workflow/models.py` | 扩展 Workflow 模型，新增 TemplateCategory 枚举和模板元数据字段 |
| `services/workflow/store.py` | 扩展 WorkflowStore，新增模板市场查询方法 |
| `services/workflow/template_service.py` | 新增 TemplateService，负责模板创建/实例化/导出/导入 |
| `services/workflow/__init__.py` | 更新模块导出 |
| `api/schemas/template.py` | 新增模板 API Schemas |
| `api/controllers/template_controller.py` | 新增模板 API 端点 |
| `api/app.py` | 注册 template_router |

### 前端实现

| 文件 | 说明 |
|------|------|
| `features/workspace/types/template.ts` | 模板类型定义 |
| `features/workspace/services/templateApi.ts` | 模板 API 服务 |
| `features/workspace/stores/templateStore.ts` | 模板 Pinia Store |
| `features/workspace/components/template/TemplateCard.vue` | 模板卡片组件 |
| `features/workspace/components/template/TemplateMarket.vue` | 模板市场页面 |
| `features/workspace/components/template/TemplateDetail.vue` | 模板详情弹窗 |
| `features/workspace/components/template/VariableFormDialog.vue` | 变量填写对话框 |
| `features/workspace/components/template/TemplateImportDialog.vue` | 导入模板对话框 |
| `features/workspace/components/template/SaveAsTemplateDialog.vue` | 保存为模板对话框 |
| `features/workspace/components/template/index.ts` | 模板组件导出 |
| `features/workspace/index.ts` | 更新模块导出 |
| `router/index.ts` | 添加模板市场路由 `/workspace/templates` |

### API 端点

```
GET    /api/v1/templates              - 模板列表（支持分类、搜索、分页）
GET    /api/v1/templates/categories   - 分类列表及统计
GET    /api/v1/templates/stats        - 模板市场统计
GET    /api/v1/templates/{id}         - 模板详情
POST   /api/v1/templates              - 创建模板
POST   /api/v1/templates/{id}/instantiate - 实例化模板
POST   /api/v1/templates/{id}/validate    - 校验变量值
GET    /api/v1/templates/{id}/export      - 导出模板
POST   /api/v1/templates/import           - 导入模板
```
