import type { ComponentAbility } from "../shared/componentManifest";
import { resolveComponentAbility, normalizeInteractions } from "../shared/componentManifest";
import type { DataBlock, UIBlock, InteractionDefinition } from "../shared/types/panel";

export interface ResolvedBlock {
  ability: ComponentAbility | null;
  block: UIBlock;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
  interactions: InteractionDefinition[];
  warnings: string[];
}

export function resolveBlock(
  block: UIBlock,
  dataBlocks: Record<string, DataBlock>
): ResolvedBlock {
  const ability = resolveComponentAbility(block.component);
  const dataBlock = block.data_ref ? dataBlocks[block.data_ref] ?? null : null;
  const dataPayload =
    block.data ??
    (dataBlock
      ? {
          items: dataBlock.records,
          schema: dataBlock.schema_summary,
          stats: dataBlock.stats,
        }
      : null);

  const warnings: string[] = [];
  if (!ability) {
    warnings.push(`未知组件：${block.component}`);
  } else {
    // 校验 props
    for (const [propKey, definition] of Object.entries(ability.props)) {
      const camelKey = convertCamelCase(propKey);
      const value = block.props[camelKey] ?? block.props[propKey];
      if (definition.required && (value === undefined || value === null)) {
        warnings.push(`缺少必需字段 ${propKey}`);
      }
    }
  }

  const interactions = normalizeInteractions(block.interactions, ability?.interactions ?? []);

  return {
    ability,
    block,
    data: dataPayload,
    dataBlock,
    interactions,
    warnings,
  };
}

function convertCamelCase(input: string): string {
  return input.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
}
