/**
 * Vue Router 配置
 *
 * 路由说明：
 * - / (MainView): 主界面，包含聊天和数据面板
 * - /research/:taskId (ResearchView): 专属研究视图，包含上下文面板和数据面板
 * - /workspace (WorkspaceView): 工作流工作台，三栏布局
 * - /workspace/templates (TemplateMarket): 模板市场页面
 * - /subscriptions (SubscriptionsView): 订阅管理页面
 * - /dev/components (DevComponentsView): 组件调试页面（仅开发模式）
 */

import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';

// 判断是否为开发模式
const isDev = import.meta.env.DEV;

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'Main',
    component: () => import('../views/MainView.vue'),
    meta: {
      title: 'Desktop Intelligence Studio',
    },
  },
  {
    path: '/research/:taskId',
    name: 'Research',
    component: () => import('../views/ResearchView.vue'),
    meta: {
      title: '研究视图',
    },
    props: true, // 将 taskId 作为 prop 传递给组件
  },
  {
    path: '/subscriptions',
    name: 'Subscriptions',
    component: () => import('../views/SubscriptionsView.vue'),
    meta: {
      title: '我的订阅',
    },
  },
  // 工作流工作台
  {
    path: '/workspace',
    name: 'Workspace',
    component: () => import('../views/WorkspaceView.vue'),
    meta: {
      title: '工作台',
    },
  },
  {
    path: '/workspace/templates',
    name: 'TemplateMarket',
    component: () => import('../features/workspace/components/template/TemplateMarket.vue'),
    meta: {
      title: '模板市场',
    },
  },
  {
    path: '/workspace/:workflowId',
    name: 'WorkspaceWorkflow',
    component: () => import('../views/WorkspaceView.vue'),
    meta: {
      title: '工作台',
    },
  },
  {
    path: '/workspace/:workflowId/run/:runId',
    name: 'WorkspaceRun',
    component: () => import('../views/WorkspaceView.vue'),
    meta: {
      title: '工作台',
    },
  },
  // 开发者组件调试页面（仅开发模式可用）
  ...(isDev
    ? [
        {
          path: '/dev/components',
          name: 'DevComponents',
          component: () => import('../views/DevComponentsView.vue'),
          meta: {
            title: '组件调试面板',
            requiresDev: true,
          },
        },
      ]
    : []),
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

// 路由守卫：设置页面标题
router.beforeEach((to, from, next) => {
  document.title = (to.meta.title as string) || '智能RSS聚合';
  next();
});

export default router;
