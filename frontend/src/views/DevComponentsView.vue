<script setup lang="ts">
/**
 * 组件调试页面
 *
 * 仅开发模式可访问，用于测试和验证各种面板组件的渲染效果
 */
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import {
  ArrowLeft,
  RefreshCw,
  Terminal,
  Package,
  LayoutGrid,
  Eye,
  X,
  Search,
  Layers,
  Maximize2,
  Minimize2,
  Square,
} from 'lucide-vue-next';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import DynamicBlockRenderer from '@/features/panel/components/blocks/DynamicBlockRenderer.vue';
import DevLogPanel from '@/features/dev/components/DevLogPanel.vue';
import {
  allTestCases,
  devLogger,
  type ComponentTestCase,
} from '@/features/dev/mockDataGenerator';
import type { UIBlock, DataBlock } from '@/shared/types/panel';
import { useDevModeStore } from '@/store/devModeStore';
import { usePanelStore } from '@/store/panelStore';
import {
  PANEL_SIZE_PRESETS,
  type PanelSizePreset,
} from '@/shared/panelSizePresets';

const router = useRouter();
const devModeStore = useDevModeStore();
const panelStore = usePanelStore();

// 布局密度模式 - 与 panelStore 同步以确保组件内部正确读取
const sizePresetOptions: { value: PanelSizePreset; label: string; icon: typeof Minimize2 }[] = [
  { value: 'compact', label: '紧凑', icon: Minimize2 },
  { value: 'balanced', label: '均衡', icon: Square },
  { value: 'spacious', label: '宽松', icon: Maximize2 },
];

// 使用 panelStore 的 sizePreset，确保组件内部的 usePanelSizePreset 能正确获取
const currentSizePreset = computed({
  get: () => panelStore.state.sizePreset,
  set: (val) => panelStore.setSizePreset(val),
});

// 当前预设配置
const sizePreset = computed(() => PANEL_SIZE_PRESETS[currentSizePreset.value]);

// CSS 变量样式
const panelCssVars = computed(() => ({
  '--panel-grid-gap': `${sizePreset.value.gridGap}px`,
  '--panel-card-padding': `${sizePreset.value.cardPadding}px`,
  '--panel-card-radius': `${sizePreset.value.cardRadius}px`,
  '--panel-font-scale': sizePreset.value.fontScale,
  '--panel-heading-size': `${sizePreset.value.headingSize}px`,
  '--panel-meta-size': `${sizePreset.value.metaSize}px`,
  '--panel-spacing-scale': sizePreset.value.spacingScale,
  '--panel-list-row-height': `${sizePreset.value.listRowHeight}px`,
}));

// 状态
const testCases = ref<ComponentTestCase[]>(allTestCases);
const selectedCase = ref<ComponentTestCase | null>(null);
const searchQuery = ref('');
const selectedComponents = ref<string[]>([]);
const showLogPanel = ref(true);
const showInspector = ref(false);

interface LoadedCase {
  testCase: ComponentTestCase;
  block: UIBlock;
  dataBlock: DataBlock;
  renderTime?: number;
}

const loadedCases = ref<LoadedCase[]>([]);
const inspectedData = ref<LoadedCase | null>(null);

// 计算属性
const componentTypes = computed(() => {
  const types = new Set(testCases.value.map((tc) => tc.component));
  return Array.from(types).sort();
});

const filteredTestCases = computed(() => {
  let result = testCases.value;

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(
      (tc) =>
        tc.name.toLowerCase().includes(query) ||
        tc.component.toLowerCase().includes(query) ||
        tc.description.toLowerCase().includes(query)
    );
  }

  if (selectedComponents.value.length > 0) {
    result = result.filter((tc) => selectedComponents.value.includes(tc.component));
  }

  return result;
});

// 方法
function toggleComponentFilter(component: string) {
  const index = selectedComponents.value.indexOf(component);
  if (index === -1) {
    selectedComponents.value.push(component);
  } else {
    selectedComponents.value.splice(index, 1);
  }
}

function selectTestCase(testCase: ComponentTestCase) {
  selectedCase.value = testCase;
  loadCase(testCase);
}

function loadCase(testCase: ComponentTestCase) {
  const existing = loadedCases.value.find((lc) => lc.testCase.name === testCase.name);
  if (existing) {
    devLogger.info('DevComponents', `组件已加载: ${testCase.name}`);
    return;
  }

  devLogger.info('DevComponents', `加载测试用例: ${testCase.name}`, {
    component: testCase.component,
  });

  const startTime = performance.now();

  try {
    const { block, dataBlock } = testCase.generator();
    const renderTime = Math.round(performance.now() - startTime);

    loadedCases.value.push({
      testCase,
      block,
      dataBlock,
      renderTime,
    });

    devLogger.info('DevComponents', `组件加载完成: ${testCase.name}`, {
      renderTime,
      dataCount: dataBlock.records.length,
    });
  } catch (error) {
    devLogger.error('DevComponents', `组件加载失败: ${testCase.name}`, error);
  }
}

function loadAllCases() {
  devLogger.info('DevComponents', '开始加载全部组件');
  loadedCases.value = [];

  filteredTestCases.value.forEach((testCase) => {
    loadCase(testCase);
  });

  devLogger.info('DevComponents', `全部组件加载完成，共 ${loadedCases.value.length} 个`);
}

function refreshCase(testCase: ComponentTestCase) {
  devLogger.info('DevComponents', `刷新组件: ${testCase.name}`);

  const index = loadedCases.value.findIndex((lc) => lc.testCase.name === testCase.name);
  if (index !== -1) {
    const startTime = performance.now();
    const { block, dataBlock } = testCase.generator();
    const renderTime = Math.round(performance.now() - startTime);

    loadedCases.value[index] = {
      testCase,
      block,
      dataBlock,
      renderTime,
    };

    devLogger.info('DevComponents', `组件刷新完成: ${testCase.name}`, { renderTime });
  }
}

function refreshAll() {
  devLogger.info('DevComponents', '刷新全部组件');
  loadedCases.value.forEach((caseData) => {
    refreshCase(caseData.testCase);
  });
}

function removeCase(name: string) {
  devLogger.info('DevComponents', `移除组件: ${name}`);
  loadedCases.value = loadedCases.value.filter((lc) => lc.testCase.name !== name);
}

function inspectCase(caseData: LoadedCase) {
  inspectedData.value = caseData;
  showInspector.value = true;
  devLogger.debug('DevComponents', `检查组件数据: ${caseData.testCase.name}`);
}

function handleInspect(payload: { block: UIBlock; dataBlock: DataBlock | null }) {
  devLogger.debug('DevComponents', '组件点击检查', payload);
}

function formatJson(data: unknown): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

function goBack() {
  router.push({ path: '/' });
}

// 生命周期
onMounted(() => {
  devModeStore.setEnabled(true);
  devLogger.info('DevComponents', '组件调试面板已加载');
});
</script>

<template>
  <div class="app-shell relative min-h-screen overflow-hidden bg-background text-foreground">
    <!-- 渐变背景装饰 -->
    <div class="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-background/40 to-background" />
    <div class="pointer-events-none absolute -top-40 right-1/4 h-[520px] w-[520px] rounded-full bg-purple-500/20 blur-[180px]" />
    <div class="pointer-events-none absolute -bottom-52 left-1/5 h-[620px] w-[620px] rounded-full bg-indigo-400/20 blur-[200px]" />

    <div class="relative z-10 flex min-h-screen flex-col gap-4 px-6 py-6">
      <!-- 顶部导航栏 -->
      <header class="app-chrome flex items-center justify-between rounded-[24px] border border-border/30 bg-[var(--shell-surface)]/75 px-5 py-3 backdrop-blur">
        <div class="flex items-center gap-3">
          <button
            type="button"
            class="inline-flex h-9 items-center gap-2 rounded-xl border border-border/40 bg-background/50 px-3 text-sm font-medium transition hover:bg-background"
            @click="goBack"
          >
            <ArrowLeft class="h-4 w-4" />
            返回主页
          </button>

          <div class="h-6 w-px bg-border/40" />

          <div>
            <p class="text-[10px] uppercase tracking-[0.5em] text-muted-foreground">Developer</p>
            <p class="text-lg font-semibold leading-tight">组件调试面板</p>
          </div>

          <Badge variant="outline" class="ml-2 border-purple-500/40 bg-purple-500/10 text-purple-600">
            DEV MODE
          </Badge>
        </div>

        <div class="flex items-center gap-3">
          <!-- 布局密度切换 -->
          <div class="flex items-center gap-1 rounded-xl border border-border/40 bg-background/50 p-1 backdrop-blur">
            <Button
              v-for="option in sizePresetOptions"
              :key="option.value"
              variant="ghost"
              size="sm"
              :class="[
                'h-7 rounded-lg px-2.5 text-xs transition-all',
                currentSizePreset === option.value
                  ? 'bg-primary/15 text-primary shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              ]"
              @click="currentSizePreset = option.value"
            >
              <component :is="option.icon" class="mr-1 h-3 w-3" />
              {{ option.label }}
            </Button>
          </div>

          <div class="h-6 w-px bg-border/40" />

          <Button
            variant="outline"
            size="sm"
            class="rounded-xl border-border/40 bg-background/50 backdrop-blur hover:bg-background"
            @click="refreshAll"
          >
            <RefreshCw class="mr-1.5 h-3.5 w-3.5" />
            刷新全部
          </Button>
          <Button
            variant="outline"
            size="sm"
            :class="[
              'rounded-xl border-border/40 backdrop-blur transition-all',
              showLogPanel
                ? 'bg-primary/10 border-primary/40 text-primary'
                : 'bg-background/50 hover:bg-background'
            ]"
            @click="showLogPanel = !showLogPanel"
          >
            <Terminal class="mr-1.5 h-3.5 w-3.5" />
            {{ showLogPanel ? '隐藏日志' : '显示日志' }}
          </Button>
        </div>
      </header>

      <!-- 主内容区域 -->
      <div class="flex flex-1 gap-4 overflow-hidden">
        <!-- 左侧测试用例列表 -->
        <aside class="w-72 flex-shrink-0 rounded-[24px] border border-border/20 bg-[var(--shell-surface)]/60 backdrop-blur">
          <div class="flex flex-col h-full">
            <!-- 侧边栏头部 -->
            <div class="flex items-center justify-between border-b border-border/20 px-4 py-3">
              <div class="flex items-center gap-2">
                <Layers class="h-4 w-4 text-primary" />
                <span class="text-sm font-semibold">测试用例</span>
              </div>
              <Badge variant="secondary" class="text-[10px]">
                {{ testCases.length }} 个
              </Badge>
            </div>

            <!-- 搜索和过滤 -->
            <div class="space-y-3 border-b border-border/20 p-3">
              <div class="relative">
                <Search class="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  v-model="searchQuery"
                  placeholder="搜索组件..."
                  class="h-8 pl-9 text-xs rounded-lg border-border/40 bg-background/50"
                />
              </div>

              <div class="flex flex-wrap gap-1.5">
                <Button
                  v-for="comp in componentTypes"
                  :key="comp"
                  size="sm"
                  :variant="selectedComponents.includes(comp) ? 'default' : 'outline'"
                  class="h-6 rounded-md px-2 text-[10px]"
                  @click="toggleComponentFilter(comp)"
                >
                  {{ comp }}
                </Button>
              </div>
            </div>

            <!-- 用例列表 -->
            <div class="flex-1 overflow-y-auto px-2 py-2">
              <div class="space-y-1.5">
                <div
                  v-for="testCase in filteredTestCases"
                  :key="testCase.name"
                  class="group cursor-pointer rounded-xl border border-transparent p-2.5 transition-all hover:border-border/40 hover:bg-background/50"
                  :class="{ 'border-primary/30 bg-primary/5': selectedCase?.name === testCase.name }"
                  @click="selectTestCase(testCase)"
                >
                  <div class="flex items-center justify-between gap-2 mb-1">
                    <span class="text-xs font-medium truncate">{{ testCase.name }}</span>
                    <Badge variant="outline" class="text-[9px] px-1.5 py-0 shrink-0">
                      {{ testCase.component }}
                    </Badge>
                  </div>
                  <p class="text-[10px] text-muted-foreground line-clamp-2">
                    {{ testCase.description }}
                  </p>
                </div>
              </div>
            </div>

            <!-- 底部操作 -->
            <div class="border-t border-border/20 p-3">
              <Button
                class="w-full rounded-xl bg-gradient-to-br from-indigo-500 to-blue-500 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25"
                @click="loadAllCases"
              >
                <LayoutGrid class="mr-1.5 h-3.5 w-3.5" />
                加载全部组件
              </Button>
            </div>
          </div>
        </aside>

        <!-- 中间组件展示区 -->
        <main class="flex-1 overflow-hidden rounded-[24px] border border-border/20 bg-[var(--canvas-gradient)]/95 backdrop-blur">
          <div class="h-full overflow-y-auto">
            <div class="p-6">
              <!-- 空状态 -->
              <div
                v-if="loadedCases.length === 0"
                class="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border/40 bg-muted/5 py-20"
              >
                <div class="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                  <Package class="h-8 w-8 text-primary" />
                </div>
                <p class="mb-2 text-lg font-semibold">选择测试用例</p>
                <p class="text-sm text-muted-foreground">
                  从左侧列表选择一个或多个测试用例，或点击"加载全部组件"
                </p>
              </div>

              <!-- 组件网格 -->
              <div
                v-else
                class="grid grid-cols-1 xl:grid-cols-2"
                :style="{ ...panelCssVars, gap: `${sizePreset.gridGap}px` }"
              >
                <div
                  v-for="caseData in loadedCases"
                  :key="caseData.testCase.name"
                  class="group relative overflow-hidden border border-border/30 bg-background/50 backdrop-blur transition-all hover:border-border/50"
                  :style="{ borderRadius: `${sizePreset.cardRadius}px` }"
                >
                  <!-- 顶部状态条 -->
                  <div class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary via-blue-500 to-primary" />

                  <!-- 卡片头部 -->
                  <div class="flex items-center justify-between border-b border-border/20 px-4 py-3">
                    <div class="flex items-center gap-2 min-w-0">
                      <span class="text-sm font-semibold truncate">{{ caseData.testCase.name }}</span>
                      <Badge variant="secondary" class="text-[10px] shrink-0">
                        {{ caseData.testCase.component }}
                      </Badge>
                    </div>
                    <div class="flex items-center gap-1 shrink-0">
                      <Button
                        variant="ghost"
                        size="icon"
                        class="h-7 w-7 rounded-lg hover:bg-primary/10 hover:text-primary"
                        @click="refreshCase(caseData.testCase)"
                      >
                        <RefreshCw class="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="h-7 w-7 rounded-lg hover:bg-primary/10 hover:text-primary"
                        @click="inspectCase(caseData)"
                      >
                        <Eye class="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="h-7 w-7 rounded-lg hover:bg-destructive/10 hover:text-destructive"
                        @click="removeCase(caseData.testCase.name)"
                      >
                        <X class="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>

                  <!-- 组件渲染区域 -->
                  <div :style="{ padding: `${sizePreset.cardPadding}px` }">
                    <DynamicBlockRenderer
                      :block="caseData.block"
                      :data-blocks="{ [caseData.dataBlock.id]: caseData.dataBlock }"
                      @inspect-component="handleInspect"
                    />
                  </div>

                  <!-- 卡片底部信息 -->
                  <div class="flex items-center justify-between border-t border-border/20 bg-muted/20 px-4 py-2 text-[10px] text-muted-foreground">
                    <span>数据量: {{ caseData.dataBlock.records.length }} 条</span>
                    <span v-if="caseData.renderTime">渲染耗时: {{ caseData.renderTime }}ms</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>

        <!-- 右侧日志面板 -->
        <aside
          v-if="showLogPanel"
          class="w-96 flex-shrink-0 rounded-[24px] border border-border/20 bg-[var(--shell-surface)]/60 backdrop-blur"
        >
          <DevLogPanel />
        </aside>
      </div>

      <!-- 底部HUD -->
      <div class="flex flex-wrap items-center justify-center gap-4 text-[11px] uppercase tracking-[0.35em] text-muted-foreground/80">
        <span class="rounded-full border border-purple-500/30 bg-purple-500/10 px-4 py-1 text-purple-600">
          开发者模式
        </span>
        <span>{{ loadedCases.length }} / {{ testCases.length }} 组件已加载</span>
      </div>
    </div>

    <!-- 组件检查器对话框 -->
    <Dialog v-model:open="showInspector">
      <DialogContent class="max-w-4xl max-h-[90vh] overflow-hidden rounded-[28px] border-2 border-border/30 bg-gradient-to-b from-card/98 to-card/95 shadow-2xl shadow-black/10 backdrop-blur-xl">
        <!-- 顶部装饰渐变 -->
        <div class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 via-blue-500 to-indigo-500 rounded-t-[28px]" />

        <DialogHeader class="relative">
          <DialogTitle class="text-xl font-bold bg-gradient-to-r from-indigo-600 to-blue-600 bg-clip-text text-transparent">
            组件数据检查器
          </DialogTitle>
          <DialogDescription>
            查看组件的完整配置和数据
          </DialogDescription>
        </DialogHeader>

        <Tabs v-if="inspectedData" default-value="block" class="w-full">
          <TabsList class="grid w-full grid-cols-4 rounded-xl bg-muted/50">
            <TabsTrigger value="block" class="rounded-lg text-xs">UIBlock</TabsTrigger>
            <TabsTrigger value="data" class="rounded-lg text-xs">DataBlock</TabsTrigger>
            <TabsTrigger value="props" class="rounded-lg text-xs">Props</TabsTrigger>
            <TabsTrigger value="options" class="rounded-lg text-xs">Options</TabsTrigger>
          </TabsList>

          <div class="h-[400px] mt-4 overflow-y-auto">
            <TabsContent value="block">
              <pre class="rounded-xl border border-border/40 bg-muted/30 p-4 text-xs font-mono overflow-x-auto">{{ formatJson(inspectedData.block) }}</pre>
            </TabsContent>

            <TabsContent value="data">
              <pre class="rounded-xl border border-border/40 bg-muted/30 p-4 text-xs font-mono overflow-x-auto">{{ formatJson(inspectedData.dataBlock) }}</pre>
            </TabsContent>

            <TabsContent value="props">
              <pre class="rounded-xl border border-border/40 bg-muted/30 p-4 text-xs font-mono overflow-x-auto">{{ formatJson(inspectedData.block.props) }}</pre>
            </TabsContent>

            <TabsContent value="options">
              <pre class="rounded-xl border border-border/40 bg-muted/30 p-4 text-xs font-mono overflow-x-auto">{{ formatJson(inspectedData.block.options) }}</pre>
            </TabsContent>
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  </div>
</template>
