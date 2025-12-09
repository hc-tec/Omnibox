/**
 * 仪表盘 API 服务
 *
 * Phase 5: Dashboard REST API 调用
 */

import type {
  DashboardCard,
  CardData,
  CardListResponse,
  PinArtifactRequest,
  PinWorkflowRequest,
  PinPanelRequest,
  UpdateCardRequest,
  UpdateLayoutRequest,
  UpdateTriggersRequest,
  Trigger,
  Notification,
  NotificationListResponse,
  UnreadCountResponse,
} from '../types/dashboard'
import { resolveHttpBase } from '@/shared/networkBase'

const API_BASE = resolveHttpBase(import.meta.env.VITE_API_BASE, '/api/v1')
const DASHBOARD_URL = `${API_BASE}/dashboard`

// ============ 卡片管理 ============

/**
 * 获取卡片列表
 */
export async function listCards(
  enabledOnly: boolean = false,
  cardType?: string
): Promise<CardListResponse> {
  const params = new URLSearchParams()
  if (enabledOnly) params.append('enabled_only', 'true')
  if (cardType) params.append('card_type', cardType)

  const url = `${DASHBOARD_URL}/cards${params.toString() ? '?' + params.toString() : ''}`
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`获取卡片列表失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 获取卡片详情
 */
export async function getCard(cardId: string): Promise<DashboardCard> {
  const response = await fetch(`${DASHBOARD_URL}/cards/${cardId}`)

  if (!response.ok) {
    throw new Error(`获取卡片失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Pin 数据产物
 */
export async function pinArtifact(
  request: PinArtifactRequest
): Promise<DashboardCard> {
  const response = await fetch(`${DASHBOARD_URL}/pin/artifact`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    throw new Error(`Pin 数据产物失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Pin 工作流
 */
export async function pinWorkflow(
  request: PinWorkflowRequest
): Promise<DashboardCard> {
  const response = await fetch(`${DASHBOARD_URL}/pin/workflow`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    throw new Error(`Pin 工作流失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Pin 面板到仪表盘
 */
export async function pinPanel(
  request: PinPanelRequest
): Promise<DashboardCard> {
  const response = await fetch(`${DASHBOARD_URL}/pin/panel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    throw new Error(`Pin 面板失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 更新卡片
 */
export async function updateCard(
  cardId: string,
  request: UpdateCardRequest
): Promise<DashboardCard> {
  const response = await fetch(`${DASHBOARD_URL}/cards/${cardId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    throw new Error(`更新卡片失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 删除卡片
 */
export async function deleteCard(cardId: string): Promise<void> {
  const response = await fetch(`${DASHBOARD_URL}/cards/${cardId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error(`删除卡片失败: ${response.statusText}`)
  }
}

// ============ 数据刷新 ============

/**
 * 刷新卡片数据
 */
export async function refreshCard(cardId: string): Promise<CardData> {
  const response = await fetch(`${DASHBOARD_URL}/cards/${cardId}/refresh`, {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error(`刷新卡片失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 获取卡片数据（优先使用缓存）
 */
export async function getCardData(cardId: string): Promise<CardData> {
  const response = await fetch(`${DASHBOARD_URL}/cards/${cardId}/data`)

  if (!response.ok) {
    throw new Error(`获取卡片数据失败: ${response.statusText}`)
  }

  return response.json()
}

// ============ 布局管理 ============

/**
 * 更新布局
 */
export async function updateLayout(
  request: UpdateLayoutRequest
): Promise<{ success: boolean; updated: number; total: number }> {
  const response = await fetch(`${DASHBOARD_URL}/layout`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    throw new Error(`更新布局失败: ${response.statusText}`)
  }

  return response.json()
}

// ============ 触发器管理 ============

/**
 * 获取卡片触发器
 */
export async function getTriggers(
  cardId: string
): Promise<{ card_id: string; triggers: Trigger[] }> {
  const response = await fetch(`${DASHBOARD_URL}/cards/${cardId}/triggers`)

  if (!response.ok) {
    throw new Error(`获取触发器失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 更新卡片触发器
 */
export async function updateTriggers(
  cardId: string,
  request: UpdateTriggersRequest
): Promise<void> {
  const response = await fetch(`${DASHBOARD_URL}/cards/${cardId}/triggers`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    throw new Error(`更新触发器失败: ${response.statusText}`)
  }
}

/**
 * 删除触发器
 */
export async function deleteTrigger(
  cardId: string,
  triggerId: string
): Promise<void> {
  const response = await fetch(
    `${DASHBOARD_URL}/cards/${cardId}/triggers/${triggerId}`,
    { method: 'DELETE' }
  )

  if (!response.ok) {
    throw new Error(`删除触发器失败: ${response.statusText}`)
  }
}

// ============ 通知管理 ============

/**
 * 获取通知列表
 */
export async function listNotifications(
  unreadOnly: boolean = false,
  cardId?: string,
  limit: number = 50
): Promise<NotificationListResponse> {
  const params = new URLSearchParams()
  if (unreadOnly) params.append('unread_only', 'true')
  if (cardId) params.append('card_id', cardId)
  params.append('limit', limit.toString())

  const response = await fetch(
    `${DASHBOARD_URL}/notifications?${params.toString()}`
  )

  if (!response.ok) {
    throw new Error(`获取通知列表失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 获取未读通知数量
 */
export async function getUnreadCount(): Promise<UnreadCountResponse> {
  const response = await fetch(`${DASHBOARD_URL}/notifications/unread/count`)

  if (!response.ok) {
    throw new Error(`获取未读数量失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 标记通知为已读
 */
export async function markNotificationRead(
  notificationId: string
): Promise<void> {
  const response = await fetch(
    `${DASHBOARD_URL}/notifications/${notificationId}/read`,
    { method: 'POST' }
  )

  if (!response.ok) {
    throw new Error(`标记已读失败: ${response.statusText}`)
  }
}

/**
 * 标记所有通知为已读
 */
export async function markAllNotificationsRead(): Promise<{ marked: number }> {
  const response = await fetch(`${DASHBOARD_URL}/notifications/read-all`, {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error(`标记全部已读失败: ${response.statusText}`)
  }

  return response.json()
}
