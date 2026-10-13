import client from './client'

export interface LoginPayload {
  username: string
  password: string
}

export function login(payload: LoginPayload) {
  const params = new URLSearchParams()
  params.append('username', payload.username)
  params.append('password', payload.password)
  return client.post('/auth/login', params, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
}

export function me() {
  return client.get('/auth/me')
}
