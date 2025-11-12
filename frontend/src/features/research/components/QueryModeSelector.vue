<template>
  <div class="flex items-center gap-2">
    <span class="text-sm text-muted-foreground">模式:</span>
    <div class="flex gap-2">
      <Button
        v-for="mode in modes"
        :key="mode.value"
        :variant="selectedMode === mode.value ? 'default' : 'outline'"
        size="sm"
        @click="selectMode(mode.value)"
      >
        <component :is="mode.icon" class="h-4 w-4 mr-1" />
        {{ mode.label }}
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Button } from '@/components/ui/button';
import { Zap, Search, Brain } from 'lucide-vue-next';
import type { QueryMode } from '../types/researchTypes';

interface Props {
  modelValue: QueryMode;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  'update:modelValue': [value: QueryMode];
}>();

const modes = [
  { value: 'auto' as QueryMode, label: '自动', icon: Zap },
  { value: 'simple' as QueryMode, label: '简单', icon: Search },
  { value: 'research' as QueryMode, label: '研究', icon: Brain },
];

const selectedMode = computed(() => props.modelValue);

function selectMode(mode: QueryMode) {
  emit('update:modelValue', mode);
}
</script>
