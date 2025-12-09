/**
 * 模板市场状态管理
 *
 * Phase 4: 模板市场 Pinia Store
 */

import { ref, computed, reactive } from 'vue'
import { defineStore } from 'pinia'
import type {
  TemplateResponse,
  TemplateListQuery,
  CategoryStats,
  CreateTemplateRequest,
  InstantiateRequest,
} from '../types/template'
import * as templateApi from '../services/templateApi'

export const useTemplateStore = defineStore('template', () => {
  // ========== 状态 ==========

  // 模板列表
  const templates = ref<TemplateResponse[]>([])
  const total = ref(0)
  const categoryStats = ref<Record<string, number>>({})

  // 分类列表
  const categories = ref<CategoryStats[]>([])

  // 筛选条件
  const filters = reactive<{
    category: string | null
    search: string
    sortBy: 'usage_count' | 'created_at' | 'name'
  }>({
    category: null,
    search: '',
    sortBy: 'usage_count',
  })

  // 分页
  const page = ref(1)
  const pageSize = ref(20)

  // UI 状态
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 当前操作
  const selectedTemplate = ref<TemplateResponse | null>(null)

  // ========== 计算属性 ==========

  const offset = computed(() => (page.value - 1) * pageSize.value)

  const totalPages = computed(() => Math.ceil(total.value / pageSize.value))

  const hasMore = computed(() => page.value < totalPages.value)

  // ========== Actions ==========

  /**
   * 加载模板列表
   */
  async function loadTemplates(resetPage = true) {
    if (resetPage) {
      page.value = 1
    }

    loading.value = true
    error.value = null

    try {
      const query: TemplateListQuery = {
        category: filters.category || undefined,
        search: filters.search || undefined,
        sort_by: filters.sortBy,
        limit: pageSize.value,
        offset: offset.value,
      }

      const response = await templateApi.listTemplates(query)

      templates.value = response.templates
      total.value = response.total
      categoryStats.value = response.categories
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载模板失败'
      console.error('loadTemplates error:', e)
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载更多（分页）
   */
  async function loadMore() {
    if (!hasMore.value || loading.value) return

    page.value++
    loading.value = true

    try {
      const query: TemplateListQuery = {
        category: filters.category || undefined,
        search: filters.search || undefined,
        sort_by: filters.sortBy,
        limit: pageSize.value,
        offset: offset.value,
      }

      const response = await templateApi.listTemplates(query)

      templates.value = [...templates.value, ...response.templates]
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载更多失败'
      page.value-- // 回退页码
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载分类列表
   */
  async function loadCategories() {
    try {
      categories.value = await templateApi.listCategories()
    } catch (e) {
      console.error('loadCategories error:', e)
    }
  }

  /**
   * 设置筛选条件
   */
  function setFilter(key: keyof typeof filters, value: unknown) {
    ;(filters as Record<string, unknown>)[key] = value
    loadTemplates(true)
  }

  /**
   * 重置筛选条件
   */
  function resetFilters() {
    filters.category = null
    filters.search = ''
    filters.sortBy = 'usage_count'
    loadTemplates(true)
  }

  /**
   * 选择模板
   */
  function selectTemplate(template: TemplateResponse | null) {
    selectedTemplate.value = template
  }

  /**
   * 获取模板详情
   */
  async function getTemplateDetail(templateId: string): Promise<TemplateResponse | null> {
    try {
      return await templateApi.getTemplate(templateId)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取模板详情失败'
      return null
    }
  }

  /**
   * 创建模板
   */
  async function createTemplate(request: CreateTemplateRequest): Promise<TemplateResponse | null> {
    loading.value = true
    error.value = null

    try {
      const template = await templateApi.createTemplate(request)

      // 刷新列表
      await loadTemplates(false)

      return template
    } catch (e) {
      error.value = e instanceof Error ? e.message : '创建模板失败'
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 实例化模板
   */
  async function instantiateTemplate(
    templateId: string,
    request: InstantiateRequest
  ): Promise<string | null> {
    loading.value = true
    error.value = null

    try {
      const response = await templateApi.instantiateTemplate(templateId, request)
      return response.workflow_id
    } catch (e) {
      error.value = e instanceof Error ? e.message : '实例化模板失败'
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 校验变量
   */
  async function validateVariables(
    templateId: string,
    values: Record<string, unknown>
  ): Promise<{ valid: boolean; errors: string[] }> {
    try {
      return await templateApi.validateVariables(templateId, values)
    } catch (e) {
      return { valid: false, errors: ['校验失败'] }
    }
  }

  /**
   * 导出模板
   */
  async function exportTemplate(templateId: string, filename?: string): Promise<boolean> {
    try {
      await templateApi.downloadTemplate(templateId, filename)
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : '导出模板失败'
      return false
    }
  }

  /**
   * 导入模板
   */
  async function importTemplate(
    data: Record<string, unknown>,
    author?: string
  ): Promise<TemplateResponse | null> {
    loading.value = true
    error.value = null

    try {
      const template = await templateApi.importTemplate({
        template_data: data,
        author: author || 'imported',
      })

      // 刷新列表
      await loadTemplates(false)

      return template
    } catch (e) {
      error.value = e instanceof Error ? e.message : '导入模板失败'
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 从文件导入模板
   */
  async function importTemplateFromFile(file: File, author?: string): Promise<TemplateResponse | null> {
    try {
      const text = await file.text()
      const data = JSON.parse(text)
      return await importTemplate(data, author)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'JSON 文件格式错误'
      return null
    }
  }

  return {
    // 状态
    templates,
    total,
    categoryStats,
    categories,
    filters,
    page,
    pageSize,
    loading,
    error,
    selectedTemplate,

    // 计算属性
    offset,
    totalPages,
    hasMore,

    // Actions
    loadTemplates,
    loadMore,
    loadCategories,
    setFilter,
    resetFilters,
    selectTemplate,
    getTemplateDetail,
    createTemplate,
    instantiateTemplate,
    validateVariables,
    exportTemplate,
    importTemplate,
    importTemplateFromFile,
  }
})
