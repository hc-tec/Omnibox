/**
 * 工作流类型定义
 *
 * 与后端 services/workflow/models.py 保持一致
 */

/**
 * 工作流状态
 */
export type WorkflowStatus = 'draft' | 'ready' | 'template';

/**
 * 步骤类型
 */
export type StepType = 'fetch' | 'process' | 'analyze' | 'output';

/**
 * 变量类型
 */
export type VariableType = 'string' | 'number' | 'boolean' | 'datasource' | 'list';

/**
 * 执行状态
 */
export type RunStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';

/**
 * 变量定义
 */
export interface Variable {
  name: string;
  var_type: VariableType;
  description: string;
  default?: unknown;
  required: boolean;
  enum_values?: unknown[];
}

/**
 * 工作流步骤
 */
export interface WorkflowStep {
  step_id: number;
  name: string;
  description: string;
  step_type: StepType;
  tool_id: string;
  params: Record<string, unknown>;
  depends_on: number[];
  output_name: string;
}

/**
 * 工作流定义
 */
export interface Workflow {
  workflow_id: string;
  name: string;
  description: string;
  status: WorkflowStatus;
  steps: WorkflowStep[];
  variables: Record<string, Variable>;
  is_template: boolean;
  template_source_id?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

/**
 * 工作流执行实例
 */
export interface WorkflowRun {
  run_id: string;
  workflow_id: string;
  status: RunStatus;
  current_step_id?: number;
  completed_step_ids: number[];
  variable_values: Record<string, unknown>;
  artifact_ids: Record<number, string>;  // step_id → artifact_id
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

/**
 * 进度事件类型
 */
export type ProgressEventType =
  | 'started'
  | 'step_started'
  | 'step_completed'
  | 'completed'
  | 'failed'
  | 'paused'
  | 'resumed'
  | 'cancelled';

/**
 * 进度事件
 */
export interface ProgressEvent {
  run_id: string;
  event_type: ProgressEventType;
  step_id?: number;
  step_name?: string;
  artifact_id?: string;
  message: string;
  progress_percent: number;
  timestamp: string;
}

/**
 * 创建工作流请求
 */
export interface CreateWorkflowRequest {
  name: string;
  description?: string;
  steps?: WorkflowStep[];
  variables?: Record<string, Variable>;
  is_template?: boolean;
}

/**
 * 执行工作流请求
 */
export interface StartWorkflowRunRequest {
  workflow_id: string;
  variable_values?: Record<string, unknown>;
}

/**
 * 工作流列表查询参数
 */
export interface ListWorkflowsParams {
  status?: WorkflowStatus;
  is_template?: boolean;
  tags?: string[];
  limit?: number;
  offset?: number;
}

/**
 * 执行实例列表查询参数
 */
export interface ListWorkflowRunsParams {
  workflow_id?: string;
  status?: RunStatus;
  limit?: number;
  offset?: number;
}

/**
 * 工作流存储统计
 */
export interface WorkflowStoreStats {
  total_workflows: number;
  total_runs: number;
  template_count: number;
  running_count: number;
}
