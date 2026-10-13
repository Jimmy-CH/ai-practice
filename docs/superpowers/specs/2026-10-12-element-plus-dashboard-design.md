# Element Plus 企业级运营后台设计

## 目标

将 content-ops-agent 前端改造为企业级内容运营后台，使用 Element Plus 提供完整导航、项目管理、来源导入、资产审核与交付体验，保持现有 API 与 Vue Router 路由语义。

## 布局

应用使用 `ElContainer`：深蓝侧栏固定导航，顶部 `ElHeader` 显示产品名与当前工作区，`ElMain` 放置页面内容。全局使用浅灰背景、白色卡片、统一间距与响应式网格。

## 页面

- 项目中心：`ElStatistic` 概览卡片、`ElTable` 项目列表、`ElDialog` + `ElForm` 创建项目。
- 来源中心：`ElSteps` 工作流、`ElCard` 资料输入、来源状态列表及 `ElButton` 触发生成。
- 创作工作台：`ElTabs` 展示公告/FAQ/海报，`ElTag` 展示状态；审核、下载与模拟发布使用主要操作栏，引用在 `ElDrawer` 查看。

## 状态与错误

请求期间以 `ElLoading` 显示忙碌状态；成功与失败使用 `ElMessage`；空资产使用 `ElEmpty`；关键失败使用 `ElResult`。所有按钮在请求中禁用，避免重复提交。

## 验证

构建必须通过 `npm run build`。页面组件测试覆盖项目创建弹窗、来源生成按钮 loading 状态、未审核资产不能下载、审核通过后显示交付操作。
