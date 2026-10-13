<script setup lang="ts">
import { useAuthStore } from './stores/auth'
import { useRoute, useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

function logout() {
  auth.logout()
  router.push('/login')
}

const editorMenus = [
  { path: '/projects', label: '项目列表' },
  { path: '/delivery', label: '发布任务' },
]
const reviewerMenus = [
  { path: '/review', label: '审核工作台' },
  { path: '/delivery', label: '发布与审计' },
]
const menus = auth.isEditor ? editorMenus : reviewerMenus
</script>

<template>
  <el-container v-if="auth.token" style="height: 100vh">
    <el-header style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e4e7ed">
      <strong>内容生产发布工作台</strong>
      <el-space>
        <span>{{ auth.username }}（{{ auth.role }}）</span>
        <el-button size="small" @click="logout">退出</el-button>
      </el-space>
    </el-header>
    <el-container>
      <el-aside width="180px" style="border-right:1px solid #e4e7ed">
        <el-menu :default-active="route.path" router>
          <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">{{ m.label }}</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
  <router-view v-else />
</template>
