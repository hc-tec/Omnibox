<template>
  <Card>
    <CardHeader v-if="block.title">
      <CardTitle>{{ block.title }}</CardTitle>
      <CardDescription v-if="dataBlock?.stats?.description">
        {{ dataBlock.stats.description }}
      </CardDescription>
    </CardHeader>

    <CardContent>
      <div v-if="isEmpty" class="flex h-[200px] items-center justify-center text-muted-foreground">
        暂无图片
      </div>

      <div v-else :class="gridClass">
        <div
          v-for="(image, index) in images"
          :key="index"
          class="group relative overflow-hidden rounded-lg border bg-muted cursor-pointer transition-all hover:shadow-lg"
          @click="openLightbox(index)"
        >
          <!-- Image -->
          <div class="aspect-square">
            <img
              :src="image.url"
              :alt="image.title || `图片 ${index + 1}`"
              class="h-full w-full object-cover transition-transform group-hover:scale-105"
              loading="lazy"
              @error="handleImageError($event, image)"
            />
          </div>

          <!-- Overlay with title -->
          <div
            v-if="image.title || image.description"
            class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-3 text-white opacity-0 transition-opacity group-hover:opacity-100"
          >
            <p v-if="image.title" class="text-sm font-medium line-clamp-1">
              {{ image.title }}
            </p>
            <p v-if="image.description" class="text-xs text-gray-300 line-clamp-2">
              {{ image.description }}
            </p>
          </div>
        </div>
      </div>

      <!-- Lightbox Dialog -->
      <Dialog :open="lightboxOpen" @update:open="lightboxOpen = $event">
        <DialogContent class="max-w-4xl">
          <DialogHeader>
            <DialogTitle v-if="currentImage?.title">
              {{ currentImage.title }}
            </DialogTitle>
            <DialogDescription v-if="currentImage?.description">
              {{ currentImage.description }}
            </DialogDescription>
          </DialogHeader>

          <div class="relative">
            <img
              v-if="currentImage"
              :src="currentImage.url"
              :alt="currentImage.title || '图片'"
              class="w-full rounded-md"
            />

            <!-- Navigation -->
            <div v-if="images.length > 1" class="mt-4 flex items-center justify-between">
              <Button
                variant="outline"
                size="sm"
                :disabled="currentImageIndex === 0"
                @click="navigateLightbox(-1)"
              >
                上一张
              </Button>
              <span class="text-sm text-muted-foreground">
                {{ currentImageIndex + 1 }} / {{ images.length }}
              </span>
              <Button
                variant="outline"
                size="sm"
                :disabled="currentImageIndex === images.length - 1"
                @click="navigateLightbox(1)"
              >
                下一张
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import type { ComponentAbility } from '@/shared/componentManifest';
import type { UIBlock, DataBlock } from '@/shared/types/panel';

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const items = (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];

const isEmpty = computed(() => {
  return items.length === 0;
});

function getProp(key: string, fallback: string): string {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[key] ?? fallback) as string;
}

function getOption<T>(key: string, fallback: T): T {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.options?.[camel] ?? props.block.options?.[key] ?? fallback) as T;
}

const urlField = getProp('url_field', 'url');
const titleField = getProp('title_field', 'title');
const descriptionField = getProp('description_field', 'description');

const columns = getOption('columns', 3); // 默认 3 列

const gridClass = computed(() => {
  const colsMap: Record<number, string> = {
    2: 'grid grid-cols-1 gap-4 sm:grid-cols-2',
    3: 'grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3',
    4: 'grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4',
    5: 'grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5',
  };
  return colsMap[columns] || colsMap[3];
});

interface GalleryImage {
  url: string;
  title?: string;
  description?: string;
}

const images = computed<GalleryImage[]>(() => {
  return items.map((item) => ({
    url: String((item as any)[urlField] || item.url || ''),
    title: (item as any)[titleField] || item.title,
    description: (item as any)[descriptionField] || item.description,
  }));
});

// Lightbox state
const lightboxOpen = ref(false);
const currentImageIndex = ref(0);

const currentImage = computed(() => {
  return images.value[currentImageIndex.value] || null;
});

function openLightbox(index: number) {
  currentImageIndex.value = index;
  lightboxOpen.value = true;
}

function navigateLightbox(direction: number) {
  const newIndex = currentImageIndex.value + direction;
  if (newIndex >= 0 && newIndex < images.value.length) {
    currentImageIndex.value = newIndex;
  }
}

function handleImageError(event: Event, image: GalleryImage) {
  const target = event.target as HTMLImageElement;
  // 使用占位图
  target.src = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400'%3E%3Crect fill='%23ddd' width='400' height='400'/%3E%3Ctext fill='%23999' x='50%25' y='50%25' text-anchor='middle' dy='.3em'%3E图片加载失败%3C/text%3E%3C/svg%3E`;
}
</script>
