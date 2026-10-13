import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import ProjectListView from '../views/ProjectListView.vue'
import SourceCenterView from '../views/SourceCenterView.vue'
import WorkspaceView from '../views/WorkspaceView.vue'
import ReviewView from '../views/ReviewView.vue'
import DeliveryView from '../views/DeliveryView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView },
    { path: '/', redirect: '/projects' },
    { path: '/projects', component: ProjectListView, meta: { role: 'editor' } },
    { path: '/projects/:id/sources', component: SourceCenterView, meta: { role: 'editor' } },
    { path: '/projects/:id/workspace', component: WorkspaceView, meta: { role: 'editor' } },
    { path: '/review', component: ReviewView, meta: { role: 'reviewer' } },
    { path: '/delivery', component: DeliveryView },
  ],
})

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  if (!auth.token && to.path !== '/login') return next('/login')
  if (to.meta.role && auth.role !== to.meta.role) return next('/login')
  next()
})

export default router
