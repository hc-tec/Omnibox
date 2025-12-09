/**
 * 工作台 API 服务
 *
 * 封装工作流管理和执行的 HTTP 请求及 WebSocket 连接
 */

import axios from 'axios'
import { resolveHttpBase, resolveWsBase } from '@/shared/networkBase'
import type {
  Workflow,
  WorkflowRun,
  CreateWorkflowRequest,
  ListWorkflowsParams,
  ProgressEvent,
} from '@/types/workflow'
import type { Artifact } from '../types/workspace'

// API 基础路径
const API_BASE = resolveHttpBase(import.meta.env.VITE_API_BASE, '/api/v1')
const WORKFLOWS_URL = `${API_BASE}/workflows`

// ========== 类型定义 ==========

export interface WorkflowListResponse {
  total: number
  items: Workflow[]
}

export interface RunListResponse {
  total: number
  items: WorkflowRun[]
}

export interface ArtifactListResponse {
  total: number
  items: Artifact[]
}

export interface ArtifactDataResponse {
  artifact_id: string
  data: unknown
  total_rows: number
}

export interface WorkflowUpdateRequest {
  name?: string
  description?: string
  status?: string
  steps?: Workflow['steps']
  variables?: Workflow['variables']
  tags?: string[]
}

export interface StartRunRequest {
  variable_values?: Record<string, unknown>
}

// ========== 工作流 CRUD ==========

/**
 * 列出工作流
 */
export async function listWorkflows(
  params?: ListWorkflowsParams
): Promise<WorkflowListResponse> {
  const response = await axios.get<WorkflowListResponse>(WORKFLOWS_URL, {
    params,
  })
  return response.data
}

/**
 * 获取工作流详情
 */
export async function getWorkflow(workflowId: string): Promise<Workflow> {
  const response = await axios.get<Workflow>(`${WORKFLOWS_URL}/${workflowId}`)
  return response.data
}

/**
 * 创建工作流
 */
export async function createWorkflow(
  data: CreateWorkflowRequest
): Promise<Workflow> {
  const response = await axios.post<Workflow>(WORKFLOWS_URL, data)
  return response.data
}

/**
 * 更新工作流
 */
export async function updateWorkflow(
  workflowId: string,
  data: WorkflowUpdateRequest
): Promise<Workflow> {
  const response = await axios.patch<Workflow>(
    `${WORKFLOWS_URL}/${workflowId}`,
    data
  )
  return response.data
}

/**
 * 删除工作流
 */
export async function deleteWorkflow(workflowId: string): Promise<void> {
  await axios.delete(`${WORKFLOWS_URL}/${workflowId}`)
}

// ========== 执行管理 ==========

/**
 * 启动工作流执行
 */
export async function startRun(
  workflowId: string,
  request?: StartRunRequest
): Promise<WorkflowRun> {
  const response = await axios.post<WorkflowRun>(
    `${WORKFLOWS_URL}/${workflowId}/runs`,
    request || {}
  )
  return response.data
}

/**
 * 列出执行记录
 */
export async function listRuns(
  workflowId: string,
  params?: { status?: string; limit?: number; offset?: number }
): Promise<RunListResponse> {
  const response = await axios.get<RunListResponse>(
    `${WORKFLOWS_URL}/${workflowId}/runs`,
    { params }
  )
  return response.data
}

/**
 * 获取执行详情
 */
export async function getRun(
  workflowId: string,
  runId: string
): Promise<WorkflowRun> {
  const response = await axios.get<WorkflowRun>(
    `${WORKFLOWS_URL}/${workflowId}/runs/${runId}`
  )
  return response.data
}

/**
 * 暂停执行
 */
export async function pauseRun(
  workflowId: string,
  runId: string
): Promise<WorkflowRun> {
  const response = await axios.post<WorkflowRun>(
    `${WORKFLOWS_URL}/${workflowId}/runs/${runId}/pause`
  )
  return response.data
}

/**
 * 恢复执行
 */
export async function resumeRun(
  workflowId: string,
  runId: string
): Promise<WorkflowRun> {
  const response = await axios.post<WorkflowRun>(
    `${WORKFLOWS_URL}/${workflowId}/runs/${runId}/resume`
  )
  return response.data
}

/**
 * 取消执行
 */
export async function cancelRun(
  workflowId: string,
  runId: string
): Promise<WorkflowRun> {
  const response = await axios.post<WorkflowRun>(
    `${WORKFLOWS_URL}/${workflowId}/runs/${runId}/cancel`
  )
  return response.data
}

// ========== 产物查询 ==========

/**
 * 列出工作流产物
 */
export async function listArtifacts(
  workflowId: string,
  params?: { artifact_type?: string; limit?: number; offset?: number }
): Promise<ArtifactListResponse> {
  const response = await axios.get<ArtifactListResponse>(
    `${WORKFLOWS_URL}/${workflowId}/artifacts`,
    { params }
  )
  return response.data
}

/**
 * 获取产物详情
 */
export async function getArtifact(
  workflowId: string,
  artifactId: string
): Promise<Artifact> {
  const response = await axios.get<Artifact>(
    `${WORKFLOWS_URL}/${workflowId}/artifacts/${artifactId}`
  )
  return response.data
}

/**
 * 获取产物数据
 */
export async function getArtifactData(
  workflowId: string,
  artifactId: string
): Promise<ArtifactDataResponse> {
  const response = await axios.get<ArtifactDataResponse>(
    `${WORKFLOWS_URL}/${workflowId}/artifacts/${artifactId}/data`
  )
  return response.data
}

// ========== WebSocket 进度流 ==========

export interface ProgressStreamCallbacks {
  onProgress: (event: ProgressEvent) => void
  onComplete: (event: ProgressEvent) => void
  onError: (error: Error) => void
  onClose: () => void
}

/**
 * 连接执行进度 WebSocket
 *
 * @param workflowId 工作流 ID
 * @param runId 执行实例 ID
 * @param callbacks 回调函数
 * @returns 关闭连接的函数
 */
export function connectProgressStream(
  workflowId: string,
  runId: string,
  callbacks: ProgressStreamCallbacks
): { close: () => void; send: (data: unknown) => void } {
  const wsBase = resolveWsBase(
    undefined,
    `/api/v1/workflows/${workflowId}/runs/${runId}/stream`
  )

  const ws = new WebSocket(wsBase)
  let pingInterval: ReturnType<typeof setInterval> | null = null

  ws.onopen = () => {
    // 定期发送 ping 保持连接
    pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as ProgressEvent | { type: string }

      // 处理 pong 响应
      if ('type' in data && data.type === 'pong') {
        return
      }

      const progressEvent = data as ProgressEvent

      // 根据事件类型分发
      if (
        progressEvent.event_type.startsWith('run_completed') ||
        progressEvent.event_type.startsWith('run_failed') ||
        progressEvent.event_type.startsWith('run_cancelled')
      ) {
        callbacks.onComplete(progressEvent)
      } else {
        callbacks.onProgress(progressEvent)
      }
    } catch (e) {
      console.error('解析 WebSocket 消息失败:', e)
    }
  }

  ws.onerror = (event) => {
    callbacks.onError(new Error('WebSocket 连接错误'))
  }

  ws.onclose = () => {
    if (pingInterval) {
      clearInterval(pingInterval)
    }
    callbacks.onClose()
  }

  return {
    close: () => {
      if (pingInterval) {
        clearInterval(pingInterval)
      }
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    },
    send: (data: unknown) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data))
      }
    },
  }
}
