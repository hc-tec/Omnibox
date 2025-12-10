/**
 * Session WebSocket 连接管理
 *
 * 管理 Workspace Session 的 WebSocket 流式执行：
 * - 连接到 /api/v1/sessions/{session_id}/stream
 * - 实时接收执行进度消息
 * - 转换为 TimelineEntry 更新 UI
 */

import { ref, computed, type Ref } from 'vue'
import { useWorkspaceStore } from '../stores/workspaceStore'
import { useSessionStore } from '../stores/sessionStore'

// 消息类型定义
export interface StreamMessage {
  type: 'stage' | 'data' | 'research_step' | 'complete' | 'error'
  stream_id: string
  stage?: string
  message?: string
  progress?: number
  data?: Record<string, unknown>
  // research_step 字段
  task_id?: string
  step_id?: string
  step_type?: string
  action?: string
  status?: string
  details?: Record<string, unknown>
  reasoning?: string  // Agent 推理内容
  // complete 字段
  success?: boolean
  total_time?: number
  // error 字段
  error_code?: string
  error_message?: string
}

export interface SessionWebSocketOptions {
  sessionId: string
  onMessage?: (message: StreamMessage) => void
  onComplete?: (success: boolean, message: string) => void
  onError?: (error: string) => void
}

export function useSessionWebSocket(options: SessionWebSocketOptions) {
  const { sessionId, onMessage, onComplete, onError } = options

  const workspaceStore = useWorkspaceStore()
  const sessionStore = useSessionStore()

  // 连接状态
  const isConnecting = ref(false)
  const isConnected = ref(false)
  const error = ref<string | null>(null)

  // WebSocket 实例
  let ws: WebSocket | null = null

  /**
   * 构建 WebSocket URL
   * 基于 VITE_API_BASE 环境变量，将 http 替换为 ws
   */
  function buildWsUrl(): string {
    const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8002/api/v1'
    // 将 http:// 替换为 ws://，https:// 替换为 wss://
    const wsBase = apiBase.replace(/^http/, 'ws')
    return `${wsBase}/sessions/${sessionId}/stream`
  }

  /**
   * 连接 WebSocket
   */
  async function connect(): Promise<void> {
    if (isConnected.value || isConnecting.value) {
      console.log('[SessionWS] 已连接或正在连接')
      return
    }

    isConnecting.value = true
    error.value = null

    return new Promise((resolve, reject) => {
      const url = buildWsUrl()
      console.log('[SessionWS] 连接:', url)

      ws = new WebSocket(url)

      ws.onopen = () => {
        console.log('[SessionWS] 连接成功')
        isConnecting.value = false
        isConnected.value = true
        resolve()
      }

      ws.onclose = (event) => {
        console.log('[SessionWS] 连接关闭:', event.code, event.reason)
        isConnecting.value = false
        isConnected.value = false
      }

      ws.onerror = (event) => {
        console.error('[SessionWS] 连接错误:', event)
        isConnecting.value = false
        error.value = 'WebSocket 连接失败'
        reject(new Error('WebSocket 连接失败'))
      }

      ws.onmessage = (event) => {
        try {
          const message: StreamMessage = JSON.parse(event.data)
          console.log('[SessionWS] 收到消息:', message.type, message)
          handleMessage(message)
        } catch (e) {
          console.error('[SessionWS] 消息解析失败:', e)
        }
      }
    })
  }

  /**
   * 发送查询请求
   */
  function sendQuery(query: string, context?: Record<string, unknown>): void {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.error('[SessionWS] 连接未就绪')
      return
    }

    const payload = { query, context }
    console.log('[SessionWS] 发送查询:', payload)
    ws.send(JSON.stringify(payload))
  }

  /**
   * 处理消息
   */
  function handleMessage(message: StreamMessage): void {
    // 调用外部回调
    onMessage?.(message)

    switch (message.type) {
      case 'stage':
        handleStageMessage(message)
        break
      case 'data':
        handleDataMessage(message)
        break
      case 'research_step':
        handleStepMessage(message)
        break
      case 'complete':
        handleCompleteMessage(message)
        break
      case 'error':
        handleErrorMessage(message)
        break
    }
  }

  /**
   * 处理阶段消息 - 转为思考条目
   */
  function handleStageMessage(message: StreamMessage): void {
    const stage = message.stage || 'unknown'
    const text = message.message || `执行阶段: ${stage}`

    // 添加思考条目到时间线
    workspaceStore.addThinkingEntry(text)
  }

  /**
   * 处理数据消息
   */
  function handleDataMessage(message: StreamMessage): void {
    const data = message.data
    if (!data) return

    // 如果是 panel_preview 类型
    if (data.type === 'panel_preview') {
      handlePanelPreview(data)
      return
    }

    // 如果是 summary 阶段的最终数据
    if (message.stage === 'summary') {
      handleSummaryData(data)
    }
  }

  /**
   * 处理面板预览
   */
  function handlePanelPreview(data: Record<string, unknown>): void {
    const panelPayload = data.panel_payload as Record<string, unknown> | undefined
    const panelSpec = data.panel_spec as Record<string, unknown> | undefined
    const previews = data.previews as Array<{ title?: string }> | undefined

    const rawLayout = panelPayload?.layout || panelSpec?.layout
    const rawBlocks = panelPayload?.blocks || panelSpec?.blocks
    const rawDataBlocks = data.data_blocks || panelSpec?.data_envelopes
    const title = previews?.[0]?.title || '数据面板'

    // 添加面板条目到时间线
    const timelineEntryId = workspaceStore.addPanelEntry({
      title,
      layout: rawLayout as unknown,
      blocks: Array.isArray(rawBlocks) ? rawBlocks as unknown[] : [],
      dataBlocks: (rawDataBlocks && typeof rawDataBlocks === 'object' ? rawDataBlocks : {}) as Record<string, unknown>,
    })

    // 添加到面板列表
    const panelId = workspaceStore.addPanelPreview({
      panel_payload: panelPayload,
      panel_spec: panelSpec,
      previews,
      data_blocks: rawDataBlocks as Record<string, unknown> | undefined,
    }, timelineEntryId)

    workspaceStore.selectPanel(panelId)
  }

  // DataStash 条目类型
  interface DataStashItem {
    step_id: number
    tool_name: string
    data_id?: string | null
    summary: string
    status: string
    error_message?: string | null
  }

  /**
   * 处理 summary 阶段的最终数据
   */
  function handleSummaryData(data: Record<string, unknown>): void {
    const finalReport = data.final_report as string | undefined
    const dataStash = data.data_stash as DataStashItem[] | undefined
    const executionSteps = data.execution_steps as Array<Record<string, unknown>> | undefined
    const panelPreviews = data.panel_previews as Array<Record<string, unknown>> | undefined
    const sessionSummary = data.session_summary as Record<string, number> | undefined

    // 更新 Session 统计
    if (sessionSummary && sessionStore.currentSession) {
      sessionStore.currentSession.data_stash_count = sessionSummary.data_stash_count || 0
      sessionStore.currentSession.chat_history_count = sessionSummary.chat_history_count || 0
      sessionStore.currentSession.recorded_steps_count = sessionSummary.recorded_steps_count || 0
    }

    // 添加工具调用条目
    if (dataStash) {
      workspaceStore.addArtifactsFromDataStash(dataStash)

      for (const ref of dataStash) {
        if (ref.tool_name && ref.tool_name !== 'emit_panel_preview') {
          workspaceStore.addToolCallEntry({
            tool_name: ref.tool_name,
            tool_id: ref.data_id || `tool-${Date.now()}`,
            status: ref.status === 'success' ? 'success' : 'error',
          })

          const lastEntry = workspaceStore.getLastToolCallEntry()
          if (lastEntry) {
            workspaceStore.updateToolCallStatus(
              lastEntry.id,
              ref.status === 'success' ? 'success' : 'error',
              {
                result_summary: ref.summary,
                data_id: ref.data_id || undefined,
                error: ref.error_message || undefined,
              }
            )
          }
        }
      }
    }

    // 处理额外的面板预览（如果之前没有通过 panel_preview 推送）
    if (panelPreviews && panelPreviews.length > 0) {
      for (const preview of panelPreviews) {
        // 检查是否已添加
        const existingPanels = workspaceStore.panelPreviews
        const alreadyAdded = existingPanels.some(
          p => p.id === (preview as { id?: string }).id
        )
        if (!alreadyAdded) {
          handlePanelPreview(preview)
        }
      }
    }

    // 如果有最终报告，添加消息条目
    if (finalReport) {
      workspaceStore.addMessageEntry(finalReport, 'success')
    }
  }

  /**
   * 处理步骤消息 - 区分思考和工具调用
   */
  function handleStepMessage(message: StreamMessage): void {
    const stepId = message.step_id || `step-${Date.now()}`
    const action = message.action || '执行步骤'
    const status = message.status || 'success'
    const stepType = message.step_type || 'tool_call'
    const reasoning = message.reasoning

    // 如果是 planning 类型（Agent 思考），添加为思考条目
    if (stepType === 'planning') {
      workspaceStore.addThinkingEntry(action, reasoning)
    } else {
      // 否则添加工具调用条目
      workspaceStore.addToolCallEntry({
        tool_name: action,
        tool_id: stepId,
        status: status === 'success' ? 'success' : status === 'error' ? 'error' : 'running',
      })
    }
  }

  /**
   * 处理完成消息
   */
  function handleCompleteMessage(message: StreamMessage): void {
    const success = message.success ?? false
    const text = message.message || (success ? '执行完成' : '执行失败')

    console.log('[SessionWS] 执行完成:', success, text)

    // 调用外部回调
    onComplete?.(success, text)

    // 刷新 Session 步骤
    sessionStore.loadRecordedSteps()
  }

  /**
   * 处理错误消息
   */
  function handleErrorMessage(message: StreamMessage): void {
    const errorMsg = message.error_message || '未知错误'
    console.error('[SessionWS] 执行错误:', errorMsg)

    error.value = errorMsg

    // 添加错误条目到时间线
    workspaceStore.addErrorEntry(errorMsg)

    // 调用外部回调
    onError?.(errorMsg)
  }

  /**
   * 断开连接
   */
  function disconnect(): void {
    if (ws) {
      ws.close()
      ws = null
    }
    isConnected.value = false
    isConnecting.value = false
  }

  return {
    // 状态
    isConnecting,
    isConnected,
    error,

    // 方法
    connect,
    sendQuery,
    disconnect,
  }
}
