<!-- src/views/LoginView.vue -->
<template>
  <div class="login-container">
    <h2>AI 聊天系统登录</h2>
    <form @submit.prevent="handleLogin">
      <input v-model="username" placeholder="用户名" required />
      <input v-model="password" type="password" placeholder="密码" required />
      <button type="submit" :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
      <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
      <p class="link">还没有账号？<a href="/register">立即注册</a></p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/user';
import { loginApi } from '@/api/auth';

const router = useRouter();
const userStore = useUserStore();
const username = ref('');
const password = ref('');
const loading = ref(false);
const errorMsg = ref('');

const handleLogin = async () => {
  loading.value = true;
  errorMsg.value = '';
  try {
    const res: any = await loginApi({ username: username.value, password: password.value });
    userStore.setToken(res.access_token);
    router.push('/'); // 登录成功，跳转聊天主页
  } catch (err: any) {
    errorMsg.value = err.response?.data?.detail || '登录失败，请检查账号密码';
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-container { max-width: 300px; margin: 100px auto; display: flex; flex-direction: column; gap: 15px; }
input { padding: 10px; border: 1px solid #ddd; border-radius: 6px; }
button { padding: 10px; background: #007bff; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.error { color: red; font-size: 14px; }
.link { font-size: 14px; text-align: center; margin-top: 10px; }
.link a { color: #007bff; text-decoration: none; }
</style>
