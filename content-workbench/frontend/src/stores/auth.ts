import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const username = ref(localStorage.getItem('username') || '')
  const role = ref(localStorage.getItem('role') || '')
  const isEditor = computed(() => role.value === 'editor')
  const isReviewer = computed(() => role.value === 'reviewer')

  async function login(usernameValue: string, password: string) {
    const { data } = await api.post('/auth/login', { username: usernameValue, password })
    token.value = data.token
    username.value = data.username
    role.value = data.role
    localStorage.setItem('token', data.token)
    localStorage.setItem('username', data.username)
    localStorage.setItem('role', data.role)
  }

  function logout() {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
  }

  return { token, username, role, isEditor, isReviewer, login, logout }
})
