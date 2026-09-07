# 前端登录/用户管理 + Agent 体验增强 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Data Analysis Agent 增加前端登录/用户管理和 Agent 体验增强（对话历史、流式响应、数据可视化、结果导出）。

**Architecture:** 分两阶段交付。第一阶段引入 Element Plus + Vue Router，实现登录页和用户管理页，后端补充启用/禁用/删除用户 API。第二阶段新增对话持久化模型、SSE 流式端点、图表工具和前端可视化/导出。

**Tech Stack:** FastAPI, SQLAlchemy, LangChain, Vue 3, TypeScript, Element Plus, Vue Router 4, ECharts, papaparse

---

## 文件结构总览

### 第一阶段新建/修改

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `frontend/src/main.ts` | 注册 Element Plus + Router |
| 新建 | `frontend/src/router/index.ts` | Vue Router 路由配置 + 路由守卫 |
| 新建 | `frontend/src/api/auth.ts` | 认证 API 封装 |
| 新建 | `frontend/src/api/users.ts` | 用户管理 API 封装 |
| 新建 | `frontend/src/composables/useAuth.ts` | 认证状态管理 |
| 新建 | `frontend/src/layouts/MainLayout.vue` | Element Plus 侧边栏布局 |
| 新建 | `frontend/src/components/LoginView.vue` | 登录页面 |
| 新建 | `frontend/src/components/UserManage.vue` | 用户管理页面 |
| 修改 | `frontend/src/App.vue` | 改为 router-view 出口 |
| 修改 | `backend/app/users/schemas.py` | 新增 UpdateActiveRequest |
| 修改 | `backend/app/users/service.py` | 新增 update_user_active, delete_user |
| 修改 | `backend/app/users/router.py` | 新增 PUT active, DELETE 端点 |

### 第二阶段新建/修改

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `backend/app/models/conversation.py` | Conversation, Message 模型 |
| 新建 | `backend/app/schemas/conversation.py` | 对话相关 Pydantic 模型 |
| 新建 | `backend/app/services/conversation.py` | 对话管理业务逻辑 |
| 新建 | `backend/app/api/conversation.py` | 对话管理 API 路由 |
| 修改 | `backend/app/api/router.py` | 注册 conversation 路由 |
| 修改 | `backend/app/main.py` | 导入 conversation 模型 |
| 修改 | `backend/app/agent/tools.py` | 新增 generate_chart 工具 |
| 修改 | `backend/app/agent/prompt.py` | 增加图表工具说明 |
| 修改 | `backend/app/agent/langchain_agent.py` | 支持 chart_data + stream_agent |
| 修改 | `backend/app/schemas/agent.py` | 新增 ChartData 模型 |
| 修改 | `backend/app/api/agent.py` | 新增 SSE 流式端点 |
| 新建 | `frontend/src/api/conversation.ts` | 对话历史 API |
| 修改 | `frontend/src/api/agent.ts` | 新增 SSE 流式请求 |
| 修改 | `frontend/src/composables/useAgentChat.ts` | 支持历史 + 流式 |
| 新建 | `frontend/src/utils/export.ts` | CSV 导出工具 |
| 修改 | `frontend/src/components/AgentChat.vue` | 全面改造 |

---

## 第一阶段：前端登录 + 用户管理

### Task 1: 前端基础设施搭建

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/router/index.ts`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: 安装前端依赖**

Run in `frontend/`:
```bash
npm install vue-router@4 element-plus @element-plus/icons-vue
```

- [ ] **Step 2: 创建路由配置 `frontend/src/router/index.ts`**

```typescript
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../components/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('../layouts/MainLayout.vue'),
      children: [
        {
          path: '',
          name: 'Chat',
          component: () => import('../components/AgentChat.vue'),
        },
        {
          path: 'users',
          name: 'Users',
          component: () => import('../components/UserManage.vue'),
          meta: { requireAdmin: true },
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  if (!to.meta.public && !token) {
    return { name: 'Login' }
  }
})

export default router
```

- [ ] **Step 3: 修改 `frontend/src/main.ts` 注册 Element Plus + Router**

```typescript
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(ElementPlus)
app.use(router)
app.mount('#app')
```

- [ ] **Step 4: 修改 `frontend/src/App.vue` 为路由出口**

```vue
<template>
  <router-view />
</template>

<style>
body {
  margin: 0;
  background: #f5f5f5;
}
</style>
```

- [ ] **Step 5: 提交**

```bash
git add frontend/
git commit -m "feat: setup Element Plus, Vue Router, and base layout"
```

---

### Task 2: 认证 API + Composable + Axios 拦截器

**Files:**
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/composables/useAuth.ts`

- [ ] **Step 1: 创建 `frontend/src/api/auth.ts`**

```typescript
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// 请求拦截器：自动附加 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 自动刷新 token
let isRefreshing = false
let pendingRequests: Array<(token: string) => void> = []

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve) => {
          pendingRequests.push((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            resolve(api(originalRequest))
          })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const { data } = await axios.post('/api/auth/refresh', {
          refresh_token: refreshToken,
        })
        const newToken = data.access_token
        localStorage.setItem('access_token', newToken)
        localStorage.setItem('refresh_token', data.refresh_token)
        pendingRequests.forEach((cb) => cb(newToken))
        pendingRequests = []
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return api(originalRequest)
      } catch {
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(error)
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(error)
  }
)

export interface LoginRequest {
  username_or_phone: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export async function login(req: LoginRequest): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>('/auth/login', req)
  return data
}
```

- [ ] **Step 2: 创建 `frontend/src/composables/useAuth.ts`**

```typescript
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { login as loginApi, type LoginRequest } from '../api/auth'
import { api } from '../api/auth'

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
```

注意：需要在 `api/auth.ts` 中导出 `api` 实例量，将 `const api = axios.create(...)` 改为 `export const api = axios.create(...)`。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/auth.ts frontend/src/composables/useAuth.ts
git commit -m "feat: add auth API, axios interceptors, and useAuth composable"
```

---

### Task 3: 登录页面 + 布局

**Files:**
- Create: `frontend/src/components/LoginView.vue`
- Create: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: 创建 `frontend/src/components/LoginView.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuth } from '../composables/useAuth'

const { login } = useAuth()
const form = ref({ username: '', password: '' })
const loading = ref(false)

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await login({ username_or_phone: form.value.username, password: form.value.password })
    ElMessage.success('登录成功')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2 style="text-align: center; margin-bottom: 24px;">📊 数据分析 Agent</h2>
      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock"
            size="large" show-password @keyup.enter="handleLogin" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" style="width: 100%" :loading="loading"
            @click="handleLogin">
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
}
.login-card {
  width: 400px;
  padding: 20px;
}
</style>
```

- [ ] **Step 2: 创建 `frontend/src/layouts/MainLayout.vue`**

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
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
```

- [ ] **Step 3: 验证前端可运行**

Run in `frontend/`:
```bash
npm run dev
```
Expected: 访问 `http://localhost:3001` 应重定向到 `/login`，显示登录页面。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/LoginView.vue frontend/src/layouts/MainLayout.vue
git commit -m "feat: add login page and main layout with sidebar"
```

---

### Task 4: 后端用户管理 API 补充

**Files:**
- Modify: `backend/app/users/schemas.py`
- Modify: `backend/app/users/service.py`
- Modify: `backend/app/users/router.py`

- [ ] **Step 1: 在 `backend/app/users/schemas.py` 末尾添加**

```python
class UpdateActiveRequest(BaseModel):
    is_active: bool
```

- [ ] **Step 2: 在 `backend/app/users/service.py` 末尾添加两个函数**

```python
async def update_user_active(db: AsyncSession, user_id: int, is_active: bool) -> User | None:
    user = await get_user_by_id(db, user_id)
    if user is None:
        return None
    user.is_active = is_active
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: int) -> bool:
    user = await get_user_by_id(db, user_id)
    if user is None:
        return False
    await db.delete(user)
    await db.commit()
    return True
```

- [ ] **Step 3: 在 `backend/app/users/router.py` 添加两个端点**

在文件顶部添加导入：
```python
from app.users.schemas import UserOut, UpdateRoleRequest, UpdateActiveRequest
from app.users.service import get_all_users, update_user_role, update_user_active, delete_user
from sqlalchemy import select, func
```

在文件末尾添加：
```python
@router.put("/{user_id}/active", response_model=UserOut)
async def toggle_user_active(
    user_id: int,
    req: UpdateActiveRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """启用/禁用用户（仅 admin）。"""
    if user_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能禁用自己的账号")
    user = await update_user_active(db, user_id, req.is_active)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return _user_to_out(user)


@router.delete("/{user_id}")
async def remove_user(
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """删除用户（仅 admin）。"""
    if user_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能删除自己")
    # 检查是否是最后一个 admin
    target = await get_user_by_id(db, user_id)
    if target and target.role and target.role.name == "admin":
        result = await db.execute(
            select(func.count(User.id)).join(Role).where(Role.name == "admin")
        )
        admin_count = result.scalar()
        if admin_count <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能删除最后一个管理员")
    deleted = await delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return {"message": "用户已删除"}
```

注意：需要在导入中添加 `from sqlalchemy import select, func` 和 `from app.users.models import User, Role`。

- [ ] **Step 4: 重启后端验证**

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8001
```
用 Swagger UI (`http://localhost:8001/docs`) 测试新端点。

- [ ] **Step 5: 提交**

```bash
git add backend/app/users/
git commit -m "feat: add user enable/disable and delete APIs"
```

---

### Task 5: 用户管理页面

**Files:**
- Create: `frontend/src/api/users.ts`
- Create: `frontend/src/components/UserManage.vue`

- [ ] **Step 1: 创建 `frontend/src/api/users.ts`**

```typescript
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
  const { data } = await api.get('/auth/roles')
  return data
}
```

注意：后端目前没有 `/auth/roles` 端点，需要在 `backend/app/api/auth.py` 中添加一个简单的获取角色列表端点：

```python
@router.get("/roles")
async def list_roles(db: AsyncSession = Depends(get_db)):
    """获取所有角色列表。"""
    from sqlalchemy import select
    from app.users.models import Role
    result = await db.execute(select(Role))
    roles = result.scalars().all()
    return [{"id": r.id, "name": r.name, "description": r.description} for r in roles]
```

- [ ] **Step 2: 创建 `frontend/src/components/UserManage.vue`**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getUsers, updateUserRole, updateUserActive, deleteUser, type UserOut } from '../api/users'
import { api } from '../api/auth'

const users = ref<UserOut[]>([])
const roles = ref<{ id: number; name: string; description: string }[]>([])
const loading = ref(false)

onMounted(async () => {
  await loadData()
})

async function loadData() {
  loading.value = true
  try {
    const [usersData, rolesData] = await Promise.all([
      getUsers(),
      api.get('/auth/roles').then(r => r.data),
    ])
    users.value = usersData
    roles.value = rolesData
  } catch (e: any) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

async function handleRoleChange(user: UserOut, roleId: number) {
  try {
    await updateUserRole(user.id, roleId)
    ElMessage.success('角色已更新')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  }
}

async function handleToggleActive(user: UserOut) {
  try {
    await updateUserActive(user.id, !user.is_active)
    user.is_active = !user.is_active
    ElMessage.success(user.is_active ? '已启用' : '已禁用')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleDelete(user: UserOut) {
  try {
    await ElMessageBox.confirm(`确定删除用户 "${user.username}" 吗？`, '确认删除', {
      type: 'warning',
    })
    await deleteUser(user.id)
    users.value = users.value.filter(u => u.id !== user.id)
    ElMessage.success('用户已删除')
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}
</script>

<template>
  <div>
    <h2 style="margin: 0 0 16px 0;">用户管理</h2>
    <el-table :data="users" v-loading="loading" stripe border style="width: 100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="email" label="邮箱" width="160">
        <template #default="{ row }">{{ row.email || '-' }}</template>
      </el-table-column>
      <el-table-column prop="phone" label="手机号" width="130">
        <template #default="{ row }">{{ row.phone || '-' }}</template>
      </el-table-column>
      <el-table-column label="角色" width="140">
        <template #default="{ row }">
          <el-select :model-value="roles.find(r => r.name === row.role_name)?.id"
            @change="(roleId: number) => handleRoleChange(row, roleId)" size="small">
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-switch :model-value="row.is_active" @change="handleToggleActive(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button type="danger" size="small" text @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
```

- [ ] **Step 3: 验证**

启动前后端，以 admin 登录后访问 `/users`，应能看到用户列表并可操作。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/users.ts frontend/src/components/UserManage.vue backend/app/api/auth.py
git commit -m "feat: add user management page with role assignment, toggle active, delete"
```

---

## 第二阶段：Agent 体验增强

### Task 6: 后端对话历史模型 + API

**Files:**
- Create: `backend/app/models/conversation.py`
- Create: `backend/app/schemas/conversation.py`
- Create: `backend/app/services/conversation.py`
- Create: `backend/app/api/conversation.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建 `backend/app/models/conversation.py`**

```python
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), default="新对话")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # "user" / "agent"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
```

- [ ] **Step 2: 创建 `backend/app/schemas/conversation.py`**

```python
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    steps: list[dict]
    created_at: datetime

    @classmethod
    def from_orm_model(cls, msg) -> "MessageOut":
        import json
        return cls(
            id=msg.id, role=msg.role, content=msg.content,
            steps=json.loads(msg.steps) if isinstance(msg.steps, str) else msg.steps,
            created_at=msg.created_at,
        )


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationCreate(BaseModel):
    title: Optional[str] = "新对话"
```

- [ ] **Step 3: 创建 `backend/app/services/conversation.py`**

```python
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.conversation import Conversation, Message


async def get_user_conversations(db: AsyncSession, user_id: int) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_conversation(db: AsyncSession, conv_id: int, user_id: int) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_conversation(db: AsyncSession, user_id: int, title: str = "新对话") -> Conversation:
    conv = Conversation(user_id=user_id, title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def delete_conversation(db: AsyncSession, conv_id: int, user_id: int) -> bool:
    conv = await get_conversation(db, conv_id, user_id)
    if conv is None:
        return False
    await db.delete(conv)
    await db.commit()
    return True


async def save_message(
    db: AsyncSession, conv_id: int, role: str, content: str,
    steps: list[dict] | None = None, title: str | None = None,
) -> Message:
    msg = Message(
        conversation_id=conv_id, role=role, content=content,
        steps=json.dumps(steps or [], ensure_ascii=False),
    )
    db.add(msg)
    if title:
        conv = await db.get(Conversation, conv_id)
        if conv:
            conv.title = title[:20]
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_messages(db: AsyncSession, conv_id: int) -> list[Message]:
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    return list(result.scalars().all())
```

- [ ] **Step 4: 创建 `backend/app/api/conversation.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.users.models import User
from app.schemas.conversation import ConversationOut, ConversationCreate, MessageOut
from app.services import conversation as conv_service

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("/", response_model=list[ConversationOut])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    convs = await conv_service.get_user_conversations(db, current_user.id)
    return convs


@router.post("/", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conv(
    req: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conv_service.create_conversation(db, current_user.id, req.title)


@router.get("/{conv_id}", response_model=list[MessageOut])
async def get_conv_messages(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await conv_service.get_conversation(db, conv_id, current_user.id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    messages = await conv_service.get_messages(db, conv_id)
    return [MessageOut.from_orm_model(m) for m in messages]


@router.delete("/{conv_id}")
async def delete_conv(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await conv_service.delete_conversation(db, conv_id, current_user.id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    return {"message": "会话已删除"}
```

- [ ] **Step 5: 修改 `backend/app/api/router.py`**

```python
from fastapi import APIRouter
from app.api import agent, auth
from app.users import router as users_router
from app.api.conversation import router as conv_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users_router.router)
api_router.include_router(agent.router)
api_router.include_router(conv_router)
```

- [ ] **Step 6: 修改 `backend/app/main.py` 添加模型导入**

在现有 `import app.users.models` 行后添加：
```python
import app.models.conversation  # noqa: F401
```

- [ ] **Step 7: 重启后端验证数据表创建和 API 可用**

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8001
```

- [ ] **Step 8: 提交**

```bash
git add backend/app/models/conversation.py backend/app/schemas/conversation.py
git add backend/app/services/conversation.py backend/app/api/conversation.py
git add backend/app/api/router.py backend/app/main.py
git commit -m "feat: add conversation history models and API"
```

---

### Task 7: 前端对话历史集成

**Files:**
- Create: `frontend/src/api/conversation.ts`
- Modify: `frontend/src/composables/useAgentChat.ts`
- Modify: `frontend/src/components/AgentChat.vue`

- [ ] **Step 1: 创建 `frontend/src/api/conversation.ts`**

```typescript
import { api } from './auth'

export interface ConversationOut {
  id: number
  title: string
  created_at: string
  updated_at: string
}

export interface MessageOut {
  id: number
  role: string
  content: string
  steps: { type: string; content: string }[]
  created_at: string
}

export async function getConversations(): Promise<ConversationOut[]> {
  const { data } = await api.get<ConversationOut[]>('/conversations/')
  return data
}

export async function createConversation(title?: string): Promise<ConversationOut> {
  const { data } = await api.post<ConversationOut>('/conversations/', { title: title || '新对话' })
  return data
}

export async function getMessages(convId: number): Promise<MessageOut[]> {
  const { data } = await api.get<MessageOut[]>(`/conversations/${convId}`)
  return data
}

export async function deleteConversation(convId: number): Promise<void> {
  await api.delete(`/conversations/${convId}`)
}

export async function saveMessage(
  convId: number, role: string, content: string, steps?: any[]
): Promise<void> {
  // 对话保存在后端 agent query 流程中自动处理，此处预留接口
}
```

- [ ] **Step 2: 改造 `frontend/src/composables/useAgentChat.ts`**

```typescript
import { ref } from 'vue'
import { queryAgent, type AgentQueryResponse, type AgentStep } from '../api/agent'
import { api } from '../api/auth'
import {
  getConversations, getMessages, createConversation, deleteConversation,
  type ConversationOut, type MessageOut,
} from '../api/conversation'

export interface ChatMessage {
  role: 'user' | 'agent'
  content: string
  steps?: AgentStep[]
  loading?: boolean
  chart_data?: any
}

const conversations = ref<ConversationOut[]>([])
const currentConvId = ref<number | null>(null)
const messages = ref<ChatMessage[]>([])
const isLoading = ref(false)

export function useAgentChat() {
  async function loadConversations() {
    try {
      conversations.value = await getConversations()
    } catch { /* ignore */ }
  }

  async function selectConversation(convId: number) {
    currentConvId.value = convId
    try {
      const msgs = await getMessages(convId)
      messages.value = msgs.map(m => ({
        role: m.role as 'user' | 'agent',
        content: m.content,
        steps: m.steps,
        loading: false,
      }))
    } catch {
      messages.value = []
    }
  }

  async function startNewConversation() {
    const conv = await createConversation()
    conversations.value.unshift(conv)
    currentConvId.value = conv.id
    messages.value = []
  }

  async function removeConversation(convId: number) {
    await deleteConversation(convId)
    conversations.value = conversations.value.filter(c => c.id !== convId)
    if (currentConvId.value === convId) {
      currentConvId.value = null
      messages.value = []
    }
  }

  async function sendQuestion(question: string) {
    // 如果没有当前会话，自动创建
    if (!currentConvId.value) {
      const conv = await createConversation(question.slice(0, 20))
      conversations.value.unshift(conv)
      currentConvId.value = conv.id
    }

    messages.value.push({ role: 'user', content: question })
    const agentMsg: ChatMessage = { role: 'agent', content: '', loading: true }
    messages.value.push(agentMsg)
    isLoading.value = true

    try {
      const result = await queryAgent(question)
      const idx = messages.value.length - 1
      messages.value[idx] = {
        role: 'agent',
        content: result.answer,
        steps: result.steps,
        loading: false,
        chart_data: (result as any).chart_data,
      }

      // 保存消息到后端
      await api.post(`/conversations/${currentConvId.value}/messages`, {
        role: 'user', content: question,
      })
      await api.post(`/conversations/${currentConvId.value}/messages`, {
        role: 'agent', content: result.answer,
        steps: result.steps,
      })
    } catch (error: any) {
      const idx = messages.value.length - 1
      messages.value[idx] = {
        role: 'agent',
        content: `请求失败: ${error.message}`,
        steps: [],
        loading: false,
      }
    } finally {
      isLoading.value = false
    }
  }

  return {
    messages, isLoading, conversations, currentConvId,
    sendQuestion, loadConversations, selectConversation,
    startNewConversation, removeConversation,
  }
}
```

注意：需要在后端 conversation router 中添加 `POST /{conv_id}/messages` 端点来保存消息：

```python
class SaveMessageRequest(BaseModel):
    role: str
    content: str
    steps: list[dict] | None = None

@router.post("/{conv_id}/messages")
async def save_msg(
    conv_id: int,
    req: SaveMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await conv_service.get_conversation(db, conv_id, current_user.id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    msg = await conv_service.save_message(db, conv_id, req.role, req.content, req.steps)
    return {"id": msg.id}
```

- [ ] **Step 3: 改造 `frontend/src/components/AgentChat.vue` 增加会话列表侧栏**

在 `<template>` 中，将现有内容包裹在一个新的布局中：

```vue
<template>
  <div style="display: flex; height: 100%;">
    <!-- 会话列表侧栏 -->
    <div class="conv-sidebar">
      <el-button size="small" style="width: 100%; margin-bottom: 8px;"
        @click="startNewConversation">+ 新对话</el-button>
      <div v-for="conv in conversations" :key="conv.id"
        :class="['conv-item', { active: conv.id === currentConvId }]"
        @click="selectConversation(conv.id)">
        <span class="conv-title">{{ conv.title }}</span>
        <el-button type="danger" size="small" text @click.stop="removeConversation(conv.id)">×</el-button>
      </div>
    </div>
    <!-- 主聊天区域 -->
    <div class="chat-main">
      <!-- 保留原有的 messages、quick-questions、input-area 结构 -->
      <div class="messages">...</div>
      <div class="quick-questions">...</div>
      <div class="input-area">...</div>
    </div>
  </div>
</template>
```

在 `<script setup>` 中引入新的 composable 方法：
```typescript
const {
  messages, isLoading, conversations, currentConvId,
  sendQuestion, loadConversations, selectConversation,
  startNewConversation, removeConversation,
} = useAgentChat()

onMounted(() => { loadConversations() })
```

添加样式：
```css
.conv-sidebar {
  width: 220px;
  border-right: 1px solid #e5e7eb;
  padding: 12px;
  overflow-y: auto;
  background: #fafafa;
}
.conv-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
}
.conv-item:hover { background: #e5e7eb; }
.conv-item.active { background: #dbeafe; }
.conv-title { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.chat-main { flex: 1; display: flex; flex-direction: column; }
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/conversation.ts frontend/src/composables/useAgentChat.ts
git add frontend/src/components/AgentChat.vue backend/app/api/conversation.py
git commit -m "feat: integrate conversation history in frontend"
```

---

### Task 8: 后端 SSE 流式响应

**Files:**
- Modify: `backend/app/agent/langchain_agent.py`
- Modify: `backend/app/api/agent.py`
- Modify: `backend/app/schemas/agent.py`

- [ ] **Step 1: 在 `backend/app/schemas/agent.py` 中添加 ChartData**

```python
from typing import List, Optional

class ChartData(BaseModel):
    type: str
    title: str
    x_axis: List[str]
    series: List[dict]

class AgentQueryResponse(BaseModel):
    answer: str
    steps: List[AgentStepResponse]
    success: bool
    chart_data: Optional[ChartData] = None
```

- [ ] **Step 2: 在 `backend/app/agent/langchain_agent.py` 中添加 stream_agent**

```python
import json
from fastapi import Request

async def stream_agent(question: str, request: Request):
    """流式运行 Agent，yield SSE 事件。"""
    llm = _build_llm()
    tools = [sql_query]
    prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)
    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent, tools=tools, max_iterations=5,
        verbose=True, handle_parsing_errors=True,
    )

    try:
        async for event in executor.astream_events({"input": question}, version="v2"):
            # 检查客户端是否断开
            if await request.is_disconnected():
                return

            kind = event.get("event", "")
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield f"event: thought\ndata: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event["data"].get("input", {})
                yield f"event: action\ndata: {json.dumps({'content': tool_name, 'input': str(tool_input)}, ensure_ascii=False)}\n\n"
            elif kind == "on_tool_end":
                output = event["data"].get("output", "")
                yield f"event: observation\ndata: {json.dumps({'content': str(output)}, ensure_ascii=False)}\n\n"

        # 获取最终结果
        result = await executor.ainvoke({"input": question})
        yield f"event: answer\ndata: {json.dumps({'content': result.get('output', '')}, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json.dumps({'success': True})}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'content': str(e)})}\n\n"
```

- [ ] **Step 3: 在 `backend/app/api/agent.py` 中添加 SSE 端点**

```python
from fastapi.responses import StreamingResponse
from app.agent.langchain_agent import stream_agent

@router.post("/query/stream")
async def query_stream(
    request: Request,
    req: AgentQueryRequest,
    _current_user: User = Depends(require_role("admin", "editor")),
):
    """SSE 流式查询。"""
    return StreamingResponse(
        stream_agent(req.question, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

需要在导入中添加 `from fastapi import Request`。

- [ ] **Step 4: 提交**

```bash
git add backend/app/agent/langchain_agent.py backend/app/api/agent.py backend/app/schemas/agent.py
git commit -m "feat: add SSE streaming endpoint for agent queries"
```

---

### Task 9: 前端 SSE 流式渲染

**Files:**
- Modify: `frontend/src/api/agent.ts`
- Modify: `frontend/src/composables/useAgentChat.ts`
- Modify: `frontend/src/components/AgentChat.vue`

- [ ] **Step 1: 在 `frontend/src/api/agent.ts` 中添加流式请求方法**

```typescript
export async function* streamQuestion(question: string): AsyncGenerator<{
  event: string; data: any
}> {
  const token = localStorage.getItem('access_token')
  const response = await fetch('/api/agent/query/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ question }),
  })

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let currentEvent = ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        yield { event: currentEvent, data: JSON.parse(line.slice(6)) }
      }
    }
  }
}
```

- [ ] **Step 2: 在 `useAgentChat.ts` 中添加流式发送方法**

```typescript
import { streamQuestion } from '../api/agent'

async function sendQuestionStream(question: string) {
  if (!currentConvId.value) {
    const conv = await createConversation(question.slice(0, 20))
    conversations.value.unshift(conv)
    currentConvId.value = conv.id
  }

  messages.value.push({ role: 'user', content: question })
  const agentMsg: ChatMessage = { role: 'agent', content: '', steps: [], loading: true }
  messages.value.push(agentMsg)
  isLoading.value = true

  let finalAnswer = ''
  try {
    for await (const { event, data } of streamQuestion(question)) {
      const idx = messages.value.length - 1
      if (event === 'thought' || event === 'action' || event === 'observation') {
        messages.value[idx].steps!.push({ type: event, content: data.content })
      } else if (event === 'answer') {
        finalAnswer = data.content
        messages.value[idx].content = finalAnswer
      } else if (event === 'done') {
        messages.value[idx].loading = false
      } else if (event === 'error') {
        messages.value[idx].content = `错误: ${data.content}`
        messages.value[idx].loading = false
      }
    }
  } catch (error: any) {
    const idx = messages.value.length - 1
    messages.value[idx] = {
      role: 'agent', content: `请求失败: ${error.message}`, steps: [], loading: false,
    }
  } finally {
    isLoading.value = false
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/agent.ts frontend/src/composables/useAgentChat.ts
git commit -m "feat: add SSE streaming support in frontend"
```

---

### Task 10: 后端图表工具 + Prompt 改造

**Files:**
- Modify: `backend/app/agent/tools.py`
- Modify: `backend/app/agent/prompt.py`
- Modify: `backend/app/agent/langchain_agent.py`

- [ ] **Step 1: 在 `backend/app/agent/tools.py` 中添加 generate_chart**

```python
import json

@tool
def generate_chart(chart_type: str, title: str, labels: str, values: str) -> str:
    """生成数据可视化图表配置。
    chart_type: 图表类型，只能是 "bar"、"line"、"pie" 之一
    title: 图表标题
    labels: JSON 数组字符串，如 '["电子产品","服装","食品"]'
    values: JSON 数组字符串，如 '[15000,8000,5000]'
    返回图表配置的 JSON 字符串。
    """
    if chart_type not in ("bar", "line", "pie"):
        return "错误：chart_type 必须是 bar、line 或 pie"
    try:
        labels_list = json.loads(labels)
        values_list = json.loads(values)
    except json.JSONDecodeError:
        return "错误：labels 和 values 必须是合法的 JSON 数组"

    chart_config = {
        "type": chart_type,
        "title": title,
        "x_axis": labels_list,
        "series": [{"name": title, "data": values_list}],
    }
    return json.dumps(chart_config, ensure_ascii=False)
```

- [ ] **Step 2: 修改 `backend/app/agent/prompt.py` 在工具列表和规则中增加图表说明**

在 `REACT_PROMPT_TEMPLATE` 的"重要规则"部分追加：
```
5. 当用户的问题涉及数据对比、趋势、占比等可视化需求时，在 sql_query 获取数据后，使用 generate_chart 工具生成图表
6. generate_chart 的 labels 和 values 参数必须是 JSON 数组字符串
```

- [ ] **Step 3: 修改 `backend/app/agent/langchain_agent.py` 解析图表数据**

在 `run_agent` 函数中，解析 intermediate_steps 时检测 generate_chart 工具输出：

```python
# 在 _parse_intermediate_steps 循环中，检测 chart 数据
chart_data = None
for action, observation in steps:
    if hasattr(action, 'tool') and action.tool == 'generate_chart':
        try:
            chart_data = json.loads(observation)
        except (json.JSONDecodeError, TypeError):
            pass

# AgentResult 新增 chart_data
class AgentResult(BaseModel):
    answer: str
    steps: List[AgentStep]
    success: bool
    chart_data: dict | None = None
```

在 `run_agent` 返回时附加 chart_data：
```python
return AgentResult(
    answer=result.get("output", "..."),
    steps=steps, success=True, chart_data=chart_data,
)
```

在 `langchain_agent.py` 顶部添加 `import json`，tools 列表改为 `tools = [sql_query, generate_chart]`。

- [ ] **Step 4: 提交**

```bash
git add backend/app/agent/
git commit -m "feat: add generate_chart tool and chart_data support"
```

---

### Task 11: 前端图表渲染 + CSV 导出

**Files:**
- Modify: `frontend/src/components/AgentChat.vue`
- Create: `frontend/src/utils/export.ts`
- Modify: `frontend/package.json` (install deps)

- [ ] **Step 1: 安装图表和导出依赖**

Run in `frontend/`:
```bash
npm install echarts vue-echarts papaparse
npm install -D @types/papaparse
```

- [ ] **Step 2: 创建 `frontend/src/utils/export.ts`**

```typescript
import Papa from 'papaparse'

export function exportToCSV(data: string[][], filename: string) {
  if (!data.length) return
  const headers = data[0]
  const rows = data.slice(1)
  const csv = Papa.unparse({ fields: headers, data: rows })

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const now = new Date()
  const ts = now.toISOString().replace(/[:.]/g, '-').slice(0, 19)
  link.href = url
  link.download = `${filename}_${ts}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

// 从 Agent observation 步骤中解析表格数据
export function parseObservationTable(steps: { type: string; content: string }[]): string[][] | null {
  for (const step of steps) {
    if (step.type === 'observation' && step.content.includes(' | ')) {
      const lines = step.content.split('\n').filter(l => l.trim() && !l.startsWith('---'))
      return lines.map(line => line.split(' | ').map(cell => cell.trim()))
    }
  }
  return null
}
```

- [ ] **Step 3: 在 `AgentChat.vue` 中添加图表渲染和导出按钮**

在 `<script setup>` 中添加：
```typescript
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { exportToCSV, parseObservationTable } from '../utils/export'

use([CanvasRenderer, BarChart, LineChart, PieChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

function buildEchartsOption(chartData: any) {
  if (chartData.type === 'pie') {
    return {
      title: { text: chartData.title },
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: '60%',
        data: chartData.x_axis.map((label: string, i: number) => ({
          name: label, value: chartData.series[0].data[i],
        })),
      }],
    }
  }
  return {
    title: { text: chartData.title },
    tooltip: {},
    xAxis: { type: 'category', data: chartData.x_axis },
    yAxis: { type: 'value' },
    series: chartData.series.map((s: any) => ({
      name: s.name, type: chartData.type, data: s.data,
    })),
  }
}

function handleExport(msg: ChatMessage) {
  const tableData = parseObservationTable(msg.steps || [])
  if (tableData) {
    exportToCSV(tableData, 'query_result')
  }
}
```

在 `<template>` 的 answer 区域添加图表和导出按钮：
```vue
<!-- 在 .answer div 后面添加 -->
<div v-if="msg.chart_data" style="margin-top: 12px;">
  <v-chart :option="buildEchartsOption(msg.chart_data)" style="height: 350px;" autoresize />
</div>
<div v-if="msg.steps && msg.steps.length && !msg.loading" style="margin-top: 8px;">
  <el-button size="small" @click="handleExport(msg)">📥 导出 CSV</el-button>
</div>
```

- [ ] **Step 4: 验证完整功能**

启动前后端，测试以下场景：
1. 登录 → 用户管理 → 退出
2. Agent 对话 → 查看思考过程 → 新建/切换会话
3. 问"各品类销售额对比" → 应出现图表
4. 点击"导出 CSV" → 应下载 CSV 文件

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/export.ts frontend/src/components/AgentChat.vue frontend/package.json
git commit -m "feat: add chart rendering and CSV export"
```

---

### Task 12: 最终集成验证

- [ ] **Step 1: 完整功能测试清单**

| 功能 | 测试步骤 | 预期结果 |
|------|----------|----------|
| 登录 | 输入 admin 账号密码 | 跳转到主页面 |
| 路由守卫 | 清除 localStorage 刷新 | 跳转到 /login |
| 用户列表 | admin 登录后访问 /users | 显示用户表格 |
| 角色分配 | 修改某用户角色 | 角色立即更新 |
| 启用/禁用 | 切换用户状态 | 状态立即更新 |
| 删除用户 | 点击删除确认 | 用户从列表消失 |
| 新建对话 | 点击"新对话" | 清空聊天区域 |
| 对话持久化 | 刷新页面 | 会话列表仍在 |
| 流式响应 | 发送问题 | 思考过程实时显示 |
| 图表 | 问"各品类销售额对比" | 显示柱状图 |
| CSV 导出 | 点击导出按钮 | 下载 CSV 文件 |

- [ ] **Step 2: 最终提交**

```bash
git add -A
git commit -m "feat: complete frontend enhancements - login, user management, agent UX"
```
