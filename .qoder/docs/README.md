# 文档索引

本目录存放各子项目的设计说明、实施计划与实现说明。文档只在本机保留，不随仓库分发。

| 子项目 | 文档 | 说明 |
|--------|------|------|
| ai-chat-lite | [设计说明](./ai-chat-lite-设计说明.md) | 功能定位、数据模型、API 契约、流任务管理（方案 A）、SSE 事件编码、前端解析、测试策略 |
| ai-chat-lite | [实施计划](./ai-chat-lite-实施计划.md) | 按 TDD 拆分的 10 个任务：骨架 → 认证 → 会话 → 流式客户端 → 流任务 → 消息接口 → 前端 → 收尾验证 |
| ai-stream-demo | [设计说明](./ai-stream-demo-设计说明.md) | 流式接口封装：SSE 线格式、CORS 预检、finally 哨兵、坑位清单与测试策略 |
| ai-stream-demo | [实施计划](./ai-stream-demo-实施计划.md) | 7 个 TDD 任务：骨架 → CORS → 正常流 → 异常收敛 → 流前校验 → 前端 → 收尾 |
| ai-stream-demo | [实现说明](./ai-stream-demo-实现说明.md) | 代码地图、数据链路、请求体与 SSE 线格式契约、不变量、接口与调度、验证与排障 |
| local-pdf-rag | [设计说明](./local-pdf-rag-设计说明.md) | 本地 PDF RAG 基础版：解析/切分/向量化/JSON 存储/余弦 Top-4/生成，含生产存储迁移说明 |
| local-pdf-rag | [实施计划](./local-pdf-rag-实施计划.md) | 9 个 TDD 任务：骨架 → 切分/余弦 → JSON 存储 → PDF 解析 → Ollama 客户端 → RAG 编排 → API → 前端/假 Ollama → 收尾 |
| local-pdf-rag | [实现说明](./local-pdf-rag-实现说明.md) | 代码地图、数据链路、JSON 表结构、口径与不变量、接口与调度、验证与排障 |
| multi-agent-research | [设计说明](./multi-agent-research-设计说明.md) | 多 Agent 调研报告编排：五角色、状态机与大纲暂停点、BM25 检索、数据模型、API/SSE、测试策略与范围边界 |
| multi-agent-research | [实施计划](./multi-agent-research-实施计划.md) | 16 个 TDD 任务：骨架/配置 → 六表 → 切分分词 → BM25 → 入库 → LLM 客户端 → 五个 Agent → 状态机 → Runner → API → SSE → 前端三列 → 文档收尾 |
