<template>
  <!-- FAB 按钮（魔棒） -->
  <div class="fixed bottom-6 right-6 z-50">
    <Button
      size="icon"
      class="h-14 w-14 rounded-full shadow-lg relative hover:scale-110 transition-transform"
      @click="toggleInbox"
    >
      <Wand2 class="h-6 w-6" />
      <Badge
        v-if="pendingCount > 0"
        class="absolute -top-1 -right-1 h-6 w-6 rounded-full p-0 flex items-center justify-center animate-pulse"
        variant="destructive"
      >
        {{ pendingCount }}
      </Badge>
    </Button>
  </div>

  <!-- 侧边栏 -->
  <Transition name="slide">
    <div
      v-if="isOpen"
      class="fixed top-0 right-0 h-screen w-96 bg-background border-l shadow-2xl z-40 flex flex-col"
    >
      <!-- Header -->
      <div class="p-4 border-b flex items-center justify-between bg-muted/50">
        <h2 class="text-lg font-semibold flex items-center gap-2">
          <Inbox class="h-5 w-5" />
          行动收件箱
          <Badge v-if="pendingCount > 0" variant="secondary">
            {{ pendingCount }}
          </Badge>
        </h2>
        <Button variant="ghost" size="icon" @click="closeInbox">
          <X class="h-4 w-4" />
        </Button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto p-4 space-y-4">
        <div v-if="pendingTasks.length === 0" class="text-center py-12 text-muted-foreground">
          <CheckCircle class="h-16 w-16 mx-auto mb-4 opacity-50" />
          <p class="text-lg font-medium">太棒了！</p>
          <p class="text-sm">没有待处理的任务</p>
        </div>

        <Card v-for="task in pendingTasks" :key="task.task_id" class="border-2 border-yellow-500">
          <CardHeader>
            <CardTitle class="text-sm flex items-center gap-2">
              <Brain class="h-4 w-4 text-yellow-500" />
              {{ task.query }}
            </CardTitle>
          </CardHeader>
          <CardContent class="space-y-3">
            <Alert>
              <Brain class="h-4 w-4" />
              <AlertTitle>助手提问</AlertTitle>
              <AlertDescription class="whitespace-pre-wrap">
                {{ task.human_request?.message }}
              </AlertDescription>
            </Alert>

            <Textarea
              v-model="responses[task.task_id]"
              placeholder="在此输入您的回复..."
              class="min-h-20"
              @keydown.ctrl.enter="submitResponse(task.task_id)"
            />
            <p class="text-xs text-muted-foreground">提示：Ctrl + Enter 快速发送</p>
          </CardContent>
          <CardFooter class="justify-end gap-2">
            <Button variant="outline" size="sm" :disabled="!!submitting[task.task_id]" @click="cancelTask(task.task_id)">
              取消任务
            </Button>
            <Button
              size="sm"
              :disabled="!!submitting[task.task_id] || !responses[task.task_id]?.trim()"
              @click="submitResponse(task.task_id)"
            >
              <Send class="h-4 w-4 mr-1" />
              回复
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  </Transition>

  <!-- 遮罩层 -->
  <Transition name="fade">
    <div
      v-if="isOpen"
      class="fixed inset-0 bg-black/20 backdrop-blur-sm z-30"
      @click="closeInbox"
    />
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Textarea } from '@/components/ui/textarea';
import { Wand2, Inbox, X, Brain, CheckCircle, Send } from 'lucide-vue-next';
import { useResearchStore } from '../stores/researchStore';
import { researchApi } from '../services/researchApi';

const researchStore = useResearchStore();

const isOpen = ref(false);
const responses = ref<Record<string, string>>({});
const submitting = ref<Record<string, boolean>>({});

const pendingTasks = computed(() => researchStore.pendingHumanTasks);
const pendingCount = computed(() => researchStore.pendingCount);

function toggleInbox() {
  isOpen.value = !isOpen.value;
}

function closeInbox() {
  isOpen.value = false;
}

async function submitResponse(taskId: string) {
  const response = responses.value[taskId];
  if (!response?.trim()) return;
  if (submitting.value[taskId]) return;

  try {
    submitting.value[taskId] = true;
    await researchApi.submitHumanResponse(taskId, response);
    delete responses.value[taskId];

    if (pendingCount.value === 0) {
      closeInbox();
    }
  } catch (error) {
    console.error('提交响应失败:', error);
    alert('提交失败，请重试');
  } finally {
    delete submitting.value[taskId];
  }
}

async function cancelTask(taskId: string) {
  try {
    submitting.value[taskId] = true;
    await researchApi.cancelTask(taskId, '用户手动取消');
  } catch (error) {
    console.error('取消任务失败:', error);
    alert('取消失败，请重试');
  } finally {
    delete submitting.value[taskId];
  }
}
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-enter-from {
  transform: translateX(100%);
}

.slide-leave-to {
  transform: translateX(100%);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
