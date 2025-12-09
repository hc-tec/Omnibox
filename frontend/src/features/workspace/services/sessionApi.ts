/**
 * Session API 服务
 *
 * 与后端 /api/v1/sessions 端点交互
 */

import axios from 'axios'
import { resolveHttpBase } from '@/shared/networkBase'

// 与 panelApi 保持一致：API_BASE 是 /api/v1，然后在各接口追加具体路径
const API_BASE = resolveHttpBase(import.meta.env.VITE_API_BASE, '/api/v1')
const SESSIONS_PATH = `${API_BASE}/sessions`

// ========== 类型定义 ==========

export interface SessionInfo {
  session_id: string
  name: string
  status: string
  workspace_id: string | null
  source_workflow_id: string | null
  data_stash_count: number
  chat_history_count: number
  recorded_steps_count: number
  created_at: string
  last_active_at: string
}

export interface CreateSessionRequest {
  workspace_id?: string
  source_workflow_id?: string
  name?: string
}

export interface CreateSessionResponse {
  success: boolean
  session: SessionInfo
}

export interface GetSessionResponse {
  success: boolean
  session: SessionInfo | null
  error?: string
}

export interface SessionChatRequest {
  query: string
  context?: Record<string, unknown>
}

export interface SessionChatResponse {
  success: boolean
  message: string
  final_report: string | null
  data: unknown | null
  data_blocks: Record<string, unknown>
  session_summary: {
    data_stash_count: number
    chat_history_count: number
    recorded_steps_count: number
  } | null
  execution_steps: Array<Record<string, unknown>> | null
  error?: string
}

export interface RecordedStepInfo {
  step_id: number
  tool_id: string
  tool_name: string
  params: Record<string, unknown>
  artifact_id: string | null
  data_id: string | null
  summary: string
  status: string
  error_message: string | null
  depends_on: number[]
  trigger_query: string
  executed_at: string
}

export interface GetRecordedStepsResponse {
  success: boolean
  session_id: string
  steps: RecordedStepInfo[]
  error?: string
}

export interface SaveAsTemplateRequest {
  name: string
  description?: string
  category?: string
  extract_variables?: boolean
}

export interface SaveAsTemplateResponse {
  success: boolean
  workflow_id: string | null
  workflow_name: string | null
  steps_count: number | null
  variables_count: number | null
  error?: string
}

export interface CloseSessionResponse {
  success: boolean
  session_id: string
  error?: string
}

export interface ListSessionsResponse {
  success: boolean
  sessions: SessionInfo[]
  total: number
  error?: string
}

// ========== API 函数 ==========

/**
 * 创建新 Session
 */
export async function createSession(
  request: CreateSessionRequest = {}
): Promise<CreateSessionResponse> {
  const response = await axios.post<CreateSessionResponse>(SESSIONS_PATH, request)
  return response.data
}

/**
 * 获取 Session 信息
 */
export async function getSession(sessionId: string): Promise<GetSessionResponse> {
  const response = await axios.get<GetSessionResponse>(`${SESSIONS_PATH}/${sessionId}`)
  return response.data
}

/**
 * 在 Session 内执行查询
 */
export async function sessionChat(
  sessionId: string,
  request: SessionChatRequest
): Promise<SessionChatResponse> {
  const response = await axios.post<SessionChatResponse>(
    `${SESSIONS_PATH}/${sessionId}/chat`,
    request
  )
  return response.data
}

/**
 * 获取执行步骤记录
 */
export async function getRecordedSteps(
  sessionId: string
): Promise<GetRecordedStepsResponse> {
  const response = await axios.get<GetRecordedStepsResponse>(
    `${SESSIONS_PATH}/${sessionId}/steps`
  )
  return response.data
}

/**
 * 保存为工作流模板
 */
export async function saveAsTemplate(
  sessionId: string,
  request: SaveAsTemplateRequest
): Promise<SaveAsTemplateResponse> {
  const response = await axios.post<SaveAsTemplateResponse>(
    `${SESSIONS_PATH}/${sessionId}/save-as-template`,
    request
  )
  return response.data
}

/**
 * 关闭 Session
 */
export async function closeSession(sessionId: string): Promise<CloseSessionResponse> {
  const response = await axios.delete<CloseSessionResponse>(`${SESSIONS_PATH}/${sessionId}`)
  return response.data
}

/**
 * 列出所有 Sessions
 */
export async function listSessions(params?: {
  workspace_id?: string
  status?: string
  limit?: number
}): Promise<ListSessionsResponse> {
  const response = await axios.get<ListSessionsResponse>(SESSIONS_PATH, { params })
  return response.data
}
