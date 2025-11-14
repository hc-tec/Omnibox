# 研究模式重复请求问题修复验证指南

## 问题回顾

**核心问题**：用户在主页面启动研究后点击卡片进入详情页时，所有已有的研究进度数据被清空，并且发送了新的重复请求，导致后端重新开始研究，用户丢失所有进度。

## 解决方案架构

### 1. 全局 WebSocket 连接管理器

创建了 `useResearchWebSocketManager.ts`，实现：

- **连接池管理**：`Map<taskId, Connection>` - 全局共享连接
- **请求状态追踪**：`Map<taskId, boolean>` - 防止重复发送
- **关键方法**：
  - `sendResearchRequestOnce()` - 带去重保护的请求发送
  - `hasRequestSent()` - 检查是否已发送请求
  - `disconnectAndCleanup()` - 安全清理连接
  - `cleanupAllConnections()` - 应用级清理

### 2. 主页面改造（MainView.vue）

- 使用全局管理器创建/复用连接
- 通过 `sendResearchRequestOnce()` 发送请求（自动去重）
- 删除任务时调用 `disconnectAndCleanup()`
- 组件卸载时调用 `cleanupAllConnections()`

### 3. 详情页面智能初始化（ResearchView.vue）

**关键逻辑**：
```typescript
// 检查是否已有研究数据（可能从主页面跳转过来）
const hasExistingData = store.state.task_id === props.taskId && store.state.steps.length > 0;

if (hasExistingData) {
  console.log("[ResearchView] 检测到已有研究数据，复用现有数据");
  // 不调用 initializeTask，保留已有数据
} else {
  console.log("[ResearchView] 首次打开研究页面，初始化新任务");
  store.initializeTask(props.taskId, resolvedQuery);
}
```

**请求去重保护**：
```typescript
watch(wsConnected, (connected) => {
  if (connected && store.state.query) {
    // 检查是否已经发送过研究请求
    if (hasRequestSent()) {
      console.log("[ResearchView] 研究请求已发送（可能在主页面），复用现有连接");
      return; // ← 跳过重复请求！
    }

    console.log("[ResearchView] WebSocket 已连接，发送研究请求");
    sendResearchRequestOnce({
      query: store.state.query,
      use_cache: true,
    });
  }
});
```

**导航回退保护**：
```typescript
async function handleBackToMain() {
  await router.push({ name: "Main" });
  // 不调用 disconnect() - 主页面可能还在使用连接
  // 不调用 store.reset() - 保留数据供后续查看
}
```

## 验证步骤

### 步骤 1：启动研究任务

1. 在主页面命令栏输入复杂查询（例如："分析比特币和以太坊的价格走势"）
2. **预期行为**：
   - 出现研究卡片（状态：processing）
   - 控制台输出：
     ```
     [MainView] 后端识别为研究模式，启动 WebSocket 连接, taskId: task-xxx
     [WebSocketManager] 创建新连接: task-xxx
     [WebSocketManager] 首次发送研究请求: task-xxx
     ```
3. **验证点**：研究卡片开始显示执行步骤和预览数据

### 步骤 2：点击卡片进入详情页（研究进行中）

1. 在研究还在进行时，点击研究卡片
2. **预期行为**：
   - 跳转到详情页 `/research/task-xxx`
   - **已有的步骤和数据面板全部可见**
   - 控制台输出：
     ```
     [ResearchView] Mounted with taskId: task-xxx
     [ResearchView] 检测到已有研究数据，复用现有数据
     [WebSocketManager] 复用现有连接: task-xxx
     [ResearchView] 研究请求已发送（可能在主页面），复用现有连接
     ```
3. **验证点**：
   - ✅ 左侧上下文面板显示已有的执行步骤
   - ✅ 右侧数据面板显示已生成的预览卡片
   - ✅ 控制台**没有**"首次发送研究请求"日志
   - ✅ 后端**没有**收到新的 research 请求

### 步骤 3：返回主页面再次进入

1. 点击"返回主界面"按钮
2. 再次点击同一研究卡片
3. **预期行为**：
   - 再次进入详情页
   - 所有数据仍然保留
   - 控制台输出相同的"复用现有数据"日志
4. **验证点**：数据持久化，无重复请求

### 步骤 4：等待研究完成后进入

1. 等待研究任务完成（卡片状态变为 completed）
2. 点击已完成的卡片
3. **预期行为**：
   - 进入详情页查看完整报告
   - 任务状态保持 completed，不会变为 processing
   - 控制台输出：
     ```
     [ResearchView] 检测到已有研究数据，复用现有数据
     [WebSocketManager] 复用现有连接: task-xxx
     ```
4. **验证点**：
   - ✅ 可以查看完整的最终报告
   - ✅ 所有历史步骤和数据可见
   - ✅ 没有重新发起研究

### 步骤 5：删除任务

1. 在主页面点击研究卡片的删除按钮
2. **预期行为**：
   - 卡片消失
   - 控制台输出：
     ```
     [WebSocketManager] 断开并清理连接: task-xxx
     ```
3. **验证点**：连接被正确清理，资源释放

## 关键控制台日志对比

### ✅ 正确流程（修复后）

**主页面启动研究**：
```
[MainView] 后端识别为研究模式，启动 WebSocket 连接
[WebSocketManager] 创建新连接: task-123
[MainView] 发送研究请求（带去重保护）
[WebSocketManager] 首次发送研究请求: task-123
```

**点击进入详情页**：
```
[ResearchView] Mounted with taskId: task-123
[ResearchView] 检测到已有研究数据，复用现有数据  ← 关键！
[WebSocketManager] 复用现有连接: task-123          ← 关键！
[ResearchView] 研究请求已发送（可能在主页面），复用现有连接  ← 关键！
```

### ❌ 错误流程（修复前）

**点击进入详情页**：
```
[ResearchView] Mounted with taskId: task-123
[ResearchView] 首次打开研究页面，初始化新任务  ← 错误：清空数据！
[WebSocketManager] 创建新连接: task-123          ← 错误：重复连接！
[WebSocketManager] 首次发送研究请求: task-123    ← 错误：重复请求！
```

## 边界情况验证

### 情况 1：直接通过 URL 访问详情页（无已有数据）

1. 手动在浏览器地址栏输入 `/research/task-new?query=测试查询`
2. **预期行为**：
   - 检测到无已有数据（`hasExistingData = false`）
   - 调用 `initializeTask()` 初始化新任务
   - 创建新连接并发送请求
3. **控制台输出**：
   ```
   [ResearchView] 首次打开研究页面，初始化新任务
   [WebSocketManager] 创建新连接: task-new
   [WebSocketManager] 首次发送研究请求: task-new
   ```

### 情况 2：多个研究任务并行

1. 启动研究任务 A
2. 启动研究任务 B
3. 分别点击进入详情页
4. **预期行为**：
   - 每个任务有独立的连接和数据
   - `activeConnections` Map 中有两个条目
   - 互不干扰

### 情况 3：应用关闭/刷新

1. 有活跃研究任务时刷新页面或关闭应用
2. **预期行为**：
   - `onBeforeUnmount` 触发
   - `cleanupAllConnections()` 被调用
   - 所有连接正确关闭
   - 控制台输出：
     ```
     [WebSocketManager] 清理所有连接
     ```

## 后续数据库集成准备

当后端接入数据库持久化研究数据时，需要做的调整：

1. **详情页数据加载**：
   ```typescript
   if (hasExistingData) {
     // 当前：复用内存中的数据
     // 未来：从 researchViewStore 加载（内部从 API 获取）
   }
   ```

2. **全局管理器无需改动**：
   - 连接池和请求去重逻辑保持不变
   - 仍然确保不会重复发送研究请求

3. **后端 API 新增**：
   - `GET /api/v1/research/{task_id}` - 获取任务详情
   - `GET /api/v1/research/{task_id}/steps` - 获取执行步骤
   - `GET /api/v1/research/{task_id}/previews` - 获取预览数据

## 涉及文件清单

### 后端文件
- ✅ `api/schemas/responses.py` - 添加了流式研究相关字段
- ✅ `api/controllers/chat_controller.py` - 传递流式研究元数据

### 前端核心文件
- ✅ `frontend/src/composables/useResearchWebSocketManager.ts` - 全局连接管理器（新建）
- ✅ `frontend/src/views/MainView.vue` - 使用全局管理器
- ✅ `frontend/src/views/ResearchView.vue` - 智能初始化 + 请求去重
- ✅ `frontend/src/features/research/stores/researchStore.ts` - 任务状态管理
- ✅ `frontend/src/shared/types/panel.ts` - TypeScript 类型定义

### 配置文件
- ✅ `frontend/.env.example` - 移除重复的 WebSocket 端点
- ✅ `frontend/.env` - 移除重复的 WebSocket 端点

## 成功标准

- ✅ 主页面启动研究，详情页打开时所有已有数据可见
- ✅ 控制台日志显示"复用现有数据"和"复用现有连接"
- ✅ 后端不会收到重复的研究请求
- ✅ 返回主页面再次进入，数据仍然保留
- ✅ 完成的研究任务可以随时查看
- ✅ 删除任务时连接正确清理
- ✅ 所有 Python 文件通过语法检查
- ✅ 前端 TypeScript 无类型错误

---

**修复完成时间**：2025-11-15
**相关文档**：`.agentdocs/workflow/251115-debugging-research-flow.md`
