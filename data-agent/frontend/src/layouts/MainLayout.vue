<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuth } from '../composables/useAuth'
import { useTheme } from '../composables/useTheme'

const { user, isAdmin, logout, fetchUser } = useAuth()
const { isDark, toggleTheme } = useTheme()

onMounted(() => {
  if (!user.value) fetchUser()
})
</script>

<template>
  <el-container style="height: 100vh">
    <el-header :style="{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      background: 'var(--header-bg)', color: 'var(--header-text)', padding: '0 20px',
    }">
      <h3 style="margin: 0; font-size: 18px;">📊 数据分析 Agent</h3>
      <div style="display: flex; align-items: center; gap: 12px;">
        <el-tag v-if="user" size="small">{{ user.role_name }}</el-tag>
        <span v-if="user">{{ user.username }}</span>
        <el-button circle size="small" @click="toggleTheme" :title="isDark ? '切换明亮模式' : '切换暗黑模式'">
          {{ isDark ? '☀️' : '🌙' }}
        </el-button>
        <el-button size="small" @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-container>
      <el-aside width="180px" :style="{
        background: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-color)',
      }">
        <el-menu :default-active="$route.path" :router="true"
          :style="{ borderRight: 'none' }"
          background-color="transparent"
          :text-color="'var(--text-primary)'"
          active-text-color="#409eff">
          <el-menu-item index="/">
            <span>💬 Agent 对话</span>
          </el-menu-item>
          <el-menu-item index="/users" v-if="isAdmin">
            <span>👥 用户管理</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main :style="{ background: 'var(--bg-secondary)', padding: '20px' }">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
