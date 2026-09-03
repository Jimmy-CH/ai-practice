// src/store/user.ts
import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useUserStore = defineStore('user', () => {
  // 从 localStorage 读取 token，防止刷新丢失
  const token = ref(localStorage.getItem('token') || '');

  const setToken = (newToken: string) => {
    token.value = newToken;
    localStorage.setItem('token', newToken);
  };

  const logout = () => {
    token.value = '';
    localStorage.removeItem('token');
  };

  return { token, setToken, logout };
});
