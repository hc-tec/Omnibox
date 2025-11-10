<template>
  <div class="panel-workspace">
    <PanelToolbar
      :loading="panelState.loading"
      :stream-loading="panelState.streamLoading"
      :default-query="query"
      :can-reset="panelState.blocks.length > 0"
      @submit="submit"
      @stream="startStream"
      @stop-stream="stopStream"
      @reset="handleReset"
    />

    <section class="workspace-body">
      <div class="workspace-board">
        <template v-if="hasPanel">
          <PanelBoard
            :layout="panelState.layout!"
            :blocks="panelState.blocks"
            :data-blocks="panelState.dataBlocks"
            @snapshot-change="panelStore.setLayoutSnapshot"
          />
        </template>
        <PanelEmptyState v-else />
      </div>

      <aside class="workspace-meta">
        <PanelMetadata
          v-if="panelState.metadata"
          :metadata="panelState.metadata"
          :message="panelState.message"
        />
        <PanelStreamLog :log="panelState.streamLog" :fetch-snapshot="panelState.fetchSnapshot" />
      </aside>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { usePanelActions } from "./usePanelActions";
import { usePanelStore } from "../../store/panelStore";
import PanelToolbar from "./components/PanelToolbar.vue";
import PanelMetadata from "./components/PanelMetadata.vue";
import PanelStreamLog from "./components/PanelStreamLog.vue";
import PanelEmptyState from "./components/PanelEmptyState.vue";
import PanelBoard from "./components/PanelBoard.vue";

const panelStore = usePanelStore();
const { state: panelState, hasPanel, query, submit, startStream, stopStream, reset } = usePanelActions();

const handleReset = () => {
  reset();
};

onMounted(() => {
  submit({ query: query.value });
});
</script>

<style scoped>
.panel-workspace {
  display: flex;
  flex-direction: column;
  gap: 24px;
  height: 100%;
}

.workspace-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 20px;
  height: 100%;
  align-items: flex-start;
}

.workspace-board {
  min-height: 480px;
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  background: #ffffff;
}

.workspace-meta {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.8);
  background: rgba(248, 250, 252, 0.8);
  backdrop-filter: blur(8px);
  max-height: calc(100vh - 240px);
  overflow-y: auto;
}

@media (max-width: 1280px) {
  .workspace-body {
    grid-template-columns: 1fr;
  }

  .workspace-meta {
    max-height: none;
  }
}
</style>
