# 证据约束内容生成设计

## 目标

将 content-ops-agent 的占位文本拼接替换为 DeepSeek 驱动的、基于项目资料证据生成的公告、FAQ 与海报文案。所有生成结果必须引用项目资料；资料不足时拒绝生成且不保存草稿。

## 数据流

1. 读取当前项目的 `Source`。
2. 将内容按空行和句末标点拆分为候选段落。
3. 用项目主题、目标受众和资产类型关键词对段落评分，选择 Top-K 证据。
4. 将带来源 ID 的证据、主题和语气交给 `DeepSeekGenerator`。
5. 要求模型只输出 JSON，并为每个生成资产返回使用的来源 ID。
6. 校验 JSON 结构、资产字段和引用；校验失败或证据不足时返回 `422 需补充资料`，不创建 `ContentAsset`。
7. 校验成功后以模型返回的正文和引用创建资产。

## 模块边界

- `services/retrieval.py`：纯函数式段落切分、评分和证据选择，易于单测。
- `services/generation.py`：定义可注入的生成器协议、DeepSeek OpenAI-compatible 客户端和测试 Fake。
- `api/generation.py`：协调检索、生成、校验和持久化，不直接拼接来源正文。
- `config.py`：增加 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL` 与 `MAX_EVIDENCE_CHUNKS`。

## 约束与错误处理

系统提示词禁止使用未在证据中出现的产品事实。模型不能引用未知来源；非法 JSON、网络超时、空证据或字段缺失都返回可理解的 422/502 错误，不保存部分资产。API Key 仅从环境变量读取，绝不通过接口返回。

## 测试

使用 FakeGenerator 验证 Top-K 证据传入、正确 JSON 持久化和引用追溯；覆盖空资料拒答、模型非法 JSON、未知引用、调用失败。DeepSeek 客户端使用 httpx mock 验证请求格式，不在测试中调用外部服务。
