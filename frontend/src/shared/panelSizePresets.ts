export type PanelSizePreset = "compact" | "balanced" | "spacious";

export type PanelLayoutSize = "quarter" | "third" | "half" | "full";

export interface PanelLayoutConfig {
  minColumns: number;
  maxColumns: number;
  baseColumnWidth: number;
  sizeSpan: Record<PanelLayoutSize, number>;
}

export interface PanelSizeConfig {
  gridGap: number;
  cardPadding: number;
  cardRadius: number;
  listMaxItems: number;
  listRowHeight: number;
  listVisibleRows: number;
  mediaRows: number;
  mediaRowHeight: number;
  mediaMaxItems: number;
  horizontalItemMinWidth: number;
  fontScale: number;
  headingSize: number;
  metaSize: number;
  spacingScale: number;
  layout: PanelLayoutConfig;
  componentSizeOverrides?: Record<string, PanelLayoutSize>;
}

export const PANEL_SIZE_PRESETS: Record<PanelSizePreset, PanelSizeConfig> = {
  compact: {
    gridGap: 14,
    cardPadding: 10,
    cardRadius: 12,
    listMaxItems: 8,
    listRowHeight: 56,
    listVisibleRows: 4,
    mediaRows: 2,
    mediaRowHeight: 180,
    mediaMaxItems: 12,
    horizontalItemMinWidth: 220,
    fontScale: 0.92,
    headingSize: 14,
    metaSize: 11,
    spacingScale: 0.85,
    layout: {
      minColumns: 12,
      maxColumns: 24,
      baseColumnWidth: 220,
      sizeSpan: {
        quarter: 0.25,
        third: 0.34,
        half: 0.5,
        full: 1,
      },
    },
    componentSizeOverrides: {
      StatisticCard: "quarter",
      ListPanel: "third",
      LineChart: "half",
      BarChart: "half",
      PieChart: "third",
      Table: "half",
      MediaCardGrid: "half",
      ImageGallery: "half",
      FallbackRichText: "full",
    },
  },
  balanced: {
    gridGap: 20,
    cardPadding: 16,
    cardRadius: 18,
    listMaxItems: 12,
    listRowHeight: 84,
    listVisibleRows: 6,
    mediaRows: 3,
    mediaRowHeight: 210,
    mediaMaxItems: 18,
    horizontalItemMinWidth: 240,
    fontScale: 1,
    headingSize: 16,
    metaSize: 12,
    spacingScale: 1,
    layout: {
      minColumns: 12,
      maxColumns: 18,
      baseColumnWidth: 260,
      sizeSpan: {
        quarter: 0.28,
        third: 0.36,
        half: 0.56,
        full: 1,
      },
    },
  },
  spacious: {
    gridGap: 28,
    cardPadding: 20,
    cardRadius: 22,
    listMaxItems: 16,
    listRowHeight: 102,
    listVisibleRows: 8,
    mediaRows: 3,
    mediaRowHeight: 240,
    mediaMaxItems: 24,
    horizontalItemMinWidth: 260,
    fontScale: 1.08,
    headingSize: 18,
    metaSize: 13,
    spacingScale: 1.08,
    layout: {
      minColumns: 10,
      maxColumns: 14,
      baseColumnWidth: 320,
      sizeSpan: {
        quarter: 0.32,
        third: 0.42,
        half: 0.64,
        full: 1,
      },
    },
  },
};
