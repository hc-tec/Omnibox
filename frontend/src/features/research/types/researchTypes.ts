/**
 * 研究功能类型定义
 */

import type { QueryMode } from '@/shared/types/panel';

/** 查询模式（从 panel types 导入） */
export type { QueryMode };

/** 研究任务状态 */
export type ResearchTaskStatus =
  | 'idle'          // 空闲
  | 'processing'    // 处理中
  | 'human_in_loop' // 等待人工输入
  | 'completed'     // 完成
  | 'error';        // 错误

/** LangGraph 节点名称 */
export type LangGraphNode =
  | 'router'
  | 'simple_chat'
  | 'planner'
  | 'tool_executor'
  | 'data_stasher'
  | 'reflector'
  | 'synthesizer'
  | 'wait_for_human';

/** 执行步骤 */
export interface ExecutionStep {
  step_id: number;
  node: LangGraphNode;
  action: string;
  status: 'success' | 'error' | 'in_progress';
  timestamp: string;
}

/** 研究任务 */
export interface ResearchTask {
  task_id: string;
  query: string;
  mode: QueryMode;
  status: ResearchTaskStatus;
  execution_steps: ExecutionStep[];
  final_report?: string;
  human_request?: {
    message: string;
    timestamp: string;
  };
  error?: string;
  metadata?: ResearchResponse["metadata"];
  created_at: string;
  updated_at: string;
}

/** API 响应 */
export interface ResearchResponse {
  success: boolean;
  message: string;
  metadata?: {
    mode: string;
    total_steps?: number;
    execution_steps?: ExecutionStep[];
    data_stash_count?: number;
    thread_id?: string;
    intent_confidence?: number;
  };
}

/** WebSocket 消息 */
export interface ResearchWebSocketMessage {
  type: 'step' | 'human_in_loop' | 'complete' | 'error';
  task_id: string;
  data?: any;
}
