import { createRouter, createWebHistory } from 'vue-router'
import ProjectListView from '../views/ProjectListView.vue'

export default createRouter({ history: createWebHistory(), routes: [{ path: '/', component: ProjectListView }] })
