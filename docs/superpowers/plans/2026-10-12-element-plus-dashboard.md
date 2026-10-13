# Element Plus 企业级后台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 Element Plus 重写 content-ops-agent 前端为企业级内容运营后台。

**Architecture:** 在 `main.ts` 全局安装 Element Plus，`App.vue` 提供容器布局与导航，各业务视图改用 Element Plus 表单、表格、卡片、步骤、标签和反馈组件，保留现有 API。

**Tech Stack:** Vue 3、TypeScript、Vite、Vue Router、Axios、Element Plus。

---

### Task 1: 安装主题与应用壳

**Files:**
- Modify: `content-ops-agent/frontend/package.json`
- Modify: `content-ops-agent/frontend/src/main.ts`
- Modify: `content-ops-agent/frontend/src/App.vue`
- Create: `content-ops-agent/frontend/src/styles/theme.css`

- [ ] 添加 `element-plus` 与 `@element-plus/icons-vue`，运行 `npm install`。
- [ ] 在 `main.ts` 导入 `ElementPlus` 和 `element-plus/dist/index.css`，调用 `app.use(ElementPlus)`。
- [ ] 用 `ElContainer`、`ElAside`、`ElHeader`、`ElMain` 重写应用壳，侧栏使用 `ElMenu` 导航项目中心、来源中心与创作工作台；theme.css 定义深蓝侧栏、浅灰背景、卡片间距。
- [ ] 运行 `npm run build`，确认通过并提交 `feat: add Element Plus application shell`。

### Task 2: 项目中心

**Files:**
- Modify: `content-ops-agent/frontend/src/views/ProjectListView.vue`

- [ ] 创建失败组件测试，断言点击“新建项目”显示 `ElDialog`。
- [ ] 用 `ElRow`/`ElCol`/`ElCard` 展示项目、待审核、已交付统计；用 `ElTable` 展示项目，并以 `ElDialog` + `ElForm` 创建项目。
- [ ] 为加载、空列表和 API 失败使用 `ElSkeleton`、`ElEmpty`、`ElMessage`。
- [ ] 运行组件测试和 `npm run build`，提交 `feat: redesign project center`。

### Task 3: 来源中心

**Files:**
- Modify: `content-ops-agent/frontend/src/views/SourceCenterView.vue`

- [ ] 创建失败组件测试，断言生成请求期间生成按钮 loading。
- [ ] 使用 `ElSteps` 呈现“导入资料—生成内容—审核交付”，用 `ElCard`、`ElForm`、`ElInput type=textarea` 收集资料，以 `ElButton` 执行导入与生成。
- [ ] 对成功、失败和 loading 使用 `ElMessage`/`ElAlert`/按钮 `loading`，生成成功后展示进入工作台按钮。
- [ ] 运行测试和构建，提交 `feat: redesign source center`。

### Task 4: 创作审核工作台

**Files:**
- Modify: `content-ops-agent/frontend/src/views/WorkspaceView.vue`

- [ ] 创建失败组件测试，断言 draft 资产没有下载按钮，approved 资产有下载与模拟发布按钮。
- [ ] 使用 `ElTabs` 分类展示公告、FAQ、海报；资产卡片使用 `ElCard`，状态使用 `ElTag`，引用使用 `ElDrawer`。
- [ ] 使用 `ElButton`、`ElPopconfirm` 完成审核/下载/模拟发布；异步操作使用 `ElLoading` 和 `ElMessage`，无资产使用 `ElEmpty`。
- [ ] 运行测试和构建，提交 `feat: redesign content workspace`。

### Task 5: 最终验证

**Files:**
- Modify: `content-ops-agent/README.md`

- [ ] 更新 README，说明 Element Plus 依赖与页面入口。
- [ ] 运行 `cd content-ops-agent/frontend; npm run build`。
- [ ] 运行 `cd content-ops-agent/backend; python -m pytest tests -v`。
- [ ] 确认通过后提交 `docs: document Element Plus dashboard`。
