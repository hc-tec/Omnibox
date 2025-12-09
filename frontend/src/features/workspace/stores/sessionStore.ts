/**
 * Session 状态管理
 *
 * 管理 Workspace 的 Session 生命周期：
 * - 创建/恢复 Session
 * - 执行查询（保持上下文）
 * - 保存为工作流模板
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as sessionApi from '../services/sessionApi'
import type {
  SessionInfo,
  RecordedStepInfo,
  SessionChatResponse,
} from '../services/sessionApi'

export const useSessionStore = defineStore('workspace-session', () => {
  // ========== 状态 ==========

  /** 当前 Session */
  const currentSession = ref<SessionInfo | null>(null)

  /** 执行步骤记录 */
  const recordedSteps = ref<RecordedStepInfo[]>([])

  /** 加载状态 */
  const loading = ref(false)

  /** 执行中 */
  const executing = ref(false)

  /** 错误信息 */
  const error = ref<string | null>(null)

  /** 最后一次执行结果 */
  const lastChatResult = ref<SessionChatResponse | null>(null)

  // ========== 计算属性 ==========

  /** 是否有活跃的 Session */
  const hasSession = computed(() => currentSession.value !== null)

  /** Session ID */
  const sessionId = computed(() => currentSession.value?.session_id || null)

  /** data_stash 数量 */
  const dataStashCount = computed(
    () => currentSession.value?.data_stash_count || 0
  )

  /** chat_history 数量 */
  const chatHistoryCount = computed(
    () => currentSession.value?.chat_history_count || 0
  )

  /** recorded_steps 数量 */
  const stepsCount = computed(
    () => currentSession.value?.recorded_steps_count || 0
  )

  /** 是否可以保存为模板 */
  const canSaveAsTemplate = computed(() => stepsCount.value > 0)

  // ========== Actions ==========

  /**
   * 创建新 Session
   */
  async function createSession(workspaceId?: string, name?: string) {
    loading.value = true
    error.value = null

    try {
      const response = await sessionApi.createSession({
        workspace_id: workspaceId,
        name,
      })

      if (response.success) {
        currentSession.value = response.session
        recordedSteps.value = []
        lastChatResult.value = null
        return response.session
      } else {
        throw new Error('创建 Session 失败')
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : '创建 Session 失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  /**
   * 恢复已有 Session
   */
  async function resumeSession(sessionId: string) {
    loading.value = true
    error.value = null

    try {
      const response = await sessionApi.getSession(sessionId)

      if (response.success && response.session) {
        currentSession.value = response.session

        // 加载执行步骤
        await loadRecordedSteps()

        return response.session
      } else {
        throw new Error(response.error || 'Session 不存在或已过期')
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : '恢复 Session 失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  /**
   * 确保有活跃的 Session
   *
   * 如果没有则自动创建
   */
  async function ensureSession(workspaceId?: string) {
    if (hasSession.value) {
      return currentSession.value!
    }
    return await createSession(workspaceId)
  }

  /**
   * 在 Session 内执行查询
   */
  async function chat(
    query: string,
    context?: Record<string, unknown>
  ): Promise<SessionChatResponse> {
    if (!sessionId.value) {
      throw new Error('没有活跃的 Session')
    }

    executing.value = true
    error.value = null

    try {
      const response = await sessionApi.sessionChat(sessionId.value, {
        query,
        context,
      })

      if (response.success) {
        // 更新 Session 统计
        if (response.session_summary && currentSession.value) {
          currentSession.value.data_stash_count =
            response.session_summary.data_stash_count
          currentSession.value.chat_history_count =
            response.session_summary.chat_history_count
          currentSession.value.recorded_steps_count =
            response.session_summary.recorded_steps_count
        }

        lastChatResult.value = response

        // 刷新执行步骤
        await loadRecordedSteps()

        return response
      } else {
        throw new Error(response.error || '执行失败')
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : '执行失败'
      throw e
    } finally {
      executing.value = false
    }
  }

  /**
   * 加载执行步骤
   */
  async function loadRecordedSteps() {
    if (!sessionId.value) return

    try {
      const response = await sessionApi.getRecordedSteps(sessionId.value)
      if (response.success) {
        recordedSteps.value = response.steps
      }
    } catch (e) {
      console.error('加载执行步骤失败:', e)
    }
  }

  /**
   * 保存为工作流模板
   */
  async function saveAsTemplate(
    name: string,
    description?: string,
    category?: string
  ) {
    if (!sessionId.value) {
      throw new Error('没有活跃的 Session')
    }

    if (!canSaveAsTemplate.value) {
      throw new Error('没有执行记录，无法保存为模板')
    }

    loading.value = true
    error.value = null

    try {
      const response = await sessionApi.saveAsTemplate(sessionId.value, {
        name,
        description,
        category,
        extract_variables: true,
      })

      if (response.success) {
        return {
          workflowId: response.workflow_id,
          workflowName: response.workflow_name,
          stepsCount: response.steps_count,
          variablesCount: response.variables_count,
        }
      } else {
        throw new Error(response.error || '保存失败')
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : '保存失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  /**
   * 关闭当前 Session
   */
  async function closeSession() {
    if (!sessionId.value) return

    try {
      await sessionApi.closeSession(sessionId.value)
    } catch (e) {
      console.error('关闭 Session 失败:', e)
    } finally {
      reset()
    }
  }

  /**
   * 重置状态
   */
  function reset() {
    currentSession.value = null
    recordedSteps.value = []
    lastChatResult.value = null
    error.value = null
    loading.value = false
    executing.value = false
  }

  return {
    // State
    currentSession,
    recordedSteps,
    loading,
    executing,
    error,
    lastChatResult,

    // Computed
    hasSession,
    sessionId,
    dataStashCount,
    chatHistoryCount,
    stepsCount,
    canSaveAsTemplate,

    // Actions
    createSession,
    resumeSession,
    ensureSession,
    chat,
    loadRecordedSteps,
    saveAsTemplate,
    closeSession,
    reset,
  }
})
