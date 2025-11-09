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

export interface BarChartRecord {
  id: string;
  x: string;
  y: number;
  series?: string | null;
  color?: string | null;
  tooltip?: string | null;
  [key: string]: unknown;
}

export interface PieChartRecord {
  id: string;
  name: string;
  value: number;
  color?: string | null;
  tooltip?: string | null;
  [key: string]: unknown;
}

export interface ImageGalleryRecord {
  id: string;
  image_url: string;
  title?: string | null;
  description?: string | null;
  link?: string | null;
  thumbnail_url?: string | null;
  [key: string]: unknown;
}

export interface TableColumn {
  key: string;
  label: string;
  type?: "text" | "number" | "date" | "currency" | "tag" | null;
  sortable?: boolean;
  align?: "left" | "center" | "right" | null;
  width?: number | null;
}

export interface TableViewModel {
  columns: TableColumn[];
  rows: Record<string, any>[];
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
  | BarChartRecord
  | PieChartRecord
  | ImageGalleryRecord
  | TableViewModel
  | FallbackRichTextRecord;

export interface PanelComponentDatasets {
  ListPanel: ListPanelRecord[];
  StatisticCard: StatisticCardRecord[];
  LineChart: LineChartRecord[];
  BarChart: BarChartRecord[];
  PieChart: PieChartRecord[];
  ImageGallery: ImageGalleryRecord[];
  Table: TableViewModel[];
  FallbackRichText: FallbackRichTextRecord[];
}
