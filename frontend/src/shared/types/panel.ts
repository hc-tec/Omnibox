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

export interface EnvelopeCursor {
  next_token?: string | null;
  total?: number | null;
  sampled?: number | null;
}

export interface StructuredDataSchema {
  type: "table" | "record" | "graph" | "geojson" | "metric_set" | "custom";
  description?: string | null;
  [key: string]: unknown;
}

export interface StructuredDataEnvelope {
  data_id: string;
  data_schema: StructuredDataSchema;
  summary?: string | null;
  preview: Record<string, unknown>[];
  cursor?: EnvelopeCursor | null;
  metadata?: Record<string, unknown>;
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
  contract_id?: string | null;
}

export interface PanelContractInfo {
  component_id: string;
  contract_id?: string | null;
  view_model_id?: string | null;
  title?: string | null;
}

export interface PanelPayload {
  mode: LayoutMode;
  layout: LayoutTree;
  blocks: UIBlock[];
}

export interface PanelSpecMetadata {
  data_envelopes: Record<string, StructuredDataEnvelope>;
  display_schemas: Record<string, unknown>;
  view_models: Record<
    string,
    {
      component_id: string;
      data: Record<string, unknown>;
      props: Record<string, unknown>;
      contract_id?: string | null;
    }
  >;
  panel_dsl?: Record<string, unknown> | null;
  rendered_preview?: unknown;
  degraded_components?: Array<Record<string, unknown>>;
  contracts_applied?: PanelContractInfo[];
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
    task_id?: string | null;
    stream_id?: string | null;
    sub_queries?: Array<{ query: string; task_type?: string }> | null;
    query_plan?: {
      sub_query_count?: number;
      estimated_steps?: number;
    } | null;
    // 流式研究相关字段（后端架构重构 v2.0 新增）
    requires_streaming?: boolean | null;
    websocket_endpoint?: string | null;
    suggested_action?: string | null;
    // Phase 2: 快速刷新元数据
    refresh_metadata?: {
      route_id: string;
      generated_path: string;
      retrieved_tools?: Array<{
        route_id: string;
        name: string;
        score: number;
      }>;
      query_plan?: any;
    } | null;
    panel_spec?: PanelSpecMetadata;
    panel_contracts?: PanelContractInfo[];
    panel_degraded_components?: Array<Record<string, unknown>>;
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

/**
 * V5.0 可观测性：LLM 调用事件
 * 用于追踪后端各个 Agent 的 LLM 调用情况
 */
export interface LLMCallEvent {
  call_id: string;
  role: "planner" | "reflector" | "synthesizer" | "data_stasher" | "entity_resolver" | "query_parser" | "router" | "other";
  status: "started" | "completed" | "failed";
  step_id?: number | null;
  stream_id?: string | null;
  timestamp?: string | null;
  duration_ms?: number | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  prompt_preview?: string | null;
  response_preview?: string | null;
  full_prompt?: string | null;
  full_response?: string | null;
  error_message?: string | null;
  model?: string | null;
  temperature?: number | null;
  metadata?: Record<string, unknown>;
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
    }
  | {
      type: "llm_call";
      stream_id: string;
      timestamp: string;
      call_id: string;
      role: LLMCallEvent["role"];
      status: LLMCallEvent["status"];
      step_id?: number | null;
      duration_ms?: number | null;
      prompt_tokens?: number | null;
      completion_tokens?: number | null;
      total_tokens?: number | null;
      prompt_preview?: string | null;
      response_preview?: string | null;
      full_prompt?: string | null;
      full_response?: string | null;
      error_message?: string | null;
      model?: string | null;
      temperature?: number | null;
      metadata?: Record<string, unknown>;
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
  task_id?: string | null;
}
