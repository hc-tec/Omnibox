<template>
  <main class="app-shell">
    <section class="app-header">
      <h1>智能数据面板</h1>
      <p class="app-subtitle">
        依据后端面板协议动态渲染组件。请使用下方控制区触发查询或通过 WebSocket 观察流式状态。
      </p>
    </section>

    <section class="app-content">
      <PanelWorkspace />
    </section>
  </main>
</template>

<script setup lang="ts">
import PanelWorkspace from "./features/panel/PanelWorkspace.vue";
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding: 24px 32px 48px;
  gap: 24px;
  background: linear-gradient(180deg, #f1f5f9 0%, #ffffff 60%);
}

.app-header h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  color: #0f172a;
}

.app-subtitle {
  margin: 8px 0 0;
  color: #475569;
  font-size: 15px;
}

.app-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
  padding: 24px;
  overflow: hidden;
}
</style>
