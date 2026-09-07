# 前端体验增强 V2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Data Analysis Agent 前端增加暗黑模式主题系统、数据仪表盘 Dashboard、移动端响应式适配和个人中心。

**Architecture:** 分三个模块按序交付。模块 1 建立 CSS 变量主题基础设施；模块 2 在主题之上构建 Dashboard 页面（含后端聚合 API）；模块 3 改造全局布局为响应式并新增个人中心页面及后端 API。

**Tech Stack:** Vue 3, TypeScript, Element Plus (dark mode), ECharts, FastAPI, SQLAlchemy

**设计文档:** `docs/superpowers/specs/2026-09-07-ux-enhancements-design.md`

---

## 文件结构总览

### 模块 1：暗黑模式

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `frontend/src/styles/themes.css` | 明亮/暗黑两套 CSS 变量 |
| 新建 | `frontend/src/composables/useTheme.ts` | 主题状态管理、切换、持久化 |
| 修改 | `frontend/src/main.ts` | 导入 themes.css |
| 修改 | `frontend/src/App.vue` | body 背景改用 CSS 变量 |
| 修改 | `frontend/src/layouts/MainLayout.vue` | Header 添加主题切换按钮 + CSS 变量化 |
| 修改 | `frontend/src/components/AgentChat.vue` | 硬编码颜色替换为 CSS 变量 |
| 修改 | `frontend/src/components/LoginView.vue` | 硬编码颜色替换为 CSS 变量 |
| 修改 | `frontend/src/components/UserManage.vue` | 无需改动（Element Plus 组件自动适配） |

### 模块 2：仪表盘

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `backend/app/schemas/agent.py` | 新增 DashboardResponse 模型 |
| 修改 | `backend/app/api/agent.py` | 新增 GET /api/agent/dashboard 端点 |
| 新建 | `frontend/src/api/dashboard.ts` | Dashboard API 封装 |
| 新建 | `frontend/src/components/Dashboard.vue` | 仪表盘页面 |
| 修改 | `frontend/src/router/index.ts` | 新增 /dashboard 路由 |
| 修改 | `frontend/src/layouts/MainLayout.vue` | 侧栏新增仪表盘菜单 |

### 模块 3：响应式 + 个人中心

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `backend/app/users/schemas.py` | 新增 UpdateProfileRequest, ChangePasswordRequest |
| 修改 | `backend/app/users/service.py` | 新增 update_profile, change_password |
| 修改 | `backend/app/users/router.py` | 新增 PUT /me, PUT /me/password |
| 新建 | `frontend/src/components/ProfileView.vue` | 个人中心页面 |
| 修改 | `frontend/src/api/users.ts` | 新增 updateProfile, changePassword |
| 修改 | `frontend/src/router/index.ts` | 新增 /profile 路由 |
| 修改 | `frontend/src/layouts/MainLayout.vue` | 响应式改造 + 个人中心入口 |
| 修改 | `frontend/src/components/AgentChat.vue` | 响应式改造 |
| 修改 | `frontend/src/components/LoginView.vue` | 响应式改造 |
| 修改 | `frontend/src/components/Dashboard.vue` | 响应式改造 |

---

## 模块 1：暗黑模式 + 主题系统

### Task 1: 主题 CSS 变量 + useTheme composable

**Files:**
- Create: `frontend/src/styles/themes.css`
- Create: `frontend/src/composables/useTheme.ts`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: 创建 `frontend/src/styles/themes.css`**

```css
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --bg-card: #ffffff;
  --bg-sidebar: #fafafa;
  --bg-input: #ffffff;
  --bg-hover: #f3f4f6;
  --text-primary: #111827;
  --text-secondary: #6b7280;
  --text-muted: #9ca3af;
  --border-color: #e5e7eb;
  --border-light: #f3f4f6;
  --shadow-color: rgba(0, 0, 0, 0.05);
  --header-bg: #1f2937;
  --header-text: #ffffff;
  --user-bubble-bg: #3b82f6;
  --agent-bubble-bg: #f3f4f6;
  --steps-panel-bg: #fafafa;
  --steps-panel-border: #e5e7eb;
  --login-gradient-start: #1f2937;
  --login-gradient-end: #374151;
}

html.dark {
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --bg-card: #1e293b;
  --bg-sidebar: #16213e;
  --bg-input: #1e293b;
  --bg-hover: #334155;
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --border-color: #334155;
  --border-light: #1e293b;
  --shadow-color: rgba(0, 0, 0, 0.3);
  --header-bg: #0f172a;
  --header-text: #f1f5f9;
  --user-bubble-bg: #2563eb;
  --agent-bubble-bg: #1e293b;
  --steps-panel-bg: #16213e;
  --steps-panel-border: #334155;
  --login-gradient-start: #0f172a;
  --login-gradient-end: #1e293b;
}
```

- [ ] **Step 2: 创建 `frontend/src/composables/useTheme.ts`**

```typescript
import { ref, watch } from 'vue'

const isDark = ref(localStorage.getItem('theme') === 'dark')

export function useTheme() {
  function applyTheme(dark: boolean) {
    document.documentElement.classList.toggle('dark', dark)
  }

  function toggleTheme() {
    isDark.value = !isDark.value
  }

  applyTheme(isDark.value)

  watch(isDark, (val) => {
    applyTheme(val)
    localStorage.setItem('theme', val ? 'dark' : 'light')
  })

  return { isDark, toggleTheme }
}
```

- [ ] **Step 3: 修改 `frontend/src/main.ts`**

在 `import 'element-plus/dist/index.css'` 之后添加：

```typescript
import 'element-plus/theme-chalk/dark/css-vars'
import './styles/themes.css'
```

- [ ] **Step 4: 修改 `frontend/src/App.vue`**

将 `<style>` 中的 `background: #f5f5f5;` 替换为：

```css
body {
  margin: 0;
  background: var(--bg-secondary);
  color: var(--text-primary);
  transition: background 0.3s, color 0.3s;
}
```

- [ ] **Step 5: 验证**

Run in `frontend/`: `npm run dev`
打开浏览器，暂时不做切换按钮，先确认 CSS 变量加载无报错。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/styles/themes.css frontend/src/composables/useTheme.ts
git add frontend/src/main.ts frontend/src/App.vue
git commit -m "feat: add theme CSS variables and useTheme composable"
```

---

### Task 2: MainLayout 主题切换按钮

**Files:**
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: 重写 MainLayout.vue**

将文件完整替换为：

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuth } from '../composables/useAuth'
import { useTheme } from '../composables/useTheme'

const { user, isAdmin, logout, fetchUser } = useAuth()
const { isDark, toggleTheme } = useTheme()

onMounted(() => {
  if (!user.value) fetchUser()
})
</script>

<template>
  <el-container style="height: 100vh">
    <el-header :style="{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      background: 'var(--header-bg)', color: 'var(--header-text)', padding: '0 20px',
    }">
      <h3 style="margin: 0; font-size: 18px;">📊 数据分析 Agent</h3>
      <div style="display: flex; align-items: center; gap: 12px;">
        <el-tag v-if="user" size="small">{{ user.role_name }}</el-tag>
        <span v-if="user">{{ user.username }}</span>
        <el-button circle size="small" @click="toggleTheme" :title="isDark ? '切换明亮模式' : '切换暗黑模式'">
          {{ isDark ? '☀️' : '🌙' }}
        </el-button>
        <el-button size="small" @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-container>
      <el-aside width="180px" :style="{
        background: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-color)',
      }">
        <el-menu :default-active="$route.path" :router="true"
          :style="{ borderRight: 'none' }"
          :background-color="'transparent'"
          :text-color="'var(--text-primary)'"
          :active-text-color="'#409eff'">
          <el-menu-item index="/">
            <span>💬 Agent 对话</span>
          </el-menu-item>
          <el-menu-item index="/users" v-if="isAdmin">
            <span>👥 用户管理</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main :style="{ background: 'var(--bg-secondary)', padding: '20px' }">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/layouts/MainLayout.vue
git commit -m "feat: add theme toggle button to header"
```

---

### Task 3: AgentChat 主题适配

**Files:**
- Modify: `frontend/src/components/AgentChat.vue`

- [ ] **Step 1: 替换 AgentChat.vue 的 `<style scoped>` 部分**

将所有硬编码颜色替换为 CSS 变量。完整替换 `<style scoped>` 为：

```css
<style scoped>
.conv-sidebar {
  width: 220px;
  border-right: 1px solid var(--border-color);
  padding: 12px;
  overflow-y: auto;
  background: var(--bg-sidebar);
}
.new-conv-btn {
  width: 100%;
  padding: 8px;
  margin-bottom: 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-card);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 13px;
}
.new-conv-btn:hover { background: var(--bg-hover); }
.conv-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  color: var(--text-primary);
}
.conv-item:hover { background: var(--bg-hover); }
.conv-item.active { background: var(--bg-hover); }
.conv-title { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.conv-delete {
  background: none; border: none; cursor: pointer; color: var(--text-muted);
  font-size: 16px; padding: 0 4px;
}
.conv-delete:hover { color: #ef4444; }

.agent-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  max-width: 900px;
}
.messages { flex: 1; overflow-y: auto; padding: 20px; }
.message { margin-bottom: 16px; }
.message.user .bubble {
  background: var(--user-bubble-bg); color: white; border-radius: 12px 12px 0 12px;
  padding: 12px 16px; max-width: 70%; margin-left: auto;
}
.message.agent .bubble {
  background: var(--agent-bubble-bg); border-radius: 12px 12px 12px 0;
  padding: 12px 16px; max-width: 85%;
  color: var(--text-primary);
}
.loading { color: var(--text-secondary); font-style: italic; }
.steps-panel {
  margin-bottom: 12px; border: 1px solid var(--steps-panel-border);
  border-radius: 8px; padding: 8px; background: var(--steps-panel-bg);
}
.steps-panel summary { cursor: pointer; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.step { margin-bottom: 8px; }
.step-tag {
  display: inline-block; color: white; font-size: 12px;
  padding: 2px 8px; border-radius: 4px; margin-right: 8px;
}
.step-content {
  margin: 4px 0 0 0; padding: 6px 10px; background: var(--bg-card);
  border-radius: 4px; font-size: 13px; white-space: pre-wrap; word-break: break-all;
  color: var(--text-primary);
}
.answer { font-size: 15px; line-height: 1.6; color: var(--text-primary); }
.quick-questions { padding: 8px 20px; display: flex; gap: 8px; flex-wrap: wrap; }
.quick-questions button {
  padding: 6px 12px; border: 1px solid var(--border-color); border-radius: 16px;
  background: var(--bg-card); cursor: pointer; font-size: 13px;
  color: var(--text-primary);
}
.quick-questions button:hover { background: var(--bg-hover); }
.input-area { display: flex; gap: 8px; padding: 16px 20px; border-top: 1px solid var(--border-color); }
.input-area input {
  flex: 1; padding: 10px 14px; border: 1px solid var(--border-color); border-radius: 8px;
  font-size: 14px; background: var(--bg-input); color: var(--text-primary);
}
.input-area button {
  padding: 10px 20px; background: #3b82f6; color: white;
  border: none; border-radius: 8px; cursor: pointer; font-size: 14px;
}
.input-area button:disabled { background: var(--text-muted); cursor: not-allowed; }
.export-btn {
  padding: 4px 10px; border: 1px solid var(--border-color); border-radius: 4px;
  background: var(--bg-card); cursor: pointer; font-size: 12px;
  color: var(--text-primary);
}
.export-btn:hover { background: var(--bg-hover); }
</style>
```

- [ ] **Step 2: 同时修改 `<script setup>` 中的 `buildEchartsOption` 函数**

在 `buildEchartsOption` 函数中，给返回的 option 对象加上 `backgroundColor: 'transparent'` 和 `textStyle: { color: ... }` 以适配主题：

在两个 return 语句前分别添加主题色适配。将函数改为：

```typescript
function buildEchartsOption(chartData: any) {
  const isDark = document.documentElement.classList.contains('dark')
  const textColor = isDark ? '#f1f5f9' : '#111827'
  if (chartData.type === 'pie') {
    return {
      backgroundColor: 'transparent',
      title: { text: chartData.title, textStyle: { color: textColor } },
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie', radius: '60%',
        data: chartData.x_axis.map((label: string, i: number) => ({
          name: label, value: chartData.series[0].data[i],
        })),
      }],
    }
  }
  return {
    backgroundColor: 'transparent',
    title: { text: chartData.title, textStyle: { color: textColor } },
    tooltip: {},
    xAxis: { type: 'category', data: chartData.x_axis, axisLabel: { color: textColor }, axisLine: { lineStyle: { color: textColor } } },
    yAxis: { type: 'value', axisLabel: { color: textColor }, axisLine: { lineStyle: { color: textColor } } },
    series: chartData.series.map((s: any) => ({
      name: s.name, type: chartData.type, data: s.data,
    })),
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/AgentChat.vue
git commit -m "feat: apply theme CSS variables to AgentChat"
```

---

### Task 4: LoginView 主题适配

**Files:**
- Modify: `frontend/src/components/LoginView.vue`

- [ ] **Step 1: 替换 LoginView.vue 的 `<style scoped>` 部分**

```css
<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, var(--login-gradient-start) 0%, var(--login-gradient-end) 100%);
}
.login-card {
  width: 400px;
  padding: 20px;
}
.login-card h2 {
  color: var(--text-primary);
}
</style>
```

- [ ] **Step 2: 验证暗黑模式**

启动前端 `npm run dev`，在 MainLayout 中点击 🌙 按钮，确认：
- 侧栏、主区域、聊天区域颜色切换正确
- 登录页背景色切换正确
- 所有文字可读

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/LoginView.vue
git commit -m "feat: apply theme CSS variables to LoginView"
```

---

## 模块 2：仪表盘 Dashboard

### Task 5: 后端 Dashboard 聚合 API

**Files:**
- Modify: `backend/app/schemas/agent.py`
- Modify: `backend/app/api/agent.py`

- [ ] **Step 1: 在 `backend/app/schemas/agent.py` 末尾添加**

```python
class DashboardSummary(BaseModel):
    total_revenue: float
    total_orders: int
    total_products: int
    monthly_revenue: float


class DashboardTrend(BaseModel):
    dates: List[str]
    values: List[float]


class DashboardCategory(BaseModel):
    labels: List[str]
    values: List[float]


class DashboardTopProducts(BaseModel):
    names: List[str]
    values: List[float]


class DashboardResponse(BaseModel):
    summary: DashboardSummary
    daily_trend: DashboardTrend
    category_distribution: DashboardCategory
    top_products: DashboardTopProducts
```

- [ ] **Step 2: 在 `backend/app/api/agent.py` 中添加 dashboard 端点**

在文件顶部 import 区追加：

```python
from sqlalchemy import text as sql_text
from app.schemas.agent import (
    AgentQueryRequest, AgentQueryResponse, AgentStepResponse,
    SchemasResponse, TableSchema, ChartData,
    DashboardResponse, DashboardSummary, DashboardTrend,
    DashboardCategory, DashboardTopProducts,
)
from app.database import sync_engine
from datetime import date, timedelta
```

在文件末尾（`get_schemas` 函数之后）添加：

```python
@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    _current_user: User = Depends(require_role("admin", "editor")),
):
    """获取仪表盘聚合数据。"""
    from app.database import sync_engine

    with sync_engine.connect() as conn:
        # 汇总统计
        summary_rows = conn.execute(sql_text("""
            SELECT
                COALESCE(SUM(oi.quantity * oi.unit_price), 0) as total_revenue,
                COUNT(DISTINCT o.id) as total_orders,
                (SELECT COUNT(*) FROM products) as total_products,
                COALESCE(SUM(CASE WHEN o.order_date >= date('now', '-30 days')
                    THEN oi.quantity * oi.unit_price ELSE 0 END), 0) as monthly_revenue
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
        """)).fetchone()

        # 近 30 天每日趋势
        trend_rows = conn.execute(sql_text("""
            SELECT date(o.order_date) as d,
                   SUM(oi.quantity * oi.unit_price) as revenue
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            WHERE o.order_date >= date('now', '-30 days')
            GROUP BY date(o.order_date)
            ORDER BY d
        """)).fetchall()

        # 品类分布
        cat_rows = conn.execute(sql_text("""
            SELECT p.category, SUM(oi.quantity * oi.unit_price) as revenue
            FROM products p
            JOIN order_items oi ON oi.product_id = p.id
            GROUP BY p.category
            ORDER BY revenue DESC
        """)).fetchall()

        # TOP 10 热销商品
        top_rows = conn.execute(sql_text("""
            SELECT p.name, SUM(oi.quantity) as qty
            FROM products p
            JOIN order_items oi ON oi.product_id = p.id
            GROUP BY p.id
            ORDER BY qty DESC
            LIMIT 10
        """)).fetchall()

    return DashboardResponse(
        summary=DashboardSummary(
            total_revenue=summary_rows[0] or 0,
            total_orders=summary_rows[1] or 0,
            total_products=summary_rows[2] or 0,
            monthly_revenue=summary_rows[3] or 0,
        ),
        daily_trend=DashboardTrend(
            dates=[str(r[0]) for r in trend_rows],
            values=[float(r[1]) for r in trend_rows],
        ),
        category_distribution=DashboardCategory(
            labels=[r[0] for r in cat_rows],
            values=[float(r[1]) for r in cat_rows],
        ),
        top_products=DashboardTopProducts(
            names=[r[0] for r in top_rows],
            values=[float(r[1]) for r in top_rows],
        ),
    )
```

注意：需要确保 `sync_engine` 已在文件顶部导入（在 `from app.database import sync_engine` 行）。如果已有则不需重复。

- [ ] **Step 3: 重启后端验证**

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8001
```

用 Swagger UI 或 curl 测试 `GET /api/agent/dashboard`，确认返回正确的聚合数据。

- [ ] **Step 4: 提交**

```bash
git add backend/app/schemas/agent.py backend/app/api/agent.py
git commit -m "feat: add dashboard aggregation API endpoint"
```

---

### Task 6: 前端 Dashboard 页面

**Files:**
- Create: `frontend/src/api/dashboard.ts`
- Create: `frontend/src/components/Dashboard.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: 创建 `frontend/src/api/dashboard.ts`**

```typescript
import { api } from './auth'

export interface DashboardData {
  summary: {
    total_revenue: number
    total_orders: number
    total_products: number
    monthly_revenue: number
  }
  daily_trend: {
    dates: string[]
    values: number[]
  }
  category_distribution: {
    labels: string[]
    values: number[]
  }
  top_products: {
    names: string[]
    values: number[]
  }
}

export async function getDashboard(): Promise<DashboardData> {
  const { data } = await api.get<DashboardData>('/agent/dashboard')
  return data
}
```

- [ ] **Step 2: 创建 `frontend/src/components/Dashboard.vue`**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { getDashboard, type DashboardData } from '../api/dashboard'

use([CanvasRenderer, BarChart, LineChart, PieChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const data = ref<DashboardData | null>(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    data.value = await getDashboard()
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
})

function chartTextColor() {
  return document.documentElement.classList.contains('dark') ? '#f1f5f9' : '#111827'
}

function trendOption() {
  if (!data.value) return {}
  return {
    backgroundColor: 'transparent',
    title: { text: '近 30 天销售趋势', textStyle: { color: chartTextColor() } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.value.daily_trend.dates, axisLabel: { color: chartTextColor() } },
    yAxis: { type: 'value', axisLabel: { color: chartTextColor() } },
    series: [{ name: '销售额', type: 'line', data: data.value.daily_trend.values, smooth: true }],
  }
}

function categoryOption() {
  if (!data.value) return {}
  return {
    backgroundColor: 'transparent',
    title: { text: '品类销售占比', textStyle: { color: chartTextColor() } },
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: '60%',
      data: data.value.category_distribution.labels.map((label, i) => ({
        name: label, value: data.value!.category_distribution.values[i],
      })),
    }],
  }
}

function topProductsOption() {
  if (!data.value) return {}
  return {
    backgroundColor: 'transparent',
    title: { text: 'TOP 10 热销商品', textStyle: { color: chartTextColor() } },
    tooltip: {},
    xAxis: { type: 'category', data: data.value.top_products.names, axisLabel: { rotate: 30, color: chartTextColor() } },
    yAxis: { type: 'value', axisLabel: { color: chartTextColor() } },
    series: [{ name: '销量', type: 'bar', data: data.value.top_products.values }],
  }
}

function formatNumber(n: number): string {
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>

<template>
  <div v-loading="loading">
    <h2 style="margin: 0 0 20px 0; color: var(--text-primary);">数据仪表盘</h2>

    <template v-if="data">
      <!-- 统计卡片 -->
      <el-row :gutter="16" class="dash-row">
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">总销售额</div>
            <div class="stat-value">¥{{ formatNumber(data.summary.total_revenue) }}</div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">总订单数</div>
            <div class="stat-value">{{ data.summary.total_orders.toLocaleString() }}</div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">商品数量</div>
            <div class="stat-value">{{ data.summary.total_products }}</div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">近 30 天销售额</div>
            <div class="stat-value">¥{{ formatNumber(data.summary.monthly_revenue) }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 图表区域 -->
      <el-row :gutter="16" class="dash-row">
        <el-col :xs="24" :sm="16">
          <el-card shadow="hover" class="chart-card">
            <v-chart :option="trendOption()" style="height: 320px;" autoresize />
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-card shadow="hover" class="chart-card">
            <v-chart :option="categoryOption()" style="height: 320px;" autoresize />
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" class="dash-row">
        <el-col :span="24">
          <el-card shadow="hover" class="chart-card">
            <v-chart :option="topProductsOption()" style="height: 350px;" autoresize />
          </el-card>
        </el-col>
      </el-row>
    </template>

    <el-empty v-else-if="!loading" description="数据加载失败" />
  </div>
</template>

<style scoped>
.dash-row {
  margin-bottom: 16px;
}
.stat-card {
  background: var(--bg-card);
  margin-bottom: 12px;
}
.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}
.chart-card {
  background: var(--bg-card);
  margin-bottom: 12px;
}
</style>
```

- [ ] **Step 3: 修改 `frontend/src/router/index.ts`**

在 `children` 数组中（`Users` 路由之前）添加：

```typescript
{
  path: 'dashboard',
  name: 'Dashboard',
  component: () => import('../components/Dashboard.vue'),
},
```

- [ ] **Step 4: 修改 `frontend/src/layouts/MainLayout.vue`**

在 `<el-menu-item index="/">` 之后、`<el-menu-item index="/users">` 之前添加：

```html
<el-menu-item index="/dashboard">
  <span>📈 仪表盘</span>
</el-menu-item>
```

- [ ] **Step 5: 验证**

启动前后端，以 admin 或 editor 登录后：
- 侧栏应显示"仪表盘"菜单项
- 点击仪表盘，应看到 4 个统计卡片和 3 个图表
- 切换暗黑模式，图表文字颜色应适配

- [ ] **Step 6: 提交**

```bash
git add frontend/src/api/dashboard.ts frontend/src/components/Dashboard.vue
git add frontend/src/router/index.ts frontend/src/layouts/MainLayout.vue
git commit -m "feat: add dashboard page with charts and stats"
```

---

## 模块 3：移动端响应式 + 个人中心

### Task 7: 后端个人中心 API

**Files:**
- Modify: `backend/app/users/schemas.py`
- Modify: `backend/app/users/service.py`
- Modify: `backend/app/users/router.py`

- [ ] **Step 1: 在 `backend/app/users/schemas.py` 末尾添加**

```python
class UpdateProfileRequest(BaseModel):
    email: str | None = None
    phone: str | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
```

- [ ] **Step 2: 在 `backend/app/users/service.py` 末尾添加**

```python
from app.auth.service import verify_password


async def update_profile(db: AsyncSession, user_id: int, email: str | None, phone: str | None) -> User | None:
    user = await get_user_by_id(db, user_id)
    if user is None:
        return None
    if email is not None:
        user.email = email
    if phone is not None:
        user.phone = phone
    await db.commit()
    await db.refresh(user)
    return user


async def change_password(db: AsyncSession, user_id: int, old_password: str, new_password: str) -> bool:
    user = await get_user_by_id(db, user_id)
    if user is None or not user.hashed_password:
        return False
    if not verify_password(old_password, user.hashed_password):
        return False
    user.hashed_password = hash_password(new_password)
    await db.commit()
    return True
```

注意：`verify_password` 已在 `app.auth.service` 中定义，`hash_password` 也已导入。确保导入正确。

- [ ] **Step 3: 在 `backend/app/users/router.py` 中添加两个端点**

在文件顶部 import 区追加：

```python
from app.users.schemas import UserOut, UpdateRoleRequest, UpdateActiveRequest, UpdateProfileRequest, ChangePasswordRequest
from app.users.service import (
    get_all_users, update_user_role, update_user_active, delete_user, get_user_by_id,
    update_profile, change_password,
)
```

注意：`get_me` 端点已存在（`GET /me`）。在它之后、`GET /` 之前添加两个新端点：

```python
@router.put("/me", response_model=UserOut)
async def update_me(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新当前用户个人信息。"""
    user = await update_profile(db, current_user.id, req.email, req.phone)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return _user_to_out(user)


@router.put("/me/password")
async def change_my_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改当前用户密码。"""
    if len(req.new_password) < 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "新密码至少 6 位")
    ok = await change_password(db, current_user.id, req.old_password, req.new_password)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "旧密码不正确")
    return {"message": "密码已修改"}
```

**重要：** 这两个端点必须在 `/{user_id}/...` 路由之前定义，否则 FastAPI 会把 "me" 当作 user_id 参数。确保它们在 `@router.put("/{user_id}/role")` 之前。

- [ ] **Step 4: 重启后端验证**

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8001
```

用 Swagger UI 测试 `PUT /api/users/me` 和 `PUT /api/users/me/password`。

- [ ] **Step 5: 提交**

```bash
git add backend/app/users/schemas.py backend/app/users/service.py backend/app/users/router.py
git commit -m "feat: add profile update and password change APIs"
```

---

### Task 8: 前端个人中心页面

**Files:**
- Create: `frontend/src/components/ProfileView.vue`
- Modify: `frontend/src/api/users.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: 在 `frontend/src/api/users.ts` 末尾添加**

```typescript
export async function updateProfile(email: string | null, phone: string | null): Promise<UserOut> {
  const { data } = await api.put<UserOut>('/users/me', { email, phone })
  return data
}

export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  await api.put('/users/me/password', { old_password: oldPassword, new_password: newPassword })
}
```

- [ ] **Step 2: 创建 `frontend/src/components/ProfileView.vue`**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuth } from '../composables/useAuth'
import { updateProfile, changePassword } from '../api/users'

const { user, fetchUser } = useAuth()

const profileForm = ref({ email: '', phone: '' })
const profileLoading = ref(false)

const pwdForm = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
const pwdLoading = ref(false)

onMounted(() => {
  if (user.value) {
    profileForm.value.email = user.value.email || ''
    profileForm.value.phone = user.value.phone || ''
  }
})

async function handleUpdateProfile() {
  profileLoading.value = true
  try {
    await updateProfile(profileForm.value.email || null, profileForm.value.phone || null)
    await fetchUser()
    ElMessage.success('个人信息已更新')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  } finally {
    profileLoading.value = false
  }
}

async function handleChangePassword() {
  if (!pwdForm.value.oldPassword || !pwdForm.value.newPassword) {
    ElMessage.warning('请填写完整密码信息')
    return
  }
  if (pwdForm.value.newPassword.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (pwdForm.value.newPassword !== pwdForm.value.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  pwdLoading.value = true
  try {
    await changePassword(pwdForm.value.oldPassword, pwdForm.value.newPassword)
    ElMessage.success('密码已修改')
    pwdForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '密码修改失败')
  } finally {
    pwdLoading.value = false
  }
}
</script>

<template>
  <div style="max-width: 500px;">
    <h2 style="margin: 0 0 20px 0; color: var(--text-primary);">个人中心</h2>

    <!-- 用户信息展示 -->
    <el-card style="margin-bottom: 20px; background: var(--bg-card);">
      <div style="display: flex; align-items: center; gap: 16px;">
        <el-avatar :size="64" :src="user?.avatar_url || undefined">
          {{ user?.username?.charAt(0)?.toUpperCase() }}
        </el-avatar>
        <div>
          <div style="font-size: 18px; font-weight: 600; color: var(--text-primary);">{{ user?.username }}</div>
          <el-tag size="small" style="margin-top: 4px;">{{ user?.role_name }}</el-tag>
        </div>
      </div>
    </el-card>

    <!-- 编辑个人信息 -->
    <el-card style="margin-bottom: 20px; background: var(--bg-card);">
      <template #header><span style="color: var(--text-primary);">个人信息</span></template>
      <el-form label-width="80px">
        <el-form-item label="邮箱">
          <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="profileForm.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="profileLoading" @click="handleUpdateProfile">保存修改</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 修改密码 -->
    <el-card style="background: var(--bg-card);">
      <template #header><span style="color: var(--text-primary);">修改密码</span></template>
      <el-form label-width="80px">
        <el-form-item label="旧密码">
          <el-input v-model="pwdForm.oldPassword" type="password" show-password placeholder="请输入旧密码" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwdForm.newPassword" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="pwdForm.confirmPassword" type="password" show-password placeholder="再次输入新密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="pwdLoading" @click="handleChangePassword">修改密码</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
```

- [ ] **Step 3: 修改 `frontend/src/router/index.ts`**

在 `children` 数组中添加（Dashboard 路由之后）：

```typescript
{
  path: 'profile',
  name: 'Profile',
  component: () => import('../components/ProfileView.vue'),
},
```

- [ ] **Step 4: 修改 `frontend/src/layouts/MainLayout.vue`**

在侧栏 `<el-menu>` 中，在用户管理菜单项之后添加：

```html
<el-menu-item index="/profile">
  <span>👤 个人中心</span>
</el-menu-item>
```

- [ ] **Step 5: 验证**

登录后访问 `/profile`，应能看到个人信息、编辑表单和密码修改区域。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/ProfileView.vue frontend/src/api/users.ts
git add frontend/src/router/index.ts frontend/src/layouts/MainLayout.vue
git commit -m "feat: add profile page with personal info and password change"
```

---

### Task 9: 全局响应式改造

**Files:**
- Modify: `frontend/src/layouts/MainLayout.vue`
- Modify: `frontend/src/components/AgentChat.vue`
- Modify: `frontend/src/components/LoginView.vue`
- Modify: `frontend/src/components/Dashboard.vue`

- [ ] **Step 1: 改造 MainLayout.vue 为响应式**

将 `<script setup>` 部分替换为：

```typescript
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuth } from '../composables/useAuth'
import { useTheme } from '../composables/useTheme'

const { user, isAdmin, logout, fetchUser } = useAuth()
const { isDark, toggleTheme } = useTheme()

const isMobile = ref(window.innerWidth < 768)
const drawerVisible = ref(false)

function onResize() {
  isMobile.value = window.innerWidth < 768
  if (!isMobile.value) drawerVisible.value = false
}

onMounted(() => {
  if (!user.value) fetchUser()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})
</script>
```

将 `<template>` 部分替换为：

```html
<template>
  <el-container style="height: 100vh">
    <el-header :style="{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      background: 'var(--header-bg)', color: 'var(--header-text)', padding: '0 16px',
    }">
      <div style="display: flex; align-items: center; gap: 12px;">
        <el-button v-if="isMobile" circle size="small" @click="drawerVisible = true">☰</el-button>
        <h3 style="margin: 0; font-size: 18px;">📊 数据分析 Agent</h3>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <el-tag v-if="user" size="small">{{ user.role_name }}</el-tag>
        <span v-if="user && !isMobile" style="font-size: 14px;">{{ user.username }}</span>
        <el-button circle size="small" @click="toggleTheme">{{ isDark ? '☀️' : '🌙' }}</el-button>
        <el-button size="small" @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-container>
      <!-- 桌面端侧栏 -->
      <el-aside v-if="!isMobile" width="180px" :style="{
        background: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-color)',
      }">
        <el-menu :default-active="$route.path" :router="true"
          :background-color="'transparent'"
          :text-color="'var(--text-primary)'"
          :active-text-color="'#409eff'"
          style="border-right: none;">
          <el-menu-item index="/"><span>💬 Agent 对话</span></el-menu-item>
          <el-menu-item index="/dashboard"><span>📈 仪表盘</span></el-menu-item>
          <el-menu-item index="/users" v-if="isAdmin"><span>👥 用户管理</span></el-menu-item>
          <el-menu-item index="/profile"><span>👤 个人中心</span></el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 移动端抽屉菜单 -->
      <el-drawer v-if="isMobile" v-model="drawerVisible" direction="ltr" :size="220" :show-close="false">
        <el-menu :default-active="$route.path" :router="true"
          @select="drawerVisible = false"
          :background-color="'transparent'"
          :text-color="'var(--text-primary)'"
          :active-text-color="'#409eff'">
          <el-menu-item index="/"><span>💬 Agent 对话</span></el-menu-item>
          <el-menu-item index="/dashboard"><span>📈 仪表盘</span></el-menu-item>
          <el-menu-item index="/users" v-if="isAdmin"><span>👥 用户管理</span></el-menu-item>
          <el-menu-item index="/profile"><span>👤 个人中心</span></el-menu-item>
        </el-menu>
      </el-drawer>

      <el-main :style="{ background: 'var(--bg-secondary)', padding: '20px' }">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
```

- [ ] **Step 2: 改造 AgentChat.vue 为响应式**

在 `<script setup>` 中添加响应式逻辑：

```typescript
import { ref, onMounted, computed } from 'vue'

const isMobile = ref(window.innerWidth < 768)
const convDrawerVisible = ref(false)

function onResize() {
  isMobile.value = window.innerWidth < 768
}

onMounted(() => {
  window.addEventListener('resize', onResize)
})

// 在 onUnmounted 中移除监听器（如果已有 onUnmounted 则合并）
import { onUnmounted } from 'vue'
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})
```

在 `<template>` 中，将最外层 `<div>` 改为：

```html
<template>
  <div style="display: flex; height: calc(100vh - 56px);">
    <!-- 桌面端会话侧栏 -->
    <div v-if="!isMobile" class="conv-sidebar">
      <button class="new-conv-btn" @click="startNewConversation">+ 新对话</button>
      <div
        v-for="conv in conversations" :key="conv.id"
        :class="['conv-item', { active: conv.id === currentConvId }]"
        @click="selectConversation(conv.id)"
      >
        <span class="conv-title">{{ conv.title }}</span>
        <button class="conv-delete" @click.stop="removeConversation(conv.id)">×</button>
      </div>
    </div>

    <!-- 移动端会话抽屉 -->
    <el-drawer v-if="isMobile" v-model="convDrawerVisible" direction="ltr" :size="260" :show-close="false"
      :style="{ background: 'var(--bg-sidebar)' }">
      <button class="new-conv-btn" @click="startNewConversation(); convDrawerVisible = false">+ 新对话</button>
      <div
        v-for="conv in conversations" :key="conv.id"
        :class="['conv-item', { active: conv.id === currentConvId }]"
        @click="selectConversation(conv.id); convDrawerVisible = false"
      >
        <span class="conv-title">{{ conv.title }}</span>
        <button class="conv-delete" @click.stop="removeConversation(conv.id)">×</button>
      </div>
    </el-drawer>

    <!-- 主聊天区域 -->
    <div class="agent-chat" :style="isMobile ? { maxWidth: '100%' } : {}">
      <!-- 移动端显示会话按钮 -->
      <div v-if="isMobile" style="padding: 8px 12px;">
        <el-button size="small" @click="convDrawerVisible = true">📋 会话列表</el-button>
      </div>

      <div class="messages">
        <!-- 消息部分保持不变 -->
      </div>

      <!-- 快捷提问在移动端横向滚动 -->
      <div class="quick-questions" :style="isMobile ? { flexWrap: 'nowrap', overflowX: 'auto' } : {}">
        <button v-for="q in quickQuestions" :key="q" @click="handleQuick(q)" :disabled="isLoading">
          {{ q }}
        </button>
      </div>

      <div class="input-area">
        <input
          v-model="inputText"
          @keyup.enter="handleSend"
          :disabled="isLoading"
          placeholder="输入你的问题..."
        />
        <button @click="handleSend" :disabled="isLoading || !inputText.trim()">发送</button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 3: 改造 LoginView.vue 为响应式**

将 `.login-card` 的 CSS 改为：

```css
.login-card {
  width: 90%;
  max-width: 400px;
  padding: 20px;
}
```

- [ ] **Step 4: Dashboard.vue 响应式已通过 el-row/el-col 的 :xs 属性实现**

Dashboard 在 Task 6 中已使用 `:xs="24" :sm="16"` 等响应式属性，无需额外改造。

- [ ] **Step 5: 全量验证**

启动前后端，在浏览器中测试：

1. 桌面端（>= 768px）：侧栏正常展开，所有页面布局正确
2. 移动端（< 768px）：
   - 侧栏隐藏，汉堡菜单可唤出抽屉
   - Agent 对话页：会话列表通过按钮唤出抽屉
   - 仪表盘：卡片和图表单列堆叠
   - 登录页：卡片宽度自适应
3. 暗黑模式：所有页面在两种主题下颜色正确

- [ ] **Step 6: 提交**

```bash
git add frontend/src/layouts/MainLayout.vue frontend/src/components/AgentChat.vue
git add frontend/src/components/LoginView.vue
git commit -m "feat: responsive layout for mobile with drawer menus"
```

---

## 最终验证

- [ ] **全量回归测试**

1. 暗黑模式：切换主题，所有页面颜色一致，无硬编码颜色残留
2. 仪表盘：数据正确加载，图表渲染正常，主题切换后图表配色跟随
3. 个人中心：信息修改成功，密码修改流程正确（旧密码验证、新密码长度、两次确认）
4. 响应式：768px 断点两侧布局正确，移动端抽屉菜单可用
5. 原有功能：Agent 对话、会话历史、用户管理、CSV 导出均正常
