/**
 * 仪表盘特性模块导出
 *
 * Phase 5: Dashboard
 */

// 组件
export { default as DashboardView } from './components/DashboardView.vue'
export { default as DashboardCard } from './components/DashboardCard.vue'
export { default as DashboardGrid } from './components/DashboardGrid.vue'
export { default as NotificationBell } from './components/NotificationBell.vue'

// 类型
export type * from './types/dashboard'
export {
  CardType,
  RefreshInterval,
  TriggerType,
  TriggerAction,
  NotificationStatus,
  REFRESH_INTERVAL_LABELS,
  TRIGGER_TYPE_LABELS,
  TRIGGER_ACTION_LABELS,
} from './types/dashboard'

// Store
export { useDashboardStore } from './stores/dashboardStore'

// API
export * as dashboardApi from './services/dashboardApi'
