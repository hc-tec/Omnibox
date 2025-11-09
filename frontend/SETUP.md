# 前端组件库安装指南

> **重要**：所有组件必须使用 shadcn-vue + ECharts，不允许自己手写样式！

---

## 1. 安装 shadcn-vue

```bash
cd frontend
npx shadcn-vue@latest init
```

按提示选择：
- TypeScript: **Yes**
- Framework: **Vite**
- Style: **Default**
- Base color: **Slate** (或其他)
- CSS variables: **Yes**
- Global CSS: `src/assets/index.css`
- Import alias: `@`
- Tailwind Config: `tailwind.config.js`

---

## 2. 安装所需的 shadcn-vue 组件

```bash
# 基础组件
npx shadcn-vue@latest add card
npx shadcn-vue@latest add badge
npx shadcn-vue@latest add separator
npx shadcn-vue@latest add alert
npx shadcn-vue@latest add table
npx shadcn-vue@latest add button
npx shadcn-vue@latest add progress
npx shadcn-vue@latest add dialog
```

---

## 3. 安装图表库

```bash
npm install echarts vue-echarts
```

---

## 4. 安装表格库

```bash
npm install @tanstack/vue-table
```

---

## 5. 安装 Markdown 渲染库

```bash
npm install marked
npm install -D @types/marked
```

---

## 6. 安装 Tailwind Typography

```bash
npm install -D @tailwindcss/typography
```

更新 `tailwind.config.js`:

```javascript
module.exports = {
  // ...其他配置
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
```

---

## 7. 全局注册 vue-echarts（可选）

在 `src/main.ts` 中：

```typescript
import { createApp } from 'vue'
import ECharts from 'vue-echarts'
import App from './App.vue'

const app = createApp(App)

// 全局注册 vue-echarts
app.component('VChart', ECharts)

app.mount('#app')
```

---

## 8. 验证安装

安装完成后，你的 `package.json` 应该包含：

```json
{
  "dependencies": {
    "vue": "^3.4.38",
    "pinia": "^2.1.7",
    "axios": "^1.7.7",
    "echarts": "^5.x.x",
    "vue-echarts": "^7.x.x",
    "@tanstack/vue-table": "^8.x.x",
    "marked": "^12.x.x",
    "radix-vue": "^1.x.x",  // shadcn-vue 依赖
    "class-variance-authority": "^0.7.x",
    "clsx": "^2.x.x",
    "tailwind-merge": "^2.x.x"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.1.2",
    "typescript": "^5.4.5",
    "vite": "^5.4.8",
    "@types/node": "^20.16.10",
    "@types/marked": "^6.x.x",
    "tailwindcss": "^3.x.x",
    "autoprefixer": "^10.x.x",
    "postcss": "^8.x.x",
    "@tailwindcss/typography": "^0.5.x"
  }
}
```

---

## 9. 组件文件位置

shadcn-vue 组件会安装到：
```
frontend/src/components/ui/
├── card.vue
├── badge.vue
├── separator.vue
├── alert.vue
├── table.vue
├── button.vue
├── progress.vue
└── dialog.vue
```

---

## 10. 下一步

安装完成后，重写以下组件：
1. ✅ ListPanelBlock.vue
2. ✅ StatisticCardBlock.vue
3. ✅ LineChartBlock.vue
4. ✅ FallbackRichTextBlock.vue
5. ➕ BarChartBlock.vue (新增)
6. ➕ PieChartBlock.vue (新增)
7. ➕ TableBlock.vue (新增)
8. ➕ ImageGalleryBlock.vue (新增)
