# content-workbench Playwright E2E 测试实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 content-workbench 建立可重复运行的 Playwright 浏览器端到端测试，覆盖从编辑登录、项目管理、资料录入、资产生成、审核、发布到审计日志的完整链路。

**Architecture:** 新增 `frontend/e2e/` 测试目录，采用 Page Object 模式封装 Element Plus 页面交互；新增 `backend/app/e2e_main.py` 入口在测试后端中注入 FakeGenerator；通过 `npm run test:e2e` 脚本自动管理前后端进程、运行 Playwright 并清理数据。

**Tech Stack:** Playwright + TypeScript，后端 FastAPI + SQLite，前端 Vue 3 + Vite + Element Plus。

---

## 文件结构

```
content-workbench/
├── backend/
│   ├── app/
│   │   └── e2e_main.py              # E2E 后端入口：覆盖 get_generator 为 FakeGenerator
│   └── e2e.db                       # 测试数据库（临时创建，测试后删除）
└── frontend/
    ├── e2e/
    │   ├── fixtures/
    │   │   └── users.ts             # 测试账号
    │   ├── helpers/
    │   │   ├── api.ts               # 基于 fetch 的数据清理
    │   │   └── setup.ts             # 启动/停止前后端服务
    │   ├── pages/
    │   │   ├── login.page.ts        # 登录页 PO
    │   │   ├── projects.page.ts     # 项目列表 PO
    │   │   ├── sources.page.ts      # 资料中心 PO
    │   │   ├── workspace.page.ts    # 创作工作台 PO
    │   │   ├── review.page.ts       # 审核工作台 PO
    │   │   └── delivery.page.ts     # 发布任务页 PO
    │   ├── specs/
    │   │   └── full-lifecycle.spec.ts
    │   └── global-setup.ts          # Playwright global setup：启动服务
    ├── playwright.config.ts         # Playwright 配置
    └── package.json                 # 新增 devDeps 与 scripts
```

---

### Task 1: 创建后端 E2E 入口

**Files:**
- Create: `content-workbench/backend/app/e2e_main.py`

- [ ] **Step 1: 写入 e2e_main.py**

```python
import os

# 强制使用独立测试数据库
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./e2e.db")

from app.main import app
from app.api.generation import get_generator
from app.services.generation import FakeGenerator

app.dependency_overrides[get_generator] = lambda: FakeGenerator()
```

- [ ] **Step 2: 验证语法**

Run:
```powershell
cd D:\StudyProjects\ai-practice\content-workbench\backend
.\venv\Scripts\python -c "import app.e2e_main; print('ok')"
```

Expected: 输出 `ok`，无异常。

- [ ] **Step 3: 验证服务可启动**

Run:
```powershell
cd D:\StudyProjects\ai-practice\content-workbench\backend
Remove-Item -ErrorAction SilentlyContinue .\e2e.db
$env:DATABASE_URL="sqlite+aiosqlite:///./e2e.db"
.\venv\Scripts\python -m uvicorn app.e2e_main:app --host 127.0.0.1 --port 8000
```

在另一个终端验证：
```powershell
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/auth/me').status)"
```

Expected: 返回 `401`（未认证访问被拦截，说明服务正常）。

---

### Task 2: 安装 Playwright 依赖

**Files:**
- Modify: `content-workbench/frontend/package.json`

- [ ] **Step 1: 安装依赖**

Run:
```powershell
cd D:\StudyProjects\ai-practice\content-workbench\frontend
npm install -D @playwright/test
npx playwright install chromium
```

- [ ] **Step 2: 更新 package.json scripts**

在 `scripts` 中新增：

```json
{
  "test:e2e": "node ./e2e/helpers/setup.js && npx playwright test",
  "test:e2e:ui": "node ./e2e/helpers/setup.js && npx playwright test --ui"
}
```

说明：`setup.js` 是 `setup.ts` 的编译后产物（或直接用 Node 脚本）。为简化执行，本计划直接使用 JavaScript 编写 `setup.js`。

---

### Task 3: 配置 Playwright

**Files:**
- Create: `content-workbench/frontend/playwright.config.ts`

- [ ] **Step 1: 写入 playwright.config.ts**

```typescript
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e/specs',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
```

- [ ] **Step 2: 验证配置**

Run:
```powershell
cd D:\StudyProjects\ai-practice\content-workbench\frontend
npx playwright test --list
```

Expected: 显示 `Total: 0 tests in 1 file` 或类似（因为还没有 spec 文件）。

---

### Task 4: 创建测试账号常量

**Files:**
- Create: `content-workbench/frontend/e2e/fixtures/users.ts`

- [ ] **Step 1: 写入 users.ts**

```typescript
export const EDITOR = { username: 'editor', password: 'editor123' }
export const REVIEWER = { username: 'reviewer', password: 'review123' }
```

---

### Task 5: 创建数据清理辅助函数

**Files:**
- Create: `content-workbench/frontend/e2e/helpers/api.ts`

- [ ] **Step 1: 写入 api.ts**

```typescript
export async function loginApi(username: string, password: string): Promise<string> {
  const response = await fetch('http://127.0.0.1:8000/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) throw new Error(`登录失败: ${response.status}`)
  const data = await response.json()
  return data.token as string
}

export async function cleanupProjects(prefix = 'e2e-'): Promise<void> {
  const token = await loginApi('editor', 'editor123')
  const response = await fetch('http://127.0.0.1:8000/api/projects', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error(`获取项目失败: ${response.status}`)
  const projects = (await response.json()) as Array<{ id: string; name: string }>
  for (const project of projects) {
    if (project.name.startsWith(prefix)) {
      const deleteResponse = await fetch(`http://127.0.0.1:8000/api/projects/${project.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!deleteResponse.ok) throw new Error(`删除项目失败: ${deleteResponse.status}`)
    }
  }
}
```

---

### Task 6: 创建启动/停止脚本

**Files:**
- Create: `content-workbench/frontend/e2e/helpers/setup.js`

- [ ] **Step 1: 写入 setup.js**

```javascript
const { spawn } = require('child_process')
const path = require('path')
const fs = require('fs')
const http = require('http')

const backendRoot = path.resolve(__dirname, '../../../backend')
const frontendRoot = path.resolve(__dirname, '../..')
const dbPath = path.join(backendRoot, 'e2e.db')

function waitForUrl(url, timeout = 30000) {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    function probe() {
      http.get(url, (res) => {
        if (res.statusCode !== undefined) {
          resolve()
        } else {
          retry()
        }
      }).on('error', retry)
    }
    function retry() {
      if (Date.now() - start > timeout) {
        reject(new Error(`等待 ${url} 超时`))
        return
      }
      setTimeout(probe, 500)
    }
    probe()
  })
}

function startBackend() {
  if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath)
  const env = { ...process.env, DATABASE_URL: 'sqlite+aiosqlite:///./e2e.db' }
  const proc = spawn(path.join(backendRoot, 'venv/Scripts/python.exe'), ['-m', 'uvicorn', 'app.e2e_main:app', '--host', '127.0.0.1', '--port', '8000'], {
    cwd: backendRoot,
    env,
    stdio: 'inherit',
    shell: true,
  })
  return proc
}

function startFrontend() {
  const proc = spawn('npm', ['run', 'dev', '--', '--port', '5173'], {
    cwd: frontendRoot,
    stdio: 'inherit',
    shell: true,
  })
  return proc
}

async function main() {
  const backend = startBackend()
  await waitForUrl('http://127.0.0.1:8000/api/auth/me')
  const frontend = startFrontend()
  await waitForUrl('http://127.0.0.1:5173/')

  function shutdown() {
    backend.kill('SIGTERM')
    frontend.kill('SIGTERM')
    if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath)
  }

  process.on('SIGINT', shutdown)
  process.on('SIGTERM', shutdown)

  // 保持脚本运行，Playwright 测试结束后由用户手动停止
  // 实际通过 package.json test:e2e 脚本：setup.js 启动服务并保持，Playwright 运行在同一进程组
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
```

说明：此脚本仅启动服务并保持运行。`npm run test:e2e` 需要更完善的进程管理。实际实现时建议将启动脚本与 Playwright `globalSetup`/`globalTeardown` 结合，确保测试结束后自动关闭服务。

---

### Task 7: 使用 Playwright globalSetup/globalTeardown 管理服务

**Files:**
- Create: `content-workbench/frontend/e2e/global-setup.ts`
- Create: `content-workbench/frontend/e2e/global-teardown.ts`
- Modify: `content-workbench/frontend/playwright.config.ts`

- [ ] **Step 1: 写入 global-setup.ts**

```typescript
import { spawn } from 'child_process'
import path from 'path'
import fs from 'fs'
import http from 'http'

const backendRoot = path.resolve(__dirname, '../../backend')
const dbPath = path.join(backendRoot, 'e2e.db')

function waitForUrl(url: string, timeout = 30000): Promise<void> {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    function probe() {
      http.get(url, (res) => {
        if (res.statusCode !== undefined) {
          resolve()
        } else {
          retry()
        }
      }).on('error', retry)
    }
    function retry() {
      if (Date.now() - start > timeout) {
        reject(new Error(`等待 ${url} 超时`))
        return
      }
      setTimeout(probe, 500)
    }
    probe()
  })
}

export default async function globalSetup() {
  if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath)

  const backend = spawn(path.join(backendRoot, 'venv/Scripts/python.exe'), ['-m', 'uvicorn', 'app.e2e_main:app', '--host', '127.0.0.1', '--port', '8000'], {
    cwd: backendRoot,
    env: { ...process.env, DATABASE_URL: 'sqlite+aiosqlite:///./e2e.db' },
    stdio: 'ignore',
    shell: true,
  })
  ;(globalThis as any).__E2E_BACKEND__ = backend

  await waitForUrl('http://127.0.0.1:8000/api/auth/me')

  const frontend = spawn('npm', ['run', 'dev', '--', '--port', '5173'], {
    cwd: path.resolve(__dirname, '..'),
    stdio: 'ignore',
    shell: true,
  })
  ;(globalThis as any).__E2E_FRONTEND__ = frontend

  await waitForUrl('http://127.0.0.1:5173/')
}
```

- [ ] **Step 2: 写入 global-teardown.ts**

```typescript
import { ChildProcess } from 'child_process'
import path from 'path'
import fs from 'fs'

const backendRoot = path.resolve(__dirname, '../../backend')
const dbPath = path.join(backendRoot, 'e2e.db')

export default async function globalTeardown() {
  const backend: ChildProcess = (globalThis as any).__E2E_BACKEND__
  const frontend: ChildProcess = (globalThis as any).__E2E_FRONTEND__
  if (frontend) frontend.kill('SIGTERM')
  if (backend) backend.kill('SIGTERM')
  await new Promise((resolve) => setTimeout(resolve, 1000))
  if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath)
}
```

- [ ] **Step 3: 修改 playwright.config.ts**

```typescript
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e/specs',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'list',
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
```

- [ ] **Step 4: 删除 setup.js（已用 globalSetup 替代）**

Run:
```powershell
Remove-Item D:\StudyProjects\ai-practice\content-workbench\frontend\e2e\helpers\setup.js
```

- [ ] **Step 5: 更新 package.json scripts**

```json
{
  "test:e2e": "npx playwright test",
  "test:e2e:ui": "npx playwright test --ui"
}
```

---

### Task 8: 创建登录页 Page Object

**Files:**
- Create: `content-workbench/frontend/e2e/pages/login.page.ts`

- [ ] **Step 1: 写入 login.page.ts**

```typescript
import type { Page } from '@playwright/test'

export class LoginPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/login')
  }

  async login(username: string, password: string) {
    await this.page.fill('input[type="text"]', username)
    await this.page.fill('input[type="password"]', password)
    await this.page.click('button:has-text("登录")')
    await this.page.waitForURL(/\/(projects|review)/)
  }
}
```

---

### Task 9: 创建项目列表 Page Object

**Files:**
- Create: `content-workbench/frontend/e2e/pages/projects.page.ts`

- [ ] **Step 1: 写入 projects.page.ts**

```typescript
import type { Page } from '@playwright/test'

export class ProjectsPage {
  constructor(private page: Page) {}

  async create(name: string, theme: string, audience: string, tone: string) {
    await this.page.click('button:has-text("新建项目")')
    await this.page.fill('.el-dialog__wrapper:visible input[type="text"] >> nth=0', name)
    await this.page.fill('.el-dialog__wrapper:visible textarea', theme)
    const inputs = this.page.locator('.el-dialog__wrapper:visible input[type="text"]')
    await inputs.nth(1).fill(audience)
    await inputs.nth(2).fill(tone)
    await this.page.click('.el-dialog__footer button:has-text("创建")')
    await this.page.waitForTimeout(500)
  }

  async openSources(projectName: string) {
    const row = this.page.locator('.el-table__row', { hasText: projectName })
    await row.locator('button:has-text("资料")').click()
    await this.page.waitForURL(/\/projects\/.*\/sources/)
  }

  async openWorkspace(projectName: string) {
    const row = this.page.locator('.el-table__row', { hasText: projectName })
    await row.locator('button:has-text("工作台")').click()
    await this.page.waitForURL(/\/projects\/.*\/workspace/)
  }
}
```

---

### Task 10: 创建资料中心 Page Object

**Files:**
- Create: `content-workbench/frontend/e2e/pages/sources.page.ts`

- [ ] **Step 1: 写入 sources.page.ts**

```typescript
import type { Page } from '@playwright/test'

export class SourcesPage {
  constructor(private page: Page) {}

  async add(name: string, content: string) {
    await this.page.fill('input[placeholder="资料名称"]', name)
    await this.page.fill('textarea', content)
    await this.page.click('button:has-text("添加资料")')
    await this.page.waitForTimeout(500)
  }

  async view(name: string) {
    const row = this.page.locator('.el-table__row', { hasText: name })
    await row.locator('button:has-text("查看")').click()
    await this.page.waitForTimeout(300)
  }

  async gotoWorkspace() {
    await this.page.click('button:has-text("工作台")')
    await this.page.waitForURL(/\/projects\/.*\/workspace/)
  }
}
```

---

### Task 11: 创建工作台 Page Object

**Files:**
- Create: `content-workbench/frontend/e2e/pages/workspace.page.ts`

- [ ] **Step 1: 写入 workspace.page.ts**

```typescript
import type { Page } from '@playwright/test'

export class WorkspacePage {
  constructor(private page: Page) {}

  async generate() {
    await this.page.click('button:has-text("一键生成")')
    await this.page.waitForTimeout(1000)
  }

  async editFaq(question: string, answer: string) {
    await this.page.click('.el-tabs__item:has-text("FAQ")')
    await this.page.waitForTimeout(300)
    await this.page.fill('.el-tab-pane:visible input[type="text"]', question)
    await this.page.fill('.el-tab-pane:visible textarea', answer)
    await this.page.click('.el-tab-pane:visible button:has-text("保存")')
    await this.page.waitForTimeout(500)
  }

  async submit(kindLabel: string) {
    await this.page.click(`.el-tabs__item:has-text("${kindLabel}")`)
    await this.page.waitForTimeout(300)
    await this.page.click('.el-tab-pane:visible button:has-text("提交审核")')
    await this.page.waitForTimeout(500)
  }
}
```

---

### Task 12: 创建审核工作台 Page Object

**Files:**
- Create: `content-workbench/frontend/e2e/pages/review.page.ts`

- [ ] **Step 1: 写入 review.page.ts**

```typescript
import type { Page } from '@playwright/test'

export class ReviewPage {
  constructor(private page: Page) {}

  async approveFirst(comment = '通过') {
    const row = this.page.locator('.el-table__row').first()
    await row.locator('button:has-text("通过")').click()
    await this.page.waitForTimeout(500)
  }
}
```

---

### Task 13: 创建发布任务页 Page Object

**Files:**
- Create: `content-workbench/frontend/e2e/pages/delivery.page.ts`

- [ ] **Step 1: 写入 delivery.page.ts**

```typescript
import type { Page } from '@playwright/test'

export class DeliveryPage {
  constructor(private page: Page) {}

  async downloadMarkdown(projectName: string) {
    const row = this.page.locator('.el-table__row', { hasText: projectName })
    const [download] = await Promise.all([
      this.page.waitForEvent('download'),
      row.locator('button:has-text("Markdown")').click(),
    ])
    await download.path()
  }

  async publish(projectName: string) {
    const row = this.page.locator('.el-table__row', { hasText: projectName })
    await row.locator('button:has-text("模拟发布")').click()
    await this.page.waitForTimeout(500)
  }
}
```

---

### Task 14: 创建完整生命周期 E2E 测试

**Files:**
- Create: `content-workbench/frontend/e2e/specs/full-lifecycle.spec.ts`

- [ ] **Step 1: 写入 full-lifecycle.spec.ts**

```typescript
import { test, expect } from '@playwright/test'
import { cleanupProjects } from '../helpers/api'
import { EDITOR, REVIEWER } from '../fixtures/users'
import { LoginPage } from '../pages/login.page'
import { ProjectsPage } from '../pages/projects.page'
import { SourcesPage } from '../pages/sources.page'
import { WorkspacePage } from '../pages/workspace.page'
import { ReviewPage } from '../pages/review.page'
import { DeliveryPage } from '../pages/delivery.page'

test.beforeAll(async () => {
  await cleanupProjects('e2e-')
})

test.afterAll(async () => {
  await cleanupProjects('e2e-')
})

test('完整内容生产发布链路', async ({ page }) => {
  const projectName = `e2e-${Date.now()}`
  const login = new LoginPage(page)
  const projects = new ProjectsPage(page)
  const sources = new SourcesPage(page)
  const workspace = new WorkspacePage(page)
  const review = new ReviewPage(page)
  const delivery = new DeliveryPage(page)

  // 1. 编辑登录
  await login.goto()
  await login.login(EDITOR.username, EDITOR.password)
  await expect(page).toHaveURL('/projects')

  // 2. 创建项目
  await projects.create(projectName, 'AI 内容生成', '企业用户', '专业')
  await expect(page.locator('.el-table__body')).toContainText(projectName)

  // 3. 添加资料并查看内容
  await projects.openSources(projectName)
  await sources.add('产品手册', '本产品面向企业用户，支持 AI 内容生成与一键发布。')
  await expect(page.locator('.el-table__body')).toContainText('产品手册')
  await sources.view('产品手册')
  await expect(page.locator('.el-dialog__body')).toContainText('本产品面向企业用户')

  // 4. 一键生成
  await sources.gotoWorkspace()
  await workspace.generate()
  await expect(page.locator('.el-tabs__nav')).toContainText('公告')
  await expect(page.locator('.el-tabs__nav')).toContainText('FAQ')
  await expect(page.locator('.el-tabs__nav')).toContainText('海报文案')

  // 5. 编辑并提交
  await workspace.editFaq('什么是本产品？', '面向企业用户的 AI 内容生成工具。')
  await workspace.submit('FAQ')

  // 6. 审核员通过
  await login.goto()
  await login.login(REVIEWER.username, REVIEWER.password)
  await expect(page).toHaveURL('/review')
  await review.approveFirst()

  // 7. 编辑下载与发布
  await login.goto()
  await login.login(EDITOR.username, EDITOR.password)
  await page.goto('/delivery')
  await delivery.downloadMarkdown(projectName)
  await delivery.publish(projectName)
  await expect(page.locator('.el-table__body')).toContainText(projectName)

  // 8. 审计日志
  await login.goto()
  await login.login(REVIEWER.username, REVIEWER.password)
  await page.goto('/delivery')
  await page.click('.el-tabs__item:has-text("审计日志")')
  const auditTable = page.locator('.el-table__body')
  await expect(auditTable).toContainText('generate')
  await expect(auditTable).toContainText('submit')
  await expect(auditTable).toContainText('review')
  await expect(auditTable).toContainText('download')
  await expect(auditTable).toContainText('deliver')
})
```

---

### Task 15: 运行并修复 E2E 测试

**Files:**
- Modify: 根据运行结果调整 Page Object 或 spec

- [ ] **Step 1: 启动测试**

Run:
```powershell
cd D:\StudyProjects\ai-practice\content-workbench\frontend
npm run test:e2e
```

- [ ] **Step 2: 根据失败信息调整选择器**

常见修复：
- Element Plus 表格行选择器可能需改为 `.el-table__row`
- 对话框输入框可能需要更精确的定位，如 `.el-dialog input`
- Tabs 标签文本可能需要等待动画结束
- 提交审核按钮可能在资产状态为 draft 或 rejected 时才出现

- [ ] **Step 3: 验证最终通过**

Expected: `1 passed`（或更多补充用例全部通过）。

---

## 自我审查

### 1. Spec 覆盖度

| Spec 要求 | 对应任务 |
|---|---|
| 后端 E2E 入口覆盖 FakeGenerator | Task 1 |
| 独立测试数据库 | Task 1, Task 7 |
| 启动/停止前后端服务 | Task 7 |
| 登录与角色路由 | Task 8, Task 14 |
| 项目管理 | Task 9, Task 14 |
| 资料中心 | Task 10, Task 14 |
| 创作与生成 | Task 11, Task 14 |
| 审核流程 | Task 12, Task 14 |
| 发布与下载 | Task 13, Task 14 |
| 审计日志 | Task 14 |
| 数据清理 | Task 5, Task 14 |

### 2. Placeholder 检查

计划中无 `TBD`、`TODO`、未填写的代码块。所有 PO 和 spec 均给出具体实现。

### 3. 类型一致性

- `cleanupProjects` 在 `api.ts` 和 `full-lifecycle.spec.ts` 中签名一致。
- `LoginPage.login` 在 Task 8 和 Task 14 中使用方式一致。
- Page Object 构造函数统一为 `(page: Page)`。

---

## 执行交接

**Plan complete and saved to `docs/superpowers/plans/2026-10-13-content-workbench-playwright-e2e.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
