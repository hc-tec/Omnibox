<template>
  <Card class="h-full">
    <CardContent class="flex h-full items-center gap-4 p-6">
      <div v-if="isEmpty" class="w-full text-center text-sm text-muted-foreground">
        暂无数据
      </div>
      <template v-else>
        <!-- 头像 -->
        <div class="flex-shrink-0">
          <div
            v-if="avatar"
            class="overflow-hidden rounded-full bg-muted"
            :style="{ width: avatarSize, height: avatarSize }"
          >
            <img
              :src="avatar"
              :alt="name"
              class="h-full w-full object-cover"
              @error="handleImageError"
            />
          </div>
          <div
            v-else
            class="flex items-center justify-center rounded-full bg-primary/10 text-primary font-semibold"
            :style="{ width: avatarSize, height: avatarSize, fontSize: avatarFontSize }"
          >
            {{ nameInitial }}
          </div>
        </div>

        <!-- 信息区 -->
        <div class="flex-1 min-w-0">
          <!-- 名称 + 认证 -->
          <div class="flex items-center gap-2">
            <h3 class="truncate font-semibold" :style="{ fontSize: nameSize }">
              {{ name }}
            </h3>
            <svg
              v-if="verified"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              class="h-4 w-4 flex-shrink-0 text-blue-500"
            >
              <path
                fill-rule="evenodd"
                d="M8.603 3.799A4.49 4.49 0 0112 2.25c1.357 0 2.573.6 3.397 1.549a4.49 4.49 0 013.498 1.307 4.491 4.491 0 011.307 3.497A4.49 4.49 0 0121.75 12a4.49 4.49 0 01-1.549 3.397 4.491 4.491 0 01-1.307 3.497 4.491 4.491 0 01-3.497 1.307A4.49 4.49 0 0112 21.75a4.49 4.49 0 01-3.397-1.549 4.49 4.49 0 01-3.498-1.306 4.491 4.491 0 01-1.307-3.498A4.49 4.49 0 012.25 12c0-1.357.6-2.573 1.549-3.397a4.49 4.49 0 011.307-3.497 4.49 4.49 0 013.497-1.307zm7.007 6.387a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z"
                clip-rule="evenodd"
              />
            </svg>
          </div>

          <!-- 简介 -->
          <p
            v-if="bio"
            class="mt-1 text-muted-foreground line-clamp-2"
            :style="{ fontSize: bioSize }"
          >
            {{ bio }}
          </p>

          <!-- 统计数据 -->
          <div v-if="hasStats" class="mt-2 flex flex-wrap gap-4">
            <div v-if="followers != null" class="flex items-center gap-1">
              <span class="text-muted-foreground" :style="{ fontSize: statLabelSize }">粉丝</span>
              <span class="font-semibold" :style="{ fontSize: statValueSize }">{{ formatNumber(followers) }}</span>
            </div>
            <div v-if="following != null" class="flex items-center gap-1">
              <span class="text-muted-foreground" :style="{ fontSize: statLabelSize }">关注</span>
              <span class="font-semibold" :style="{ fontSize: statValueSize }">{{ formatNumber(following) }}</span>
            </div>
            <div v-if="posts != null" class="flex items-center gap-1">
              <span class="text-muted-foreground" :style="{ fontSize: statLabelSize }">作品</span>
              <span class="font-semibold" :style="{ fontSize: statValueSize }">{{ formatNumber(posts) }}</span>
            </div>
          </div>
        </div>

        <!-- 链接按钮 -->
        <div v-if="link" class="flex-shrink-0">
          <a
            :href="link"
            target="_blank"
            rel="noopener noreferrer"
            class="flex h-8 w-8 items-center justify-center rounded-full bg-muted hover:bg-muted/80 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
              <path
                fill-rule="evenodd"
                d="M4.25 5.5a.75.75 0 00-.75.75v8.5c0 .414.336.75.75.75h8.5a.75.75 0 00.75-.75v-4a.75.75 0 011.5 0v4A2.25 2.25 0 0112.75 17h-8.5A2.25 2.25 0 012 14.75v-8.5A2.25 2.25 0 014.25 4h5a.75.75 0 010 1.5h-5z"
                clip-rule="evenodd"
              />
              <path
                fill-rule="evenodd"
                d="M6.194 12.753a.75.75 0 001.06.053L16.5 4.44v2.81a.75.75 0 001.5 0v-4.5a.75.75 0 00-.75-.75h-4.5a.75.75 0 000 1.5h2.553l-9.056 8.194a.75.75 0 00-.053 1.06z"
                clip-rule="evenodd"
              />
            </svg>
          </a>
        </div>
      </template>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { Card, CardContent } from '@/components/ui/card';
import type { UIBlock, DataBlock } from '@/shared/types/panel';
import type { ComponentAbility } from '@/shared/componentManifest';
import { usePanelSizePreset } from '@/composables/usePanelSizePreset';

const props = defineProps<{
  block: UIBlock;
  ability: ComponentAbility | null;
  data: Record<string, unknown> | null;
  dataBlock: DataBlock | null;
}>();

const sizePreset = usePanelSizePreset();
const imageError = ref(false);

// 数据源
const record = computed(() => {
  const items = (props.data?.items as Record<string, unknown>[]) ?? props.dataBlock?.records ?? [];
  return items[0] ?? null;
});

const isEmpty = computed(() => !record.value);

// 字段映射
function getProp(key: string, fallback: string): string {
  const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return (props.block.props[camel] ?? props.block.props[key] ?? fallback) as string;
}

const nameField = getProp('name_field', 'name');
const avatarField = getProp('avatar_field', 'avatar');
const bioField = getProp('bio_field', 'bio');
const verifiedField = getProp('verified_field', 'verified');
const followersField = getProp('followers_field', 'followers');
const followingField = getProp('following_field', 'following');
const postsField = getProp('posts_field', 'posts');
const linkField = getProp('link_field', 'link');

// 提取值
const name = computed(() => record.value ? String(record.value[nameField] ?? '') : '');
const avatar = computed(() => {
  if (imageError.value) return '';
  return record.value ? String(record.value[avatarField] ?? '') : '';
});
const bio = computed(() => record.value ? String(record.value[bioField] ?? '') : '');
const verified = computed(() => record.value ? Boolean(record.value[verifiedField]) : false);
const link = computed(() => record.value ? String(record.value[linkField] ?? '') : '');

const followers = computed(() => {
  if (!record.value || !(followersField in record.value)) return null;
  const val = record.value[followersField];
  return typeof val === 'number' ? val : Number(val) || 0;
});

const following = computed(() => {
  if (!record.value || !(followingField in record.value)) return null;
  const val = record.value[followingField];
  return typeof val === 'number' ? val : Number(val) || 0;
});

const posts = computed(() => {
  if (!record.value || !(postsField in record.value)) return null;
  const val = record.value[postsField];
  return typeof val === 'number' ? val : Number(val) || 0;
});

const hasStats = computed(() => followers.value != null || following.value != null || posts.value != null);

// 名称首字母
const nameInitial = computed(() => {
  const n = name.value;
  if (!n) return '?';
  return n.charAt(0).toUpperCase();
});

// 格式化数字
function formatNumber(val: number): string {
  if (val >= 10000) return `${(val / 10000).toFixed(1)}万`;
  return val.toLocaleString();
}

// 图片加载错误处理
function handleImageError() {
  imageError.value = true;
}

// 响应式尺寸
const avatarSize = computed(() => `${Math.round(sizePreset.value.headingSize * 3.5)}px`);
const avatarFontSize = computed(() => `${Math.round(sizePreset.value.headingSize * 1.5)}px`);
const nameSize = computed(() => `${sizePreset.value.headingSize}px`);
const bioSize = computed(() => `${sizePreset.value.metaSize}px`);
const statLabelSize = computed(() => `${sizePreset.value.metaSize * 0.9}px`);
const statValueSize = computed(() => `${sizePreset.value.metaSize}px`);
</script>
