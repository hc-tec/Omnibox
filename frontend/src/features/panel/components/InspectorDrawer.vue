<template>
  <Dialog :open="open" @update:open="onOpenChange">
    <DialogPortalPrimitive>
      <DialogOverlayPrimitive class="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0" />
      <DialogContent
        class="fixed right-0 top-0 z-50 h-svh w-full max-w-md translate-x-0 translate-y-0 rounded-none border-l border-border/70 bg-background p-6 shadow-2xl data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right sm:w-[420px]"
      >
        <DialogHeader class="mb-4 space-y-1">
          <DialogTitle class="text-base uppercase tracking-[0.4em] text-muted-foreground">
            Inspector
          </DialogTitle>
          <DialogDescription class="text-lg font-semibold text-foreground">调试信息</DialogDescription>
        </DialogHeader>
        <div class="flex flex-col gap-4 overflow-y-auto">
          <PanelMetadata :metadata="metadata" :message="message" />
          <PanelStreamLog :log="log" :fetch-snapshot="fetchSnapshot" />
        </div>
      </DialogContent>
    </DialogPortalPrimitive>
  </Dialog>
</template>

<script setup lang="ts">
import type { PanelResponse, PanelStreamFetchPayload, StreamMessage } from "@/shared/types/panel";
import PanelMetadata from "./PanelMetadata.vue";
import PanelStreamLog from "./PanelStreamLog.vue";
import Dialog from "@/components/ui/dialog/Dialog.vue";
import DialogContent from "@/components/ui/dialog/DialogContent.vue";
import DialogDescription from "@/components/ui/dialog/DialogDescription.vue";
import DialogHeader from "@/components/ui/dialog/DialogHeader.vue";
import DialogTitle from "@/components/ui/dialog/DialogTitle.vue";
import { DialogOverlay as DialogOverlayPrimitive, DialogPortal as DialogPortalPrimitive } from "reka-ui";

const props = defineProps<{
  open: boolean;
  metadata: PanelResponse["metadata"];
  message: string;
  log: StreamMessage[];
  fetchSnapshot: PanelStreamFetchPayload | null;
}>();

const emit = defineEmits<{
  (event: "close"): void;
}>();

const onOpenChange = (value: boolean) => {
  if (!value) emit("close");
};
</script>
