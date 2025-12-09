/**
 * 工作台特性模块导出
 */

// 主要组件
export { default as WorkspaceLayout } from './WorkspaceLayout.vue'

// 子组件
export { default as WorkflowPanel } from './components/workflow/WorkflowPanel.vue'
export { default as WorkflowListItem } from './components/workflow/WorkflowListItem.vue'
export { default as WorkflowStepTree } from './components/workflow/WorkflowStepTree.vue'

export { default as MainCanvas } from './components/canvas/MainCanvas.vue'
export { default as CanvasEmptyState } from './components/canvas/CanvasEmptyState.vue'
export { default as ChatInteractionArea } from './components/canvas/ChatInteractionArea.vue'

export { default as ArtifactPanel } from './components/artifact/ArtifactPanel.vue'
export { default as ArtifactListItem } from './components/artifact/ArtifactListItem.vue'
export { default as ArtifactPreview } from './components/artifact/ArtifactPreview.vue'

// 模板组件
export * from './components/template'

// Store
export { useWorkspaceStore } from './stores/workspaceStore'
export { useTemplateStore } from './stores/templateStore'

// API
export * as workspaceApi from './services/workspaceApi'
export * as templateApi from './services/templateApi'

// 类型
export type * from './types/workspace'
export type * from './types/template'
