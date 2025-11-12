<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from "vue";

// 全局主题初始化
const initTheme = () => {
  const root = document.documentElement;
  if (!root.classList.contains("theme-dark") && !root.classList.contains("theme-light")) {
    root.classList.add("theme-dark");
    root.classList.add("dark");
    document.body.classList.add("dark");
  }
};

// 全局快捷键监听（如有需要）
const handleGlobalShortcut = (event: KeyboardEvent) => {
  // 全局快捷键逻辑可在此处理
  // 各视图内的快捷键应在各自视图中处理
};

onMounted(() => {
  initTheme();
  window.addEventListener("keydown", handleGlobalShortcut);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleGlobalShortcut);
});
</script>

<style>
/* 全局样式继承自 styles/base.css */
</style>
