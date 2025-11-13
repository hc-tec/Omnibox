/**
 * 订阅管理 Pinia Store
 *
 * 统一管理订阅数据状态和操作
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  Subscription,
  SubscriptionCreateRequest,
  SubscriptionUpdateRequest,
  SubscriptionQueryParams,
  ActionInfo,
} from '@/types/subscription'
import * as subscriptionApi from '@/services/subscriptionApi'

export const useSubscriptionStore = defineStore('subscription', () => {
  // ==================== 状态 ====================

  /** 订阅列表 */
  const subscriptions = ref<Subscription[]>([])

  /** 总数 */
  const total = ref<number>(0)

  /** 加载状态 */
  const loading = ref<boolean>(false)

  /** 当前选中的订阅 */
  const currentSubscription = ref<Subscription | null>(null)

  /** 当前订阅的动作列表 */
  const currentActions = ref<ActionInfo[]>([])

  /** 错误信息 */
  const error = ref<string | null>(null)

  // ==================== 计算属性 ====================

  /** 按平台分组的订阅 */
  const subscriptionsByPlatform = computed(() => {
    const grouped: Record<string, Subscription[]> = {}
    subscriptions.value.forEach((sub) => {
      if (!grouped[sub.platform]) {
        grouped[sub.platform] = []
      }
      grouped[sub.platform].push(sub)
    })
    return grouped
  })

  /** 激活的订阅列表 */
  const activeSubscriptions = computed(() => {
    return subscriptions.value.filter((sub) => sub.is_active)
  })

  // ==================== 操作方法 ====================

  /**
   * 加载订阅列表
   */
  async function fetchSubscriptions(params?: SubscriptionQueryParams, append: boolean = false) {
    loading.value = true
    error.value = null

    try {
      const response = await subscriptionApi.listSubscriptions(params)

      if (append) {
        // 追加模式：将新数据添加到现有列表
        subscriptions.value = [...subscriptions.value, ...(response.items || [])]
      } else {
        // 替换模式：替换整个列表
        subscriptions.value = response.items || []
      }

      total.value = response.total || 0
    } catch (err: any) {
      error.value = err.message || '加载订阅列表失败'
      console.error('加载订阅列表失败:', err)

      // 失败时，如果不是追加模式才清空
      if (!append) {
        subscriptions.value = []
        total.value = 0
      }
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取订阅详情
   */
  async function fetchSubscription(id: number) {
    loading.value = true
    error.value = null

    try {
      const subscription = await subscriptionApi.getSubscription(id)
      currentSubscription.value = subscription

      // 同时加载动作列表
      await fetchSubscriptionActions(id)

      return subscription
    } catch (err: any) {
      error.value = err.message || '加载订阅详情失败'
      console.error('加载订阅详情失败:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建订阅
   */
  async function createSubscription(data: SubscriptionCreateRequest) {
    loading.value = true
    error.value = null

    try {
      const subscription = await subscriptionApi.createSubscription(data)

      // 添加到列表
      subscriptions.value.unshift(subscription)
      total.value += 1

      return subscription
    } catch (err: any) {
      error.value = err.message || '创建订阅失败'
      console.error('创建订阅失败:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新订阅
   */
  async function updateSubscription(
    id: number,
    data: SubscriptionUpdateRequest
  ) {
    loading.value = true
    error.value = null

    try {
      const updated = await subscriptionApi.updateSubscription(id, data)

      // 更新列表中的订阅
      const index = subscriptions.value.findIndex((sub) => sub.id === id)
      if (index !== -1) {
        subscriptions.value[index] = updated
      }

      // 更新当前订阅
      if (currentSubscription.value?.id === id) {
        currentSubscription.value = updated
      }

      return updated
    } catch (err: any) {
      error.value = err.message || '更新订阅失败'
      console.error('更新订阅失败:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 删除订阅
   */
  async function deleteSubscription(id: number) {
    loading.value = true
    error.value = null

    try {
      await subscriptionApi.deleteSubscription(id)

      // 从列表中移除
      subscriptions.value = subscriptions.value.filter((sub) => sub.id !== id)
      total.value -= 1

      // 清空当前订阅
      if (currentSubscription.value?.id === id) {
        currentSubscription.value = null
        currentActions.value = []
      }
    } catch (err: any) {
      error.value = err.message || '删除订阅失败'
      console.error('删除订阅失败:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取订阅支持的动作列表
   */
  async function fetchSubscriptionActions(id: number) {
    try {
      const actions = await subscriptionApi.getSubscriptionActions(id)
      currentActions.value = actions
      return actions
    } catch (err: any) {
      console.error('加载动作列表失败:', err)
      throw err
    }
  }

  /**
   * 清空错误信息
   */
  function clearError() {
    error.value = null
  }

  /**
   * 重置状态
   */
  function reset() {
    subscriptions.value = []
    total.value = 0
    loading.value = false
    currentSubscription.value = null
    currentActions.value = []
    error.value = null
  }

  return {
    // 状态
    subscriptions,
    total,
    loading,
    currentSubscription,
    currentActions,
    error,

    // 计算属性
    subscriptionsByPlatform,
    activeSubscriptions,

    // 操作方法
    fetchSubscriptions,
    fetchSubscription,
    createSubscription,
    updateSubscription,
    deleteSubscription,
    fetchSubscriptionActions,
    clearError,
    reset,
  }
})
