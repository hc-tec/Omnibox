import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import { usePanelStore } from "../../store/panelStore";

export function usePanelActions(initialQuery = "虎扑步行街最新帖子") {
  const panelStore = usePanelStore();
  const { state, hasPanel } = storeToRefs(panelStore);
  const query = ref(initialQuery);
  const datasource = ref<string | null>(null);

  const isBusy = computed(() => state.value.loading || state.value.streamLoading);

  const submit = async (payload: { query: string; datasource?: string | null }) => {
    query.value = payload.query;
    datasource.value = payload.datasource ?? null;
    await panelStore.fetchPanel(query.value, datasource.value);
  };

  const startStream = (payload: { query: string; datasource?: string | null }) => {
    query.value = payload.query;
    datasource.value = payload.datasource ?? null;
    panelStore.connectStream(query.value, datasource.value);
  };

  const stopStream = () => {
    panelStore.disconnectStream();
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
  };
}
