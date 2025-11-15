<template>
  <div class="panel-stage w-full">
    <div class="canvas-stack w-full space-y-8">
      <template v-if="hasPanel">
        <PanelBoard
          :layout="panelState.layout!"
          :blocks="panelState.blocks"
          :data-blocks="panelState.dataBlocks"
          @snapshot-change="panelStore.setLayoutSnapshot"
          @inspect-component="$emit('inspect-component', $event)"
        />
      </template>
      <PanelEmptyState v-else />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, withDefaults } from "vue";
import type { UIBlock, DataBlock } from "@/shared/types/panel";
import { usePanelActions } from "./usePanelActions";
import { usePanelStore } from "../../store/panelStore";
import PanelEmptyState from "./components/PanelEmptyState.vue";
import PanelBoard from "./components/PanelBoard.vue";

const props = withDefaults(
  defineProps<{
    autoInitialize?: boolean;
  }>(),
  {
    autoInitialize: true,
  }
);

const emit = defineEmits<{
  (event: "inspect-component", payload: { block: UIBlock; dataBlock: DataBlock | null }): void;
}>();

const panelStore = usePanelStore();
const { state: panelState, hasPanel, query, submit } = usePanelActions();

onMounted(() => {
  if (props.autoInitialize) {
    submit({ query: query.value });
  }
});
</script>
