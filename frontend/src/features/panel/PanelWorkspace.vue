<template>
  <div class="panel-workspace">
    <PanelToolbar
      :loading="panelState.loading"
      :stream-loading="panelState.streamLoading"
      :default-query="query"
      @submit="submit"
      @stream="startStream"
      @stop-stream="stopStream"
    />

    <section class="panel-body">
      <aside class="panel-meta" v-if="panelState.metadata">
        <PanelMetadata :metadata="panelState.metadata" :message="panelState.message" />
        <PanelStreamLog :log="panelState.streamLog" :fetch-snapshot="panelState.fetchSnapshot" />
      </aside>

      <section class="panel-board">
        <template v-if="hasPanel">
          <LayoutBoard
            :layout="panelState.layout!"
            :blocks="panelState.blocks"
            :data-blocks="panelState.dataBlocks"
          />
        </template>
        <PanelEmptyState v-else />
      </section>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { usePanelActions } from "./usePanelActions";
import PanelToolbar from "./components/PanelToolbar.vue";
import PanelMetadata from "./components/PanelMetadata.vue";
import PanelStreamLog from "./components/PanelStreamLog.vue";
import PanelEmptyState from "./components/PanelEmptyState.vue";
import LayoutBoard from "./components/LayoutBoard.vue";

const { state: panelState, hasPanel, query, submit, startStream, stopStream } = usePanelActions();

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

.panel-body {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 24px;
  height: 100%;
}

.panel-meta {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-right: 8px;
  border-right: 1px solid rgba(226, 232, 240, 0.8);
  overflow-y: auto;
}

.panel-board {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}

@media (max-width: 1200px) {
  .panel-body {
    grid-template-columns: 1fr;
  }

  .panel-meta {
    border-right: none;
    border-bottom: 1px solid rgba(226, 232, 240, 0.8);
    padding-right: 0;
    padding-bottom: 16px;
  }
}
</style>
