// src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router';
import { useUserStore } from '@/stores/user';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'Login', component: () => import('@/views/LoginView.vue') },
    { path: '/register', name: 'Register', component: () => import('@/views/RegisterView.vue') },
    { path: '/', name: 'Chat', component: () => import('@/views/ChatView.vue'), meta: { requiresAuth: true } },
  ],
});

// 全局前置守卫
router.beforeEach((to, _from, next) => {
  const userStore = useUserStore();
  if (to.meta.requiresAuth && !userStore.token) {
    next({ name: 'Login' }); // 未登录且需要鉴权，跳转登录页
  } else {
    next();
  }
});

export default router;
