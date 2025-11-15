/**
 * 查询卡片类型定义
 * 用于统一工作区的卡片管理
 */

import type { UIBlock, PanelResponse, StreamMessage, PanelStreamFetchPayload } from '@/shared/types/panel';

/**
 * 查询模式
 */
export type QueryMode = 'simple' | 'research';

/**
 * 卡片状态
 */
export type CardStatus = 'pending' | 'processing' | 'completed' | 'error';

/**
 * 触发来源
 */
export type TriggerSource = 'manual_input' | 'shortcut' | 'api';

/**
 * 刷新元数据
 * 用于快速刷新功能，跳过 RAG/LLM 推理
 */
export interface RefreshMetadata {
  route_id: string;
  generated_path: string;
  retrieved_tools?: Array<{
    route_id: string;
    name: string;
    score: number;
  }>;
  query_plan?: any;
}

/**
 * 查询卡片
 */
export interface QueryCard {
  /** 卡片 ID（UUID） */
  id: string;

  /** 查询文本 */
  query: string;

  /** 查询模式 */
  mode: QueryMode;

  /** 卡片状态 */
  status: CardStatus;

  /** 触发来源 */
  trigger_source: TriggerSource;

  /** 创建时间 */
  created_at: string;

  /** 更新时间 */
  updated_at: string;

  /** 完成时间 */
  completed_at?: string;

  /** 面板数据（completed 状态） */
  panels?: UIBlock[];

  /** 错误信息（error 状态） */
  error_message?: string;

  /** 刷新元数据 */
  refresh_metadata?: RefreshMetadata;

  /** 当前步骤描述（processing 状态） */
  current_step?: string;

  /** 进度（0-100） */
  progress?: number;

  /** Inspector 调试信息：响应元数据 */
  metadata?: PanelResponse['metadata'];

  /** Inspector 调试信息：响应消息 */
  message?: string;

  /** Inspector 调试信息：流式日志（RSS Hub 接口调用记录） */
  streamLog?: StreamMessage[];

  /** Inspector 调试信息：最后一次 fetch 快照 */
  fetchSnapshot?: PanelStreamFetchPayload | null;
}
