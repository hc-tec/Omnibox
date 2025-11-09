## 智能数据面板前端

基于 Vue3 + Vite + Pinia 的渲染端，用于消费后端的智能数据面板协议。

### 结构
```
frontend/
  ├─ src/
  │   ├─ features/panel/           # 面板渲染、工具栏、流式日志
  │   ├─ services/                 # REST / WebSocket 封装
  │   ├─ shared/                   # 与后端对齐的类型 & 组件能力表
  │   ├─ store/                    # Pinia 状态管理
  │   └─ utils/                    # 数据解析辅助
  ├─ package.json
  └─ vite.config.mts
```

### 命令
```bash
npm install
npm run dev     # http://localhost:5173
npm run build
```

### 说明
- 组件能力表在 `src/shared/componentManifest.ts` 中维护，需与后端保持一致。
- 面板数据结构对齐 `docs/backend-intelligent-panel-overview.md`。
- 当前未接入真实图表库，可在 `LineChartBlock` 中替换为可视化实现。
