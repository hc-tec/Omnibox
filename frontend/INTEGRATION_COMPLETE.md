# LangGraph Agents 前后端集成完成报告

## ✅ 已完成的工作

### 1. 后端集成（已完成）

#### 1.1 ResearchService 增强
- **文件**：`services/research_service.py`
- **内容**：引入 `ResearchTaskHub` 统一管理任务上下文/监听队列/人工请求，支持 `client_task_id` 透传、保存最新 LangGraph state，并在收到 ActionInbox 回复后自动续写。

#### 1.2 研究专用 API
- **文件**：`api/controllers/research_controller.py`, `api/app.py`
- **端点**：
  - `GET /api/v1/research/stream`（WebSocket），推送 `step/human_in_loop/human_response_ack/complete/cancelled`
  - `POST /api/v1/research/human-response`（ActionInbox 回复）
  - `POST /api/v1/research/cancel`
- **说明**：三组接口共用 ResearchService，上线前需配置 `CHAT_SERVICE_MODE=production` 以启用真实服务。

#### 1.3 ChatService / Schema 同步
- **文件**：`services/chat_service.py`, `api/schemas/responses.py`, `api/controllers/chat_controller.py`
- **改动**：
  - `ChatRequest` 新增 `client_task_id`
  - `ChatResponse.metadata` 增加 `task_id/thread_id/total_steps/data_stash_count`
  - `_handle_research` 会把 `client_task_id` 作为 ResearchService 的任务 ID，metadata 默认回填

#### 1.4 ResearchTaskHub
- **文件**：`services/research_task_hub.py`
- **功能**：持久化任务历史、人工请求、人工回复、最近 LangGraph state，并向 WebSocket 监听者推送事件；供 REST 与 WebSocket 共享。

#### 1.5 测试/工具
- **新增**：`tests/services/test_research_task_hub.py`（上下文事件）与 `tests/services/test_chat_service.py`（client_task_id 透传）。
- **运行**：`pytest tests/services/test_chat_service.py tests/services/test_research_task_hub.py -q`

------

### 2. 前端集成（已完成）

#### 2.1 请求参数与类型
- **文件**：`frontend/src/shared/types/panel.ts`, `frontend/src/services/panelApi.ts`, `frontend/src/store/panelStore.ts`, `frontend/src/features/panel/usePanelActions.ts`
- **内容**：REST / WebSocket 请求均支持 `mode` 与 `client_task_id`，研究模式下会把任务 ID 传给后端，metadata 中回传 `task_id` 供 UI 显示。

#### 2.2 研究态管理
- **文件**：`frontend/src/features/research/stores/researchStore.ts`, `frontend/src/features/research/services/researchStream.ts`
- **内容**：
  - 引入 `ResearchStreamClient`，在创建研究任务时立刻连接 `/api/v1/research/stream?task_id=...`
  - `researchStore` 统一处理 `step/human_in_loop/human_response_ack/complete/cancelled` 事件，自动更新 Pinia 状态并在任务终止时回收 WebSocket

#### 2.3 组件更新
- **App.vue**：提交研究查询时创建 `taskId`，将其作为 `client_task_id` 发往 REST；任务完成或出错自动调用 store 更新
- **ResearchLiveCard.vue**：新增 `task_id/thread_id/total_steps/data_stash_count` 调试信息区域
- **ActionInbox.vue**：按钮行为与 `researchApi` 接口打通，支持发送人工回复、取消任务，并显示加载状态

#### 2.4 文档 / 调试
- `researchTypes.ts`、`ResearchResponse.metadata` 同步新增字段用于 TS 类型提示
- `frontend/src/features/research/services/researchApi.ts` 读取 `VITE_API_BASE` 并暴露 `submitHumanResponse/cancelTask`

------

### 3. 研究功能组件（已创建）

#### 3.1 QueryModeSelector（已集成到 CommandBar）
- **集成方式**: 直接内嵌到 CommandBar.vue
- **功能**: 三个模式按钮（自动/简单/研究）
- **图标**: Zap(自动) / Search(简单) / Brain(研究)

#### 3.2 ResearchLiveCard
- **文件**: `frontend/src/features/research/components/ResearchLiveCard.vue`
- **功能**:
  - 动态显示任务状态（processing/human_in_loop/completed/error）
  - 执行步骤列表（带进度图标）
  - 人机交互提示
  - 最终报告显示
  - 删除按钮（完成或错误状态）

#### 3.3 ActionInbox
- **文件**: `frontend/src/features/research/components/ActionInbox.vue`
- **功能**:
  - FAB 按钮（右下角魔棒图标）
  - 徽章显示待处理数量
  - 侧边栏（从右滑入）
  - 用户回复输入框
  - Ctrl+Enter 快捷键提交

#### 3.4 researchStore
- **文件**: `frontend/src/features/research/stores/researchStore.ts`
- **功能**:
  - 任务状态管理
  - computed 属性（activeTasks, pendingHumanTasks）
  - 任务 CRUD 操作

#### 3.5 researchApi
- **文件**: `frontend/src/features/research/services/researchApi.ts`
- **功能**:
  - `submitQuery()` - 提交研究查询
  - `submitHumanResponse()` - 提交人工响应（待实现）
  - `cancelTask()` - 取消任务（待实现）

#### 3.6 researchTypes
- **文件**: `frontend/src/features/research/types/researchTypes.ts`
- **类型**:
  - `QueryMode` (从 panel.ts 导入)
  - `ResearchTaskStatus`
  - `LangGraphNode`
  - `ExecutionStep`
  - `ResearchTask`
  - `ResearchResponse`

---

## 🎯 架构设计

### 数据流向

```
User Input (CommandBar)
  ↓ (select mode: auto/simple/research)
CommandPalette
  ↓ (emit submit with mode)
App.vue handleCommandSubmit()
  ↓ (call submit(query, mode))
usePanelActions.submit()
  ↓ (call fetchPanel(query, datasource, snapshot, mode))
panelStore.fetchPanel()
  ↓ (call requestPanel with mode)
panelApi.requestPanel()
  ↓ (HTTP POST /api/v1/chat with { query, mode, ... })
Backend API
  ↓ (route based on mode)
ChatService.chat()
  ├─ mode="auto" → IntentService → DataQueryService
  ├─ mode="simple" → DataQueryService
  └─ mode="research" → ResearchService
      ↓ (execute LangGraph workflow)
      ↓ (stream execution steps)
      ↓ (return research result)
Frontend receives response
  ├─ mode="simple/auto" → Update PanelWorkspace
  └─ mode="research" → Create ResearchTask → Update ResearchLiveCard
```

### 组件层次

```
App.vue
├── CommandPalette
│   └── CommandBar (with inline mode selector)
├── PanelWorkspace (existing panels)
├── ResearchLiveCard Grid (new, above workspace)
│   └── ResearchLiveCard × N (for active tasks)
└── ActionInbox (new, floating overlay)
    └── Sidebar with pending human tasks
```

---

## 📋 测试清单

### 前端测试（需要手动进行）

#### 1. 安装依赖
```bash
cd frontend
npm install lucide-vue-next
# 如果 Textarea 组件缺失，运行：
# npx shadcn-vue@latest add textarea
```

#### 2. 启动服务
```bash
# Terminal 1: 启动后端
cd D:\AIProject\omni
python -m api.app

# Terminal 2: 启动前端
cd frontend
npm run dev
```

#### 3. 功能测试

**测试 1: 模式选择器显示**
- [ ] 打开应用
- [ ] 点击 CMD 按钮或按 Ctrl+Space 唤醒 CommandPalette
- [ ] 确认看到三个模式按钮：自动/简单/研究
- [ ] 确认图标正确显示（闪电/搜索/大脑）
- [ ] 点击不同模式，确认选中状态切换正常

**测试 2: 简单查询（existing功能，确保未破坏）**
- [ ] 选择"简单"或"自动"模式
- [ ] 输入查询：`bilibili热搜`
- [ ] 点击"生成面板"
- [ ] 确认：直接显示 Panel，无 ResearchLiveCard

**测试 3: 研究模式（new功能）**
- [ ] 选择"研究"模式
- [ ] 输入查询：`分析GitHub上最热门的Python项目`
- [ ] 点击"生成面板"
- [ ] 确认：
  - [ ] PanelWorkspace 上方出现 ResearchLiveCard
  - [ ] 卡片显示"处理中"状态
  - [ ] 卡片显示查询文本
  - [ ] 卡片边框为蓝色（processing）
  - [ ] 卡片显示执行步骤（如果后端返回）

**测试 4: Action Inbox**
- [ ] 查看右下角是否有魔棒按钮
- [ ] 点击魔棒按钮
- [ ] 确认侧边栏从右侧滑入
- [ ] 如果没有待处理任务，显示"没有待处理的任务"

**测试 5: 研究任务生命周期**
- [ ] 创建研究任务
- [ ] 观察状态变化（processing → completed/error）
- [ ] 完成后点击"删除"按钮
- [ ] 确认卡片消失

**测试 6: 响应式布局**
- [ ] 调整浏览器窗口大小
- [ ] 确认 ResearchLiveCard 网格正确响应（1/2/3列）
- [ ] 确认模式选择器在小屏幕上不换行

---

### 后端测试

#### 已修复的问题
- ✅ MockChatService 签名更新（添加 layout_snapshot 和 mode）
- ✅ Pydantic v2 兼容性（regex → pattern）
- ✅ ChatRequest schema 验证

#### 运行测试
```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行 LangGraph Agents 测试
python -m pytest tests/langgraph_agents/ -v

# 运行 API 测试
python -m pytest tests/api/ -v
```

---

## ⚠️ 已知限制和待实现功能

### 当前不支持的功能
1. **任务历史持久化** - 当前任务上下文保存在内存，刷新页面或后端重启后将丢失，可在后续落地数据库/IndexedDB
2. **研究报告导出** - 暂未提供 Markdown/PDF 导出入口
3. **多模型调度** - 仍依赖单一 LLM 配置，后续可根据任务动态选择不同 provider

### 边界情况处理
1. **并发任务** - Pinia store 与 WebSocket 客户端支持多任务并行，每个 taskId 维护独立连接
2. **错误处理** - REST/WebSocket 返回 error 时会同步到卡片与 ActionInbox，便于定位
3. **空状态** - 无任务时隐藏 ResearchLiveCard 网格与 ActionInbox badge
4. **模式默认值** - CommandBar/CommandPalette 默认 `auto`，允许用户切换为 `simple` 或 `research`

---

## 🎨 设计决策

### 1. 最小侵入性集成
- 研究功能作为独立层叠加在现有 Panel 系统之上
- 不修改 PanelWorkspace 内部逻辑
- 保持向后兼容，现有功能零破坏

### 2. 类型复用
- `QueryMode` 定义在 `panel.ts`，研究模块通过 re-export 使用
- 避免类型重复定义

### 3. 模式选择器集成
- 直接内嵌到 CommandBar 而非独立组件
- 利用现有设计系统（shadcn-vue + Tailwind）
- 仅在展开状态显示，紧凑模式下隐藏

### 4. 状态管理分离
- ResearchStore 独立于 PanelStore
- 通过 computed 属性暴露必要数据
- 避免循环依赖

---

## 📚 相关文档

- **后端设计**: `.agentdocs/workflow/langgraph-agents-integration-plan.md`
- **后端使用**: `.agentdocs/workflow/langgraph-agents-integration-usage.md`
- **前端设计**: `docs/langgraph-agents-frontend-design.md`
- **前端实现**: `.agentdocs/workflow/langgraph-agents-frontend-implementation.md`
- **用户指南**: `frontend/RESEARCH_INTEGRATION_GUIDE.md`

---

## ✨ 下一步增强建议

### 高优先级
1. **实现 WebSocket 实时推送**
   - 后端：创建 `/api/v1/research/stream` endpoint
   - 前端：监听 WebSocket 消息更新 ResearchStore

2. **完成人机交互流程**
   - 后端：实现 `/api/v1/research/human-response` endpoint
   - 集成到 LangGraph 的 `wait_for_human` 节点

3. **错误恢复机制**
   - 任务失败后的重试逻辑
   - 断点续传支持

### 中优先级
4. **任务历史持久化**
   - LocalStorage 或 IndexedDB 存储
   - 历史任务查看界面

5. **UI 动画优化**
   - 卡片进入/退出动画
   - 步骤列表滚动效果
   - 加载骨架屏

6. **键盘快捷键**
   - 快速切换模式
   - 快速打开 Action Inbox

### 低优先级
7. **任务导出**
   - 导出研究报告为 Markdown/PDF
   - 分享研究结果

8. **高级配置**
   - 自定义研究步骤数
   - 选择不同 LLM 模型
   - 调整参数（temperature, max_tokens）

---

**当前状态**: ✅ 基础集成完成，前端可以开始测试！

**版本**: v1.0.0
**完成日期**: 2025-11-12
**负责人**: Claude Code (Sonnet 4.5)


