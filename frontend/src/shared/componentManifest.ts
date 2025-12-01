import type { InteractionDefinition } from "./types/panel";

export interface ComponentAbility {
  id: string;
  tag: string;
  props: Record<
    string,
    {
      type: "string" | "number" | "boolean" | "array" | "object";
      required: boolean;
    }
  >;
  options: Record<
    string,
    {
      type: "string" | "number" | "boolean";
      default: unknown;
    }
  >;
  interactions: string[];
  layoutDefaults: {
    span: number;
    minHeight: number;
    order?: number;
    priority?: number;
  };
  categories: string[];
}

export interface ComponentManifest {
  components: ComponentAbility[];
}

export const componentManifest: ComponentManifest = {
  components: [
    {
      id: "ListPanel",
      tag: "list",
      props: {
        title_field: { type: "string", required: true },
        link_field: { type: "string", required: true },
        description_field: { type: "string", required: false },
        pub_date_field: { type: "string", required: false },
        hot_field: { type: "string", required: false },
      },
      options: {
        variant: { type: "string", default: "standard" }, // 'minimal' | 'standard'
        show_description: { type: "boolean", default: true },
        show_metadata: { type: "boolean", default: true },
        show_categories: { type: "boolean", default: true },
        show_rank: { type: "boolean", default: false },
        compact: { type: "boolean", default: false },
        max_items: { type: "number", default: 10 },
        span: { type: "number", default: 12 },
      },
      interactions: ["open_link", "refresh"],
      layoutDefaults: { span: 12, minHeight: 320 },
      categories: ["list", "text"],
    },
    {
      id: "LineChart",
      tag: "chart",
      props: {
        x_field: { type: "string", required: true },
        y_field: { type: "string", required: true },
        series_field: { type: "string", required: false },
      },
      options: {
        area_style: { type: "boolean", default: false },
        span: { type: "number", default: 12 },
      },
      interactions: ["filter", "compare"],
      layoutDefaults: { span: 12, minHeight: 280 },
      categories: ["chart", "numeric"],
    },
    {
      id: "BarChart",
      tag: "chart",
      props: {
        x_field: { type: "string", required: true },
        y_field: { type: "string", required: true },
        series_field: { type: "string", required: false },
      },
      options: {
        horizontal: { type: "boolean", default: false },
        stacked: { type: "boolean", default: false },
        show_values: { type: "boolean", default: true },
        span: { type: "number", default: 12 },
      },
      interactions: ["filter", "sort"],
      layoutDefaults: { span: 12, minHeight: 280 },
      categories: ["chart", "numeric"],
    },
    {
      id: "PieChart",
      tag: "chart",
      props: {
        name_field: { type: "string", required: true },
        value_field: { type: "string", required: true },
      },
      options: {
        donut: { type: "boolean", default: false },
        show_legend: { type: "boolean", default: true },
        show_label: { type: "boolean", default: true },
        span: { type: "number", default: 12 },
      },
      interactions: ["filter"],
      layoutDefaults: { span: 12, minHeight: 280 },
      categories: ["chart", "numeric"],
    },
    {
      id: "Table",
      tag: "table",
      props: {},
      options: {
        pagination: { type: "boolean", default: true },
        page_size: { type: "number", default: 20 },
        span: { type: "number", default: 12 },
      },
      interactions: ["sort", "filter"],
      layoutDefaults: { span: 12, minHeight: 320 },
      categories: ["table", "structured"],
    },
    {
      id: "StatisticCard",
      tag: "stat",
      props: {
        title_field: { type: "string", required: true },
        value_field: { type: "string", required: true },
        trend_field: { type: "string", required: false },
      },
      options: {
        span: { type: "number", default: 6 },
      },
      interactions: [],
      layoutDefaults: { span: 6, minHeight: 160 },
      categories: ["stat", "numeric"],
    },
    {
      id: "FallbackRichText",
      tag: "fallback",
      props: {
        title_field: { type: "string", required: true },
        description_field: { type: "string", required: false },
      },
      options: {
        span: { type: "number", default: 12 },
      },
      interactions: [],
      layoutDefaults: { span: 12, minHeight: 200 },
      categories: ["fallback"],
    },
    {
      id: "MediaCardGrid",
      tag: "media",
      props: {
        title_field: { type: "string", required: true },
        link_field: { type: "string", required: false },
        cover_field: { type: "string", required: false },
        author_field: { type: "string", required: false },
        duration_field: { type: "string", required: false },
        view_count_field: { type: "string", required: false },
        like_count_field: { type: "string", required: false },
        badges_field: { type: "string", required: false },
      },
      options: {
        columns: { type: "number", default: 3 },
        max_items: { type: "number", default: 6 },
        span: { type: "number", default: 6 },
        compact: { type: "boolean", default: false },
      },
      interactions: ["open_link"],
      layoutDefaults: { span: 6, minHeight: 260 },
      categories: ["media", "card"],
    },
    {
      id: "ImageGallery",
      tag: "gallery",
      props: {
        url_field: { type: "string", required: true },
        title_field: { type: "string", required: false },
        description_field: { type: "string", required: false },
      },
      options: {
        columns: { type: "number", default: 3 },
        span: { type: "number", default: 12 },
      },
      interactions: ["open_lightbox"],
      layoutDefaults: { span: 12, minHeight: 280 },
      categories: ["media", "gallery"],
    },
    // 新增原子化组件
    {
      id: "CountCard",
      tag: "stat",
      props: {
        title_field: { type: "string", required: false },
        value_field: { type: "string", required: true },
        unit_field: { type: "string", required: false },
        description_field: { type: "string", required: false },
      },
      options: {
        color: { type: "string", default: "default" },
        span: { type: "number", default: 4 },
      },
      interactions: [],
      layoutDefaults: { span: 4, minHeight: 140 },
      categories: ["stat", "numeric"],
    },
    {
      id: "ProgressBar",
      tag: "stat",
      props: {
        label_field: { type: "string", required: false },
        value_field: { type: "string", required: true },
        max_field: { type: "string", required: false },
        description_field: { type: "string", required: false },
      },
      options: {
        color: { type: "string", default: "primary" },
        show_percentage: { type: "boolean", default: true },
        span: { type: "number", default: 6 },
      },
      interactions: [],
      layoutDefaults: { span: 6, minHeight: 120 },
      categories: ["stat", "numeric"],
    },
    {
      id: "QuoteCard",
      tag: "text",
      props: {
        content_field: { type: "string", required: true },
        author_field: { type: "string", required: false },
        source_field: { type: "string", required: false },
        timestamp_field: { type: "string", required: false },
      },
      options: {
        compact: { type: "boolean", default: false },
        span: { type: "number", default: 6 },
      },
      interactions: [],
      layoutDefaults: { span: 6, minHeight: 160 },
      categories: ["text", "content"],
    },
    {
      id: "ComparisonCard",
      tag: "stat",
      props: {
        left_label_field: { type: "string", required: false },
        left_value_field: { type: "string", required: true },
        left_unit_field: { type: "string", required: false },
        right_label_field: { type: "string", required: false },
        right_value_field: { type: "string", required: true },
        right_unit_field: { type: "string", required: false },
      },
      options: {
        show_diff: { type: "boolean", default: true },
        span: { type: "number", default: 6 },
      },
      interactions: [],
      layoutDefaults: { span: 6, minHeight: 160 },
      categories: ["stat", "comparison"],
    },
    {
      id: "AuthorCard",
      tag: "card",
      props: {
        name_field: { type: "string", required: true },
        avatar_field: { type: "string", required: false },
        bio_field: { type: "string", required: false },
        verified_field: { type: "string", required: false },
        followers_field: { type: "string", required: false },
        following_field: { type: "string", required: false },
        posts_field: { type: "string", required: false },
        link_field: { type: "string", required: false },
      },
      options: {
        span: { type: "number", default: 6 },
      },
      interactions: ["open_link"],
      layoutDefaults: { span: 6, minHeight: 140 },
      categories: ["card", "profile"],
    },
    {
      id: "TagCloud",
      tag: "chart",
      props: {
        name_field: { type: "string", required: true },
        count_field: { type: "string", required: true },
      },
      options: {
        max_tags: { type: "number", default: 30 },
        show_count: { type: "boolean", default: false },
        span: { type: "number", default: 6 },
      },
      interactions: [],
      layoutDefaults: { span: 6, minHeight: 220 },
      categories: ["chart", "distribution"],
    },
    {
      id: "TimelineCard",
      tag: "list",
      props: {
        title_field: { type: "string", required: true },
        timestamp_field: { type: "string", required: true },
        description_field: { type: "string", required: false },
        status_field: { type: "string", required: false },
        type_field: { type: "string", required: false },
        link_field: { type: "string", required: false },
      },
      options: {
        max_items: { type: "number", default: 10 },
        show_description: { type: "boolean", default: true },
        span: { type: "number", default: 6 },
      },
      interactions: ["open_link"],
      layoutDefaults: { span: 6, minHeight: 280 },
      categories: ["list", "timeline"],
    },
    {
      id: "HeatmapCalendar",
      tag: "chart",
      props: {
        date_field: { type: "string", required: true },
        value_field: { type: "string", required: true },
      },
      options: {
        weeks: { type: "number", default: 52 },
        show_stats: { type: "boolean", default: true },
        value_unit: { type: "string", default: "次" },
        span: { type: "number", default: 12 },
      },
      interactions: [],
      layoutDefaults: { span: 12, minHeight: 220 },
      categories: ["chart", "calendar"],
    },
    {
      id: "ServiceStatus",
      tag: "monitor",
      props: {
        name_field: { type: "string", required: false },
        timestamp_field: { type: "string", required: false },
        availability_field: { type: "string", required: false },
        latency_field: { type: "string", required: false },
        current_status_field: { type: "string", required: false },
        history_field: { type: "string", required: false },
      },
      options: {
        span: { type: "number", default: 6 },
      },
      interactions: ["refresh"],
      layoutDefaults: { span: 6, minHeight: 280 },
      categories: ["monitor", "status"],
    },
  ],
};

export function resolveComponentAbility(componentId: string): ComponentAbility | null {
  return componentManifest.components.find((item) => item.id === componentId) ?? null;
}

export function normalizeInteractions(
  definitions: InteractionDefinition[] | undefined,
  allowed: string[]
): InteractionDefinition[] {
  if (!definitions || definitions.length === 0) {
    return [];
  }
  return definitions.filter((interaction) => allowed.includes(interaction.type));
}
