import { computed } from "vue";
import { usePanelStore } from "@/store/panelStore";
import { PANEL_SIZE_PRESETS } from "@/shared/panelSizePresets";

export function usePanelSizePreset() {
  const panelStore = usePanelStore();
  return computed(() => PANEL_SIZE_PRESETS[panelStore.state.sizePreset]);
}
