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
      },
      options: {
        show_description: { type: "boolean", default: true },
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
