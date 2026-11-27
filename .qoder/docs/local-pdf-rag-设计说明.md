# local-pdf-rag 设计说明

## 1. 功能定位

`local-pdf-rag` 是 AI Practice 项目集中的「RAG 基础版」子项目：把 PDF 文档变成可问答的本地知识库，完整串起 **解析 → 切分 → 向量化 → 本地存储 → 相似度检索 → 生成** 六个环节。

技术栈：FastAPI、pypdf、Ollama（本地推理）、BGE-M3（Embedding）、Qwen2.5 3B（生成）、原生 HTML。

与现有 `rag-knowledge-base` 的区别：后者用 LangChain + ChromaDB + HuggingFace/DeepSeek，功能更全；本项目刻意用 **pypdf + 纯 Python 余弦 + JSON 索引 + Ollama**，把每一步都暴露出来，便于理解与替换存储后端。

## 2. 范围与非目标

完成项：

- PDF 上传（单文件）、逐页解析、页码保留
- 字符级滑窗切分：默认 800 字符、重叠 100 字符，不跨页
- Ollama `/api/embed` 批量向量化（bge-m3）
- JSON 本地索引：文档元数据 + 片段 + 向量
- 余弦相似度排序，Top-4 片段作为上下文
- Ollama `/api/chat` 生成（qwen2.5:3b，非流式），返回答案与来源
- 多 PDF 共享知识库：列表、删除、跨文档检索
- 原生 HTML 单页：上传、文档列表、提问、答案与来源
- 存储抽象 `VectorStore`，为 Redis/PostgreSQL 迁移预留接口
- 假 Ollama 服务，便于无 Ollama 环境跑通全链路

非目标：

- 多轮对话历史、流式输出
- OCR、扫描版 PDF、表格结构化抽取
- 认证、多租户、并发上传限流
- 真正的 Redis/PostgreSQL 实现（本次只留接口与迁移说明）
- 前端框架与构建链

## 3. 目录结构

```
local-pdf-rag/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py              # pydantic-settings，显式 env_file
│   │   ├── schemas.py             # 请求/响应模型
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # VectorStore 协议 + 数据类
│   │   │   └── json_store.py      # JSON 实现（原子写 + 锁）
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── pdf_parser.py      # pypdf 逐页提取
│   │   │   └── chunker.py         # 滑窗切分 + 余弦工具
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ollama_client.py   # httpx 调 Ollama
│   │   │   └── rag_service.py     # 入库与问答编排
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes.py
│   │   └── main.py                # 装配 + StaticFiles
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── fixtures/sample.pdf
│   │   ├── test_chunker.py
│   │   ├── test_cosine.py
│   │   ├── test_json_store.py
│   │   ├── test_parser.py
│   │   ├── test_rag_service.py
│   │   └── test_api.py
│   ├── scripts/fake_ollama.py
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── .env.example
│   └── data/                      # 运行时生成 index.json，gitignore
├── frontend/index.html
└── README.md
```

## 4. 关键技术决策

| 决策 | 选择 | 被否决方案与理由 |
| --- | --- | --- |
| 架构 | 分层模块（config/storage/ingestion/services/api） | 单文件（难测、难迁移）；LangChain + Chroma（重复现有项目、偏离指定栈） |
| PDF 解析 | pypdf `PdfReader` 逐页 `extract_text()` | LangChain PyPDFLoader（多一层依赖，且要拆页元数据） |
| 切分 | 纯 Python 字符滑窗 | RecursiveCharacterTextSplitter（默认优先标点，难以精确保证 800/100） |
| 向量 | Ollama `/api/embed`（bge-m3） | sentence-transformers 本地加载（需下载模型与 torch，资源更重） |
| 检索 | 纯 Python 余弦 + 内存遍历 | Chroma/pgvector（基础版不需要，且掩盖余弦细节） |
| 存储 | 单 JSON 文件 + `VectorStore` 协议 | SQLite（引入 ORM，偏离“JSON → 生产迁移”的叙事） |
| 生成 | Ollama `/api/chat` 非流式 | 流式（单轮问答不需要，且需处理检索与流式的组合） |
| 前端 | 原生 HTML，同源托管 | Vue（构建链与体量不必要） |

## 5. 数据链路

```
上传
浏览器 ──multipart──▶ POST /api/documents
                          │ 校验扩展名/大小
                          ▼
                     PdfParser.parse_bytes()
                          │ list[(page_no, text)]
                          ▼
                     TextChunker.split()  # 800/100，逐页
                          │ list[ChunkPiece]
                          ▼
                     OllamaClient.embed(texts)  # POST /api/embed
                          │ list[vector]
                          ▼
                     JsonVectorStore.add_document()  # 原子写 index.json
                          ▼
                     返回 DocumentOut

问答
浏览器 ──JSON──▶ POST /api/ask {question}
                    │ 知识库为空 → 400
                    ▼
               OllamaClient.embed([question])
                    ▼
               JsonVectorStore.search(qvec, top_k=4)
                    │ 余弦降序，返回片段 + 分数
                    ▼
               组装带编号与 [文件名 p页码] 的上下文
                    ▼
               OllamaClient.chat(messages)  # POST /api/chat
                    ▼
               返回 {answer, sources[Top-4]}
```

## 6. 存储契约

`data/index.json`：

```json
{
  "version": 1,
  "documents": [
    {"id": "uuid", "filename": "a.pdf", "page_count": 3, "chunk_count": 12,
     "created_at": "2026-11-27T06:00:00Z"}
  ],
  "chunks": [
    {"id": "uuid", "doc_id": "uuid", "filename": "a.pdf", "page": 2, "index": 5,
     "start": 0, "end": 800, "text": "...", "embedding": [0.01, 0.02]}
  ]
}
```

`VectorStore` 协议（`storage/base.py`）：

```python
class VectorStore(Protocol):
    async def add_document(self, document: DocumentRecord, chunks: list[ChunkRecord]) -> None: ...
    async def list_documents(self) -> list[DocumentRecord]: ...
    async def delete_document(self, doc_id: str) -> bool: ...
    async def search(self, query_embedding: list[float], top_k: int) -> list[SearchHit]: ...
    async def counts(self) -> tuple[int, int]: ...
```

- JSON 实现内部 `asyncio.Lock` 串行化写操作。
- 落盘使用「同目录临时文件 + `os.replace`」，避免进程中断留下半截 JSON。
- 启动时若文件不存在则视为空库；JSON 损坏时抛错并在 health 中体现，不静默清空。
- 生产迁移：新增 `RedisVectorStore` / `PostgresVectorStore` 实现同一协议即可；Redis 承载会话缓存，PostgreSQL（pgvector）承载文档、片段与向量。

## 7. 切分与检索口径

**切分**：

- 输入：单页文本；参数 `size=800`、`overlap=100`，步长 `size - overlap = 700`。
- 从 `start=0` 开始，`end=min(start+size, len(text))`；不足一个 step 时结束。
- 片段做 `strip()`，空片段丢弃；保留原始 `start/end` 偏移。
- 重叠 100 字符只发生在同一页内；不跨页拼接，避免把两页语义缝在一起。
- `overlap >= size` 时直接 `ValueError`。

**检索**：

- 余弦相似度：`dot(a,b) / (||a|| * ||b||)`；任一范数为 0 返回 0.0；维度不一致抛 `ValueError`。
- 得分降序排序，取 `min(TOP_K, 片段总数)`。
- `sources` 中 `snippet` 取片段前 120 字符，便于前端展示。

## 8. Ollama 调用契约

Embedding：

```http
POST /api/embed
{"model": "bge-m3", "input": ["文本1", "文本2"]}

→ 200 {"embeddings": [[...], [...]]}
```

- 返回数量必须与输入数量一致，否则 `ollama_bad_response`。
- 所有向量维度必须一致且非空。

生成：

```http
POST /api/chat
{"model": "qwen2.5:3b", "stream": false,
 "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]}

→ 200 {"message": {"role": "assistant", "content": "..."}}
```

健康检查：`GET /api/tags`，只判断可达性，不在线校验模型是否已拉取（模型缺失会在实际调用时暴露为 `ollama_bad_response`）。

错误映射：

| 情况 | code |
| --- | --- |
| `httpx.ConnectError` / 超时 | `ollama_unreachable` |
| 非 200、JSON 解析失败、结构缺字段 | `ollama_bad_response` |

## 9. API 契约

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | `{status, ollama_reachable, embed_model, chat_model, documents, chunks}` |
| POST | `/api/documents` | multipart `file`；201 返回文档信息 |
| GET | `/api/documents` | 文档列表（按创建时间倒序） |
| DELETE | `/api/documents/{doc_id}` | 删除文档及其片段；204 |
| POST | `/api/ask` | `{question}` → `{answer, sources}` |

示例返回：

```json
{
  "answer": "根据文档…… [a.pdf p2]",
  "sources": [
    {"index": 1, "document_id": "uuid", "filename": "a.pdf", "page": 2,
     "score": 0.83, "snippet": "……"}
  ]
}
```

## 10. 异常与不变量

- 非 `.pdf` → `400 unsupported_file`；文件超过 `MAX_UPLOAD_MB` → `400 file_too_large`。
- 加密 PDF 或解析失败 → `400 parse_failed`；整份文档无可提取文本 → `400 empty_document`。
- 知识库为空时提问 → `400 empty_index`（提示先上传）。
- 空问题 → `400 empty_question`。
- Ollama 异常 → `502`，detail 区分 `ollama_unreachable` / `ollama_bad_response`。
- 向量数量/维度不一致 → 不写入任何片段（先全部校验再落盘）。
- 删除不存在的文档 → `404`。
- 所有写入成功后 `index.json` 必须是完整可解析的 JSON。

## 11. 前端

- 单页原生 HTML：上传区、文档列表（含删除）、提问区、答案区、来源列表、状态行。
- 与后端同源（`:8000`），API 使用相对路径，无 CORS。
- 上传后刷新列表；提问时禁用按钮，返回后渲染 `answer` 与 `sources`；错误显示 `detail`。
- 来源展示：`#index 文件名 p页码（score）` + 片段摘要。

## 12. 测试与验证

pytest + pytest-asyncio + `httpx.ASGITransport`，全部使用假 Ollama，不触网：

| 文件 | 覆盖 |
| --- | --- |
| `test_chunker.py` | 800/100 重叠、边界、空文本、overlap 非法 |
| `test_cosine.py` | 排序、正交/零向量、维度不一致 |
| `test_json_store.py` | 增删查、持久化往返、原子写后文件可解析 |
| `test_parser.py` | 真实 `sample.pdf` 提取文本与页码；加密/空文本错误 |
| `test_rag_service.py` | 入库向量数量一致、Top-4 数量、Prompt 含来源、空库拒绝 |
| `test_api.py` | 上传/列表/删除/问答/空库 400/非 PDF 400 |

真实联调两种方式：

1. **假 Ollama**：`python scripts/fake_ollama.py` 监听 `:11434`，后端照常启动，可完成浏览器全链路。
2. **真 Ollama**：安装 Ollama 后执行 `ollama pull bge-m3` 与 `ollama pull qwen2.5:3b`，无需改代码。

## 13. 配置与依赖

`.env.example`：

```ini
OLLAMA_BASE_URL=http://localhost:11434
EMBED_MODEL=bge-m3
CHAT_MODEL=qwen2.5:3b
CHUNK_SIZE=800
CHUNK_OVERLAP=100
TOP_K=4
MAX_UPLOAD_MB=20
OLLAMA_TIMEOUT=120
# INDEX_PATH=./data/index.json
```

依赖：`fastapi`、`uvicorn[standard]`、`pypdf`、`httpx`、`pydantic-settings`、`python-dotenv`、`python-multipart`、`pytest`、`pytest-asyncio`。

## 14. 运行与成功标准

```powershell
cd local-pdf-rag/backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8000
# 无 Ollama 时另开终端：
python scripts/fake_ollama.py
```

成功标准：

1. 上传示例 PDF 后，`GET /api/documents` 能看到文档与片段数。
2. 提问返回答案，`sources` 为 Top-4 且含文件名/页码/分数。
3. 删除文档后其片段不再参与检索。
4. `pytest` 全绿；假 Ollama 下浏览器可完成上传与问答。
