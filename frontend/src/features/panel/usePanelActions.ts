import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import { usePanelStore } from "../../store/panelStore";
import type { PanelResponse } from "@/shared/types/panel";

interface SubmitPayload {
  query: string;
  datasource?: string | null;
  mode?: string;
  client_task_id?: string | null;
}

export function usePanelActions(initialQuery = "我想看看bilibili热搜") {
  const panelStore = usePanelStore();
  const { state, hasPanel } = storeToRefs(panelStore);
  const query = ref(initialQuery);
  const datasource = ref<string | null>(null);

  const isBusy = computed(() => state.value.loading || state.value.streamLoading);

  const submit = async (payload: SubmitPayload): Promise<PanelResponse> => {
    query.value = payload.query;
    datasource.value = payload.datasource ?? null;
    return panelStore.fetchPanel(query.value, datasource.value, panelStore.getLayoutSnapshot(), payload.mode, payload.client_task_id ?? null);
  };

  const startStream = (payload: { query: string; datasource?: string | null; mode?: string }) => {
    query.value = payload.query;
    datasource.value = payload.datasource ?? null;
    panelStore.connectStream(query.value, datasource.value, panelStore.getLayoutSnapshot(), payload.mode);
  };

  const stopStream = () => {
    panelStore.disconnectStream();
  };

  const reset = () => {
    panelStore.resetPanel();
  };

  return {
    state,
    hasPanel,
    query,
    datasource,
    isBusy,
    submit,
    startStream,
    stopStream,
    reset,
  };
}
