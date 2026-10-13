<template>
  <el-container direction="vertical" style="height: 100vh">
    <el-header v-if="auth.isLoggedIn" style="display: flex; align-items: center; gap: 16px; background: #fff; border-bottom: 1px solid #e4e7ed;">
      <router-link to="/">生成助手</router-link>
      <router-link v-if="auth.isEditor" to="/materials">我的资产</router-link>
      <router-link v-if="auth.isReviewer" to="/review">审核</router-link>
      <router-link to="/approved">已审核</router-link>
      <div style="flex: 1"></div>
      <span>{{ auth.role }}</span>
      <el-button size="small" @click="logout">退出</el-button>
    </el-header>
    <router-view />
  </el-container>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
a {
  color: #606266;
  text-decoration: none;
}
a.router-link-active {
  color: #7b2cbf;
  font-weight: 600;
}
</style>
