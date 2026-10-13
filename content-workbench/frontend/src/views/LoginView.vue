<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const form = ref({ username: '', password: '' })
const loading = ref(false)

async function submit() {
  loading.value = true
  try {
    await auth.login(form.value.username, form.value.password)
    router.push(auth.isEditor ? '/projects' : '/review')
  } catch (error) {
    ElMessage.error('登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="height:100vh;display:flex;align-items:center;justify-content:center">
    <el-card title="内容生产发布工作台" style="width:360px">
      <h2 style="text-align:center">登录</h2>
      <el-form label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" @keydown.enter="submit" />
        </el-form-item>
        <el-button type="primary" style="width:100%" :loading="loading" @click="submit">登录</el-button>
      </el-form>
      <p style="color:#999;font-size:12px;margin-top:12px">测试账号：editor/editor123（编辑）、reviewer/review123（审核）</p>
    </el-card>
  </div>
</template>
