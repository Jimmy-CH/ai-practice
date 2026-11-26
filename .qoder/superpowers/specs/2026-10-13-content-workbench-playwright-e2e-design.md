# content-workbench Playwright 端到端测试设计

## 背景

content-workbench 后端已具备 15 个 pytest 测试文件，覆盖 API、服务、导出、发布、审计等模块，全量 45 个用例通过。前端已完成登录、项目列表、资料中心、创作工作台、审核工作台、发布/审计页的实现，`npm run build` 通过。但前端目前没有任何自动化测试，无法持续验证前后端集成的真实用户体验。

## 目标

为 content-workbench 引入可重复运行的 Playwright 浏览器端到端测试，模拟真实用户从登录到发布的完整内容生产链路，确保前端 UI、路由、状态管理与后端 API 的集成正确。

## 范围

### 纳入测试的业务流程

1. **登录与角色路由**：编辑（editor）和审核员（reviewer）分别登录后跳转至对应首页。
2. **项目管理**：编辑创建新项目，项目列表展示，删除项目。
3. **资料中心**：进入项目资料页，添加名称和内容的资料，资料列表更新；点击"查看"按钮，对话框显示资料原文。
4. **创作与生成**：在工作台点击"一键生成"，三类资产（announcement/faq/poster）生成成功并展示；编辑 FAQ/海报文案并保存，提交审核。
5. **审核流程**：审核员登录，审核工作台显示待审资产，审核通过后资产消失。
6. **发布与下载**：编辑登录，发布任务页显示已审核资产，下载 Markdown 文件，点击"模拟发布"，发布任务列表出现新记录。
7. **审计日志**：审核员登录，审计日志页记录生成、编辑、提交、审核、下载、发布等关键动作。

### 不纳入范围

- 支付、第三方 OAuth、真实渠道发布等本系统未涉及的功能。
- 性能测试、安全渗透测试、多浏览器兼容性矩阵（默认 Chromium）。

## 技术方案

### 选型

- **测试框架**：`@playwright/test`（官方推荐，TypeScript 原生支持，自动等待，Trace 与截图能力）。
- **浏览器**：Chromium（默认），后续可扩展 Firefox/WebKit。
- **测试目录**：`content-workbench/frontend/e2e/`，与单元测试目录分离。
- **运行脚本**：
  - `npm run test:e2e`：启动后端 + 前端，运行 Playwright，结束后关闭服务。
  - `npx playwright test`：在已手动启动服务时运行测试。
  - `npx playwright test --ui`：本地调试模式。

### 项目结构

```
content-workbench/frontend/
├── e2e/
│   ├── fixtures/
│   │   └── users.ts          # 测试账号常量（editor / reviewer）
│   ├── pages/
│   │   ├── login.page.ts     # 登录页 PO
│   │   ├── projects.page.ts  # 项目列表 PO
│   │   ├── sources.page.ts   # 资料中心 PO
│   │   ├── workspace.page.ts # 创作工作台 PO
│   │   ├── review.page.ts    # 审核工作台 PO
│   │   └── delivery.page.ts  # 发布任务页 PO
│   ├── helpers/
│   │   ├── api.ts            # 基于 fetch 的测试数据清理辅助
│   │   └── setup.ts          # 启动/停止前后端服务
│   ├── specs/
│   │   └── full-lifecycle.spec.ts  # 完整生命周期 E2E 用例
│   └── playwright.config.ts
├── package.json
└── ...
```

### 环境管理

- **后端**：在测试专用数据库启动 uvicorn，端口 `8000`。
  - 使用独立 SQLite 文件 `e2e.db`（位于 `backend/e2e.db`），避免污染开发数据库 `workbench.db`。
  - 通过环境变量 `DATABASE_URL=sqlite+aiosqlite:///./e2e.db` 覆盖 `.env` 配置。
  - 使用独立的 E2E 入口 `backend/app/e2e_main.py` 启动后端：导入 `app.main` 的 `app` 实例，并覆盖 `app.api.generation.get_generator` 依赖为 `FakeGenerator()`，确保生成服务不调用真实 DeepSeek API。该入口不修改业务代码。
- **前端**：`npm run dev -- --port 5173`，通过 `vite.config.ts` 代理 `/api` 到 `http://127.0.0.1:8000`。
- **`test:e2e` 脚本流程**：
  1. 清理并创建 `backend/e2e.db`。
  2. 启动后端（子进程）。
  3. 启动前端 dev server（子进程）。
  4. 等待服务可用（轮询 `http://127.0.0.1:8000/api/auth/login` 与前端首页）。
  5. 运行 `npx playwright test`。
  6. 关闭前后端子进程，清理 `backend/e2e.db`。

### 数据隔离

- 每个 `spec` 文件开始前，通过 API 清理所有测试创建的项目（按名称前缀 `e2e-` 匹配）。
- 测试用例之间使用不同的项目名（时间戳 + 随机数），避免并发冲突。
- 登录状态通过 `localStorage` 设置 token 实现快速切换角色，或在每个角色段落重新登录。

## 测试用例设计

### `full-lifecycle.spec.ts`

```ts
// 伪代码，仅描述断言点
test('完整内容生产发布链路', async ({ page }) => {
  // 1. 编辑登录
  await login(page, 'editor', 'editor123')
  await expect(page).toHaveURL('/projects')

  // 2. 创建项目
  const projectName = `e2e-${Date.now()}`
  await projectsPage.create(projectName, 'theme', 'audience', 'tone')
  await expect(projectsPage.table).toContainText(projectName)

  // 3. 添加资料并查看内容
  await projectsPage.openSources(projectName)
  await sourcesPage.add('产品手册', '本产品面向企业用户，支持 AI 内容生成。')
  await expect(sourcesPage.table).toContainText('产品手册')
  await sourcesPage.view('产品手册')
  await expect(page.locator('.el-dialog__body')).toContainText('本产品面向企业用户')

  // 4. 一键生成资产
  await sourcesPage.gotoWorkspace()
  await workspacePage.generate()
  await expect(workspacePage.tabs).toContainText('公告')
  await expect(workspacePage.tabs).toContainText('FAQ')
  await expect(workspacePage.tabs).toContainText('海报文案')

  // 5. 编辑并提交审核
  await workspacePage.editFaq([{ question: 'Q1', answer: 'A1' }])
  await workspacePage.submitAll()

  // 6. 审核员登录并审核通过
  await login(page, 'reviewer', 'review123')
  await page.goto('/review')
  await reviewPage.approveFirst('通过')
  await expect(reviewPage.table).not.toContainText(projectName)

  // 7. 编辑下载与发布
  await login(page, 'editor', 'editor123')
  await page.goto('/delivery')
  await deliveryPage.downloadMarkdown(projectName)
  await deliveryPage.publish(projectName)
  await expect(deliveryPage.deliveriesTable).toContainText(projectName)

  // 8. 审核员查看审计日志
  await login(page, 'reviewer', 'review123')
  await page.goto('/delivery')
  await expect(deliveryPage.auditTable).toContainText('generate')
  await expect(deliveryPage.auditTable).toContainText('submit')
  await expect(deliveryPage.auditTable).toContainText('review')
  await expect(deliveryPage.auditTable).toContainText('download')
  await expect(deliveryPage.auditTable).toContainText('deliver')
})
```

### 角色权限验证（可选补充用例）

- `reviewer` 直接访问 `/projects` 应被重定向到 `/login`。
- 未登录访问 `/review` 应被重定向到 `/login`。

## 与现有测试的关系

- Playwright E2E 测试补充真实浏览器和前后端联调覆盖，不替代后端 pytest 测试。
- 后端单元/集成测试继续负责状态机、边界条件、服务逻辑的快速验证。
- E2E 测试运行较慢，放在 CI 最后阶段或本地发布前回归。

## 风险与注意事项

1. **生成服务隔离**：必须确保 E2E 环境使用 `FakeGenerator`，否则测试会调用真实 DeepSeek API，产生费用并不可靠。
2. **端口占用**：`8000`/`5173` 可能被开发实例占用，脚本需检测并提供清理/重试机制。
3. **Element Plus 组件异步渲染**：表格、对话框、Tabs 的动画和异步加载需要 Playwright 的自动等待和显式 `expect` 断言。
4. **文件下载断言**：Playwright 下载事件需监听 `download` 事件并验证文件名。
5. **时间戳项目名**：审计日志按时间排序，断言时使用文本包含而非索引，避免时序抖动。

## 验收标准

- `npm run test:e2e` 在干净环境下成功运行，`full-lifecycle.spec.ts` 通过。
- 测试完成后 `backend/e2e.db` 被清理，不污染开发数据。
- 不修改业务代码，仅新增测试相关文件和脚本。
