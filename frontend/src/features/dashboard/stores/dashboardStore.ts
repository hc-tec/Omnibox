/**
 * 仪表盘状态管理
 *
 * Phase 5: Dashboard Pinia Store
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  DashboardCard,
  CardData,
  Notification,
  Trigger,
  PinArtifactRequest,
  PinWorkflowRequest,
  PinPanelRequest,
  UpdateCardRequest,
  Position,
} from '../types/dashboard'
import * as dashboardApi from '../services/dashboardApi'

export const useDashboardStore = defineStore('dashboard', () => {
  // ============ State ============

  // 卡片列表
  const cards = ref<DashboardCard[]>([])

  // 卡片数据缓存
  const cardDataMap = ref<Record<string, CardData>>({})

  // 正在加载的卡片
  const loadingCards = ref<Set<string>>(new Set())

  // 通知列表
  const notifications = ref<Notification[]>([])

  // 未读通知数量
  const unreadCount = ref(0)

  // UI 状态
  const editMode = ref(false)
  const selectedCardId = ref<string | null>(null)
  const showAddCardDialog = ref(false)
  const showSettingsDialog = ref(false)

  // 加载状态
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ============ Getters ============

  const selectedCard = computed(() => {
    if (!selectedCardId.value) return null
    return cards.value.find((c) => c.card_id === selectedCardId.value) || null
  })

  const enabledCards = computed(() => {
    return cards.value.filter((c) => c.enabled)
  })

  const sortedCards = computed(() => {
    return [...cards.value].sort((a, b) => {
      if (a.position.y !== b.position.y) {
        return a.position.y - b.position.y
      }
      return a.position.x - b.position.x
    })
  })

  const unreadNotifications = computed(() => {
    return notifications.value.filter((n) => n.status !== 'read')
  })

  // ============ Actions ============

  /**
   * 加载卡片列表
   */
  async function loadCards(enabledOnly: boolean = false) {
    loading.value = true
    error.value = null

    try {
      const response = await dashboardApi.listCards(enabledOnly)
      cards.value = response.cards
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载卡片失败'
      console.error('加载卡片失败:', e)
    } finally {
      loading.value = false
    }
  }

  /**
   * Pin 数据产物
   */
  async function pinArtifact(request: PinArtifactRequest): Promise<DashboardCard | null> {
    loading.value = true
    error.value = null

    try {
      const card = await dashboardApi.pinArtifact(request)
      cards.value.push(card)
      return card
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Pin 失败'
      console.error('Pin 数据产物失败:', e)
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * Pin 工作流
   */
  async function pinWorkflow(request: PinWorkflowRequest): Promise<DashboardCard | null> {
    loading.value = true
    error.value = null

    try {
      const card = await dashboardApi.pinWorkflow(request)
      cards.value.push(card)
      return card
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Pin 失败'
      console.error('Pin 工作流失败:', e)
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * Pin 面板到仪表盘
   */
  async function pinPanel(request: PinPanelRequest): Promise<DashboardCard | null> {
    loading.value = true
    error.value = null

    try {
      const card = await dashboardApi.pinPanel(request)
      cards.value.push(card)
      return card
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Pin 面板失败'
      console.error('Pin 面板失败:', e)
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新卡片
   */
  async function updateCard(
    cardId: string,
    request: UpdateCardRequest
  ): Promise<boolean> {
    try {
      const updated = await dashboardApi.updateCard(cardId, request)
      const index = cards.value.findIndex((c) => c.card_id === cardId)
      if (index !== -1) {
        cards.value[index] = updated
      }
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : '更新失败'
      console.error('更新卡片失败:', e)
      return false
    }
  }

  /**
   * 删除卡片
   */
  async function deleteCard(cardId: string): Promise<boolean> {
    try {
      await dashboardApi.deleteCard(cardId)
      cards.value = cards.value.filter((c) => c.card_id !== cardId)
      delete cardDataMap.value[cardId]
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : '删除失败'
      console.error('删除卡片失败:', e)
      return false
    }
  }

  /**
   * 刷新卡片数据
   */
  async function refreshCard(cardId: string): Promise<CardData | null> {
    loadingCards.value.add(cardId)

    try {
      const data = await dashboardApi.refreshCard(cardId)
      cardDataMap.value[cardId] = data

      // 更新卡片的 last_refresh_at
      const card = cards.value.find((c) => c.card_id === cardId)
      if (card) {
        card.last_refresh_at = data.refreshed_at
      }

      return data
    } catch (e) {
      console.error('刷新卡片失败:', e)
      return null
    } finally {
      loadingCards.value.delete(cardId)
    }
  }

  /**
   * 获取卡片数据（优先使用缓存）
   */
  async function getCardData(cardId: string): Promise<CardData | null> {
    // 如果有缓存，直接返回
    if (cardDataMap.value[cardId]) {
      return cardDataMap.value[cardId]
    }

    loadingCards.value.add(cardId)

    try {
      const data = await dashboardApi.getCardData(cardId)
      cardDataMap.value[cardId] = data
      return data
    } catch (e) {
      console.error('获取卡片数据失败:', e)
      return null
    } finally {
      loadingCards.value.delete(cardId)
    }
  }

  /**
   * 刷新所有卡片
   */
  async function refreshAll(): Promise<void> {
    const promises = cards.value
      .filter((c) => c.enabled)
      .map((c) => refreshCard(c.card_id))

    await Promise.all(promises)
  }

  /**
   * 更新布局
   */
  async function updateLayout(
    layouts: Array<{ card_id: string } & Position>
  ): Promise<boolean> {
    try {
      await dashboardApi.updateLayout({ layouts })

      // 更新本地状态
      for (const layout of layouts) {
        const card = cards.value.find((c) => c.card_id === layout.card_id)
        if (card) {
          card.position = {
            x: layout.x,
            y: layout.y,
            width: layout.width,
            height: layout.height,
          }
        }
      }

      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : '更新布局失败'
      console.error('更新布局失败:', e)
      return false
    }
  }

  /**
   * 更新触发器
   */
  async function updateTriggers(
    cardId: string,
    triggers: Trigger[]
  ): Promise<boolean> {
    try {
      await dashboardApi.updateTriggers(cardId, { triggers })

      // 更新本地状态
      const card = cards.value.find((c) => c.card_id === cardId)
      if (card) {
        card.triggers = triggers
      }

      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : '更新触发器失败'
      console.error('更新触发器失败:', e)
      return false
    }
  }

  // ============ 通知相关 ============

  /**
   * 加载通知列表
   */
  async function loadNotifications(unreadOnly: boolean = false): Promise<void> {
    try {
      const response = await dashboardApi.listNotifications(unreadOnly)
      notifications.value = response.notifications
      unreadCount.value = response.unread_count
    } catch (e) {
      console.error('加载通知失败:', e)
    }
  }

  /**
   * 刷新未读数量
   */
  async function refreshUnreadCount(): Promise<void> {
    try {
      const response = await dashboardApi.getUnreadCount()
      unreadCount.value = response.count
    } catch (e) {
      console.error('获取未读数量失败:', e)
    }
  }

  /**
   * 标记通知为已读
   */
  async function markRead(notificationId: string): Promise<boolean> {
    try {
      await dashboardApi.markNotificationRead(notificationId)

      const notification = notifications.value.find(
        (n) => n.notification_id === notificationId
      )
      if (notification) {
        notification.status = 'read'
        notification.read_at = new Date().toISOString()
      }

      unreadCount.value = Math.max(0, unreadCount.value - 1)
      return true
    } catch (e) {
      console.error('标记已读失败:', e)
      return false
    }
  }

  /**
   * 标记所有通知为已读
   */
  async function markAllRead(): Promise<boolean> {
    try {
      await dashboardApi.markAllNotificationsRead()

      notifications.value.forEach((n) => {
        n.status = 'read'
        n.read_at = new Date().toISOString()
      })

      unreadCount.value = 0
      return true
    } catch (e) {
      console.error('标记全部已读失败:', e)
      return false
    }
  }

  /**
   * 添加新通知（用于 WebSocket 推送）
   */
  function addNotification(notification: Notification): void {
    notifications.value.unshift(notification)
    if (notification.status !== 'read') {
      unreadCount.value++
    }
  }

  // ============ UI 操作 ============

  function selectCard(cardId: string | null): void {
    selectedCardId.value = cardId
  }

  function toggleEditMode(): void {
    editMode.value = !editMode.value
  }

  function clearError(): void {
    error.value = null
  }

  function openAddCardDialog(): void {
    showAddCardDialog.value = true
  }

  function closeAddCardDialog(): void {
    showAddCardDialog.value = false
  }

  function openSettingsDialog(cardId: string): void {
    selectedCardId.value = cardId
    showSettingsDialog.value = true
  }

  function closeSettingsDialog(): void {
    showSettingsDialog.value = false
    selectedCardId.value = null
  }

  /**
   * 检查卡片是否正在加载
   */
  function isCardLoading(cardId: string): boolean {
    return loadingCards.value.has(cardId)
  }

  return {
    // State
    cards,
    cardDataMap,
    loadingCards,
    notifications,
    unreadCount,
    editMode,
    selectedCardId,
    showAddCardDialog,
    showSettingsDialog,
    loading,
    error,

    // Getters
    selectedCard,
    enabledCards,
    sortedCards,
    unreadNotifications,

    // Actions
    loadCards,
    pinArtifact,
    pinWorkflow,
    pinPanel,
    updateCard,
    deleteCard,
    refreshCard,
    getCardData,
    refreshAll,
    updateLayout,
    updateTriggers,

    // 通知
    loadNotifications,
    refreshUnreadCount,
    markRead,
    markAllRead,
    addNotification,

    // UI
    selectCard,
    toggleEditMode,
    clearError,
    isCardLoading,
    openAddCardDialog,
    closeAddCardDialog,
    openSettingsDialog,
    closeSettingsDialog,
  }
})
