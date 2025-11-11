<template>
  <Card class="empty-state h-full items-center justify-center border-dashed border-border/70 bg-[var(--shell-surface)]/30 text-center">
    <CardContent class="space-y-5 py-16">
      <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/15 text-primary">
        <Sparkles class="h-8 w-8" />
      </div>
      <div class="space-y-3">
        <CardTitle class="text-2xl font-semibold">{{ copy.title }}</CardTitle>
        <p class="text-sm text-muted-foreground">
          {{ copy.description }}
        </p>
      </div>
      <div class="inline-flex flex-wrap items-center justify-center gap-3 text-[11px] uppercase tracking-[0.35em] text-muted-foreground/80">
        <span v-for="badge in copy.badges" :key="badge" class="rounded-full border border-border/60 px-3 py-1">
          {{ badge }}
        </span>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { Sparkles } from "lucide-vue-next";
import { Card, CardContent, CardTitle } from "@/components/ui/card";

const copy = {
  title: "\u7b49\u5f85\u65b0\u7684\u7075\u611f",
  description: "\u4f7f\u7528\u5feb\u6377\u952e\u5524\u9192\u8f93\u5165\u6846\uff0c\u63cf\u8ff0\u4f60\u60f3\u770b\u5230\u7684\u52a8\u6001\uff0cOmnibox \u4f1a\u81ea\u52a8\u62fc\u88c5\u5361\u7247\u3001\u56fe\u8868\u4e0e\u5e03\u5c40\u3002",
  badges: ["Append \u6a21\u5f0f", "\u5b9e\u65f6\u6d41\u5f0f", "\u81ea\u52a8\u6392\u7248"],
};
</script>
