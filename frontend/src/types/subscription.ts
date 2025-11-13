/**
 * 订阅管理相关类型定义
 *
 * 与后端 API Schema 保持一致
 * 后端定义：api/schemas/subscription.py
 */

/**
 * 订阅响应（与后端 SubscriptionResponse 对应）
 */
export interface Subscription {
  id: number
  display_name: string
  platform: string
  entity_type: string
  identifiers: Record<string, any>
  description: string | null
  avatar_url: string | null
  aliases: string[]
  tags: string[]
  supported_actions: string[]
  subscribe_count: number
  last_fetched_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

/**
 * 创建订阅请求（与后端 SubscriptionCreate 对应）
 */
export interface SubscriptionCreateRequest {
  display_name: string
  platform: string
  entity_type: string
  identifiers: Record<string, any>
  description?: string
  avatar_url?: string
  aliases?: string[]
  tags?: string[]
}

/**
 * 更新订阅请求（与后端 SubscriptionUpdate 对应）
 */
export interface SubscriptionUpdateRequest {
  display_name?: string
  platform?: string
  entity_type?: string
  identifiers?: Record<string, any>
  description?: string
  avatar_url?: string
  aliases?: string[]
  tags?: string[]
  is_active?: boolean
}

/**
 * 订阅列表响应（与后端 SubscriptionListResponse 对应）
 */
export interface SubscriptionListResponse {
  total: number
  items: Subscription[]
}

/**
 * 动作信息（与后端 ActionInfo 对应）
 */
export interface ActionInfo {
  action: string
  display_name: string
  description: string | null
  path_template: string
}

/**
 * 解析实体请求（与后端 ResolveEntityRequest 对应）
 */
export interface ResolveEntityRequest {
  entity_name: string
  platform: string
  entity_type: string
}

/**
 * 解析实体响应（与后端 ResolveEntityResponse 对应）
 */
export interface ResolveEntityResponse {
  success: boolean
  identifiers: Record<string, any> | null
  subscription_id: number | null
  message: string | null
}

/**
 * 订阅列表查询参数
 */
export interface SubscriptionQueryParams {
  platform?: string
  entity_type?: string
  is_active?: boolean
  limit?: number
  offset?: number
}

/**
 * 平台枚举
 */
export type Platform = 'bilibili' | 'zhihu' | 'weibo' | 'github' | 'gitee'

/**
 * 实体类型枚举
 */
export type EntityType = 'user' | 'column' | 'repo' | 'topic' | 'channel'

/**
 * 平台显示名称映射
 */
export const PLATFORM_DISPLAY_NAMES: Record<string, string> = {
  bilibili: 'B站',
  zhihu: '知乎',
  weibo: '微博',
  github: 'GitHub',
  gitee: 'Gitee',
}

/**
 * 实体类型显示名称映射
 */
export const ENTITY_TYPE_DISPLAY_NAMES: Record<string, string> = {
  user: '用户',
  column: '专栏',
  repo: '仓库',
  topic: '话题',
  channel: '频道',
}

/**
 * 动作显示名称映射
 */
export const ACTION_DISPLAY_NAMES: Record<string, string> = {
  videos: '投稿视频',
  following: '关注列表',
  favorites: '收藏',
  dynamics: '动态',
  articles: '文章',
  activities: '动态',
  posts: '微博',
  commits: 'Commits',
  issues: 'Issues',
  pull_requests: 'Pull Requests',
  releases: 'Releases',
}
