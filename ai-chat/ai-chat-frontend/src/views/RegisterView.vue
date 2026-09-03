<!-- src/views/RegisterView.vue -->
<template>
  <div class="register-container">
    <h2>AI 聊天系统注册</h2>
    <form @submit.prevent="handleRegister">
      <input v-model="username" placeholder="用户名" required />
      <input v-model="password" type="password" placeholder="密码" required />
      <input v-model="confirmPassword" type="password" placeholder="确认密码" required />
      
      <button type="submit" :disabled="loading">{{ loading ? '注册中...' : '注册' }}</button>
      
      <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
      <p v-if="successMsg" class="success">{{ successMsg }}</p>
      
      <p class="link">
        已有账号？<a href="/login">立即登录</a>
      </p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { registerApi } from '@/api/auth';

const router = useRouter();
const username = ref('');
const password = ref('');
const confirmPassword = ref('');
const loading = ref(false);
const errorMsg = ref('');
const successMsg = ref('');

const handleRegister = async () => {
  loading.value = true;
  errorMsg.value = '';
  successMsg.value = '';

  // 前端基础校验：两次密码是否一致
  if (password.value !== confirmPassword.value) {
    errorMsg.value = '两次输入的密码不一致';
    loading.value = false;
    return;
  }

  try {
    await registerApi({ username: username.value, password: password.value });
    successMsg.value = '注册成功！即将跳转到登录页...';
    // 注册成功后，2秒后自动跳转到登录页
    setTimeout(() => router.push('/login'), 2000);
  } catch (err: any) {
    errorMsg.value = err.response?.data?.detail || '注册失败，请检查用户名是否已存在';
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.register-container { max-width: 300px; margin: 100px auto; display: flex; flex-direction: column; gap: 15px; }
input { padding: 10px; border: 1px solid #ddd; border-radius: 6px; }
button { padding: 10px; background: #28a745; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
button:disabled { background: #ccc; cursor: not-allowed; }
.error { color: red; font-size: 14px; }
.success { color: green; font-size: 14px; }
.link { font-size: 14px; text-align: center; margin-top: 10px; }
.link a { color: #007bff; text-decoration: none; }
</style>