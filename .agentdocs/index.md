# 项目文档索引

## 项目概述
智能RSS聚合系统 - 基于RAG + LLM的自然语言到API调用转换系统

## 架构文档
- `../ARCHITECTURE.md` - 项目整体分层架构说明，修改任何模块时必读
- `../README.md` - 项目使用说明和快速开始

## 技术架构文档
- `../docs/intelligent-data-panel-design.md` - 智能数据面板后端设计方案（数据→组件→布局全流程）
- `../docs/frontend-electron-shadcn-design.md` - 前端 Electron + Shadcn UI 实现指南（组件能力、布局渲染、状态管理、交互规范）
- `../docs/backend-intelligent-panel-overview.md` - 面向前端的后端面板联调指南（数据结构、字段语义、布局约束）
- `panel-nested-components-design.md` - **面板组件嵌套架构设计**（支持 Card、Tabs 等容器组件嵌套子组件）

### 前端架构（必读）
- rontend-design-guidelines.md - 前端界面/组件设计规范（布局、shadcn 使用、MediaCardGrid 等，2025-11 已补充 `layout_size` 语义＆ Electron 调试/打包说明）
- `frontend-architecture.md` - 前端架构与技术约束，修改任何前端代码时必读
  - **技术栈铁律**：Vue 3 + shadcn-vue + ECharts（不是 React！）
  - 组件开发规范（Composition API、TypeScript、数据契约一致性）
  - shadcn-vue 使用规范（安装配置、主题、组件使用）
  - ECharts 集成规范（按需引入、响应式调整）
  - 禁止事项（React 语法、其他 UI 库、其他图表库）
  - **已实现组件清单**（8个组件全部完成）

- `frontend-panel-components.md` - **前端面板组件实现指南**（开发面板组件时必读）
  - 8个已实现组件的详细实现说明（ListPanel、StatisticCard、LineChart、BarChart、PieChart、Table、ImageGallery、FallbackRichText）
  - 每个组件的核心功能、关键代码、配置项、数据契约
  - 通用模式（Props接口、数据获取、字段映射、响应式调整）
  - 组件注册机制（DynamicBlockRenderer、ComponentManifest）

### 后端架构（必读）
- `backend-architecture.md` - 后端（Integration/Service/Controller层）架构设计与技术约束，修改任何后端代码时必读
  - Integration层可复用组件（DataExecutor、CacheService）使用规范
  - URL编码安全最佳实践
  - 测试策略（单元测试与真实服务隔离）
  - 同步/异步策略
  - FeedItem通用数据模型（"万物皆可RSS"）

### RAG系统
- `../rag_system/` - 向量检索模块，包含embedding模型、向量存储、检索管道

### 查询处理
- `../query_processor/` - 查询解析模块，包含LLM客户端、Prompt构建器、结果解析器

### 编排层
- `../orchestrator/` - 流程编排模块，协调RAG和LLM完成端到端处理

## 当前任务文档
- `workflow/251031-rss-aggregation-layered-architecture.md` - 实现RSS聚合系统分层架构
- `workflow/251031-rss-aggregation-architecture-refine.md` - RSS聚合架构落地改进方案，补充本地依赖、同步异步策略与接口设计
- `workflow/251101-intelligent-panel-backend.md` - 智能数据面板后端整改与质量保障方案

## 技术使用指南
- `service-layer-usage.md` - Service层完整使用指南，包含所有服务的创建、使用和扩展方法
- `adapter-codegen-prompt.md` - 路由适配器代码生成提示词模板，用于根据RSSHub TypeScript路由文件自动生成Python adapter代码

## 全局重要记忆

### 项目架构
- 项目采用单体应用分层架构，不使用微服务
- 分层结构：Controller → Service → Integration（Data/Cache）
- Integration层和Service层保持同步实现，Controller层通过线程池调度

### 代码规范
- 所有代码注释和文档使用中文（UTF-8编码）
- 严格遵循CLAUDE.md中的代码质量要求
- 单个代码文件不超过1000行
- 优先复用现有代码，避免重复造轮子

### Integration层核心组件（必须复用）
- **DataExecutor** - 所有RSSHub数据获取统一走DataExecutor，不允许直接拼接URL
- **CacheService** - 所有数据缓存统一走CacheService（全局单例），不允许使用functools.lru_cache
- **URL编码安全** - RSSHub路径包含特殊字符（如`#步行街主干道`）会被DataExecutor正确编码，不会截断

### Service层核心组件（必须复用）
- **IntentService** - 意图识别服务（全局单例），判断data_query/chitchat
- **DataQueryService** - 数据查询服务，整合RAGInAction+DataExecutor+双层缓存
- **ChatService** - 统一对话入口，自动意图路由，所有对话请求必须走ChatService
- **双层缓存** - RAG结果缓存（避免重复RAG）+ RSS数据缓存（避免重复HTTP请求）

**重要记忆**:
- 所有业务调用必须通过Service层，禁止直接调用Integration层组件
- IntentService和CacheService使用全局单例，DataQueryService使用上下文管理器
- ChatService默认为调用方管理DataQueryService生命周期，只有在`manage_data_service=True`时才会自动关闭
- ChatResponse.to_dict()用于API响应序列化，包含丰富的元数据信息
- FastAPI 层通过 `CHAT_SERVICE_MODE` 控制服务初始化（auto/mock/production），测试环境推荐设为 `mock`

### 配置管理
- RSSHub配置统一使用`RSSHubSettings`（`query_processor/config.py`）
- `PathSettings.base_url`已废弃，不要使用
- 所有Python依赖在根目录`requirements.txt`统一维护

### 测试策略
- 真实RSSHub测试必须隔离（环境变量`RSSHUB_TEST_REAL=1`或健康检查跳过）
- CI和离线环境默认只运行纯单元测试
- pytest为必需依赖，已在requirements.txt启用

### 数据模型
- RSSHub支持"万物皆可RSS"（视频/社交/论坛/商品等），使用FeedItem通用模型
- 不要将FeedItem改名为Article或Post
- `media_type`无媒体时为`None`，不是空字符串

### 前端面板组件
- **已实现 8 个组件**：ListPanelBlock、StatisticCardBlock、LineChartBlock、BarChartBlock、PieChartBlock、TableBlock、ImageGalleryBlock、FallbackRichTextBlock
- **技术栈铁律**：所有组件必须使用 shadcn-vue + ECharts，禁止使用 React 语法或其他 UI 库
- **组件路径**：`frontend/src/features/panel/components/blocks/`
- **组件注册**：通过 `DynamicBlockRenderer.vue` 动态路由，通过 `componentManifest.ts` 声明能力
- **数据契约**：前端 TypeScript 类型必须与后端 Pydantic 模型一致（定义在 `docs/backend-panel-view-models.md`）
- **嵌套支持**：所有组件支持 `UIBlock.children` 嵌套架构
- **响应式图表**：ECharts 组件使用 ResizeObserver 实现响应式调整
- **依赖状态**：shadcn-vue（8个组件）、ECharts、TanStack Table、marked 均已安装
- **配置预设系统**：`services/panel/adapters/config_presets.py` 提供标准化尺寸预设（compact/normal/large/full），让 AI planner 灵活控制组件大小
- **ListPanel 配置**：支持 compact 模式、max_items、show_description、show_metadata、show_categories 等配置项
- **数据追加模式**：
  - 前端 `panelStore.ts` 正确处理后端返回的 `mode` 字段（append/replace/insert），支持多轮对话时数据追加显示
  - 后端 `layout_engine.py` 使用 UUID 生成唯一 node id（`row-{batch_id}-{index}`），确保 append 模式下布局节点不重复
  - 前端包含详细的 console.log 调试日志，可查看数据合并过程
