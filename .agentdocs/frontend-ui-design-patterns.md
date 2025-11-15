# 前端 UI 设计范式

本文档定义 Omnibox 前端界面的统一设计语言，所有新组件应遵循以下设计原则。

## 设计理念

### 核心原则
- **玻璃态质感（Glassmorphism）** - 半透明背景 + 毛玻璃效果 + 微妙边框
- **状态即视觉（Status-Driven Design）** - 每种状态都有专属的颜色方案和视觉反馈
- **渐进式披露（Progressive Disclosure）** - 初始呈现概览，悬停/交互时展示细节
- **即时反馈（Immediate Feedback）** - 用户操作后 0.1 秒内必须有视觉响应
- **平台感知（Platform-Aware）** - 根据数据来源平台动态调整配色

### 设计约束
- ❌ **禁止过度动效** - 不使用 `scale` 变换，不使用夸张的弹跳动画
- ✅ **推荐微妙过渡** - 使用颜色、透明度、位置的平滑过渡（300ms duration）
- ✅ **保持简洁** - 圆角统一使用 `rounded-xl`（12px）或 `rounded-2xl`（16px）
- ✅ **语义化颜色** - 使用 CSS 变量（`--foreground`、`--muted-foreground`）而非硬编码颜色

---

## 卡片组件设计范式

### 1. 结构布局

**三段式结构**：
```
┌─────────────────────────────────┐
│ 顶部状态条（1px 渐变色）        │ ← 状态指示
├─────────────────────────────────┤
│ Header（图标 + 标题 + 元信息）  │
│ Content（主要内容区域）         │
│ Footer（操作按钮/统计信息）     │ ← 可选
└─────────────────────────────────┘
```

**关键类名组合**：
```vue
<div class="relative overflow-hidden rounded-2xl border backdrop-blur-sm transition-all duration-300">
  <!-- 顶部状态条 -->
  <div class="absolute top-0 left-0 right-0 h-1 transition-all duration-500" />

  <!-- 状态背景渐变 -->
  <div class="absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-5" />

  <!-- 卡片内容 -->
  <div class="relative">
    <!-- Header/Content/Footer -->
  </div>
</div>
```

### 2. 状态配色系统

#### 2.1 研究任务状态

| 状态 | 中文名称 | 顶部状态条 | 图标容器 | 背景渐变 |
|------|---------|-----------|---------|---------|
| `idle` | 待启动 | `from-primary to-purple-500` | `bg-primary/10 shadow-primary/20` | - |
| `processing` | 处理中 | `from-blue-500 via-cyan-500 to-blue-500` + `animate-pulse` | `bg-blue-500/10 shadow-blue-500/20` | `from-blue-500/20 to-cyan-500/20` |
| `human_in_loop` | 等待回复 | `from-amber-500 to-orange-500` | `bg-amber-500/10 shadow-amber-500/20` | - |
| `completed` | 已完成 | `from-emerald-500 to-green-500` | `bg-emerald-500/10 shadow-emerald-500/20` | `from-emerald-500/20 to-green-500/20` |
| `error` | 出错 | `from-red-500 to-rose-500` | `bg-red-500/10 shadow-red-500/20` | - |

**代码示例**：
```typescript
const statusBarClass = computed(() => {
  switch (status) {
    case "processing":
      return "bg-gradient-to-r from-blue-500 via-cyan-500 to-blue-500 animate-pulse";
    case "completed":
      return "bg-gradient-to-r from-emerald-500 to-green-500";
    // ...
  }
});

const iconContainerClass = computed(() => ({
  "transition-all duration-300": true,
  "bg-blue-500/10 shadow-lg shadow-blue-500/20": status === "processing",
  "bg-emerald-500/10 shadow-lg shadow-emerald-500/20": status === "completed",
  // ...
}));
```

#### 2.2 平台配色方案

适用于订阅卡片、数据来源标识等场景。

| 平台 | 渐变起点 | 渐变终点 | 边框色 | 阴影色 |
|------|---------|---------|--------|--------|
| GitHub | `from-gray-500/20` | `to-slate-600/20` | `border-gray-500/40` | `shadow-gray-500/20` |
| Bilibili | `from-pink-500/20` | `to-rose-500/20` | `border-pink-500/40` | `shadow-pink-500/20` |
| 知乎 | `from-blue-500/20` | `to-indigo-500/20` | `border-blue-500/40` | `shadow-blue-500/20` |
| 微博 | `from-orange-500/20` | `to-amber-500/20` | `border-orange-500/40` | `shadow-orange-500/20` |
| RSS | `from-orange-500/20` | `to-yellow-500/20` | `border-orange-500/40` | `shadow-orange-500/20` |
| 默认 | `from-indigo-500/20` | `to-blue-500/20` | `border-indigo-500/40` | `shadow-indigo-500/20` |

**代码示例**（SubscriptionCard.vue 参考）：
```typescript
const platformColors = computed(() => {
  const colorMap: Record<string, ColorScheme> = {
    'bilibili': { from: 'from-pink-500/20', to: 'to-rose-500/20', border: 'border-pink-500/40', shadow: 'shadow-pink-500/20' },
    // ...
  }
  return colorMap[platform] || defaultScheme;
});
```

### 3. 交互动效规范

#### 3.1 禁止的动效
```css
/* ❌ 禁止缩放变换 */
.card:hover {
  transform: scale(1.05); /* 不允许 */
}

/* ❌ 禁止旋转动画 */
.icon {
  animation: rotate 1s infinite; /* 不允许 */
}
```

#### 3.2 推荐的动效

**悬停效果**：
```vue
<!-- ✅ 只改变颜色和透明度 -->
<button
  class="transition-colors duration-200 hover:bg-primary/10 hover:text-primary"
  @click="handleClick"
>
  操作按钮
</button>

<!-- ✅ 微妙的位移（最多 2px） -->
<div class="transition-transform duration-300 hover:translate-y-[-2px]">
  卡片内容
</div>
```

**加载状态**：
```vue
<!-- ✅ 旋转边框（processing 状态） -->
<div class="h-3.5 w-3.5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />

<!-- ✅ 脉动效果（animate-pulse） -->
<div class="bg-gradient-to-r from-blue-500 to-cyan-500 animate-pulse" />
```

### 4. 徽章（Badge）设计

**尺寸标准**：
- 小徽章：`text-[10px] px-1.5 py-0 rounded-md`
- 中等徽章：`text-xs px-2 py-0.5 rounded-lg`
- 圆形标签：`rounded-full text-[10px] px-2 py-0`

**变体（Variant）使用**：
```vue
<Badge variant="default">处理中</Badge>      <!-- 蓝色主题 -->
<Badge variant="secondary">待启动</Badge>     <!-- 灰色主题 -->
<Badge variant="outline">已完成</Badge>       <!-- 透明边框 -->
<Badge variant="destructive">出错</Badge>     <!-- 红色主题 -->
```

**语义化标签**：
```vue
<Badge variant="secondary" class="text-[10px] uppercase tracking-wider">
  {{ platformName }}
</Badge>
<Badge variant="outline" class="text-[10px]">
  {{ entityType }}
</Badge>
```

### 5. 按钮设计

#### 5.1 尺寸规范
- **小按钮**：`size="sm" class="h-8 rounded-lg text-xs"`
- **图标按钮**：`size="icon" class="h-8 w-8"`
- **默认按钮**：`class="h-10 rounded-xl"`

#### 5.2 变体使用

**主要操作**：
```vue
<Button class="rounded-xl bg-gradient-to-br from-indigo-500 via-blue-500 to-indigo-600">
  启动研究
</Button>
```

**次要操作**：
```vue
<Button variant="outline" class="rounded-xl">
  取消
</Button>
```

**危险操作**：
```vue
<Button
  variant="ghost"
  class="hover:text-destructive hover:bg-destructive/10"
  @click="handleDelete"
>
  <Trash2 class="mr-1.5 h-3.5 w-3.5" />
  删除
</Button>
```

#### 5.3 加载状态

```vue
<Button :disabled="loading">
  <span class="flex items-center gap-2">
    <span v-if="loading" class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
    {{ loading ? '提交中...' : '提交' }}
  </span>
</Button>
```

### 6. 信息面板设计

#### 6.1 提示面板（建议性信息）

```vue
<div class="rounded-xl border border-primary/30 bg-primary/5 p-3.5 backdrop-blur-sm">
  <div class="flex items-start gap-3">
    <Brain class="h-4 w-4 text-primary flex-shrink-0 mt-0.5" />
    <div class="flex-1 space-y-2">
      <p class="text-xs font-semibold text-foreground">标题</p>
      <p class="text-xs leading-relaxed text-muted-foreground">
        详细说明文本...
      </p>
    </div>
  </div>
</div>
```

#### 6.2 警告面板（需要用户注意）

```vue
<div class="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3.5 backdrop-blur-sm">
  <div class="flex items-start gap-3">
    <AlertCircle class="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
    <div class="flex-1 space-y-1.5">
      <p class="text-xs font-semibold text-foreground">需要你的回复</p>
      <p class="text-xs leading-relaxed text-muted-foreground">
        等待响应...
      </p>
    </div>
  </div>
</div>
```

#### 6.3 错误面板（出错信息）

```vue
<div class="rounded-xl border border-red-500/30 bg-red-500/5 p-3.5 backdrop-blur-sm">
  <div class="flex items-start gap-3">
    <AlertCircle class="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
    <div class="flex-1 space-y-1.5">
      <p class="text-xs font-semibold text-foreground">执行出错</p>
      <p class="text-xs leading-relaxed text-muted-foreground">
        {{ errorMessage }}
      </p>
    </div>
  </div>
</div>
```

### 7. 列表与进度展示

#### 7.1 步骤列表（带状态图标）

```vue
<div
  v-for="step in steps"
  :key="step.id"
  class="flex items-center gap-2.5 text-xs group/step"
>
  <div class="flex-shrink-0">
    <CheckCircle
      v-if="step.status === 'success'"
      class="h-3.5 w-3.5 text-emerald-500"
    />
    <div
      v-else
      class="h-3.5 w-3.5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin"
    />
  </div>
  <span class="text-muted-foreground group-hover/step:text-foreground transition-colors">
    {{ step.action }}
  </span>
</div>
```

#### 7.2 数据预览列表

```vue
<div class="rounded-xl border border-border/40 bg-gradient-to-br from-muted/10 to-muted/5 p-3 backdrop-blur-sm">
  <div class="flex items-center justify-between gap-2 mb-2">
    <p class="text-xs font-semibold text-foreground">{{ title }}</p>
    <div class="flex h-5 w-5 items-center justify-center rounded-md bg-primary/10">
      <Zap class="h-3 w-3 text-primary" />
    </div>
  </div>
  <ul class="space-y-1">
    <li
      v-for="item in items"
      :key="item.id"
      class="text-xs text-muted-foreground truncate"
    >
      {{ formatItem(item) }}
    </li>
  </ul>
</div>
```

### 8. 表单设计

#### 8.1 分组布局

```vue
<!-- 基本信息分组 -->
<div class="space-y-4 rounded-2xl border border-border/20 bg-background/30 p-4">
  <p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">基本信息</p>
  <!-- 表单字段 -->
</div>

<!-- 重要配置分组（高亮） -->
<div class="space-y-4 rounded-2xl border border-indigo-500/20 bg-indigo-500/5 p-4">
  <p class="text-xs font-semibold uppercase tracking-wider text-indigo-600">标识符配置</p>
  <!-- 表单字段 -->
</div>
```

#### 8.2 输入框样式

```vue
<Label for="field_name" class="text-sm font-medium">显示名称 *</Label>
<Input
  id="field_name"
  v-model="formData.field_name"
  placeholder="提示文本"
  class="rounded-xl border-border/40 bg-background/50"
/>
```

#### 8.3 对话框（Dialog）设计

```vue
<DialogContent class="max-w-2xl max-h-[90vh] overflow-y-auto rounded-[28px] border-2 border-border/30 bg-gradient-to-b from-card/98 to-card/95 shadow-2xl shadow-black/10 backdrop-blur-xl">
  <!-- 顶部装饰渐变 -->
  <div class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 via-blue-500 to-indigo-500 rounded-t-[28px]" />

  <DialogHeader class="relative">
    <DialogTitle class="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-blue-600 bg-clip-text text-transparent">
      {{ title }}
    </DialogTitle>
  </DialogHeader>

  <!-- 表单内容 -->

  <DialogFooter class="gap-3 pt-2">
    <Button variant="outline" @click="handleClose">取消</Button>
    <Button @click="handleSubmit" class="rounded-xl bg-gradient-to-br from-indigo-500 via-blue-500 to-indigo-600">
      提交
    </Button>
  </DialogFooter>
</DialogContent>
```

---

## 组件开发清单

### 开发新卡片组件时必须包含：

- [ ] 顶部 1px 渐变状态条（根据状态动态变色）
- [ ] 半透明背景 + `backdrop-blur-sm`
- [ ] 状态驱动的图标容器（带阴影和渐变背景）
- [ ] 三段式结构（Header/Content/Footer）
- [ ] 响应式圆角（`rounded-xl` 或 `rounded-2xl`）
- [ ] 平滑过渡动画（`transition-all duration-300`）
- [ ] 语义化 Badge 标签（状态、平台、类型）
- [ ] 符合 0.1s 响应法则的交互反馈
- [ ] 禁用缩放动效，使用颜色/透明度变化
- [ ] 使用 CSS 变量而非硬编码颜色

### 开发新表单时必须包含：

- [ ] 分组布局（基本信息/重要配置/补充信息）
- [ ] 统一的输入框样式（`rounded-xl border-border/40 bg-background/50`）
- [ ] 必填字段标识（`*`）
- [ ] 清晰的 Label 文本
- [ ] 加载状态按钮（带旋转图标）
- [ ] 渐变装饰条（对话框顶部）
- [ ] 最大高度限制 + 滚动（`max-h-[90vh] overflow-y-auto`）

---

## 参考实现

### 优秀示例组件

1. **ResearchLiveCard.vue** - 研究任务卡片（状态驱动设计典范）
   - 路径：`frontend/src/features/research/components/ResearchLiveCard.vue`
   - 亮点：完整的状态配色系统、渐进式信息披露、平滑过渡动画

2. **SubscriptionCard.vue** - 订阅卡片（平台配色系统典范）
   - 路径：`frontend/src/components/subscription/SubscriptionCard.vue`
   - 亮点：平台感知配色、头像/图标容器设计、操作按钮布局

3. **SubscriptionForm.vue** - 订阅表单（表单分组典范）
   - 路径：`frontend/src/components/subscription/SubscriptionForm.vue`
   - 亮点：清晰的分组结构、渐变装饰、加载状态处理

### 代码复用建议

- **颜色方案生成器** - 参考 `SubscriptionCard.vue` 中的 `platformColors` computed
- **状态图标映射** - 参考 `ResearchLiveCard.vue` 中的 `statusIcon` computed
- **条件样式绑定** - 使用 computed 返回对象，而非 ternary 嵌套
- **信息面板模板** - 直接复制提示/警告/错误面板的结构

---

## 设计决策记录

### 为什么禁止 scale 动效？

**原因**：
1. 用户反馈："不需要 hover 悬浮效果"（2025-11-15）
2. 桌面应用追求稳重感，而非网页的轻盈感
3. scale 变换会触发重排，影响性能
4. 微妙的颜色变化已经足够提供视觉反馈

**替代方案**：
- 使用 `translateY(-2px)` 提供轻微提升感
- 使用 `opacity` 和 `background-color` 过渡
- 使用边框颜色变化（`border-primary/40`）

### 为什么使用 10px/12px/16px 圆角？

**原因**：
1. 与现代设计趋势一致（iOS/macOS 大圆角风格）
2. 玻璃态效果需要足够的圆角半径才能呈现
3. 统一的圆角规范减少视觉噪音

**使用规则**：
- 小组件（Badge、Button）：`rounded-lg`（8px）或 `rounded-xl`（12px）
- 卡片：`rounded-2xl`（16px）
- 对话框：`rounded-[28px]`（28px，特大圆角）
- 圆形元素：`rounded-full`

### 为什么状态条只有 1px 高度？

**原因**：
1. 足够提供状态指示，但不喧宾夺主
2. 渐变色在窄条上更加精致
3. 与卡片主体内容视觉上分离，不干扰阅读

**注意事项**：
- 必须使用渐变色（`bg-gradient-to-r`），单色不够醒目
- 使用 `animate-pulse` 强调 processing 状态
- 使用 `transition-all duration-500` 确保状态切换平滑

---

## 常见错误与修复

### ❌ 错误示例 1：硬编码颜色

```vue
<!-- 错误：使用硬编码颜色 -->
<div class="bg-blue-500 text-white">处理中</div>
```

```vue
<!-- 正确：使用语义化变量 -->
<div class="bg-primary text-primary-foreground">处理中</div>

<!-- 或使用状态驱动的类绑定 -->
<div :class="{ 'bg-blue-500/10 text-blue-500': status === 'processing' }">
  处理中
</div>
```

### ❌ 错误示例 2：过度嵌套三元表达式

```vue
<!-- 错误：难以维护的三元嵌套 -->
<div :class="status === 'processing' ? 'bg-blue-500' : status === 'completed' ? 'bg-green-500' : 'bg-gray-500'">
```

```vue
<!-- 正确：使用 computed 属性 -->
<script setup lang="ts">
const statusClass = computed(() => {
  switch (status) {
    case 'processing': return 'bg-blue-500/10 text-blue-500';
    case 'completed': return 'bg-emerald-500/10 text-emerald-500';
    default: return 'bg-muted text-muted-foreground';
  }
});
</script>

<template>
  <div :class="statusClass">{{ statusText }}</div>
</template>
```

### ❌ 错误示例 3：忽略可访问性

```vue
<!-- 错误：无 aria-label，图标按钮语义不明 -->
<button @click="handleDelete">
  <Trash2 class="h-4 w-4" />
</button>
```

```vue
<!-- 正确：添加 aria-label -->
<button @click="handleDelete" aria-label="删除订阅">
  <Trash2 class="h-4 w-4" />
</button>
```

---

## 更新日志

- **2025-11-15** - 创建文档，基于 ResearchLiveCard、SubscriptionCard、SubscriptionForm 提取设计范式
- **2025-11-15** - 添加状态配色系统、交互动效规范、表单设计模式
