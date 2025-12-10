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
- `../docs/langgraph-agents-design.md` - LangGraph 多代理研究工作流（V2 动态自适应方案）
- `../docs/langgraph-agents-frontend-design.md` - LangGraph 动态研究在 Desktop Intelligence Studio 中的前端实时呈现方案
- `langgraph-v4.4-architecture-design.md` - **LangGraph V4.4 架构设计方案 v1.0（2025-01-13 待评审）**
  - **状态**: 设计方案（待评审会议确认是否实施）
  - **核心改进**: V4.0（显式依赖解析）+ V4.1（扇出防爆）+ V4.2（工具发现，可选）+ V4.4（前置语义 + GraphRenderer）
  - **集成方案**: 与现有 V2 架构的渐进式集成路径（5个阶段，5.5-7.5天）
  - **关键决策**: 是否实施 V4.2 工具发现（建议：暂缓）
- `langgraph-v5.0-flexible-agent-architecture.md` - **LangGraph V5.0 灵活代理架构设计方案（2025-01-16 待评审）** ✨NEW
  - **状态**: 设计方案（解决 Agent 能力被单一工具限制的根本问题）
  - **核心问题**: RAG+RSSHub 应该只是工具之一，而非 Agent 的全部能力
  - **核心改进**:
    - 工具库扩展：从 1 个工具扩展到 8+ 个（探索、过滤、对比、分析、交互）
    - 流程优化：引入轻量模式（探索类工具跳过存储）+ 多步规划（支持依赖链）
    - 数据流改进：工作记忆 vs 外部存储分层 + 知识图谱组织数据关系
  - **P0 工具**: search_data_sources（发现数据源）、data_operator（动态代码算子）、ask_user_clarification（用户交互）
  - **实施路线**: 6 个阶段，约 14 天（3 周）
  - **与 V4.4 关系**: V4.4 提供执行基础设施，V5.0 提供能力多样性，两者互补
  - **AI IDE 参考**: 借鉴 Claude Code、Cursor、Kiro、Trae-agent 的工具设计模式
- `runtime-persistence-plan.md` - Runtime CRUD 与持久化总体方案（账户/会话/研究/运行时配置/模型/RSSHub 等）

## 测试与验证
- `../docs/langgraph-agent-test-plan.md` - LangGraph V5 Agent 全量测试方案（覆盖前端查询→LangGraph→工具层→面板渲染的测试用例、执行顺序与度量）

### 工作台架构（必读）
- `workspace-core-concepts.md` - **工作台核心概念与架构规范**（开发工作台功能时必读）✨NEW
  - **核心概念区分**：数据产物（幕后）vs 面板（前台主角）vs 步骤信息 vs 思考信息
  - **设计原则**：面板是第一公民、数据产物是幕后英雄、透明度是信任的基础
  - **当前问题清单**：画布空、数据产物被当主角、步骤/思考信息缺失、Pin 放错对象
  - **与研究视图关系**：复用设计模式，增加 Session 持续性

### 前端架构（必读）
- rontend-design-guidelines.md - 前端界面/组件设计规范（布局、shadcn 使用、MediaCardGrid 等，2025-11 已补充 `layout_size` 语义＆ Electron 调试/打包说明）
- `frontend-architecture.md` - 前端架构与技术约束，修改任何前端代码时必读
  - **技术栈铁律**：Vue 3 + shadcn-vue + ECharts（不是 React！）
  - 组件开发规范（Composition API、TypeScript、数据契约一致性）
  - shadcn-vue 使用规范（安装配置、主题、组件使用）
  - ECharts 集成规范（按需引入、响应式调整）
  - 禁止事项（React 语法、其他 UI 库、其他图表库）
  - **已实现组件清单**（8个组件全部完成）
- `component_contracts.md` - 前后端共享的组件契约清单（contract-first 渲染基线，Phase13 实施必须引用，不得通过 heuristics 猜测组件）

- `frontend-panel-components.md` - **前端面板组件实现指南**（开发面板组件时必读）
  - 8个已实现组件的详细实现说明（ListPanel、StatisticCard、LineChart、BarChart、PieChart、Table、ImageGallery、FallbackRichText）
  - 每个组件的核心功能、关键代码、配置项、数据契约
  - 通用模式（Props接口、数据获取、字段映射、响应式调整）
  - 组件注册机制（DynamicBlockRenderer、ComponentManifest）

- `frontend-ui-design-patterns.md` - **前端 UI 设计范式**（设计新组件/界面时必读）✨NEW
  - **设计理念**：玻璃态质感、状态驱动设计、渐进式披露、即时反馈（0.1s 响应法则）、平台感知
  - **卡片组件设计**：三段式结构、状态配色系统（5 种状态）、平台配色方案（6 个平台）
  - **交互动效规范**：禁止缩放变换、推荐微妙过渡（颜色/透明度/位移）
  - **标准组件**：徽章（Badge）、按钮（Button）、信息面板（提示/警告/错误）
  - **表单设计**：分组布局、输入框样式、对话框设计
  - **参考实现**：ResearchLiveCard、SubscriptionCard、SubscriptionForm
  - **设计决策记录**：为什么禁止 scale 动效、为什么使用大圆角、为什么状态条只有 1px

### 后端架构（必读）
- `backend-architecture.md` - 后端（Integration/Service/Controller层）架构设计与技术约束，修改任何后端代码时必读
  - Integration层可复用组件（DataExecutor、CacheService）使用规范
  - URL编码安全最佳实践
  - 测试策略（单元测试与真实服务隔离）
  - 同步/异步策略
  - FeedItem通用数据模型（"万物皆可RSS"）
- `runtime-persistence-plan.md` - **Runtime 持久化渐进式实施方案**（数据库/配置管理/会话历史/研究任务持久化）
  - 技术选型：SQLite + SQLModel + Alembic + Fernet
  - 5 个阶段：基础持久化 MVP → 会话 → 研究 → 用户 → 付费
  - 渐进式演进路径，避免过度设计
- `knowledge-base-design.md` - **知识库系统设计方案 v1.1（2025-11-13 Codex审查修订）**
  - **⭐ v1.1修订**：修复 Codex 审查发现的 5 个关键问题
    - P0 - 安全：移除 `eval()` 调用,替换为 `json.loads()`
    - P0 - 数据库集成：新增 1.3 章节,说明如何集成到 `services/database/models.py`,定义 Alembic 迁移工作流,明确 `user_id` 处理策略
    - P1 - 派生字段：新增 1.4 章节,定义 `calculate_derived_fields()` 自动计算 `content_plain`/`word_count`/`read_time_minutes`
    - P1 - 依赖关系：明确 Bookmark 对 PanelSession 的依赖,区分 Phase 1（数据引用）和 Phase 2+（完整快照）实现
    - P1 - 依赖注入：完善服务层 DI 设计,新增 `services/knowledge/dependencies.py`,使用 `@lru_cache()` 实现单例
  - 核心功能：Markdown笔记、双向链接、标签系统、混合检索（全文+语义）、知识图谱
  - 技术选型：SQLite（结构化数据）+ ChromaDB（独立Collection `user_knowledge`）+ bge-m3（向量化）
  - 与现有功能集成：Panel收藏、研究任务关联、LangGraph工具、智能推荐
  - 5个阶段实施路线图：基础MVP → 知识检索 → 智能关联 → 知识图谱 → 高级功能
- `subscription-system-design.md` - **订阅管理系统设计方案 v2.2（2025-11-13 Codex审查修正）**
  - **⭐ v2.2修订**：修复 Codex 审查发现的 3 个关键问题
    - P0 - QueryParser 可靠性：保持 LLM 驱动，新增缓存、重试、枚举校验、降级策略
    - P1 - API 完整性：补充完整 CRUD 接口（list/get/update/delete），Service 层新增对应方法
    - P2 - 多用户隔离：明确 Stage 4 之前 `user_id=NULL`（单用户模式），添加唯一约束和向后兼容设计
  - **⭐ v2.0修订（2025-11-13）**：修复严重架构缺陷 - **分离实体识别与动作确定**
    - 错误设计：`resource_type="user_video"` 混淆了实体和动作，同一UP主需要多个订阅记录
    - 正确设计：`entity_type="user"` + `ActionRegistry`，一个实体支持多个动作（投稿/关注/收藏/动态）
  - 核心问题：自然语言标识（"科技美学"）→ 机器标识（uid=12345）的通用映射机制
  - 架构设计：**实体 (Entity)** vs **动作 (Action)** 分离
    - Subscription表：存储实体信息（entity_type="user"，不再是resource_type）
    - ActionRegistry：配置驱动的动作管理（platform, entity_type, action） → 路径模板
    - QueryParser：LLM驱动 + 工程可靠性（缓存/重试/校验/降级）
  - 技术方案：订阅管理 + 语义搜索（ChromaDB `subscriptions` Collection）+ LLM智能解析
  - Fallback机制：订阅系统（模糊搜索）→ 语义搜索 → 实时搜索API → 提示用户订阅
  - 通用支持：B站/知乎/微博/GitHub等多平台，动作可扩展
  - 与知识库协作：笔记引用订阅、订阅内容记笔记、LangGraph同时检索两者
- `subscription-action-registry-automation.md` - **ActionRegistry 自动化生成方案**（从 RSSHub 路由定义自动推断）
  - **核心问题**：不可能手动维护 ACTION_TEMPLATES，需要从 `datasource_definitions.json` 自动生成
  - **解决方案**：RouteAnalyzer 自动分析路由定义，推断 entity_type 和 action
  - **推断规则**：
    - 参数名 → entity_type（`:uid` → `user`，`:column_id` → `column`）
    - 路径模式 → action（`/followings/video` → `following`，`/user/video` → `videos`）
    - name关键词 → action（"投稿" → `videos`，"关注" → `following`）
  - **置信度评分**：自动计算推断置信度，高置信度自动使用，低置信度人工审核
  - **QueryParser修订**：绝对不使用规则引擎，始终使用LLM解析
  - **使用流程**：运行 `python -m scripts.generate_action_registry` → 生成配置文件 → 重启应用

### RAG系统
- `../rag_system/` - 向量检索模块，包含embedding模型、向量存储、检索管道

### 查询处理
- `../query_processor/` - 查询解析模块，包含LLM客户端、Prompt构建器、结果解析器

### 编排层
- `../orchestrator/` - 流程编排模块，协调RAG和LLM完成端到端处理

## 当前任务文档
- `workflow/251210-content-analyzer-agent.md` - **ContentAnalyzer Agent 设计**（待实施）
  - **目标**：安全可控地让 LLM 访问原始数据子集，支持内容分析
  - **核心方案**：两阶段分析（AI 智能选择字段 → 加载过滤数据 → 执行分析）
  - **安全保障**：数量限制（最多10条）+ 字段黑名单 + 值截断 + token 预估
- `workflow/251210-workspace-panel-improvement.md` - **工作台面板展示改进**（待确认方案）
  - **目标**：将工作台从"数据产物为主角"改为"面板为主角"
  - **核心改进**：画布中央展示 Panel、右侧面板重构为 ContextPanel、Pin 功能迁移到面板
  - **3 个 Phase**：面板存储与展示 → 右侧面板重构 → Pin 功能迁移
- `new-architecture.md` - **工作流工作台架构总设计**（已确认方向，Phase 1-6 全部完成）
  - 6 个 Phase：基础设施 → 工作流引擎 → 工作台 UI → 模板系统 → 仪表盘 → Session Runtime
- `workflow/251117-v5-phase3-p1-tools.md` - **V5.0 Phase 3: P1 工具 + 聚合 + 私有数据**（已完成）✅
  - 目标：支持私有数据访问和聚合统计，实现完整的数据分析闭环
  - 核心工具：data_operator（动态算子，统一过滤/对比/聚合）、fetch_private_data（私有数据框架）
  - 测试覆盖：20 个 P1 工具测试 + 106 个完整测试套件全部通过
  - 关键优化：错误处理统一化、容量限制保护、自动采样和超时保护
- `workflow/251117-v5-phase2-lightweight-mode.md` - **V5.0 Phase 2: 轻量模式支持**（已完成）✅
  - 目标：探索类工具跳过数据存储，提升效率
  - 核心功能：ToolSpec 扩展、工作流路由、working_memory、Planner 集成
  - 轻量工具：search_data_sources、ask_user_clarification
  - 测试覆盖：5 个集成测试 + 34 个单元测试全部通过
- `workflow/251116-v5-p0-implementation.md` - **V5.0 Phase 1 (P0) 实施任务**（已完成核心功能）
  - 4 个核心工具：search_data_sources、data_operator、ask_user_clarification、fetch_public_data
  - 简化架构，直接启用 V5.0 工具（移除 Feature Flag）
  - 单元测试覆盖率 100% (32/32 通过)
  - 代码质量修复：私有源信息、正则安全、静默失败、DataStasher 优化
- `workflow/251115-unified-workspace-architecture.md` - **统一工作区架构设计方案**（设计方案，待评审）
  - **核心问题**：研究卡片与普通面板割裂、无统一历史记录、缺少进度反馈、普通查询无身份信息
  - **解决方案**：所有查询都生成卡片，统一生命周期（pending → processing → completed）
  - **即时反馈设计**：0.1s 响应法则、骨架屏、实时进度推送
  - **卡片身份信息**：查询文本 + 时间戳 + 模式标识 + 触发来源
  - **后端支持**：快速刷新机制（复用元数据，节省 70-80% 时间）、交互式研究工作流（计划审核）
  - **实施路线图**：5 个阶段（基础卡片系统 → 进度反馈 → 快速刷新 → 交互式研究 → 持久化）
- `workflow/251113-subscription-system-implementation.md` - **订阅管理系统 Phase 1 实施任务**（已完成 ✅）
  - 基础订阅管理（数据库 + Service + API + 前端）
  - Stage 1-4 全部完成，20 个测试用例全部通过
- `workflow/251113-langgraph-v4.4-implementation.md` - **LangGraph V4.4 架构实施任务**（已批准，待开始）
  - 5 个阶段详细 TODO 清单（共 34 个子任务）
  - V4.0: 显式依赖解析（1天）
  - V4.1: 扇出并行执行（2天）
  - V4.2: RSSHub 路由发现（2天）
  - V4.4: 前置语义 + GraphRenderer（1天）
  - 前端可视化 + 测试优化（1天）
  - 预计工作量：7.5 天，预计完成：2025-01-20
- `workflow/251113-runtime-persistence-implementation.md` - **Runtime 持久化实施任务**（规划完成，待开始）
  - 5 个阶段详细 TODO 清单
  - 技术决策记录与风险应对
  - 进度跟踪与完成记录

## 最近完成任务文档
- `workflow/done/251210-workspace-timeline-display-fix.md` - **工作台时间线显示问题修复** [✅ 完成 2025-12-10]
  - **修复问题**：
    1. 重复的"思考中"条目 → addThinkingEntry 去重逻辑
    2. 面板生成重复 → addPanelPreview 去重 + 后端 summary 移除 panel_previews
    3. Agent reasoning 缺失 → 完整的 reasoning 推送链路（research_agent → sync_executor → runtime_manager → session_controller → WebSocket → frontend）
  - **核心改进**：
    - Phase 1: Agent Reasoning 实时推送（扩展 LangGraph 回调机制 + ResearchStepMessage 带 reasoning 字段 + ThinkingEntry.vue 显示详细推理）
    - Phase 2: 去重机制（后端/前端双重去重）
    - Phase 3: 时间线优化（合并连续思考条目）
  - **ThinkingEntry 新功能**：主要内容 + 详细推理（带 Lightbulb 图标和"详细推理"标签）
- `workflow/done/251209-session-runtime-unified-architecture.md` - **工作流工作台 Phase 6: Session Runtime** [✅ 完成 2025-12-09]
  - **目标**：实现 Session Runtime 统一架构，解决每次请求创建新 LangGraph workflow 导致上下文丢失的问题
  - **核心功能**：SessionRuntimeManager、跨请求上下文保持（data_stash/chat_history/working_memory）、RecordedStep 记录、保存为模板
  - **后端实现**：services/session 模块（models.py/store.py/runtime_manager.py/workflow_extractor.py）+ session_controller.py API
  - **前端实现**：sessionStore + sessionApi + ChatInteractionArea 集成
  - **关键修复**：chat_history 格式转换（Dict→str）、LangGraphExecutionResult.data_stash 适配
- `workflow/done/251209-phase5-dashboard-design.md` - **工作流工作台 Phase 5: 仪表盘** [✅ 完成 2025-12-09]
  - **目标**：实现数据监控仪表盘，支持卡片 Pin、定时刷新、条件触发、通知推送
  - **核心功能**：DashboardCard、SchedulerService（Python threading）、TriggerService、NotificationService
  - **前端组件**：DashboardView、DashboardGrid（CSS Grid）、DashboardCard、NotificationBell
  - **路由**：`/dashboard` 独立页面
- `workflow/251209-phase4-template-system-design.md` - **工作流工作台 Phase 4: 模板系统** [✅ 完成 2025-12-09]
  - **目标**：实现工作流模板化，支持模板创建、分享、市场发现
  - **核心功能**：模板创建/实例化、变量系统、模板市场、导出导入
  - **后端实现**：TemplateService + template_controller.py API
  - **前端实现**：TemplateMarket、TemplateCard、VariableFormDialog 等组件
- `workflow/done/251209-phase3-workspace-ui-design.md` - **工作流工作台 Phase 3: 工作台 UI** [✅ 完成 2025-12-09]
  - **目标**：实现三栏式工作台界面，支持工作流可视化、数据产物管理、实时交互
  - **核心组件**：WorkspaceLayout、WorkflowPanel、MainCanvas、ArtifactPanel、ChatInteractionArea
  - **后端实现**：workflow_controller.py API + WebSocket 进度推送
- `workflow/done/251209-phase2-workflow-engine-design.md` - **工作流工作台 Phase 2: Workflow Engine** [✅ 完成 2025-12-09]
  - **目标**：建立工作流引擎层，支持多步骤 DAG 执行、进度追踪、中断/恢复
  - **核心内容**：Workflow/WorkflowRun 模型、WorkflowStore、WorkflowEngine、变量系统
  - **复用现有组件**：DatabaseConnection、DataArtifact、ArtifactStore
  - **测试覆盖**：54 个单元测试全部通过
- `workflow/done/251209-phase1-data-artifact-design.md` - **工作流工作台 Phase 1: DataArtifact 基础设施** [✅ 完成 2025-12-09]
  - **目标**：建立"数据产物"核心模型，作为工作流工作台的基础
  - **核心内容**：DataArtifact 模型、ArtifactStore 存储层、ViewSpec 推断器、LangGraph 集成
  - **复用现有组件**：ResearchDataStore、EnhancedDataReference、DatabaseConnection
  - **测试覆盖**：24 个单元测试全部通过
- `workflow/done/251128-single-agent-architecture-proposal.md` - **V6.0 单Agent架构重构** [✅ 完成 2025-11-28]
  - **核心改进**：融合 Planner + Reflector + Synthesizer 为单一 ResearchAgent
  - **保留 Router**：作为前置分流，减少简单查询的开销
  - **新架构工作流**：router → research_agent → tool_executor → data_stasher → research_agent (循环)
  - **测试覆盖**：278 个测试通过
  - **关键文件**：`langgraph_agents/agents/research_agent.py`、`langgraph_agents/prompts/research_agent_system.txt`
  - **Phase 2 工具层增强**：智能摘要（`_smart_default_summary`）、统一数据引用（`data_ref_resolver.py`）、执行保护（`execution_wrapper.py`）
  - **Phase 3 上下文管理**：分层记忆系统（`context_manager.py`）、历史压缩、使用监控
- `workflow/done/251127-unify-v5-langgraph-architecture.md` - **V5.0 架构统一：废弃 services/agent_graph** [✅ 完成 2025-11-27]
  - 核心问题：存在两套并行的任务执行系统（V5.0 单步迭代 vs Task Graph 多步一次性规划）
  - 解决方案：统一使用 V5.0 完整 LangGraph 状态机（单步迭代规划，类似 Claude Code 工作方式）
  - 新增：`langgraph_agents/sync_executor.py` 同步执行适配层
  - 删除：`services/agent_graph/` 整个目录、`services/chat/task_graph_handler.py`
  - 测试覆盖：190 个 LangGraph 测试 + 10 个 ChatService 测试全部通过
- `workflow/done/251117-v5-phase5-data-flow-optimization.md` - **V5.0 Phase 5: 数据流优化（知识图谱 + 智能摘要）** [✅ 完成 2025-11-17]
  - 目标：引入知识图谱和智能摘要，提升数据组织能力和决策智能性
  - 核心功能：KnowledgeGraph（数据结构）、EnhancedDataReference（增强元数据）、MetadataExtractor（自动提取）、EnhancedDataStasher（图谱集成）、GraphHelper（决策支持）
  - 测试覆盖：11 个 Phase 5 测试 + 143 个完整测试套件全部通过
  - 关键特性：数据血缘追溯、质量评分、智能摘要、向后兼容
  - 代码统计：新增 ~1,121 行代码（5 个新文件 + 1 个修改），测试覆盖率 100%
- `workflow/done/251117-v5-phase4-multi-step-planning.md` - **V5.0 Phase 4: 多步执行计划与依赖解析** [✅ 完成 2025-11-17]
  - 目标：支持多步工具调用和依赖解析，实现复杂数据分析工作流
  - 核心功能：ExecutionPlan（执行计划）、StashReference（依赖解析）、ExecutionEngine（任务调度器）
  - 测试覆盖：10 个 Phase 4 测试 + 129 个完整测试套件全部通过
  - 关键特性：DAG 依赖图、JSONPath 字段提取、循环依赖检测、部分失败容忍
- `workflow/251115-debugging-research-flow.md` - **研究模式前端流程调试与重复请求修复** [✅ 完成 2025-11-15]
  - **修复4项关键问题**：
    1. 后端 `ResponseMetadata` 缺失 `requires_streaming` 等字段（API schema + controller 修复）
    2. 前端 TypeScript 类型定义缺失对应字段（`panel.ts` 修复）
    3. 已完成研究卡片立即消失（`researchStore.ts` 修复，增加 completed 状态显示）
    4. **重复请求架构问题**（全局 WebSocket 管理器方案）
  - **核心成果 - 全局 WebSocket 连接管理器**（`useResearchWebSocketManager.ts`）：
    - 连接池管理：`Map<taskId, Connection>` - 主页面和详情页共享连接
    - 请求去重：`Map<taskId, boolean>` - 确保研究请求只发送一次
    - 智能初始化：详情页检测已有数据，避免清空进度
    - 导航保护：返回主页面时不断开连接，保留数据供后续查看
  - **验证指南**：`workflow/251115-duplicate-request-fix-verification.md`（9个验证步骤，控制台日志对比）
- `workflow/done/251115-websocket-unification-and-p0p1-fixes.md` - **WebSocket 统一 + P0/P1 问题修复** [✅ 完成 2025-11-15]
  - WebSocket 架构优化：统一 `/api/v1/chat/stream` 和 `/api/v1/chat/research-stream` 为单一端点，净减少 163 行代码
  - P0 修复 - LangGraph 模式缺少兜底逻辑：`research_service` 未初始化时正确回退到简单查询
  - P1 修复 - 订阅解析失败被误判为成功：引入 `resolution_status: Dict[str, bool]`，orchestrator 检查实际解析状态
  - 前端适配：`useResearchWebSocket` 更新为统一端点，添加 `mode: "research"` 参数
- `workflow/done/251114-subscription-architecture-refactor-v2.md` - **订阅系统架构重构方案 v2.0**（Codex 审核修订版）[✅ 完成 2025-11-15]
  - Phase 0-5 全部完成（Schema 元数据 / entity_resolver_helper / RAG 集成 / Service 清理 / LangGraph 提示统一 / 文档归档）
  - 运行时修复：8 个问题全部修复（Vector DB Schema / LLM Prompt / Subscription Vector Service / Research Mode / WebSocket 统一 / LangGraph 兜底 / 订阅解析状态 / 文档更新）
  - 核心改进：移除启发式判断，基于 schema.parameter_type 标记（entity_ref/literal/enum）
  - 详细迁移计划：明确每个 Phase 的改造点和依赖关系
- `workflow/done/251114-subscription-integration.md` - **订阅系统集成到主查询流程**（DataQueryService订阅预检、ChatService集成、Codex审查修复）[✅ 完成 2025-11-14]
  - Stage 1-4: LangGraph Prompt优化、DataQueryService核心改造、ChatService集成、测试覆盖（27个测试全部通过）
  - Codex修复：缓存API、DataExecutor API、集成测试
- `workflow/done/251114-subscription-phase2-intelligent-parsing.md` - **订阅系统 Phase 2（历史实现记录）** [📚 归档]
  - 保留 Stage 1-4 的旧架构分析与调试记录，新架构以 `workflow/251114-subscription-architecture-refactor-v2.md` 为准。
- `workflow/251113-research-view-implementation.md` - **专属研究视图实施完成**（WebSocket流式推送、双栏布局、实时进度可视化）[✅ 完成 2025-11-13]
- `workflow/251113-research-streaming-and-nesting.md` - **研究模式实时推送与数据归属可视化方案**（WebSocket流式推送、嵌套容器设计）[✅ 规划完成]
- `code-review-20251113.md` - **Codex 生成代码审查报告**（P0 bug修复、P1架构改进、测试补充）[✅ 完成]

## 已完成任务文档
- `workflow/251111-langgraph-agents-refactor.md` - **LangGraph Agents 代码审查与全面修复**（P0-P2 问题修复，测试补充）[✅ 完成]
  - `workflow/langgraph-agents-p0-verification-report.md` - P0 阶段验证报告
  - `workflow/langgraph-agents-p1-completion-report.md` - P1 阶段完成报告
  - `workflow/langgraph-agents-p2-completion-report.md` - P2 阶段完成报告
  - `workflow/langgraph-agents-integration-plan.md` - 系统整合方案设计
  - `workflow/langgraph-agents-integration-usage.md` - **集成使用指南**（后端+前端）
  - `workflow/langgraph-agents-frontend-implementation.md` - **前端实现方案**（Vue 3 + shadcn-vue）
- `workflow/251031-rss-aggregation-layered-architecture.md` - 实现RSS聚合系统分层架构
- `workflow/251031-rss-aggregation-architecture-refine.md` - RSS聚合架构落地改进方案，补充本地依赖、同步异步策略与接口设计
- `workflow/251101-intelligent-panel-backend.md` - 智能数据面板后端整改与质量保障方案

## 技术使用指南
- `service-layer-usage.md` - Service层完整使用指南，包含所有服务的创建、使用和扩展方法
- `adapter-codegen-prompt.md` - 路由适配器代码生成提示词模板，用于根据RSSHub TypeScript路由文件自动生成Python adapter代码
- `llm-call-tracking-integration-guide.md` - **LLM 调用追踪系统集成指南**（可观测性）✅ 完成
  - **核心功能**：实时追踪所有 LLM 调用（Planner、Reflector、Synthesizer、订阅解析等）
  - **前端可视化**：调用时间线、Token 统计、耗时分析
  - **开发者模式**：查看完整 prompt/response，调试系统行为
  - **架构设计**：LLMCallTracker + WebSocket 实时推送 + 前端时间线组件
  - **使用场景**：调试查询规划、Token 使用优化、性能瓶颈定位
  - **已完成**：后端全链路集成（LLM Client → Runtime → SyncExecutor → ChatService → chat_stream）、前端 Store 扩展（llmCalls + llmCallStats）、LLMCallTimeline 组件
  - **文件清单**：
    - 后端：`api/schemas/llm_call_event.py`、`api/schemas/stream_messages.py`（LLMCallMessage）、`query_processor/llm_client.py`、`langgraph_agents/runtime.py`、`langgraph_agents/factory.py`、`langgraph_agents/sync_executor.py`、`services/chat_service.py`、`api/controllers/chat_stream.py`
    - 前端：`frontend/src/shared/types/panel.ts`（LLMCallEvent 类型）、`frontend/src/store/panelStore.ts`（llmCalls 状态）、`frontend/src/components/debug/LLMCallTimeline.vue`

## 全局重要记忆

### ⚠️⚠️⚠️ 启发式判断与规则引擎警告 ⚠️⚠️⚠️

**极度危险区域 - 可维护性杀手**

本项目历史上曾多次因启发式判断和规则引擎导致严重问题，必须高度警惕：

1. **绝对禁止规则引擎**
   - ❌ 禁止关键词匹配（如"科技美学" → bilibili_user-video）
   - ❌ 禁止正则表达式判断（如 `/.*用户.*/` → entity_type=user）
   - ❌ 禁止基于字符集的启发式（如"包含中文" → 需要订阅解析）
   - ✅ 所有实体识别必须通过 LLM 或基于 schema 的明确标记

2. **启发式判断的严格限制**
   - ⚠️ 只允许在数据准备阶段使用（如 `enrich_tool_definitions.py`）
   - ⚠️ 必须有明确的置信度评分（低置信度必须人工审核）
   - ⚠️ 必须有兜底机制（schema 缺失时才使用）
   - ⚠️ 日志必须使用醒目前缀：`[HEURISTIC_FALLBACK]`、`[LOW_CONFIDENCE]`

3. **正确的实现方式**
   - ✅ 使用 schema 明确标记（`parameter_type: "entity_ref"`）
   - ✅ 使用 LLM 进行语义理解（不依赖规则）
   - ✅ 基于数据驱动（从 datasource_definitions 获取元数据）
   - ✅ 保持代码简单可预测（避免复杂条件判断）

**违反上述原则的代码必须立即重构！**

### ⚠️⚠️⚠️ 泛化性与鲁棒性原则 ⚠️⚠️⚠️

**禁止"打补丁"式开发 - 必须追求泛化性**

1. **什么是"打补丁"**
   - ❌ 在提示词中添加针对特定查询的示例（如"B站影视飓风投稿视频中，标题包含英雄联盟"）
   - ❌ 在代码中添加针对特定字符串模式的处理逻辑
   - ❌ 为了解决一个 case 而添加 if-else 分支
   - ❌ 通过增加示例/规则来"教会"系统处理特定场景
   - ❌ 添加 filter_hint、post_search_suggestion 等"提示"字段来引导 LLM

2. **为什么打补丁是错误的**
   - 用户查询是多样的，不可能穷举所有模式
   - 每个补丁都增加系统复杂度，降低可维护性
   - 补丁之间可能产生冲突或意外交互
   - 无法保证对新类型查询的泛化能力

3. **正确的解决思路**
   - ✅ 从**架构层面**解决问题，而非从**规则层面**
   - ✅ 增强**工具能力**（让工具能处理更广泛的输入），而非教 LLM 如何绕过工具限制
   - ✅ 使用**类型系统/Schema**来定义能力边界，而非用示例来暗示
   - ✅ 如果 LLM 无法正确处理某类查询，问题很可能在**工具设计**或**数据流架构**

4. **具体案例分析**

   **问题**：查询 "B站影视飓风投稿视频中，标题包含英雄联盟的视频" 被 DataQueryService 返回 needs_clarification

   **错误做法（打补丁）**：
   - 在 Planner 提示词中添加"模式 B2"示例，教 LLM 分解这类查询
   - 添加 query_analysis 字段强制 LLM 先分析再决策
   - 使用正则表达式检测"标题包含"等关键词

   **正确做法（泛化）**：
   - 分析 DataQueryService 为什么无法处理复合查询
   - 增强 DataQueryService 的能力，让它能理解"数据源+过滤条件"的组合
   - 或者设计更合理的工具边界，让工具本身具备过滤能力

5. **判断标准：一个解决方案是否是"打补丁"**
   - 问自己：这个方案能处理所有**同类**问题吗？还是只能处理**这一个**问题？
   - 问自己：如果用户换一种表达方式，方案还有效吗？
   - 问自己：这个方案是在**增加系统能力**还是在**添加特例处理**？

**记住：泛化性 > 特定 case 的正确性。宁可暂时不解决问题，也不要用补丁污染代码库！**

### ⚠️⚠️⚠️ V5.0 工具纯粹性原则 ⚠️⚠️⚠️

**工具必须保持职责单一 - 禁止跨工具耦合**

1. **核心原则：工具应该做什么**
   - ✅ 每个工具只负责**一件事情**
   - ✅ `fetch_public_data` 只负责获取数据，不包含任何过滤提示、后置处理建议
   - ✅ `data_operator` 负责所有动态数据处理（过滤/聚合/对比），通过 schema + 样例生成 Python 代码来保证泛化
   - ✅ 工具之间通过 `data_id` 引用，而非通过 hint/suggestion 字段

2. **禁止的做法**
   - ❌ 在工具输出中添加 `filter_hint` 字段引导 Planner 调用下一个工具
   - ❌ 在工具输出中添加 `suggested_next_action` 字段
   - ❌ 在 Planner 提示词中添加"模式 E: filter_hint 自动过滤"等特定场景处理
   - ❌ 在数据流中传递 `post_filters` 等不属于工具结果的元信息

3. **正确的架构模式**
   - ✅ Planner 应该从工具的 **schema**、样例和执行历史中学习如何组合工具
   - ✅ 数据获取与数据处理应该是两个独立的步骤，没有内在耦合
   - ✅ 第一步：`fetch_public_data("B站影视飓风投稿视频")` → 返回 30 条数据
   - ✅ 第二步：`data_operator(source_ref="lg-abc123", instruction="筛选标题包含英雄联盟")` → 返回 1 条数据

4. **Planner 应该如何学习**
   - ✅ 从 `data_stash` 中看到过去的执行历史：fetch → data_operator 的成功案例
   - ✅ 从工具 schema 中理解：data_operator 需要 source_ref + instruction
   - ✅ 从当前查询中识别：用户需要先获取数据，然后用自然语言指令描述转换
   - ❌ 不应该依赖：特定的提示词模式、hint 字段、中间元信息

5. **2025-11-27 架构清理记录**
   - **问题根源**：为了支持 "B站影视飓风投稿视频中，标题包含英雄联盟的视频" 这类复合查询，错误地在工具之间添加了 filter_hint 机制
   - **错误实现**：
     - `public_data.py` 添加 `_convert_post_filters_to_conditions` 函数
     - `_format_success_payload` 检查 `rag_trace.post_filters` 并生成 filter_hint
     - `data_query_service.py` 的 `_build_rag_trace` 传递 post_filters
     - `planner_system.txt` 添加"模式 E: filter_hint 自动过滤"和对应的决策优先级
   - **正确做法**：完全移除所有 filter_hint 逻辑，让工具保持纯粹
   - **测试结果**：409/411 测试通过（1 个失败与 MockChatService 参数无关）
   - **核心教训**：工具设计不应该为了解决某个 case 而引入跨工具通信机制

**记住：工具的纯粹性是架构健康的基石。任何形式的 hint/suggestion 都是架构退化的信号！**

### ⚠️⚠️⚠️ LLM Token 限制防护原则 ⚠️⚠️⚠️

**Agent 节点不应将原始数据发送给 LLM - 必须使用摘要**

1. **问题根源**
   - LLM 有严格的 token 限制（如 DeepSeek 为 131,072 tokens）
   - 完整的原始数据可能包含数百条记录，每条记录包含多个字段
   - 将原始数据序列化为 JSON 并发送给 LLM 会导致请求超过 token 限制

2. **2025-11-27 Synthesizer Bug 修复**
   - **问题现象**：`BadRequestError: maximum context length is 131072 tokens. However, you requested 5326231 tokens`
   - **错误实现**：
     ```python
     raw = runtime.data_store.load(ref.data_id)  # 加载完整原始数据
     records.append({"raw": raw})  # 将 5MB+ 数据放入 prompt
     ```
   - **正确实现**：
     ```python
     summaries.append({
         "data_id": ref.data_id,
         "tool": ref.tool_name,
         "status": ref.status,
         "summary": ref.summary,  # 只使用摘要（几百字符）
     })
     ```
   - **修复文件**：`langgraph_agents/agents/synthesizer.py`
   - **函数改名**：`_load_raw_records` → `_build_data_summaries`

3. **架构规范**
   - ✅ **Planner**: 只使用 `ref.summary`（已正确）
   - ✅ **Reflector**: 只使用 `ref.summary`（已正确）
   - ✅ **Synthesizer**: 只使用 `ref.summary`（已修复）
   - ✅ **DataStasher**: 负责生成高质量的 summary（已实现）
   - ❌ **禁止**：在任何 Agent 节点中调用 `runtime.data_store.load()` 获取完整数据

4. **DataReference 设计理念**
   - `data_id`: 数据引用标识符（用于前端或后续工具调用）
   - `summary`: 数据摘要（用于 LLM 推理）
   - `metadata`: 元信息（条数、来源、质量分数等）
   - **原始数据**: 存储在 data_store 中，仅在需要时（如前端展示、工具处理）才加载

5. **Token 使用量对比**
   - 修复前：5,326,231 tokens（完整数据）
   - 修复后：~5,000 tokens（仅摘要）
   - **减少了 99.9% 的 token 使用**

**记住：LLM 应该基于数据摘要进行推理，而不是处理完整的原始数据！**

---

### 订阅系统集成（2025-11-15 更新）

- ✅ **RAG 内建实体解析**：`orchestrator/rag_in_action.py` 使用 `entity_resolver_helper` 根据 schema 自动判断 `entity_ref` 参数，无需额外解析器。
- ✅ **Service 层简化**：DataQueryService/ChatService 已移除订阅预检与 `SubscriptionResolver` 注入逻辑，所有查询统一走 RAG 流程。
- ✅ **LangGraph 工具统一**：已删除 `fetch_subscription_data`，Planner 只需调用 `fetch_public_data`，RAG 会决定是否命中订阅实体。
- ⚠️ **多用户支持**：当前仍默认 `user_id=None`（单用户模式），如需用户隔离另行规划。

### 项目架构
- 项目采用单体应用分层架构，不使用微服务
- 分层结构：Controller → Service → Integration（Data/Cache）
- Integration层和Service层保持同步实现，Controller层通过线程池调度

### 持久化与配置管理（2025-11 新增）
- **渐进式演进原则** - 先实现核心功能（AI模型/RSSHub配置），再扩展会话/研究任务，最后按需实施用户/付费系统
- **技术选型务实** - SQLite（统一开发/生产）+ SQLModel（类型安全 + Pydantic风格）+ Alembic（迁移）+ Fernet（加密）
- **最小化复杂度** - 能用1张表不用4张表，能用JSON字段不新增关系表，能复用现有组件不造轮子
- **保持向后兼容** - 配置优先级：数据库 → 环境变量 → 代码默认值，数据库不可用时自动fallback
- **避免过度设计** - 不使用 PostgreSQL + Redis（早期不需要），不使用 Magic Link + MFA（早期不需要），不使用 audit_logs（早期不需要）

### 知识库系统（2025-11 设计）
- **Markdown为中心** - 纯文本格式，易于版本控制，不被平台绑定，支持代码块/公式/图表
- **双向链接** - `[[笔记名称]]`语法，自动建立关联，显示反向链接，形成知识网络
- **标签优于文件夹** - 一篇笔记多个标签，动态组织，灵活调整；保留层级支持但不强制
- **混合检索** - 全文搜索（SQLite FTS5）+ 语义搜索（RAG），互补优势，覆盖不同场景
- **独立向量空间** - 为知识库创建独立ChromaDB Collection（`user_knowledge`），与RSSHub路由分离，避免干扰
- **智能集成** - Panel收藏、研究任务关联笔记、LangGraph检索知识库、智能推荐相关笔记
- **知识图谱** - 可视化笔记间关联关系，支持交互探索（Cytoscape.js/D3.js）

### 代码规范
- 所有代码注释和文档使用中文（UTF-8编码）
- 严格遵循CLAUDE.md中的代码质量要求
- 单个代码文件不超过1000行
- 优先复用现有代码，避免重复造轮子
- ⚠️ **绝对禁止启发式判断和规则引擎**（见上方警告区域）

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
- **DataQueryResult 携带 retrieved_tools 字段**，包含 RAG 检索到的候选工具列表（route_id/name/score 等），供前端展示 AI 推理过程（2025-11）
- **ChatService 格式化 retrieved_tools**，通过 `_format_retrieved_tools()` 方法限制描述长度、提取关键字段，避免前端 payload 过大
- `DATA_QUERY_SINGLE_ROUTE=1` 会让 DataQueryService 默认仅执行 primary route；ChatService 在 `filter_datasource` 场景下也会自动启用单路模式
- LLM Query Planner 返回的每个子查询都必须包含 `task_type`（data_fetch / analysis / report），ChatService 会据此决定是否触发 RAG 还是复用已有数据做总结
- **_build_dataset_preview 均匀采样** - 在多数据集场景下，预览数据会在所有数据集间均匀分配采样配额（`max_items // len(datasets)`），确保每个数据集都有代表性样本
- **LLM 响应空值检查** - 所有 LLM 调用后必须检查 `response is None or not response.strip()`，避免空响应导致的 AttributeError

### 配置管理
- **服务层配置优先使用** - 通过 `services/config.py` 的 `get_data_query_config()` 获取配置，禁止使用 `os.getenv()` 硬编码
- **配置单例模式** - `DataQueryConfig` 使用全局单例，测试时通过 `reset_data_query_config()` 重置
- **Pydantic V2 兼容** - 所有配置类使用 `SettingsConfigDict`，设置 `extra='ignore'` 避免冲突
- **环境变量映射** - 配置项通过 `alias` 参数映射环境变量，支持 `.env` 文件自动加载
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
- **已实现 17 个组件**：
  - **核心组件（8个）**：ListPanelBlock、StatisticCardBlock、LineChartBlock、BarChartBlock、PieChartBlock、TableBlock、ImageGalleryBlock、FallbackRichTextBlock
  - **原子化组件（v0.2 新增，8个）**：CountCardBlock、ProgressBarBlock、QuoteCardBlock、ComparisonCardBlock、AuthorCardBlock、TagCloudBlock、TimelineCardBlock、HeatmapCalendarBlock
  - **监控组件（v0.4 重构，1个）**：ServiceStatusBlock（完全配置驱动，支持自定义状态、颜色、指标）
- **技术栈铁律**：所有组件必须使用 shadcn-vue + ECharts，禁止使用 React 语法或其他 UI 库
- **组件路径**：`frontend/src/features/panel/components/blocks/`
- **组件注册**：通过 `DynamicBlockRenderer.vue` 动态路由，通过 `componentManifest.ts` 声明能力
- **数据契约**：前端 TypeScript 类型必须与后端 Pydantic 模型一致（定义在 `docs/backend-panel-view-models.md`）
- **嵌套支持**：所有组件支持 `UIBlock.children` 嵌套架构
- **响应式图表**：ECharts 组件使用 ResizeObserver 实现响应式调整
- **依赖状态**：shadcn-vue（9个组件：Card、Badge、Separator、Alert、Table、Button、Progress、Dialog、Tooltip）、ECharts、TanStack Table、marked 均已安装
- **配置预设系统**：`services/panel/adapters/config_presets.py` 提供标准化尺寸预设（compact/normal/large/full），让 AI planner 灵活控制组件大小
- **ListPanel 配置**：支持 compact 模式、max_items、show_description、show_metadata、show_categories 等配置项
- **数据追加模式**：
  - 前端 `panelStore.ts` 正确处理后端返回的 `mode` 字段（append/replace/insert），支持多轮对话时数据追加显示
  - 后端 `layout_engine.py` 使用 UUID 生成唯一 node id（`row-{batch_id}-{index}`），确保 append 模式下布局节点不重复
  - 前端包含详细的 console.log 调试日志，可查看数据合并过程

### 专属研究视图（2025-11-13 新增）
- **WebSocket 流式推送** - 后端使用 Generator 逐步 yield 研究进度消息，前端通过 WebSocket 实时接收
- **双栏布局** - 左侧 30% 显示研究上下文（计划、步骤、进度），右侧 70% 显示数据面板和分析结果
- **路由配置** - `/research/:taskId` 路由跳转到专属研究视图，主界面通过 `mode="research"` 触发跳转
- **消息类型** - 6 种研究专用消息：start、step、panel、analysis、complete、error（定义在 `api/schemas/stream_messages.py:176-415`）
- **Store 管理** - `researchViewStore.ts` 管理研究任务状态、步骤列表、面板数据、分析结果
- **自动重连** - WebSocket 连接支持自动重连（最多 5 次，延迟递增），确保稳定性
- **组件复用** - 数据面板复用现有的 `DynamicBlockRenderer`，无需重复开发
- **文件清单**：
  - 后端：`api/schemas/stream_messages.py`（消息类型）、`services/chat_service.py:790-1171`（流式生成器）、`api/controllers/research_stream.py`（WebSocket 端点）
  - 前端：`frontend/src/views/ResearchView.vue`（主容器）、`frontend/src/composables/useResearchWebSocket.ts`（WebSocket 管理）、`frontend/src/store/researchViewStore.ts`（状态管理）、`frontend/src/features/research/components/ResearchContextPanel.vue`（左侧面板）、`frontend/src/features/research/components/ResearchDataPanel.vue`（右侧面板）

### 全局 WebSocket 连接管理器（2025-11-15 新增）
- **核心问题** - 主页面和详情页各自创建连接、各自发送请求，导致研究重复执行、进度数据丢失
- **解决方案** - 全局连接池 + 请求去重（`useResearchWebSocketManager.ts`）
- **连接池管理** - `Map<taskId, Connection>` 确保同一任务只有一个 WebSocket 连接，跨页面共享
- **请求去重** - `Map<taskId, boolean>` 追踪请求状态，`sendResearchRequestOnce()` 确保研究请求只发送一次
- **智能初始化** - `ResearchView.vue` 在挂载时检查是否已有数据（`store.state.task_id === props.taskId && store.state.steps.length > 0`），有则复用，无则初始化
- **导航保护** - 返回主页面时不调用 `disconnect()`，不调用 `store.reset()`，保留数据供后续查看
- **资源清理** - 删除任务时调用 `disconnectAndCleanup()`，应用卸载时调用 `cleanupAllConnections()`
- **数据库集成准备** - 当后端接入数据库持久化时，管理器架构无需改动，只需在智能初始化时从 API 加载数据
- **⚠️ 初始化时序约束** - 在 MainView 创建 WebSocket 连接之前，必须先初始化 researchViewStore（`viewStore.initializeTask(taskId, query)`），确保 `task_id` 被正确设置。否则当 WebSocket 消息到达时，store 的 `task_id` 仍为 `null`，导致 ResearchView 无法识别已有数据而重新初始化。参见 `MainView.vue:172-190`。
- **关键方法**：
  - `useResearchWebSocketManager(options)` - 获取或创建连接（自动复用已有连接）
  - `sendResearchRequestOnce(payload)` - 带去重保护的请求发送（幂等操作）
  - `hasRequestSent()` - 检查是否已发送研究请求
  - `disconnectAndCleanup()` - 断开连接并清理资源
  - `cleanupAllConnections()` - 清理所有连接（应用级）
- **验证方式** - 查看控制台日志：首次连接显示"创建新连接"+"首次发送研究请求"，后续打开显示"复用现有连接"+"研究请求已发送，跳过"

### 开发者模式与组件调试（2025-12-02 更新）
- **开发者模式 Store** - `frontend/src/store/devModeStore.ts` 提供全局开发者模式状态管理，支持 localStorage 持久化
- **组件调试页面** - `/dev/components` 路由（仅开发模式可访问）
  - **入口**：`frontend/src/views/DevComponentsView.vue`
  - **功能**：展示所有面板组件在模拟数据下的渲染效果，用于发现和调试组件问题
  - **布局**：三栏设计（左侧测试用例列表 / 中间组件展示区 / 右侧日志面板）
  - **布局密度切换**：紧凑(compact) / 均衡(balanced) / 宽松(spacious)，与 `panelStore.sizePreset` 同步
  - **组件检查器**：点击眼睛图标查看组件的 UIBlock、DataBlock、Props、Options 完整数据
- **Mock 数据生成器** - `frontend/src/features/dev/mockDataGenerator.ts`
  - 为 17 种组件生成标准化测试数据（包括核心组件：ListPanel、StatisticCard、LineChart、BarChart、PieChart、Table、ImageGallery、MediaCardGrid，以及原子化组件：CountCard、ProgressBar、QuoteCard、ComparisonCard、AuthorCard、TagCloud、TimelineCard、HeatmapCalendar，以及监控组件：ServiceStatus）
  - 包含边界情况测试（空数据、大量数据、特殊字符）
  - 内置 DevLogger 日志系统，支持 debug/info/warn/error 级别
- **日志面板** - `frontend/src/features/dev/components/DevLogPanel.vue`
  - 实时显示组件加载、渲染过程的调试日志
  - 支持按级别过滤、自动滚动、展开详情
- **Props 命名规范**：所有 mock 数据使用 snake_case（如 `title_field`、`value_field`），与 `componentManifest.ts` 保持一致
- **ComponentInspector** - `frontend/src/features/panel/components/ComponentInspector.vue` 用于显示组件调试信息
  - **设计规范**：完全遵循 QueryCard 的设计语言（`bg-background/95`、`border-border/30`、shadcn-vue 组件）
  - **展示内容**：组件基础信息（类型、ID、标题、置信度）、数据块信息（数据源、记录数、路由）、数据字段 Schema、Props/Options/Raw JSON
  - **交互方式**：Tab 式导航（概览、Props、Options、Raw JSON）、居中模态对话框（`max-w-5xl`、`max-h-90vh`）
- **组件点击支持** - `DynamicBlockRenderer.vue` 在开发者模式下支持点击组件 header 触发 `inspect-component` 事件
  - 事件传递链：DynamicBlockRenderer → PanelBoard → PanelWorkspace → MainView
  - 开发者模式视觉反馈：显示"🔧 DEV"徽章、边框高亮（`border-primary/30`）、悬停发光效果
