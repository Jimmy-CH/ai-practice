import { api } from './auth'

export interface UserOut {
  id: number
  username: string
  email: string | null
  phone: string | null
  avatar_url: string | null
  is_active: boolean
  role_name: string
  created_at: string
}

export interface RoleOut {
  id: number
  name: string
  description: string
}

export async function getUsers(): Promise<UserOut[]> {
  const { data } = await api.get<UserOut[]>('/users/')
  return data
}

export async function updateUserRole(userId: number, roleId: number): Promise<UserOut> {
  const { data } = await api.put<UserOut>(`/users/${userId}/role`, { role_id: roleId })
  return data
}

export async function updateUserActive(userId: number, isActive: boolean): Promise<UserOut> {
  const { data } = await api.put<UserOut>(`/users/${userId}/active`, { is_active: isActive })
  return data
}

export async function deleteUser(userId: number): Promise<void> {
  await api.delete(`/users/${userId}`)
}

export async function getRoles(): Promise<RoleOut[]> {
  const { data } = await api.get<RoleOut[]>('/auth/roles')
  return data
}

export async function updateProfile(email: string | null, phone: string | null): Promise<UserOut> {
  const { data } = await api.put<UserOut>('/users/me', { email, phone })
  return data
}

export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  await api.put('/users/me/password', { old_password: oldPassword, new_password: newPassword })
}

export interface ProfileStats {
  total_queries: number
  saved_queries: number
  shared_links: number
  data_sources: number
}

export async function getProfileStats(): Promise<ProfileStats> {
  const { data } = await api.get<ProfileStats>('/users/me/stats')
  return data
}
