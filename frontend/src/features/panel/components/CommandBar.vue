<template>
  <section :class="commandBarClasses" @mouseenter="hovered = true" @mouseleave="hovered = false">
    <form :class="['flex flex-col', condensed ? 'space-y-3' : 'space-y-5']" @submit.prevent="handleSubmit">
      <div class="flex flex-col gap-4 md:flex-row md:items-center">
        <div class="flex flex-1 items-center gap-3">
          <div
            :class="[
              'flex items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-blue-600 text-white shadow-lg shadow-indigo-500/30 transition-all',
              condensed ? 'h-10 w-10 text-sm' : 'h-12 w-12 text-base'
            ]"
          >
            <Sparkles class="h-5 w-5" />
          </div>
          <div class="flex-1">
            <p class="text-[11px] uppercase tracking-[0.5em] text-muted-foreground">{{ copy.label }}</p>
            <input
              ref="inputRef"
              v-model="localQuery"
              type="text"
              :placeholder="copy.placeholder"
              :disabled="loading"
              class="w-full bg-transparent text-foreground placeholder:text-muted-foreground/80 focus:outline-none transition-all"
              :class="condensed ? 'text-base font-medium' : 'text-2xl font-semibold'"
              @focus="handleFocus"
              @blur="handleBlur"
            />
          </div>
        </div>
        <Button
          type="submit"
          :disabled="loading || !localQuery.trim()"
          :size="condensed ? 'sm' : 'lg'"
          class="no-drag rounded-2xl font-semibold transition-all"
          :class="condensed ? 'px-5 text-sm' : 'px-8 text-base'"
        >
          {{ loading ? copy.submitLoading : copy.submitIdle }}
        </Button>
      </div>

      <div v-if="!condensed" class="flex flex-col gap-3">
        <!-- Mode Selector -->
        <div class="flex items-center gap-2">
          <span class="text-[11px] uppercase tracking-[0.4em] text-muted-foreground/70">模式</span>
          <div class="flex gap-2">
            <Button
              v-for="mode in modes"
              :key="mode.value"
              :variant="queryMode === mode.value ? 'default' : 'outline'"
              size="sm"
              type="button"
              class="rounded-full text-xs h-7 px-3"
              @click="queryMode = mode.value"
            >
              <component :is="mode.icon" class="h-3 w-3 mr-1" />
              {{ mode.label }}
            </Button>
          </div>
        </div>

        <!-- Samples -->
        <div class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span class="tracking-[0.4em] uppercase text-muted-foreground/70">{{ copy.samplesLabel }}</span>
          <Button
            v-for="sample in samples"
            :key="sample"
            variant="outline"
            size="sm"
            type="button"
            class="rounded-full border-dashed border-border/70 text-foreground hover:border-foreground/80"
            @click="useSample(sample)"
          >
            {{ sample }}
          </Button>
        </div>
      </div>

      <div v-if="!condensed" class="flex flex-wrap items-center justify-between gap-3 text-[12px] uppercase tracking-[0.4em] text-muted-foreground/70">
        <span>{{ copy.helper }}</span>
        <Button
          v-if="hasLayout"
          type="button"
          variant="ghost"
          class="rounded-full px-4 py-1 text-xs font-medium tracking-[0.3em] text-muted-foreground transition hover:text-destructive"
          @click="$emit('reset-panels')"
        >
          {{ copy.reset }}
        </Button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { Sparkles, Zap, Search, Brain } from "lucide-vue-next";
import { Button } from "@/components/ui/button";
import { onMounted, ref, watch, defineExpose, computed } from "vue";
import type { QueryMode } from "@/shared/types/panel";

const props = defineProps<{
  loading: boolean;
  defaultQuery: string;
  hasLayout: boolean;
  condensed?: boolean;
}>();

const emit = defineEmits<{
  (event: "submit", payload: { query: string; mode: QueryMode }): void;
  (event: "reset-panels"): void;
  (event: "focus-change", value: boolean): void;
}>();

const modes = [
  { value: 'auto' as QueryMode, label: '自动', icon: Zap },
  { value: 'simple' as QueryMode, label: '简单', icon: Search },
  { value: 'research' as QueryMode, label: '研究', icon: Brain },
];

const copy = {
  label: "\u8f93\u5165\u6307\u4ee4",
  placeholder: "\u6bd4\u5982\uff1a\u5206\u6790 GitHub \u4eca\u65e5\u8d8a\u70ed\uff0c\u751f\u6210\u70ed\u5ea6\u56fe + \u6458\u8981\u5361\u7247",
  submitIdle: "\u751f\u6210\u9762\u677f",
  submitLoading: "\u751f\u6210\u4e2d...",
  samplesLabel: "\u793a\u4f8b",
  helper: "Enter \u751f\u6210\u9762\u677f \u00b7 Shift + Enter \u6362\u884c",
  reset: "\u6e05\u7a7a\u753b\u5e03",
  samples: [
    "\u805a\u5408 B \u7ad9\u5b9e\u65f6\u70ed\u641c\uff0c\u8f93\u51fa\u5217\u8868 + \u70ed\u5ea6\u5206\u5e03\u56fe",
    "\u68b3\u7406 A \u80a1\u65b0\u80fd\u6e90\u9f99\u5934 30 \u5929\u52a8\u6001\uff0c\u7f16\u5236\u6298\u7ebf\u56fe",
    "\u603b\u7ed3 Product Hunt \u4eca\u65e5 TOP3 \u4ea7\u54c1\uff0c\u9644\u4eae\u70b9\u8bc4\u4ef7",
  ],
};

const samples = copy.samples;
const localQuery = ref(props.defaultQuery);
const queryMode = ref<QueryMode>('auto');
const inputRef = ref<HTMLInputElement | null>(null);
const hovered = ref(false);
const focused = ref(false);
const condensed = computed(() => props.condensed ?? false);
const isActive = computed(() => hovered.value || focused.value || props.loading);
const commandBarClasses = computed(() => [
  "command-bar w-full rounded-[32px] border backdrop-blur-2xl transition duration-300",
  isActive.value ? "opacity-100 shadow-[0_32px_90px_rgba(5,8,20,0.45)]" : "opacity-75 shadow-[0_18px_50px_rgba(5,8,20,0.2)]",
  condensed.value ? "border-border/30 bg-[var(--shell-surface)]/40 p-3" : "border-border/50 bg-[var(--shell-surface)]/90 p-6"
]);

watch(
  () => props.defaultQuery,
  (value) => {
    localQuery.value = value;
  }
);

function focusInput() {
  inputRef.value?.focus();
}

defineExpose({ focusInput });

function handleSubmit() {
  const value = localQuery.value.trim();
  if (!value) return;
  emit("submit", { query: value, mode: queryMode.value });
}

function useSample(sample: string) {
  localQuery.value = sample;
  focusInput();
}

function handleFocus() {
  focused.value = true;
  emit("focus-change", true);
}

function handleBlur() {
  focused.value = false;
  emit("focus-change", false);
}

// 移除自动聚焦，用户需要手动点击或按快捷键打开
// onMounted(() => {
//   focusInput();
// });
</script>
