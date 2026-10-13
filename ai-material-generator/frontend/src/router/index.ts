import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'
import GeneratorView from '@/views/GeneratorView.vue'
import MaterialListView from '@/views/MaterialListView.vue'
import MaterialEditorView from '@/views/MaterialEditorView.vue'
import ReviewView from '@/views/ReviewView.vue'
import ApprovedListView from '@/views/ApprovedListView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/', component: GeneratorView, meta: { role: 'editor' } },
    { path: '/materials', component: MaterialListView },
    { path: '/materials/:id/edit', component: MaterialEditorView, meta: { role: 'editor' } },
    { path: '/review', component: ReviewView, meta: { role: 'reviewer' } },
    { path: '/approved', component: ApprovedListView },
  ],
})

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return next('/login')
  }
  if (to.meta.role === 'editor' && !auth.isEditor) {
    return next('/login')
  }
  if (to.meta.role === 'reviewer' && !auth.isReviewer) {
    return next('/login')
  }
  next()
})

export default router
