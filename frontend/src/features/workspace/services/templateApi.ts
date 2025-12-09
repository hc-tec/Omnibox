/**
 * 模板 API 服务
 *
 * Phase 4: 模板市场相关 API 调用
 */

import type {
  TemplateResponse,
  TemplateListResponse,
  TemplateListQuery,
  CreateTemplateRequest,
  InstantiateRequest,
  InstantiateResponse,
  ValidateVariablesResponse,
  CategoryStats,
  TemplateStatsResponse,
  ImportTemplateRequest,
} from '../types/template'

const API_BASE = '/api/v1/templates'

/**
 * 获取模板列表
 */
export async function listTemplates(
  query: TemplateListQuery = {}
): Promise<TemplateListResponse> {
  const params = new URLSearchParams()

  if (query.category) params.set('category', query.category)
  if (query.tags?.length) params.set('tags', query.tags.join(','))
  if (query.search) params.set('search', query.search)
  if (query.sort_by) params.set('sort_by', query.sort_by)
  if (query.limit) params.set('limit', String(query.limit))
  if (query.offset) params.set('offset', String(query.offset))

  const url = params.toString() ? `${API_BASE}?${params}` : API_BASE
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`获取模板列表失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 获取模板详情
 */
export async function getTemplate(templateId: string): Promise<TemplateResponse> {
  const response = await fetch(`${API_BASE}/${templateId}`)

  if (!response.ok) {
    throw new Error(`获取模板详情失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 获取分类列表
 */
export async function listCategories(): Promise<CategoryStats[]> {
  const response = await fetch(`${API_BASE}/categories`)

  if (!response.ok) {
    throw new Error(`获取分类列表失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 获取模板市场统计
 */
export async function getTemplateStats(): Promise<TemplateStatsResponse> {
  const response = await fetch(`${API_BASE}/stats`)

  if (!response.ok) {
    throw new Error(`获取模板统计失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 创建模板
 */
export async function createTemplate(
  request: CreateTemplateRequest
): Promise<TemplateResponse> {
  const response = await fetch(API_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `创建模板失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 实例化模板
 */
export async function instantiateTemplate(
  templateId: string,
  request: InstantiateRequest
): Promise<InstantiateResponse> {
  const response = await fetch(`${API_BASE}/${templateId}/instantiate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `实例化模板失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 校验变量值
 */
export async function validateVariables(
  templateId: string,
  variableValues: Record<string, unknown>
): Promise<ValidateVariablesResponse> {
  const response = await fetch(`${API_BASE}/${templateId}/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ variable_values: variableValues }),
  })

  if (!response.ok) {
    throw new Error(`校验变量失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 导出模板
 */
export async function exportTemplate(
  templateId: string
): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/${templateId}/export`)

  if (!response.ok) {
    throw new Error(`导出模板失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 导入模板
 */
export async function importTemplate(
  request: ImportTemplateRequest
): Promise<TemplateResponse> {
  const response = await fetch(`${API_BASE}/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `导入模板失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 下载模板 JSON 文件
 */
export async function downloadTemplate(templateId: string, filename?: string): Promise<void> {
  const data = await exportTemplate(templateId)

  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)

  const a = document.createElement('a')
  a.href = url
  a.download = filename || `template-${templateId}.json`
  document.body.appendChild(a)
  a.click()

  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
