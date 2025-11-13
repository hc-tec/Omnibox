/**
 * Vue Router 配置
 *
 * 路由说明：
 * - / (MainView): 主界面，包含聊天和数据面板
 * - /research/:taskId (ResearchView): 专属研究视图，包含上下文面板和数据面板
 * - /subscriptions (SubscriptionsView): 订阅管理页面
 */

import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';

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
