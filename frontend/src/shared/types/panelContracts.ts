export interface ListPanelRecord {
  id: string;
  title: string;
  link?: string | null;
  summary?: string | null;
  published_at?: string | null;
  author?: string | null;
  categories?: string[] | null;
  [key: string]: unknown;
}

export interface StatisticCardRecord {
  id: string;
  metric_title: string;
  metric_value: number;
  metric_unit?: string | null;
  metric_delta_text?: string | null;
  metric_delta_value?: number | null;
  metric_trend?: "up" | "down" | "flat" | null;
  description?: string | null;
  [key: string]: unknown;
}

export interface LineChartRecord {
  id: string;
  x: string | number;
  y: number;
  series?: string | null;
  tooltip?: string | null;
  [key: string]: unknown;
}

export interface FallbackRichTextRecord {
  id: string;
  title?: string | null;
  content: string;
  [key: string]: unknown;
}

export type PanelComponentRecord =
  | ListPanelRecord
  | StatisticCardRecord
  | LineChartRecord
  | FallbackRichTextRecord;

export interface PanelComponentDatasets {
  ListPanel: ListPanelRecord[];
  StatisticCard: StatisticCardRecord[];
  LineChart: LineChartRecord[];
  FallbackRichText: FallbackRichTextRecord[];
}
