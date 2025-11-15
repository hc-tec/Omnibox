/**
 * 开发者模式状态管理
 *
 * 功能：
 * - 开启/关闭开发者模式
 * - 开发者模式下可以点击组件查看 metadata 调试信息
 */

import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useDevModeStore = defineStore('devMode', () => {
  // 开发者模式开关（默认关闭）
  const enabled = ref(false);

  // 从 localStorage 恢复状态
  const savedState = localStorage.getItem('dev_mode_enabled');
  if (savedState !== null) {
    enabled.value = savedState === 'true';
  }

  /**
   * 切换开发者模式
   */
  function toggle() {
    enabled.value = !enabled.value;
    localStorage.setItem('dev_mode_enabled', String(enabled.value));
  }

  /**
   * 设置开发者模式
   */
  function setEnabled(value: boolean) {
    enabled.value = value;
    localStorage.setItem('dev_mode_enabled', String(value));
  }

  return {
    enabled,
    toggle,
    setEnabled,
  };
});
