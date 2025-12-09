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

export const useWorkspaceStore = defineStore('workspace', () => {
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
  function selectArtifact(artifactId: string) {
    selectedArtifactId.value = artifactId

    // 加载产物数据到画布
    const artifact = artifacts.value.find(a => a.artifact_id === artifactId)
    if (artifact) {
      currentStepOutput.value = {
        stepId: artifact.source.step_id || 0,
        stepName: artifact.name,
        artifactId: artifact.artifact_id,
        data: null, // TODO: 加载完整数据
      }
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
    startRun,
    pauseRun,
    resumeRun,
    cancelRun,
    handleProgressEvent,
    loadArtifactById,
    setCanvasView,
    toggleLeftPanel,
    toggleRightPanel,
    setWsConnected,
    reset,
    cleanup,
  }
})
