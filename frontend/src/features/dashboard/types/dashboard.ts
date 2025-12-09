/**
 * 仪表盘类型定义
 *
 * Phase 5: Dashboard 前端类型
 */

// ============ 枚举常量 ============

export const CardType = {
  ARTIFACT: 'artifact',
  WORKFLOW: 'workflow',
  CUSTOM: 'custom',
} as const

export type CardTypeValue = typeof CardType[keyof typeof CardType]

export const RefreshInterval = {
  MANUAL: 'manual',
  HOURLY: 'hourly',
  DAILY: 'daily',
  WEEKLY: 'weekly',
} as const

export type RefreshIntervalValue = typeof RefreshInterval[keyof typeof RefreshInterval]

export const TriggerType = {
  VALUE_CHANGE: 'value_change',
  THRESHOLD: 'threshold',
  PATTERN: 'pattern',
} as const

export type TriggerTypeValue = typeof TriggerType[keyof typeof TriggerType]

export const TriggerAction = {
  NOTIFY: 'notify',
  REFRESH: 'refresh',
  RUN_WORKFLOW: 'run_workflow',
} as const

export type TriggerActionValue = typeof TriggerAction[keyof typeof TriggerAction]

export const NotificationStatus = {
  PENDING: 'pending',
  SENT: 'sent',
  READ: 'read',
  FAILED: 'failed',
} as const

export type NotificationStatusValue = typeof NotificationStatus[keyof typeof NotificationStatus]

// ============ 基础类型 ============

export interface Position {
  x: number
  y: number
  width: number
  height: number
}

export interface Trigger {
  trigger_id?: string
  name: string
  enabled: boolean
  trigger_type: TriggerTypeValue
  condition: Record<string, unknown>
  action: TriggerActionValue
  action_config: Record<string, unknown>
  last_triggered_at?: string
  trigger_count?: number
}

// ============ 卡片类型 ============

export interface DashboardCard {
  card_id: string
  name: string
  description: string
  card_type: CardTypeValue
  source_config: Record<string, unknown>
  view_config: Record<string, unknown>
  refresh_interval: RefreshIntervalValue
  last_refresh_at?: string
  next_refresh_at?: string
  triggers: Trigger[]
  position: Position
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface CardData {
  card_id: string
  data: unknown
  layout?: Record<string, unknown>
  blocks?: Array<Record<string, unknown>>
  schema?: Record<string, unknown>
  suggested_views?: Array<Record<string, unknown>>
  view_config?: Record<string, unknown>
  refreshed_at: string
  error?: string
}

// ============ 通知类型 ============

export interface Notification {
  notification_id: string
  title: string
  message: string
  source_type: string
  source_id?: string
  card_id?: string
  channel: string
  status: NotificationStatusValue
  data: Record<string, unknown>
  created_at: string
  sent_at?: string
  read_at?: string
}

// ============ 请求类型 ============

export interface PinArtifactRequest {
  artifact_id: string
  name: string
  description?: string
  view_config?: Record<string, unknown>
  refresh_interval?: RefreshIntervalValue
  triggers?: Trigger[]
  position?: Position
}

export interface PinWorkflowRequest {
  workflow_id: string
  name: string
  variable_values: Record<string, unknown>
  description?: string
  view_config?: Record<string, unknown>
  refresh_interval?: RefreshIntervalValue
  triggers?: Trigger[]
  position?: Position
}

export interface PinPanelRequest {
  title: string
  layout: Record<string, unknown>
  blocks: Array<Record<string, unknown>>
  data_blocks: Record<string, unknown>
  description?: string
  position?: Position
}

export interface UpdateCardRequest {
  name?: string
  description?: string
  view_config?: Record<string, unknown>
  refresh_interval?: RefreshIntervalValue
  enabled?: boolean
}

export interface UpdateLayoutRequest {
  layouts: Array<{
    card_id: string
    x: number
    y: number
    width: number
    height: number
  }>
}

export interface UpdateTriggersRequest {
  triggers: Trigger[]
}

// ============ 响应类型 ============

export interface CardListResponse {
  cards: DashboardCard[]
  total: number
}

export interface NotificationListResponse {
  notifications: Notification[]
  total: number
  unread_count: number
}

export interface UnreadCountResponse {
  count: number
}

// ============ 刷新频率标签映射 ============

export const REFRESH_INTERVAL_LABELS: Record<RefreshIntervalValue, string> = {
  manual: '手动刷新',
  hourly: '每小时',
  daily: '每天',
  weekly: '每周',
}

// ============ 触发类型标签映射 ============

export const TRIGGER_TYPE_LABELS: Record<TriggerTypeValue, string> = {
  value_change: '值变化',
  threshold: '阈值触发',
  pattern: '模式匹配',
}

// ============ 触发动作标签映射 ============

export const TRIGGER_ACTION_LABELS: Record<TriggerActionValue, string> = {
  notify: '发送通知',
  refresh: '刷新卡片',
  run_workflow: '执行工作流',
}
