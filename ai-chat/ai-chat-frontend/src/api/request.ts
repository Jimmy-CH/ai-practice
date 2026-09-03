// src/api/request.ts
import axios from 'axios';
import { useUserStore } from '@/stores/user';
import router from '@/router';

const request = axios.create({
  baseURL: '/api',
  timeout: 60000,
});

request.interceptors.request.use((config) => {
  const userStore = useUserStore();
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`;
  }
  return config;
});

request.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    if (error.response?.status === 401) {
      // const userStore = useUserStore();
      // userStore.logout();
      router.push('/login');
    }
    return Promise.reject(error);
  }
);

export default request;