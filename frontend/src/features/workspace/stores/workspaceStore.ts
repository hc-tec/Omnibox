/**
 * 工作台状态管理
 *
 * 管理工作流、执行状态、数据产物
 */

import { defineStore } from 'pinia'
import { ref, computed, onUnmounted } from 'vue'
import type {
  Workflow,
  WorkflowRun,
  WorkflowStep,
  Artifact,
  StepStatusMap,
  CanvasView,
  StepOutput,
  ProgressEvent,
  RunStatus,
} from '../types/workspace'
import * as api from '../services/workspaceApi'

export const useWorkspaceStore = defineStore('workflow-workspace', () => {
  // ========== 工作流管理 ==========
  const workflows = ref<Workflow[]>([])
  const currentWorkflowId = ref<string | null>(null)
  const currentRunId = ref<string | null>(null)

  // ========== 执行状态 ==========
  const currentRun = ref<WorkflowRun | null>(null)
  const stepStatuses = ref<StepStatusMap>({})

  // ========== 数据产物 ==========
  const artifacts = ref<Artifact[]>([])
  const selectedArtifactId = ref<string | null>(null)

  // ========== 画布状态 ==========
  const canvasView = ref<CanvasView>('chart')
  const currentStepOutput = ref<StepOutput | null>(null)

  // ========== UI 状态 ==========
  const leftPanelCollapsed = ref(false)
  const rightPanelCollapsed = ref(false)
  const leftPanelWidth = ref(240)
  const rightPanelWidth = ref(280)
  const showCreateWorkflowDialog = ref(false)

  // ========== 加载状态 ==========
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ========== WebSocket ==========
  const wsConnected = ref(false)
  const progressEvents = ref<ProgressEvent[]>([])

  // ========== 计算属性 ==========

  const currentWorkflow = computed(() => {
    if (!currentWorkflowId.value) return null
    return workflows.value.find(w => w.workflow_id === currentWorkflowId.value) || null
  })

  const currentWorkflowSteps = computed((): WorkflowStep[] => {
    return currentWorkflow.value?.steps || []
  })

  const selectedArtifact = computed(() => {
    if (!selectedArtifactId.value) return null
    return artifacts.value.find(a => a.artifact_id === selectedArtifactId.value) || null
  })

  const isRunning = computed(() => currentRun.value?.status === 'running')
  const isPaused = computed(() => currentRun.value?.status === 'paused')
  const isCompleted = computed(() => currentRun.value?.status === 'completed')
  const isFailed = computed(() => currentRun.value?.status === 'failed')

  const completedStepsCount = computed(() => {
    return Object.values(stepStatuses.value).filter(s => s === 'completed').length
  })

  const progressPercentage = computed(() => {
    const totalSteps = currentWorkflowSteps.value.length
    if (totalSteps === 0) return 0
    return Math.round((completedStepsCount.value / totalSteps) * 100)
  })

  // ========== Actions ==========

  /**
   * 加载工作流列表
   */
  async function loadWorkflows() {
    loading.value = true
    error.value = null
    try {
      const response = await api.listWorkflows()
      workflows.value = response.items
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载工作流失败'
    } finally {
      loading.value = false
    }
  }

  /**
   * 选择工作流
   */
  function selectWorkflow(workflowId: string) {
    currentWorkflowId.value = workflowId
    currentRunId.value = null
    currentRun.value = null
    stepStatuses.value = {}
    currentStepOutput.value = null

    // 加载关联的产物
    loadArtifacts(workflowId)
  }

  /**
   * 加载数据产物
   */
  async function loadArtifacts(workflowId?: string) {
    if (!workflowId) return
    try {
      const response = await api.listArtifacts(workflowId)
      artifacts.value = response.items
    } catch (e) {
      console.error('加载产物失败:', e)
    }
  }

  /**
   * 选择产物
   */
  async function selectArtifact(artifactId: string) {
    selectedArtifactId.value = artifactId

    // 加载产物数据到画布
    const artifact = artifacts.value.find(a => a.artifact_id === artifactId)
    if (artifact && currentWorkflowId.value) {
      currentStepOutput.value = {
        stepId: artifact.source.step_id || 0,
        stepName: artifact.name,
        artifactId: artifact.artifact_id,
        data: null,
      }

      // 加载产物完整数据
      try {
        const artifactData = await api.getArtifactData(
          currentWorkflowId.value,
          artifactId
        )
        if (currentStepOutput.value?.artifactId === artifactId) {
          currentStepOutput.value.data = artifactData.data
        }
      } catch (e) {
        console.error('加载产物数据失败:', e)
      }
    }
  }

  /**
   * 加载执行状态
   */
  async function loadRun(workflowId: string, runId: string) {
    loading.value = true
    error.value = null

    try {
      const run = await api.getRun(workflowId, runId)
      currentRun.value = run
      currentRunId.value = run.run_id

      // 初始化步骤状态
      stepStatuses.value = {}
      currentWorkflowSteps.value.forEach(step => {
        // 根据 run 的 completed_step_ids 设置状态
        if (run.completed_step_ids?.includes(step.step_id)) {
          stepStatuses.value[step.step_id] = 'completed'
        } else if (run.current_step_id === step.step_id) {
          stepStatuses.value[step.step_id] = run.status === 'running' ? 'running' : 'pending'
        } else {
          stepStatuses.value[step.step_id] = 'pending'
        }
      })

      // 如果执行正在进行中，连接 WebSocket
      if (run.status === 'running') {
        connectProgressWebSocket(workflowId, runId)
      }

      // 加载关联的产物
      await loadArtifacts(workflowId)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载执行状态失败'
    } finally {
      loading.value = false
    }
  }

  // WebSocket 连接管理
  let wsConnection: { close: () => void; send: (data: unknown) => void } | null = null

  /**
   * 启动工作流执行
   */
  async function startRun(variableValues: Record<string, unknown> = {}) {
    if (!currentWorkflowId.value) return

    loading.value = true
    error.value = null

    try {
      const run = await api.startRun(currentWorkflowId.value, { variable_values: variableValues })
      currentRun.value = run
      currentRunId.value = run.run_id

      // 初始化步骤状态
      stepStatuses.value = {}
      currentWorkflowSteps.value.forEach(step => {
        stepStatuses.value[step.step_id] = 'pending'
      })

      // 连接 WebSocket 接收进度
      connectProgressWebSocket(currentWorkflowId.value, run.run_id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '启动执行失败'
    } finally {
      loading.value = false
    }
  }

  /**
   * 连接进度 WebSocket
   */
  function connectProgressWebSocket(workflowId: string, runId: string) {
    // 关闭现有连接
    if (wsConnection) {
      wsConnection.close()
    }

    wsConnection = api.connectProgressStream(workflowId, runId, {
      onProgress: (event) => {
        handleProgressEvent(event)
      },
      onComplete: (event) => {
        handleProgressEvent(event)
        setWsConnected(false)
      },
      onError: (err) => {
        console.error('WebSocket 错误:', err)
        error.value = err.message
        setWsConnected(false)
      },
      onClose: () => {
        setWsConnected(false)
      },
    })
    setWsConnected(true)
  }

  /**
   * 暂停执行
   */
  async function pauseRun() {
    if (!currentWorkflowId.value || !currentRunId.value) return

    try {
      const run = await api.pauseRun(currentWorkflowId.value, currentRunId.value)
      currentRun.value = run
    } catch (e) {
      error.value = e instanceof Error ? e.message : '暂停失败'
    }
  }

  /**
   * 恢复执行
   */
  async function resumeRun() {
    if (!currentWorkflowId.value || !currentRunId.value) return

    try {
      const run = await api.resumeRun(currentWorkflowId.value, currentRunId.value)
      currentRun.value = run

      // 重新连接 WebSocket
      connectProgressWebSocket(currentWorkflowId.value, currentRunId.value)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '恢复失败'
    }
  }

  /**
   * 取消执行
   */
  async function cancelRun() {
    if (!currentWorkflowId.value || !currentRunId.value) return

    try {
      const run = await api.cancelRun(currentWorkflowId.value, currentRunId.value)
      currentRun.value = run

      // 关闭 WebSocket
      if (wsConnection) {
        wsConnection.close()
        wsConnection = null
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : '取消失败'
    }
  }

  /**
   * 处理进度事件
   */
  function handleProgressEvent(event: ProgressEvent) {
    progressEvents.value.push(event)

    switch (event.event_type) {
      case 'started':
        if (currentRun.value) {
          currentRun.value.status = 'running'
        }
        break

      case 'step_started':
        if (event.step_id !== undefined) {
          stepStatuses.value[event.step_id] = 'running'
          if (currentRun.value) {
            currentRun.value.current_step_id = event.step_id
          }
        }
        break

      case 'step_completed':
        if (event.step_id !== undefined) {
          stepStatuses.value[event.step_id] = 'completed'
          if (event.artifact_id) {
            loadArtifactById(event.artifact_id)
          }
        }
        break

      case 'completed':
        if (currentRun.value) {
          currentRun.value.status = 'completed'
        }
        break

      case 'failed':
        if (currentRun.value) {
          currentRun.value.status = 'failed'
          currentRun.value.error_message = event.message
        }
        if (event.step_id !== undefined) {
          stepStatuses.value[event.step_id] = 'failed'
        }
        break

      case 'paused':
        if (currentRun.value) {
          currentRun.value.status = 'paused'
        }
        break
    }
  }

  /**
   * 加载单个产物
   */
  async function loadArtifactById(artifactId: string) {
    if (!currentWorkflowId.value) return
    try {
      const artifact = await api.getArtifact(currentWorkflowId.value, artifactId)
      // 添加到列表（如果不存在）
      const existing = artifacts.value.findIndex(a => a.artifact_id === artifactId)
      if (existing >= 0) {
        artifacts.value[existing] = artifact
      } else {
        artifacts.value.push(artifact)
      }
    } catch (e) {
      console.error('加载产物失败:', e)
    }
  }

  /**
   * 从 Session data_stash 添加产物
   *
   * 将后端返回的 DataReference 转换为前端 Artifact 格式
   */
  function addArtifactFromDataRef(dataRef: {
    step_id: number
    tool_name: string
    data_id?: string | null
    summary: string
    status: string
    error_message?: string | null
  }) {
    // 仅处理成功状态且有 data_id 的数据
    if (dataRef.status !== 'success' || !dataRef.data_id) {
      return
    }

    // 生成 artifact_id（使用 data_id）
    const artifactId = dataRef.data_id

    // 检查是否已存在
    const existing = artifacts.value.findIndex(a => a.artifact_id === artifactId)
    if (existing >= 0) {
      return // 已存在则不重复添加
    }

    // 根据工具名推断 artifact_type
    const toolToType: Record<string, Artifact['artifact_type']> = {
      fetch_rss: 'dataset',
      fetch_feed: 'dataset',
      fetch_api: 'dataset',
      data_query: 'dataset',
      data_operator: 'dataset',
      data_filter: 'dataset',
      data_sort: 'dataset',
      data_aggregate: 'dataset',
      analyze: 'analysis',
      compare: 'analysis',
      summarize: 'insight',
      generate_insight: 'insight',
      generate_report: 'document',
      emit_panel_preview: 'document',
    }
    const artifactType = toolToType[dataRef.tool_name] || 'dataset'

    // 创建 Artifact
    const artifact: Artifact = {
      artifact_id: artifactId,
      name: `${dataRef.tool_name} #${dataRef.step_id}`,
      artifact_type: artifactType,
      description: dataRef.summary,
      source: {
        step_id: dataRef.step_id,
        tool_name: dataRef.tool_name,
        created_at: new Date().toISOString(),
      },
      schema_info: {
        fields: [],
        total_count: 0,
      },
      suggested_views: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }

    artifacts.value.push(artifact)
  }

  /**
   * 批量从 data_stash 添加产物
   */
  function addArtifactsFromDataStash(
    dataStash: Array<{
      step_id: number
      tool_name: string
      data_id?: string | null
      summary: string
      status: string
      error_message?: string | null
    }>
  ) {
    for (const ref of dataStash) {
      addArtifactFromDataRef(ref)
    }
  }

  /**
   * 清空产物列表
   */
  function clearArtifacts() {
    artifacts.value = []
    selectedArtifactId.value = null
  }

  /**
   * 切换画布视图
   */
  function setCanvasView(view: CanvasView) {
    canvasView.value = view
  }

  /**
   * 折叠/展开左侧面板
   */
  function toggleLeftPanel() {
    leftPanelCollapsed.value = !leftPanelCollapsed.value
  }

  /**
   * 折叠/展开右侧面板
   */
  function toggleRightPanel() {
    rightPanelCollapsed.value = !rightPanelCollapsed.value
  }

  /**
   * 打开创建工作流对话框
   */
  function openCreateWorkflowDialog() {
    showCreateWorkflowDialog.value = true
  }

  /**
   * 关闭创建工作流对话框
   */
  function closeCreateWorkflowDialog() {
    showCreateWorkflowDialog.value = false
  }

  /**
   * 选择步骤并在画布中显示
   */
  function selectStep(step: WorkflowStep) {
    currentStepOutput.value = {
      stepId: step.step_id,
      stepName: step.name,
      artifactId: undefined,
      data: null,
    }
  }

  /**
   * 设置 WebSocket 连接状态
   */
  function setWsConnected(connected: boolean) {
    wsConnected.value = connected
  }

  /**
   * 重置状态
   */
  function reset() {
    // 关闭 WebSocket 连接
    if (wsConnection) {
      wsConnection.close()
      wsConnection = null
    }

    workflows.value = []
    currentWorkflowId.value = null
    currentRunId.value = null
    currentRun.value = null
    stepStatuses.value = {}
    artifacts.value = []
    selectedArtifactId.value = null
    currentStepOutput.value = null
    progressEvents.value = []
    error.value = null
    wsConnected.value = false
  }

  /**
   * 清理资源（组件卸载时调用）
   */
  function cleanup() {
    if (wsConnection) {
      wsConnection.close()
      wsConnection = null
    }
  }

  return {
    // State
    workflows,
    currentWorkflowId,
    currentRunId,
    currentRun,
    stepStatuses,
    artifacts,
    selectedArtifactId,
    canvasView,
    currentStepOutput,
    leftPanelCollapsed,
    rightPanelCollapsed,
    leftPanelWidth,
    rightPanelWidth,
    showCreateWorkflowDialog,
    loading,
    error,
    wsConnected,
    progressEvents,

    // Computed
    currentWorkflow,
    currentWorkflowSteps,
    selectedArtifact,
    isRunning,
    isPaused,
    isCompleted,
    isFailed,
    completedStepsCount,
    progressPercentage,

    // Actions
    loadWorkflows,
    selectWorkflow,
    loadArtifacts,
    selectArtifact,
    selectStep,
    loadRun,
    startRun,
    pauseRun,
    resumeRun,
    cancelRun,
    handleProgressEvent,
    loadArtifactById,
    addArtifactFromDataRef,
    addArtifactsFromDataStash,
    clearArtifacts,
    setCanvasView,
    toggleLeftPanel,
    toggleRightPanel,
    openCreateWorkflowDialog,
    closeCreateWorkflowDialog,
    setWsConnected,
    reset,
    cleanup,
  }
})
