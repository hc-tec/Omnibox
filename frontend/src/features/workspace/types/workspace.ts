/**
 * 工作台类型定义
 *
 * 扩展 workflow.ts 中的基础类型，添加 UI 专用类型
 */

import type {
  Workflow,
  WorkflowStep,
  WorkflowRun,
  RunStatus,
  ProgressEvent,
} from '@/types/workflow'

// 重新导出基础类型
export type {
  Workflow,
  WorkflowStep,
  WorkflowRun,
  RunStatus,
  StepType,
  WorkflowStatus,
  Variable,
  VariableType,
  ProgressEvent,
} from '@/types/workflow'

/**
 * 数据产物（前端视图模型）
 */
export interface Artifact {
  artifact_id: string
  name: string
  artifact_type: 'dataset' | 'analysis' | 'insight' | 'document'
  description: string

  // 来源追溯
  source: {
    workflow_id?: string
    workflow_run_id?: string
    step_id?: number
    tool_name: string
    created_at: string
  }

  // Schema 信息
  schema_info: {
    fields: Array<{
      name: string
      type: string
      sample_values?: unknown[]
    }>
    total_count: number
  }

  // 统计信息
  statistics?: {
    numeric_stats?: Record<string, { min: number; max: number; avg: number }>
    category_counts?: Record<string, Record<string, number>>
  }

  // 可视化建议
  suggested_views: Array<{
    component: string
    confidence: number
    props: Record<string, unknown>
  }>

  // 时间戳
  created_at: string
  updated_at: string
}

/**
 * 步骤状态映射
 */
export type StepStatusMap = Record<number, RunStatus>

/**
 * 画布视图类型
 */
export type CanvasView = 'chart' | 'table' | 'text' | 'raw'

/**
 * 工作台状态
 */
export interface WorkspaceState {
  // 工作流管理
  workflows: Workflow[]
  currentWorkflowId: string | null
  currentRunId: string | null

  // 执行状态
  currentRun: WorkflowRun | null
  stepStatuses: StepStatusMap

  // 数据产物
  artifacts: Artifact[]
  selectedArtifactId: string | null

  // 画布状态
  canvasView: CanvasView
  currentStepOutput: StepOutput | null

  // UI 状态
  leftPanelCollapsed: boolean
  rightPanelCollapsed: boolean
  leftPanelWidth: number
  rightPanelWidth: number

  // 加载状态
  loading: boolean
  error: string | null

  // WebSocket
  wsConnected: boolean
  progressEvents: ProgressEvent[]
}

/**
 * 步骤输出（用于画布渲染）
 */
export interface StepOutput {
  stepId: number
  stepName: string
  artifactId?: string
  data: unknown
  layout?: unknown
  blocks?: unknown[]
  dataBlocks?: Record<string, unknown>
}

/**
 * 工作流列表项（简化视图）
 */
export interface WorkflowListItem {
  workflow_id: string
  name: string
  description: string
  status: string
  is_template: boolean
  updated_at: string
  step_count: number
}

/**
 * 工作流执行请求
 */
export interface StartRunRequest {
  workflow_id: string
  variable_values: Record<string, unknown>
}

/**
 * API 响应类型
 */
export interface WorkflowListResponse {
  workflows: WorkflowListItem[]
  total: number
}

export interface WorkflowDetailResponse {
  workflow_id: string
  name: string
  description: string
  status: string
  steps: WorkflowStep[]
  variables: Record<string, unknown>
  is_template: boolean
  template_source_id?: string
  tags: string[]
  created_at: string
  updated_at: string
}

export interface ArtifactListResponse {
  artifacts: Artifact[]
  total: number
}
