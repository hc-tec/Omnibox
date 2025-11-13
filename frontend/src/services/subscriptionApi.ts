/**
 * 订阅管理 API 服务
 *
 * 封装所有与订阅相关的 HTTP 请求
 */

import axios from 'axios'
import { resolveHttpBase } from '@/shared/networkBase'
import type {
  Subscription,
  SubscriptionCreateRequest,
  SubscriptionUpdateRequest,
  SubscriptionListResponse,
  SubscriptionQueryParams,
  ActionInfo,
  ResolveEntityRequest,
  ResolveEntityResponse,
} from '@/types/subscription'

// API 基础路径（使用项目统一的路径解析方法）
const API_BASE = resolveHttpBase(import.meta.env.VITE_API_BASE, '/api/v1')
const API_BASE_URL = `${API_BASE}/subscriptions`

/**
 * 列出订阅
 */
export async function listSubscriptions(
  params?: SubscriptionQueryParams
): Promise<SubscriptionListResponse> {
  const response = await axios.get<SubscriptionListResponse>(API_BASE_URL, {
    params,
  })
  return response.data
}

/**
 * 获取订阅详情
 */
export async function getSubscription(id: number): Promise<Subscription> {
  const response = await axios.get<Subscription>(`${API_BASE_URL}/${id}`)
  return response.data
}

/**
 * 创建订阅
 */
export async function createSubscription(
  data: SubscriptionCreateRequest
): Promise<Subscription> {
  const response = await axios.post<Subscription>(API_BASE_URL, data)
  return response.data
}

/**
 * 更新订阅
 */
export async function updateSubscription(
  id: number,
  data: SubscriptionUpdateRequest
): Promise<Subscription> {
  const response = await axios.patch<Subscription>(
    `${API_BASE_URL}/${id}`,
    data
  )
  return response.data
}

/**
 * 删除订阅
 */
export async function deleteSubscription(id: number): Promise<void> {
  await axios.delete(`${API_BASE_URL}/${id}`)
}

/**
 * 获取订阅支持的动作列表
 */
export async function getSubscriptionActions(
  id: number
): Promise<ActionInfo[]> {
  const response = await axios.get<ActionInfo[]>(
    `${API_BASE_URL}/${id}/actions`
  )
  return response.data
}

/**
 * 解析实体标识符
 */
export async function resolveEntity(
  data: ResolveEntityRequest
): Promise<ResolveEntityResponse> {
  const response = await axios.post<ResolveEntityResponse>(
    `${API_BASE_URL}/resolve`,
    data
  )
  return response.data
}
