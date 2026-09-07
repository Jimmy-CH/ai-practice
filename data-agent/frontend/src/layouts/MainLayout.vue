<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuth } from '../composables/useAuth'

const { user, isAdmin, logout, fetchUser } = useAuth()

onMounted(() => {
  if (!user.value) fetchUser()
})
</script>

<template>
  <el-container style="height: 100vh">
    <el-header style="display: flex; align-items: center; justify-content: space-between;
      background: #1f2937; color: white; padding: 0 20px;">
      <h3 style="margin: 0; font-size: 18px;">📊 数据分析 Agent</h3>
      <div style="display: flex; align-items: center; gap: 12px;">
        <el-tag v-if="user" size="small">{{ user.role_name }}</el-tag>
        <span v-if="user">{{ user.username }}</span>
        <el-button size="small" @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-container>
      <el-aside width="180px" style="background: #fff; border-right: 1px solid #e5e7eb;">
        <el-menu :default-active="$route.path" :router="true" style="border-right: none;">
          <el-menu-item index="/">
            <span>💬 Agent 对话</span>
          </el-menu-item>
          <el-menu-item index="/users" v-if="isAdmin">
            <span>👥 用户管理</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main style="background: #f5f5f5; padding: 20px;">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
