<template>
  <main class="app-shell">
    <section class="hero">
      <div>
        <p class="hero-badge">桌面端 · Electron</p>
        <h1>智能面板工作台</h1>
        <p class="hero-subtitle">
          输入一个需求，系统会持续 append 组件并按照宫格布局呈现洞察。支持实时流式模式与一键清空。
        </p>
      </div>
      <div class="hero-actions">
        <span class="hero-version" v-if="version">版本 {{ version }}</span>
        <span class="hero-version muted" v-else>初始化桌面容器…</span>
      </div>
    </section>

    <section class="app-content">
      <PanelWorkspace />
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import PanelWorkspace from "./features/panel/PanelWorkspace.vue";

const version = ref<string | null>(null);

onMounted(async () => {
  if (window.desktop?.getVersion) {
    version.value = await window.desktop.getVersion();
  }
});
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding: 32px 40px 48px;
  gap: 24px;
  background: radial-gradient(circle at top, #dbeafe 0%, #f8fafc 50%, #ffffff 80%);
}

.hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.hero h1 {
  margin: 8px 0 12px;
  font-size: 36px;
  font-weight: 700;
  color: #0f172a;
}

.hero-subtitle {
  margin: 0;
  color: #475569;
  font-size: 16px;
  max-width: 640px;
}

.hero-badge {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #1d4ed8;
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.15);
  padding: 4px 12px;
  border-radius: 999px;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #64748b;
  font-size: 14px;
}

.hero-version {
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
}

.hero-version.muted {
  background: transparent;
  border: 1px dashed rgba(148, 163, 184, 0.6);
}

.app-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  box-shadow: 0 30px 60px rgba(15, 23, 42, 0.12);
  padding: 28px;
  overflow: hidden;
}

@media (max-width: 1024px) {
  .hero {
    flex-direction: column;
  }
}
</style>
