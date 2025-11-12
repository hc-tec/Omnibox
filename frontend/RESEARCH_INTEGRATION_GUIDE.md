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

```vue
<template>
  <div class="app-container">
    <!-- 原有的聊天输入区域 -->
    <div class="chat-input-area">
      <!-- 添加模式选择器 -->
      <QueryModeSelector v-model="queryMode" />

      <!-- 原有的输入框 -->
      <input v-model="userQuery" @keyup.enter="handleSubmit" />
      <button @click="handleSubmit">发送</button>
    </div>

    <!-- 研究任务卡片区域（新增） -->
    <div v-if="activeTasks.length > 0" class="research-cards">
      <ResearchLiveCard
        v-for="task in activeTasks"
        :key="task.task_id"
        :task="task"
        @delete="handleDeleteTask"
      />
    </div>

    <!-- 原有的内容区域 -->
    <div class="content-area">
      <!-- 原有内容 -->
    </div>

    <!-- Action Inbox（全局浮动组件） -->
    <ActionInbox />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import QueryModeSelector from '@/features/research/components/QueryModeSelector.vue';
import ResearchLiveCard from '@/features/research/components/ResearchLiveCard.vue';
import ActionInbox from '@/features/research/components/ActionInbox.vue';
import { useResearchStore } from '@/features/research/stores/researchStore';
import { researchApi } from '@/features/research/services/researchApi';
import type { QueryMode } from '@/features/research/types/researchTypes';

const researchStore = useResearchStore();
const userQuery = ref('');
const queryMode = ref<QueryMode>('auto');

const activeTasks = computed(() => researchStore.activeTasks);

async function handleSubmit() {
  if (!userQuery.value.trim()) return;

  const query = userQuery.value;
  const mode = queryMode.value;

  // 创建任务
  const taskId = researchStore.createTask(query, mode);

  // 清空输入
  userQuery.value = '';

  try {
    // 发送请求
    const response = await researchApi.submitQuery(query, mode);

    // 处理响应
    if (response.success) {
      if (response.metadata?.mode === 'research') {
        // 研究模式：更新步骤
        response.metadata.execution_steps?.forEach(step => {
          researchStore.updateTaskStep(taskId, step);
        });
      }

      // 完成任务
      researchStore.completeTask(taskId, response.message);
    } else {
      researchStore.setTaskError(taskId, response.message);
    }
  } catch (error) {
    researchStore.setTaskError(
      taskId,
      `请求失败: ${error instanceof Error ? error.message : '未知错误'}`
    );
  }
}

function handleDeleteTask(taskId: string) {
  researchStore.deleteTask(taskId);
}
</script>

<style scoped>
.research-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}
</style>
```

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
