# 研究模式前端调试指南

**创建时间**：2025-11-15
**状态**：调试中
**相关任务**：`251115-websocket-unification-and-p0p1-fixes.md`

---

## 问题描述

**症状**：
- 后端正常执行（REST API 返回 `requires_streaming: true`，WebSocket 发送消息）
- 前端没有任何反应（没有研究卡片，没有界面更新）

**预期行为**：
1. 用户输入研究查询后，前端检测到 `requires_streaming: true`
2. 前端创建研究任务并显示研究卡片（status=processing）
3. 前端启动 WebSocket 连接到 `/api/v1/chat/stream`
4. 前端接收并显示研究进度更新

---

## 调试步骤

### 1. 使用调试页面测试后端

打开浏览器访问：`http://localhost:5173/debug-research.html`

**测试内容**：
1. 点击"测试 POST /api/v1/chat" - 验证 REST API 返回 `requires_streaming: true`
2. 点击"连接并发送研究查询" - 验证 WebSocket 正常工作

**预期结果**：
- REST API 应该返回：
  ```json
  {
    "metadata": {
      "requires_streaming": true,
      "websocket_endpoint": "/api/v1/chat/stream",
      "suggested_action": "使用 WebSocket 连接获取流式研究进度"
    }
  }
  ```
- WebSocket 应该收到至少 10 条消息（research_start, research_step, research_panel, etc.）

---

### 2. 检查浏览器控制台日志

启动前端应用后，打开浏览器开发者工具（F12），输入测试查询：

```
我想看看bilibili中，up主行业101的视频投稿，同时呢，帮我分析一下这个up主最近做的视频方向是什么
```

**查看控制台日志，按顺序检查**：

#### 2.1 提交阶段
```
[usePanelActions] submit payload: {...}
[usePanelActions] response: {...}
[usePanelActions] response.metadata: {...}
[usePanelActions] requires_streaming: true  ← 应该是 true
[usePanelActions] requiresStreaming (boolean): true  ← 应该是 true
```

**检查点**：
- ✅ 如果 `requires_streaming: true` → 继续下一步
- ❌ 如果 `requires_streaming: undefined/false` → **后端问题**，检查 `api/schemas/responses.py`

#### 2.2 任务创建阶段
```
[usePanelActions] 创建研究任务 (processing 状态)
[usePanelActions] 任务已创建, taskId: task-1731654321-abc123
[usePanelActions] researchStore.activeTasks: [...]  ← 应该包含新创建的任务
```

**检查点**：
- ✅ 如果 `activeTasks` 包含新任务 → 继续下一步
- ❌ 如果 `activeTasks` 为空 → **Store 问题**，检查 `researchStore.ts`

#### 2.3 WebSocket 连接阶段
```
[MainView] handleCommandSubmit: {...}
[MainView] submit result: {...}
[MainView] requiresStreaming: true
[MainView] taskId: task-1731654321-abc123
[MainView] 启动 WebSocket 连接, taskId: task-1731654321-abc123
```

**检查点**：
- ✅ 如果看到"启动 WebSocket 连接" → 继续下一步
- ❌ 如果看到"未启动 WebSocket 连接" → **逻辑问题**，检查 `MainView.vue:229-236`

#### 2.4 WebSocket 建立连接
```
[MainView] connectResearchWebSocket: {taskId: "...", query: "..."}
[MainView] 创建 WebSocket 连接
[MainView] WebSocket 连接已保存到 activeWebSocketConnections
[MainView] 调用 wsConnection.connect()
[MainView] WebSocket 连接状态变化: true
[MainView] 发送研究请求
```

**检查点**：
- ✅ 如果看到"连接状态变化: true" → WebSocket 连接成功
- ❌ 如果没有"连接状态变化"或一直是 false → **WebSocket 连接失败**

---

### 3. 检查研究卡片渲染

在浏览器控制台运行：

```javascript
// 检查 activeTasks
const tasks = document.querySelector('.research-cards-grid');
console.log('研究卡片容器:', tasks);
console.log('子元素数量:', tasks?.children.length);

// 如果使用 Vue DevTools，可以查看组件状态
// 1. 安装 Vue DevTools 扩展
// 2. 打开 Vue DevTools
// 3. 查找 MainView 组件
// 4. 检查 activeTasks 计算属性
```

**检查点**：
- ✅ 如果 `tasks.children.length > 0` → 研究卡片已渲染
- ❌ 如果 `tasks === null` 或 `children.length === 0` → **渲染问题**

---

### 4. 可能的问题和解决方案

#### 问题1：`requires_streaming` 字段丢失
**症状**：控制台显示 `requires_streaming: undefined`

**原因**：`ResponseMetadata` 类缺少字段定义

**解决方案**：
```bash
# 检查文件
cat api/schemas/responses.py | grep requires_streaming

# 应该看到：
# requires_streaming: Optional[bool] = Field(...)
```

#### 问题2：任务创建成功但 `activeTasks` 为空
**症状**：日志显示任务已创建，但 `activeTasks: []`

**原因**：`activeTasks` computed 过滤条件不匹配

**解决方案**：
```typescript
// 检查 src/features/research/stores/researchStore.ts:32-37
const activeTasks = computed(() =>
  Array.from(tasks.value.values()).filter(
    t =>
      t.status === 'processing' ||  // ← 应该包含 processing
      t.status === 'human_in_loop' ||
      t.status === 'idle'
  )
);
```

#### 问题3：WebSocket 连接失败
**症状**：没有看到"连接状态变化: true"

**原因**：
1. WebSocket URL 错误
2. 后端 WebSocket 服务未启动
3. 防火墙阻止连接

**解决方案**：
```bash
# 检查后端 WebSocket 端点是否正常
python test_research_flow.py

# 应该看到：
# ✅ WebSocket 连接成功
# ✅ 收到 10 条消息
```

#### 问题4：研究卡片不显示
**症状**：`activeTasks` 有数据，但页面没有渲染

**原因**：
1. CSS 问题（display: none）
2. 组件注册问题
3. Vue 响应式失效

**解决方案**：
```javascript
// 在控制台运行
const grid = document.querySelector('.research-cards-grid');
console.log('Grid 样式:', window.getComputedStyle(grid).display);

// 应该是 'grid'，如果是 'none' 说明 CSS 问题
```

---

## 关键修复记录

### ✅ 修复1：前端 TypeScript 类型定义缺失（2025-11-15）

**问题**：前端 `PanelResponse` 接口缺少后端新增的流式研究字段，导致 `requires_streaming` 等字段无法正确传递。

**修复**：在 `frontend/src/shared/types/panel.ts` 的 `PanelResponse.metadata` 中添加：
```typescript
// 流式研究相关字段（后端架构重构 v2.0 新增）
requires_streaming?: boolean | null;
websocket_endpoint?: string | null;
suggested_action?: string | null;
```

**验证**：检查浏览器控制台日志，应该能看到 `requires_streaming: true`

---

### ✅ 修复2：研究完成后卡片立即消失（2025-11-15）

**问题**：研究完成后，卡片从主页面立即消失，用户无法查看结果或进入研究页面。

**根本原因**：`activeTasks` 计算属性不包含 `completed` 状态的任务。

**修复**：
1. **`frontend/src/features/research/stores/researchStore.ts:32-53`** - 修改 `activeTasks` 过滤逻辑
   ```typescript
   const activeTasks = computed(() =>
     Array.from(tasks.value.values()).filter(
       t =>
         t.status === 'processing' ||
         t.status === 'human_in_loop' ||
         t.status === 'idle' ||
         t.status === 'completed'  // ← 添加 completed 状态
     ).sort((a, b) => {
       // 按状态优先级排序：processing > human_in_loop > idle > completed
       // 相同状态按更新时间倒序（最新的在前）
     })
   );
   ```

2. **`frontend/src/features/research/components/ResearchLiveCard.vue:2-6`** - 让卡片可点击
   ```vue
   <Card
     class="research-live-card"
     :class="[statusClass, clickableClass]"
     @click="handleCardClick"
   >
   ```
   - completed 和 processing 状态的卡片可点击进入研究页面
   - 添加 `cursor-pointer hover:shadow-lg` 样式

3. **`frontend/src/views/MainView.vue:266-270`** - 修复打开任务逻辑
   ```typescript
   // 只有 idle 状态的任务才需要改为 processing
   // completed 和 processing 状态的任务直接打开查看
   if (task.status === 'idle') {
     researchStore.markTaskProcessing(taskId);
   }
   ```

**验证**：
- 研究完成后，卡片保留在主页面（绿色边框，"已完成" 状态）
- 点击卡片可以进入研究详情页面
- 用户可以手动点击"删除"按钮移除卡片

---

### ✅ 修复3：移除自动跳转，由用户控制何时进入研究页面（2025-11-15）

**问题**：即使用户在命令面板主动选择"研究"模式，也会立即自动跳转到研究页面，用户失去控制权。

**期望行为**：无论哪种方式启动研究（用户主动选择 / 后端自动检测），都应该：
1. 在主页面显示研究卡片（处理中状态）
2. 不自动跳转
3. 用户点击卡片时才进入研究详情页面

**修复**：`frontend/src/views/MainView.vue:221-228`
```typescript
// 修改前：用户选择"研究"模式会立即跳转
if (payload.mode === "research") {
  const taskId = researchStore.createTask(payload.query, payload.mode);
  await router.push({ path: `/research/${taskId}` }); // ❌ 自动跳转
  return;
}

// 修改后：仅创建卡片和启动 WebSocket，不自动跳转
if (payload.mode === "research") {
  const taskId = researchStore.createTask(payload.query, payload.mode);
  persistResearchTaskQuery(taskId, payload.query);
  connectResearchWebSocket(taskId, payload.query); // ✅ 仅启动连接
  return; // ✅ 停留在主页面
}
```

**验证**：
- 在命令面板选择"研究"模式后，停留在主页面
- 主页面显示研究卡片（蓝色边框，"处理中" 状态）
- 点击研究卡片才进入研究详情页面

**统一行为**：
- **用户主动选择"研究"模式** → 主页面显示卡片，不跳转 ✅
- **后端自动检测为研究模式** → 主页面显示卡片，不跳转 ✅
- **用户点击研究卡片** → 进入研究详情页面 ✅

---

### ✅ 修复4：解决重复请求问题，实现连接共享（2025-11-15）

**问题**：用户从主页面点击研究卡片进入详情页面后，详情页面会：
1. 清空所有已有的研究数据
2. 重新创建 WebSocket 连接
3. 重新发送研究请求
4. 导致后端重新开始研究，浪费资源且用户体验极差

**根本原因**：
1. `ResearchView.vue` 每次 mount 都调用 `store.initializeTask()`，这会清空所有数据
2. `ResearchView.vue` 创建新的 WebSocket 连接，不复用主页面的连接
3. `ResearchView.vue` 连接成功后无条件发送研究请求

**解决方案**：

**1. 创建全局 WebSocket 连接管理器**

**文件**：`frontend/src/composables/useResearchWebSocketManager.ts`（新建）

- 维护全局连接池：`Map<taskId, WebSocketConnection>`
- 维护请求状态：`Map<taskId, boolean>`（记录是否已发送请求）
- 提供 `sendResearchRequestOnce()` 方法：只有首次调用才发送，后续调用忽略
- 提供 `hasRequestSent()` 方法：检查是否已发送请求
- 提供 `disconnectAndCleanup()` 方法：断开并清理连接

**2. 修改 MainView.vue 使用全局管理器**

**修改**：`frontend/src/views/MainView.vue`

```typescript
// 修改前：每次创建新连接
const wsConnection = useResearchWebSocket({ taskId });

// 修改后：使用全局管理器（自动处理复用）
const wsManager = useResearchWebSocketManager({ taskId });
wsManager.sendResearchRequestOnce({ query, use_cache: true });
```

**3. 修改 ResearchView.vue 智能初始化**

**修改1**：检查是否已有数据，避免清空

```typescript
// 修改前：无条件初始化，清空所有数据
store.initializeTask(props.taskId, resolvedQuery);

// 修改后：智能初始化
const hasExistingData = store.state.task_id === props.taskId && store.state.steps.length > 0;

if (hasExistingData) {
  console.log("[ResearchView] 检测到已有研究数据，复用现有数据");
  // 不调用 initializeTask，保留已有数据
} else {
  console.log("[ResearchView] 首次打开研究页面，初始化新任务");
  store.initializeTask(props.taskId, resolvedQuery);
}
```

**修改2**：使用全局管理器，避免重复请求

```typescript
// 修改前：无条件发送研究请求
watch(wsConnected, (connected) => {
  if (connected && store.state.query) {
    sendResearchRequest({ query: store.state.query, use_cache: true });
  }
});

// 修改后：检查是否已发送
watch(wsConnected, (connected) => {
  if (connected && store.state.query) {
    if (hasRequestSent()) {
      console.log("[ResearchView] 研究请求已发送（可能在主页面），复用现有连接");
      return;
    }
    sendResearchRequestOnce({ query: store.state.query, use_cache: true });
  }
});
```

**修改3**：返回主页面时不断开连接

```typescript
// 修改前：返回主页面时断开连接
async function handleBackToMain() {
  disconnect();  // ← 会断开主页面正在使用的连接！
  await router.push({ name: "Main" });
  store.reset();  // ← 会清空研究数据！
}

// 修改后：保持连接和数据
async function handleBackToMain() {
  // 不断开连接，不清空数据
  await router.push({ name: "Main" });
}
```

**验证**：
1. 在主页面启动研究（auto 或 research 模式）
2. 研究进行中，点击卡片进入详情页面
3. 详情页面应显示已有的研究进度（steps、panels、analyses）
4. **不应该重新发送研究请求**
5. 返回主页面，再次进入详情页面，数据仍然保留

**控制台日志验证**：
```
[MainView] 发送研究请求（带去重保护）
[WebSocketManager] 首次发送研究请求: task-xxx
# 用户点击卡片进入详情页面
[ResearchView] 检测到已有研究数据，复用现有数据
[WebSocketManager] 复用现有连接: task-xxx
[ResearchView] 研究请求已发送（可能在主页面），复用现有连接
# ✅ 没有重新发送请求！
```

**相关文件**：
- `frontend/src/composables/useResearchWebSocketManager.ts` - 全局连接管理器（新建）
- `frontend/src/views/MainView.vue:172-200` - 使用全局管理器
- `frontend/src/views/ResearchView.vue:112-127` - 使用全局管理器
- `frontend/src/views/ResearchView.vue:184-200` - 智能初始化
- `frontend/src/views/ResearchView.vue:198-214` - 防重复请求逻辑

---

## 已添加的调试日志位置

### 前端文件
1. **`frontend/src/views/MainView.vue`**
   - `handleCommandSubmit` (Line 210-237)
   - `connectResearchWebSocket` (Line 175-216)

2. **`frontend/src/features/panel/usePanelActions.ts`**
   - `submit` (Line 31-74)

3. **`frontend/src/shared/types/panel.ts`**
   - `PanelResponse.metadata` - 添加流式研究字段

### 关键日志前缀
- `[MainView]` - MainView.vue 中的日志
- `[usePanelActions]` - usePanelActions.ts 中的日志

---

## 完整的工作流程

```
用户输入查询
  ↓
CommandPalette 调用 handleCommandSubmit
  ↓
usePanelActions.submit 调用 panelStore.fetchPanel
  ↓
panelStore 调用 REST API /api/v1/chat
  ↓
REST API 返回 {metadata: {requires_streaming: true}}
  ↓
usePanelActions 检查 requiresStreaming === true
  ↓
usePanelActions 调用 researchStore.createTask (status='processing')
  ↓
返回 {response, requiresStreaming: true, taskId}
  ↓
MainView 检查 result.requiresStreaming && result.taskId
  ↓
MainView 调用 connectResearchWebSocket(taskId, query)
  ↓
useResearchWebSocket 创建 WebSocket 连接
  ↓
WebSocket 连接成功后发送 {query, mode: "research", task_id}
  ↓
后端 chat_stream.py 接收消息并路由到研究模式
  ↓
后端开始发送 research_* 消息
  ↓
前端 useResearchWebSocket 接收消息并更新 researchViewStore
  ↓
researchViewStore 更新触发组件重新渲染
  ↓
研究卡片显示在主页面
```

---

## 清理调试日志

当问题解决后，移除以下日志：
- [ ] `frontend/src/views/MainView.vue` (所有 console.log)
- [ ] `frontend/src/features/panel/usePanelActions.ts` (所有 console.log)

或者使用条件编译：
```typescript
const DEBUG = import.meta.env.DEV;
if (DEBUG) console.log('[MainView] ...');
```

---

## 相关文件

- `.agentdocs/workflow/251115-websocket-unification-and-p0p1-fixes.md` - 主要修复文档
- `frontend/debug-research.html` - 独立调试页面
- `test_research_flow.py` - 后端测试脚本
