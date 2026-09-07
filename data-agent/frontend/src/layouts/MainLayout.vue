<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuth } from '../composables/useAuth'
import { useTheme } from '../composables/useTheme'

const { user, isAdmin, logout, fetchUser } = useAuth()
const { isDark, toggleTheme } = useTheme()

const isMobile = ref(window.innerWidth < 768)
const drawerVisible = ref(false)

function onResize() {
  isMobile.value = window.innerWidth < 768
  if (!isMobile.value) drawerVisible.value = false
}

onMounted(() => {
  if (!user.value) fetchUser()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})
</script>

<template>
  <el-container style="height: 100vh">
    <el-header :style="{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      background: 'var(--header-bg)', color: 'var(--header-text)', padding: '0 16px',
    }">
      <div style="display: flex; align-items: center; gap: 12px;">
        <el-button v-if="isMobile" circle size="small" @click="drawerVisible = true">☰</el-button>
        <h3 style="margin: 0; font-size: 18px;">📊 数据分析 Agent</h3>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <el-tag v-if="user" size="small">{{ user.role_name }}</el-tag>
        <span v-if="user && !isMobile" style="font-size: 14px;">{{ user.username }}</span>
        <el-button circle size="small" @click="toggleTheme">{{ isDark ? '☀️' : '🌙' }}</el-button>
        <el-button size="small" @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-container>
      <!-- 桌面端侧栏 -->
      <el-aside v-if="!isMobile" width="180px" :style="{
        background: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-color)',
      }">
        <el-menu :default-active="$route.path" :router="true"
          background-color="transparent"
          :text-color="'var(--text-primary)'"
          active-text-color="#409eff"
          style="border-right: none;">
          <el-menu-item index="/"><span>💬 Agent 对话</span></el-menu-item>
          <el-menu-item index="/dashboard"><span>📈 仪表盘</span></el-menu-item>
          <el-menu-item index="/users" v-if="isAdmin"><span>👥 用户管理</span></el-menu-item>
          <el-menu-item index="/profile"><span>👤 个人中心</span></el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 移动端抽屉菜单 -->
      <el-drawer v-if="isMobile" v-model="drawerVisible" direction="ltr" :size="220" :show-close="false">
        <el-menu :default-active="$route.path" :router="true"
          @select="drawerVisible = false"
          background-color="transparent"
          :text-color="'var(--text-primary)'"
          active-text-color="#409eff">
          <el-menu-item index="/"><span>💬 Agent 对话</span></el-menu-item>
          <el-menu-item index="/dashboard"><span>📈 仪表盘</span></el-menu-item>
          <el-menu-item index="/users" v-if="isAdmin"><span>👥 用户管理</span></el-menu-item>
          <el-menu-item index="/profile"><span>👤 个人中心</span></el-menu-item>
        </el-menu>
      </el-drawer>

      <el-main :style="{ background: 'var(--bg-secondary)', padding: '20px' }">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
