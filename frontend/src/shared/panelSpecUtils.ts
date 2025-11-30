import type {
  PanelSpecMetadata,
  DataBlock,
  StructuredDataEnvelope,
  SchemaFieldSummary,
} from "./types/panel";

/**
 * 根据 panel_spec 中的 data_envelopes 构造 data_blocks，供 DynamicBlockRenderer 复用。
 */
export function buildDataBlocksFromSpec(spec?: PanelSpecMetadata | null): Record<string, DataBlock> {
  if (!spec || !spec.data_envelopes) {
    return {};
  }

  const entries = Object.entries(spec.data_envelopes).map(([key, envelope]) => [
    key,
    envelopeToDataBlock(envelope),
  ]);
  return Object.fromEntries(entries);
}

function envelopeToDataBlock(envelope: StructuredDataEnvelope): DataBlock {
  const preview = Array.isArray(envelope.preview) ? envelope.preview : [];
  const metadata = (envelope.metadata as Record<string, unknown>) || {};
  const statsMeta = (metadata.stats as Record<string, unknown>) || {};
  const baseStats: Record<string, unknown> = {
    ...statsMeta,
    total: statsMeta.total ?? envelope.cursor?.total ?? preview.length,
    sampled: statsMeta.sampled ?? envelope.cursor?.sampled ?? preview.length,
  };

  return {
    id: envelope.data_id,
    source_info: {
      datasource: String(metadata.datasource ?? metadata.source ?? "unknown"),
      route: String(
        metadata.generated_path ??
          metadata.route ??
          metadata.source_route ??
          "/unknown"
      ),
      params:
        (metadata.params as Record<string, unknown>) !== undefined
          ? ((metadata.params as Record<string, unknown>) ?? {})
          : {},
      fetched_at:
        typeof metadata.fetched_at === "string" ? metadata.fetched_at : null,
      request_id:
        typeof metadata.request_id === "string" ? metadata.request_id : null,
    },
    records: preview,
    stats: baseStats,
    schema_summary: {
      fields: buildFieldSummaries(preview),
      stats: {},
      schema_digest:
        envelope.data_schema?.description ||
        `${envelope.data_schema?.type ?? "record"}`,
    },
    full_data_ref: envelope.data_id,
  };
}

function buildFieldSummaries(preview: Record<string, unknown>[]): SchemaFieldSummary[] {
  if (!preview.length || typeof preview[0] !== "object") {
    return [];
  }
  const first = preview[0] as Record<string, unknown>;
  return Object.keys(first)
    .slice(0, 8)
    .map((key) => ({
      name: key,
      type: typeof first[key],
      sample: [first[key]],
      stats: null,
    }));
}
