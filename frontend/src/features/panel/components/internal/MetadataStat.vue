<template>
  <article class="rounded-xl border border-border/60 bg-muted/30 px-3 py-3">
    <p class="text-[11px] uppercase tracking-[0.3em] text-muted-foreground">{{ label }}</p>
    <p class="mt-1 text-lg font-semibold text-foreground">{{ value }}</p>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  label: string;
  value: string;
}>();
</script>
