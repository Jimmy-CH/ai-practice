import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../components/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('../layouts/MainLayout.vue'),
      children: [
        {
          path: '',
          name: 'Chat',
          component: () => import('../components/AgentChat.vue'),
        },
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('../components/Dashboard.vue'),
        },
        {
          path: 'users',
          name: 'Users',
          component: () => import('../components/UserManage.vue'),
          meta: { requireAdmin: true },
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  if (!to.meta.public && !token) {
    return { name: 'Login' }
  }
})

export default router
