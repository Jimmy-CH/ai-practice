# 前端体验增强 V2：暗黑模式 + 仪表盘 + 响应式 + 个人中心

## 概述

为 Data Analysis Agent 前端进行第二轮体验增强，包含三个独立模块，按依赖顺序交付：

1. **暗黑模式 + 主题系统** — 全局主题切换基础设施
2. **仪表盘 Dashboard** — 关键数据概览页面
3. **移动端响应式 + 个人中心** — 布局适配与用户自助管理

## 交付顺序与依赖

```
模块 1: 暗黑模式 → 模块 2: Dashboard(复用主题) → 模块 3: 响应式 + 个人中心
```

---

## 模块 1：暗黑模式 + 主题系统

### 目标

支持明亮/暗黑两种主题，用户可在 Header 中一键切换，偏好持久化到 localStorage。

### 技术方案

- 使用 CSS 自定义属性（CSS Variables）定义颜色体系
- 在 `<html>` 元素上切换 `class="dark"` 触发暗黑主题
- 利用 Element Plus 内置的暗黑模式 CSS 变量覆盖（`element-plus/dark/css-vars`）
- 主题状态通过 composable 管理，跨组件共享

### 文件变更

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `frontend/src/styles/themes.css` | 定义 `:root` 和 `.dark` 两套 CSS 变量 |
| 新建 | `frontend/src/composables/useTheme.ts` | 主题状态管理、切换、持久化 |
| 修改 | `frontend/src/main.ts` | 导入 themes.css，初始化主题 |
| 修改 | `frontend/src/layouts/MainLayout.vue` | Header 添加主题切换按钮 |
| 修改 | `frontend/src/components/AgentChat.vue` | 硬编码颜色替换为 CSS 变量 |
| 修改 | `frontend/src/components/LoginView.vue` | 硬编码颜色替换为 CSS 变量 |
| 修改 | `frontend/src/components/UserManage.vue` | 硬编码颜色替换为 CSS 变量 |

### CSS 变量设计

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
}
```

### useTheme composable

```typescript
// frontend/src/composables/useTheme.ts
import { ref, watch } from 'vue'

const isDark = ref(localStorage.getItem('theme') === 'dark')

export function useTheme() {
  function applyTheme(dark: boolean) {
    document.documentElement.classList.toggle('dark', dark)
  }

  function toggleTheme() {
    isDark.value = !isDark.value
  }

  // 初始化
  applyTheme(isDark.value)

  // 监听变化
  watch(isDark, (val) => {
    applyTheme(val)
    localStorage.setItem('theme', val ? 'dark' : 'light')
  })

  return { isDark, toggleTheme }
}
```

### 图表主题联动

ECharts 图表根据主题动态调整配色：

```typescript
function getChartTheme() {
  const isDark = document.documentElement.classList.contains('dark')
  return {
    backgroundColor: 'transparent',
    textStyle: { color: isDark ? '#f1f5f9' : '#111827' },
    title: { textStyle: { color: isDark ? '#f1f5f9' : '#111827' } },
    // ...
  }
}
```

---

## 模块 2：仪表盘 Dashboard

### 目标

新增 Dashboard 页面，展示关键业务数据概览，让用户快速掌握数据全貌。

### 后端设计

**新增端点：** `GET /api/agent/dashboard`

权限：admin + editor

响应结构：

```json
{
  "summary": {
    "total_revenue": 1234567.89,
    "total_orders": 5432,
    "total_products": 21,
    "monthly_revenue": 234567.89
  },
  "daily_trend": {
    "dates": ["2026-08-08", "2026-08-09", ...],
    "values": [12345, 15678, ...]
  },
  "category_distribution": {
    "labels": ["电子产品", "服装", "食品", ...],
    "values": [456789, 234567, ...]
  },
  "top_products": {
    "names": ["商品A", "商品B", ...],
    "values": [1234, 1100, ...]
  }
}
```

**实现方式：** 在 `app/api/agent.py` 中新增端点，直接使用 SQL 聚合查询（不经过 Agent/LLM），使用 `sync_engine` 执行。

**新增 Pydantic 模型：** 在 `app/schemas/agent.py` 中新增 `DashboardResponse`。

### 前端设计

**新路由：** `/dashboard`

**新组件：** `frontend/src/components/Dashboard.vue`

**布局结构：**

```
┌────────────────────────────────────────────────┐
│  统计卡片行                                      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐           │
│  │总销售额│ │总订单 │ │商品数 │ │月销售额│           │
│  └──────┘ └──────┘ └──────┘ └──────┘           │
├────────────────────────────────────────────────┤
│  图表区域                                        │
│  ┌─────────────────┐ ┌─────────────────┐       │
│  │  销售趋势折线图   │ │  品类分布饼图    │       │
│  │  (占 2/3 宽度)   │ │  (占 1/3 宽度)  │       │
│  └─────────────────┘ └─────────────────┘       │
│  ┌─────────────────────────────────────┐       │
│  │        TOP 10 热销商品柱状图          │       │
│  └─────────────────────────────────────┘       │
└────────────────────────────────────────────────┘
```

**文件变更：**

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `frontend/src/components/Dashboard.vue` | 仪表盘页面 |
| 新建 | `frontend/src/api/dashboard.ts` | Dashboard API 封装 |
| 修改 | `frontend/src/router/index.ts` | 新增 `/dashboard` 路由 |
| 修改 | `frontend/src/layouts/MainLayout.vue` | 侧栏新增"仪表盘"菜单项 |
| 修改 | `backend/app/api/agent.py` | 新增 dashboard 端点 |
| 修改 | `backend/app/schemas/agent.py` | 新增 DashboardResponse 模型 |

**权限：** 仅 admin + editor 可访问 Dashboard 页面（前端路由守卫 + 后端 RBAC）。

---

## 模块 3：移动端响应式 + 个人中心

### 3a：响应式改造

**断点设计：**

- 桌面：>= 768px（当前布局不变）
- 移动端：< 768px

**MainLayout 改造：**

- 桌面：侧栏正常展开（180px）
- 移动端：侧栏隐藏，Header 左侧添加汉堡菜单按钮，点击展开为 `el-drawer`
- 使用 CSS media query + JS 响应式检测

**AgentChat 改造：**

- 桌面：会话侧栏 220px 正常展示
- 移动端：会话侧栏隐藏，通过按钮唤出为 `el-drawer`
- 消息区取消 `max-width: 900px` 限制，全屏展示
- 快捷提问区域在移动端改为横向滚动

**Dashboard 改造：**

- 桌面：图表按设计稿排列（2列 / 1列）
- 移动端：所有卡片和图表单列堆叠，图表高度自适应

**LoginView 改造：**

- 登录卡片宽度从固定 400px 改为 `width: 90%; max-width: 400px`

**UserManage 改造：**

- 移动端表格启用横向滚动（`el-table` 的 `stripe` 属性保留）
- 操作列固定到右侧

### 3b：个人中心

**新路由：** `/profile`

**新组件：** `frontend/src/components/ProfileView.vue`

**页面结构：**

```
┌─────────────────────────────────┐
│  头像（大尺寸）                    │
│  用户名 (角色标签)                 │
├─────────────────────────────────┤
│  个人信息                         │
│  ┌───────────────────────────┐  │
│  │ 邮箱: [可编辑输入框]        │  │
│  │ 手机号: [可编辑输入框]      │  │
│  │        [保存修改]           │  │
│  └───────────────────────────┘  │
├─────────────────────────────────┤
│  修改密码                         │
│  ┌───────────────────────────┐  │
│  │ 旧密码: [输入框]            │  │
│  │ 新密码: [输入框]            │  │
│  │ 确认密码: [输入框]          │  │
│  │        [修改密码]           │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

**后端新增端点：**

| 方法 | 路径 | 功能 | 权限 |
|------|------|------|------|
| PUT | `/api/users/me` | 更新个人信息（邮箱、手机号） | 所有已登录用户 |
| PUT | `/api/users/me/password` | 修改密码 | 所有已登录用户 |

**修改密码逻辑：**
- 验证旧密码正确
- 新密码最少 6 位
- 更新 hashed_password

**文件变更：**

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `frontend/src/components/ProfileView.vue` | 个人中心页面 |
| 修改 | `frontend/src/router/index.ts` | 新增 `/profile` 路由 |
| 修改 | `frontend/src/layouts/MainLayout.vue` | 侧栏新增"个人中心"入口 + 响应式改造 |
| 修改 | `frontend/src/components/AgentChat.vue` | 响应式改造 |
| 修改 | `frontend/src/components/LoginView.vue` | 响应式改造 |
| 修改 | `frontend/src/components/UserManage.vue` | 响应式改造 |
| 修改 | `backend/app/users/router.py` | 新增 PUT /me 和 PUT /me/password |
| 修改 | `backend/app/users/schemas.py` | 新增 UpdateProfileRequest, ChangePasswordRequest |
| 修改 | `backend/app/users/service.py` | 新增 update_profile, change_password |

---

## 错误处理

- Dashboard API 查询失败时，前端显示空状态提示（`el-empty`）
- 个人中心修改密码失败时，显示具体错误（旧密码错误 / 格式不对）
- 响应式断点检测使用 `window.matchMedia`，不依赖第三方库

## 测试策略

- 手动验证：两种主题下所有页面的颜色一致性
- 手动验证：768px 断点两侧布局正确
- 手动验证：Dashboard 数据加载和图表渲染
- 手动验证：个人中心信息修改和密码修改流程
