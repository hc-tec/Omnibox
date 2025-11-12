# LangGraph Agents 前端集成指南

## ✅ 已完成的工作

### 文件结构
```
frontend/src/features/research/
├── types/
│   └── researchTypes.ts          ✅ 类型定义
├── stores/
│   └── researchStore.ts          ✅ Pinia 状态管理
├── services/
│   └── researchApi.ts            ✅ API 服务
└── components/
    ├── QueryModeSelector.vue     ✅ 模式选择器
    ├── ResearchLiveCard.vue      ✅ 实时进度卡片
    └── ActionInbox.vue           ✅ 行动收件箱
```

---

## 📦 安装依赖

### 必须安装

```bash
cd frontend

# 安装图标库
npm install lucide-vue-next

# 安装 shadcn-vue 缺失的组件（如果需要）
npx shadcn-vue@latest add textarea
```

### 验证已有依赖

确保以下依赖已安装（应该已在 package.json 中）：
- `pinia` - 状态管理
- `axios` - HTTP 请求
- `@/components/ui/*` - shadcn-vue 组件

---

## 🔧 集成到 App.vue

### 方案 A：简单集成（最小修改）

在现有的聊天界面添加研究功能：

## 🧠 集成要点（App.vue）

1. 使用 useResearchStore() 在研究模式下生成 	askId，并把它作为 client_task_id 透传给 /api/v1/chat
2. esearchStore 在创建任务时会自动实例化 ResearchStreamClient，监听 /api/v1/research/stream?task_id=xxx
3. 当 REST 响应返回 metadata 时，根据 metadata.mode 决定是否进入研究流程

`	s
const handleCommandSubmit = async (payload: { query: string; mode: QueryMode }) => {
  let taskId: string | null = null;
  if (payload.mode === 'research') {
    taskId = researchStore.createTask(payload.query, payload.mode);
  }
  try {
    const response = await submit({ ...payload, client_task_id: taskId ?? undefined });
    if (taskId) {
      const metadata = response.metadata as ResearchResponse['metadata'] | undefined;
      if (metadata?.mode === 'research') {
        researchStore.completeTask(taskId, response.message, metadata);
      } else {
        researchStore.setTaskError(taskId, '服务器未返回研究元数据');
      }
    }
  } catch (error) {
    if (taskId) {
      researchStore.setTaskError(taskId, error instanceof Error ? error.message : '研究请求失败');
    }
    throw error;
  }
};
`

## 📨 ActionInbox
- 入口：rontend/src/features/research/components/ActionInbox.vue
- 调用：esearchApi.submitHumanResponse / esearchApi.cancelTask
- 收敛：WebSocket 推送 human_response_ack 后，store 会把任务重新标记为 processing

## 🔌 WebSocket 客户端
- rontend/src/features/research/services/researchStream.ts
- 默认地址：${VITE_API_BASE}/research/stream
- 事件类型：step、human_in_loop、human_response_ack、complete、error、cancelled
- 断线策略：任务完成/报错/取消时自动断开，防止资源泄露


---

## 🎯 使用方式

### 1. 简单查询（原有功能不变）

```typescript
// 用户输入："今天热榜"
// 选择模式："自动" 或 "简单"
// 结果：直接显示数据，无研究过程
```

### 2. 复杂研究（新功能）

```typescript
// 用户输入："分析最近一周GitHub上最热门的Python项目的特点和趋势"
// 选择模式："研究"
// 结果：
// 1. 出现 Live Card，显示实时进度
// 2. 执行步骤逐步更新
// 3. 如需人工输入，右下角魔棒按钮显示徽章 🪄 [1]
// 4. 点击魔棒，侧边栏滑出，显示 AI 提问
// 5. 用户回复后，研究继续
// 6. 完成后，Live Card 显示最终报告
```

---

## 🧪 测试步骤

### 1. 启动后端服务

```bash
# 在项目根目录
python -m api.app
```

后端应该输出：
```
初始化服务（模式：auto）...
初始化 ResearchService...
✓ ResearchService 初始化完成
✓ 服务初始化完成（production模式）
✓ 应用启动完成
```

### 2. 启动前端服务

```bash
cd frontend
npm run dev
```

### 3. 测试基本功能

1. **测试模式选择器**
   - 点击 "自动"、"简单"、"研究" 按钮
   - 确认按钮状态切换正常

2. **测试简单查询**
   - 输入："今天热榜"
   - 选择："简单"
   - 发送请求
   - 验证：直接返回结果，无 Live Card

3. **测试研究模式**
   - 输入："分析GitHub热门项目"
   - 选择："研究"
   - 发送请求
   - 验证：
     - ✅ 出现 Live Card
     - ✅ 显示处理状态
     - ✅ 显示执行步骤
     - ✅ 完成后显示报告

4. **测试 Action Inbox**
   - 右下角应该有魔棒按钮 🪄
   - 点击魔棒，侧边栏滑出
   - 如果有待处理任务，应显示徽章数字

---

## 🎨 样式自定义

所有组件使用 Tailwind CSS 和 shadcn-vue 主题，可以通过以下方式自定义：

### 修改主题色

```css
/* frontend/src/styles/globals.css */

:root {
  --primary: 你的颜色;
  --secondary: 你的颜色;
}
```

### 修改卡片样式

```vue
<!-- ResearchLiveCard.vue -->
<style scoped>
.research-live-card {
  /* 自定义样式 */
}
</style>
```

---

## ⚠️ 注意事项

### 1. 后端 API 兼容性

确保后端已经：
- ✅ 初始化 ResearchService（已完成）
- ✅ ChatService 支持 `mode` 参数（已完成）
- ✅ API endpoint 接受 `mode` 字段（已完成）

### 2. 类型安全

所有类型定义在 `researchTypes.ts` 中，确保前后端数据结构一致。

### 3. WebSocket（可选）

当前实现使用轮询方式（HTTP 请求）。如需实时进度推送，需要：
1. 后端实现 WebSocket endpoint
2. 前端添加 WebSocket 客户端
3. 参考 `.agentdocs/workflow/langgraph-agents-integration-plan.md` 阶段 4

---

## 📚 相关文档

- `.agentdocs/workflow/langgraph-agents-frontend-implementation.md` - 详细实现方案
- `.agentdocs/workflow/langgraph-agents-integration-usage.md` - 后端集成
- `docs/langgraph-agents-frontend-design.md` - 设计理念

---

## 🐛 故障排查

### 问题 1：组件导入失败

**症状**: `Cannot find module '@/features/research/...'`

**解决**: 检查 TypeScript 路径配置（tsconfig.json）

### 问题 2：图标不显示

**症状**: 图标位置是空白的

**解决**: 确保安装了 `lucide-vue-next`

```bash
npm install lucide-vue-next
```

### 问题 3：API 请求失败

**症状**: 控制台显示 CORS 错误或 404

**解决**: 确认：
1. 后端服务已启动
2. API 路径正确（`/api/v1/chat`）
3. CORS 已配置

---

## ✨ 下一步增强

1. **WebSocket 实时推送** - 真正的实时进度更新
2. **UI 动画优化** - 添加更流畅的过渡效果
3. **键盘快捷键** - 快速切换模式、提交查询
4. **任务历史** - 保存和查看历史研究任务

---

**当前状态**: ✅ 基础功能已完成，可以开始测试！

