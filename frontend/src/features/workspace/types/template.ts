/**
 * 模板系统类型定义
 *
 * Phase 4: 模板市场相关类型
 */

/**
 * 变量定义
 */
export interface VariableSchema {
  name: string
  var_type: 'string' | 'number' | 'boolean' | 'datasource' | 'list'
  description: string
  default?: unknown
  required: boolean
  enum_values?: unknown[]
}

/**
 * 模板响应
 */
export interface TemplateResponse {
  template_id: string
  name: string
  description: string
  category: string | null
  author: string | null
  tags: string[]
  usage_count: number
  preview_image: string | null
  version: string

  // 变量定义
  variables: Record<string, VariableSchema>

  // 步骤概要
  step_count: number
  step_types: string[]

  created_at: string
  updated_at: string
}

/**
 * 模板列表响应
 */
export interface TemplateListResponse {
  templates: TemplateResponse[]
  total: number
  categories: Record<string, number>
}

/**
 * 模板列表查询参数
 */
export interface TemplateListQuery {
  category?: string | null
  tags?: string[]
  search?: string
  sort_by?: 'usage_count' | 'created_at' | 'name'
  limit?: number
  offset?: number
}

/**
 * 创建模板请求
 */
export interface CreateTemplateRequest {
  workflow_id: string
  category: string
  author?: string
  preview_image?: string
  tags?: string[]
}

/**
 * 实例化模板请求
 */
export interface InstantiateRequest {
  variable_values: Record<string, unknown>
  new_name?: string
}

/**
 * 实例化响应
 */
export interface InstantiateResponse {
  workflow_id: string
  name: string
  status: string
  template_source_id: string
}

/**
 * 变量校验响应
 */
export interface ValidateVariablesResponse {
  valid: boolean
  errors: string[]
}

/**
 * 分类统计
 */
export interface CategoryStats {
  category: string
  label: string
  count: number
}

/**
 * 模板市场统计
 */
export interface TemplateStatsResponse {
  total: number
  categories: CategoryStats[]
}

/**
 * 导入模板请求
 */
export interface ImportTemplateRequest {
  template_data: Record<string, unknown>
  author?: string
}

/**
 * 模板分类枚举
 */
export const TEMPLATE_CATEGORIES = {
  data_analysis: '数据分析',
  content_research: '内容研究',
  competitive: '竞品分析',
  social_monitoring: '社交监控',
  report_generation: '报告生成',
  custom: '自定义',
} as const

export type TemplateCategoryKey = keyof typeof TEMPLATE_CATEGORIES
