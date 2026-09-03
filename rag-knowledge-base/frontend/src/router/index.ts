import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: () => import('@/layouts/ChatLayout.vue'),
      children: [
        {
          path: '',
          name: 'chat-main',
          component: () => import('@/views/ChatView.vue'),
        },
      ],
    },
  ],
})

export default router
