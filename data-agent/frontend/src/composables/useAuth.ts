import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { login as loginApi, api, type LoginRequest } from '../api/auth'

export interface UserInfo {
  id: number
  username: string
  email: string | null
  phone: string | null
  avatar_url: string | null
  is_active: boolean
  role_name: string
  created_at: string
}

const user = ref<UserInfo | null>(null)
const token = ref(localStorage.getItem('access_token') || '')

export function useAuth() {
  const router = useRouter()
  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role_name === 'admin')

  async function login(req: LoginRequest) {
    const res = await loginApi(req)
    token.value = res.access_token
    localStorage.setItem('access_token', res.access_token)
    localStorage.setItem('refresh_token', res.refresh_token)
    await fetchUser()
    router.push('/')
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    router.push('/login')
  }

  async function fetchUser() {
    try {
      const { data } = await api.get<UserInfo>('/users/me')
      user.value = data
    } catch {
      logout()
    }
  }

  return { user, token, isAuthenticated, isAdmin, login, logout, fetchUser }
}
