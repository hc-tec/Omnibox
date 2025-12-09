/**
 * 数据产物（DataArtifact）类型定义
 *
 * 与后端 services/artifact/models.py 保持一致
 */

/**
 * 产物类型
 */
export type ArtifactType = 'dataset' | 'analysis' | 'insight' | 'document';

/**
 * 可视化类型
 */
export type ViewType = 'table' | 'line_chart' | 'bar_chart' | 'pie_chart' | 'list' | 'card' | 'text';

/**
 * 可视化规格
 */
export interface ViewSpec {
  view_type: ViewType;
  title?: string;
  config: Record<string, unknown>;
}

/**
 * 数据产物来源
 */
export interface ArtifactSource {
  workflow_id?: string;
  step_id: number;
  tool_name: string;
  created_at: string;
}

/**
 * 数据产物引用
 */
export interface ArtifactRef {
  artifact_id: string;
  relation_type: 'derived_from' | 'compared_with' | 'generated';
}

/**
 * 数据产物
 *
 * 工作流工作台的核心数据单元
 */
export interface DataArtifact {
  // 产物标识
  artifact_id: string;
  data_id?: string;

  // 基本信息
  name: string;
  description: string;
  artifact_type: ArtifactType;

  // LangGraph 兼容字段
  step_id: number;
  tool_name: string;
  summary: string;
  status: 'success' | 'error' | 'needs_user_input';
  error_message?: string;

  // 元数据
  schema_info?: Record<string, string>;
  statistics?: Record<string, unknown>;
  sample_items?: Record<string, unknown>[];
  quality_score?: number;

  // 来源追溯
  source?: ArtifactSource;

  // 可视化建议
  suggested_views: ViewSpec[];

  // 引用关系
  derived_from: ArtifactRef[];
  used_by: ArtifactRef[];

  // 标签
  tags: string[];
}

/**
 * 产物列表请求参数
 */
export interface ListArtifactsParams {
  workflow_id?: string;
  artifact_type?: ArtifactType;
  tags?: string[];
  limit?: number;
  offset?: number;
}

/**
 * 产物导出格式
 */
export type ExportFormat = 'json' | 'csv';

/**
 * 产物导出结果
 */
export interface ArtifactExport {
  metadata: DataArtifact;
  data: unknown;
}

/**
 * 产物存储统计
 */
export interface ArtifactStoreStats {
  total_artifacts: number;
  by_type: Record<ArtifactType, number>;
  data_store: {
    items: number;
    max_items: number;
    ttl_seconds: number;
  };
}
