export type LayoutMode = "append" | "replace" | "insert";

export interface SourceInfo {
  datasource: string;
  route: string;
  params: Record<string, unknown>;
  fetched_at?: string | null;
  request_id?: string | null;
}

export interface SchemaFieldSummary {
  name: string;
  type: string;
  sample: unknown[];
  stats?: Record<string, unknown> | null;
}

export interface SchemaSummary {
  fields: SchemaFieldSummary[];
  stats: Record<string, unknown>;
  schema_digest: string;
}

export interface DataBlock {
  id: string;
  source_info: SourceInfo;
  records: Record<string, unknown>[];
  stats: Record<string, unknown>;
  schema_summary: SchemaSummary;
  full_data_ref?: string | null;
}

export interface LayoutGridMeta {
  x: number;
  y: number;
  w: number;
  h: number;
  minH?: number;
  size?: string;
  layoutSize?: string;
  layout_size?: string;
}

export interface LayoutNode {
  type: "row" | "column" | "grid" | "cell";
  id: string;
  children: string[];
  props?: {
    span?: number;
    order?: number;
    priority?: number;
    min_height?: number;
    responsive?: Record<string, unknown>;
    grid?: LayoutGridMeta;
  };
}

export interface LayoutTree {
  mode: LayoutMode;
  nodes: LayoutNode[];
  history_token?: string | null;
}

export interface InteractionDefinition {
  type: string;
  label?: string;
  payload?: Record<string, unknown> | null;
}

export interface UIBlock {
  id: string;
  component: string;
  data_ref?: string | null;
  data?: Record<string, unknown> | null;
  props: Record<string, unknown>;
  options: Record<string, unknown>;
  interactions?: InteractionDefinition[];
  confidence?: number | null;
  title?: string | null;
  children?: UIBlock[] | null;
}

export interface PanelPayload {
  mode: LayoutMode;
  layout: LayoutTree;
  blocks: UIBlock[];
}

export interface PanelResponse {
  success: boolean;
  message: string;
  data: PanelPayload | null;
  data_blocks: Record<string, DataBlock>;
  metadata?: {
    intent_type?: string | null;
    research_type?: string | null;
    intent_confidence?: number | null;
    generated_path?: string | null;
    source?: string | null;
    cache_hit?: string | null;
    feed_title?: string | null;
    status?: string | null;
    reasoning?: string | null;
    component_confidence?: Record<string, number>;
    debug?: Record<string, unknown>;
    sub_queries?: Array<{ query: string; task_type?: string }> | null;
    query_plan?: {
      sub_query_count?: number;
      estimated_steps?: number;
    } | null;
    // 流式研究相关字段（后端架构重构 v2.0 新增）
    requires_streaming?: boolean | null;
    websocket_endpoint?: string | null;
    suggested_action?: string | null;
  };
}

export interface PanelStreamSummaryPayload {
  success: boolean;
  intent_type: string;
  message: string;
  data: PanelPayload | null;
  data_blocks: Record<string, DataBlock>;
  metadata?: PanelResponse["metadata"];
}

export interface PanelStreamFetchPayload {
  items_count: number;
  block_count: number;
  cache_hit?: string | null;
  source?: string | null;
}

export interface LayoutSnapshotItem {
  block_id: string;
  component: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export type StreamMessage =
  | {
      type: "stage";
      stream_id: string;
      timestamp: string;
      stage: "intent" | "rag" | "fetch" | "summary";
      message: string;
      progress?: number;
    }
  | {
      type: "data";
      stream_id: string;
      timestamp: string;
      stage: "intent";
      data: {
        intent_type: string;
        confidence: number;
        reasoning?: string;
      };
    }
  | {
      type: "data";
      stream_id: string;
      timestamp: string;
      stage: "fetch";
      data: PanelStreamFetchPayload;
    }
  | {
      type: "data";
      stream_id: string;
      timestamp: string;
      stage: "summary";
      data: PanelStreamSummaryPayload;
    }
  | {
      type: "error";
      stream_id: string;
      timestamp: string;
      error_code: string;
      error_message: string;
      stage?: "intent" | "rag" | "fetch" | "summary" | null;
    }
  | {
      type: "complete";
      stream_id: string;
      timestamp: string;
      success: boolean;
      message: string;
      total_time?: number;
    };

export type QueryMode = 'auto' | 'simple' | 'research';

export interface ChatRequestParams {
  query: string;
  filter_datasource?: string | null;
  use_cache?: boolean;
  layout_snapshot?: LayoutSnapshotItem[] | null;
  mode?: QueryMode;
  client_task_id?: string | null;
}

export interface StreamRequestPayload extends ChatRequestParams {
  use_cache?: boolean;
  mode?: QueryMode;
}

