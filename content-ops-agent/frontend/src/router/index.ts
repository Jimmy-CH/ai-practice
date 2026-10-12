import { createRouter, createWebHistory } from 'vue-router'
import ProjectListView from '../views/ProjectListView.vue'
import SourceCenterView from '../views/SourceCenterView.vue'
import WorkspaceView from '../views/WorkspaceView.vue'

export default createRouter({ history: createWebHistory(), routes: [{ path: '/', component: ProjectListView }, { path: '/projects/:id/sources', component: SourceCenterView }, { path: '/projects/:id/workspace', component: WorkspaceView }] })
