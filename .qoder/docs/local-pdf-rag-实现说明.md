# local-pdf-rag 实现说明

## 1. 功能定位

`local-pdf-rag` 是本地 PDF 文档问答的 RAG 基础版，完整串起六个环节：

1. **解析**：pypdf 逐页提取文本，保留页码。
2. **切分**：字符级滑窗，默认 800 字符、重叠 100 字符，按页切分不跨页。
3. **向量化**：调用 Ollama `/api/embed`，默认 `bge-m3`。
4. **本地存储**：文档元数据、片段、向量写入 `data/index.json`。
5. **相似度检索**：纯 Python 余弦相似度排序，取 Top-4。
6. **生成**：调用 Ollama `/api/chat`，默认 `qwen2.5:3b`，返回答案与来源。

定位是「把每一步暴露出来」的教学版，与 `rag-knowledge-base`（LangChain + ChromaDB + OpenAI Embedding）形成对照。生产存储通过 `VectorStore` 协议预留替换点。

## 2. 代码地图

```
local-pdf-rag/
├── backend/
│   ├── app/
│   │   ├── config.py              # pydantic-settings，显式 env_file
│   │   ├── schemas.py             # AskRequest / DocumentOut / SourceOut / AskResponse / HealthOut
│   │   ├── storage/
│   │   │   ├── base.py            # DocumentRecord / ChunkRecord / SearchHit / VectorStore 协议
│   │   │   └── json_store.py      # JSON 实现：asyncio.Lock + 临时文件 + os.replace
│   │   ├── ingestion/
│   │   │   ├── pdf_parser.py      # PdfParser.parse_bytes -> list[PageText]
│   │   │   └── chunker.py         # TextChunker + cosine_similarity
│   │   ├── services/
│   │   │   ├── ollama_client.py   # embed / chat / ping，错误映射
│   │   │   └── rag_service.py     # ingest / ask / _build_messages / get_service
│   │   ├── api/routes.py          # 5 个接口
│   │   └── main.py                # FastAPI 装配 + StaticFiles
│   ├── tests/                     # 20 项 pytest
│   ├── scripts/fake_ollama.py     # 假 Ollama（:11434）
│   ├── requirements.txt
│   ├── pytest.ini                 # asyncio_mode=auto, pythonpath=.
│   └── .env.example
├── frontend/index.html            # 上传 + 文档列表 + 提问 + 答案/来源
└── README.md
```

关键入口：

- `get_service()`：`lru_cache` 单例，装配 `JsonVectorStore` 与 `OllamaClient`；测试用 `app.dependency_overrides` 替换。
- `RagService.ingest()`：解析 → 切分 → 批量 embed → 组装记录 → 落盘。
- `RagService.ask()`：空库校验 → 问题向量化 → 余弦检索 → 组装 Prompt → chat → 返回来源。

## 3. 数据链路

### 上传

```
前端 FormData
  -> POST /api/documents
  -> 校验 .pdf 扩展名与 MAX_UPLOAD_MB
  -> PdfParser.parse_bytes(bytes)
       逐页 extract_text()，返回 [(page, text)]
  -> TextChunker.split(page.text)
       800 字符窗口，步长 700，片段 strip，丢弃空片段
  -> OllamaClient.embed([片段文本...])
       POST /api/embed {"model":"bge-m3","input":[...]}
  -> 校验 embeddings 数量与维度
  -> JsonVectorStore.add_document(document, chunks)
       追加内存 -> 原子写 index.json
  -> 201 DocumentOut
```

### 问答

```
POST /api/ask {"question":"..."}
  -> question.strip()，空则 400 empty_question
  -> store.counts()，片段为 0 则 400 empty_index
  -> embed([question])[0]
  -> store.search(qvec, TOP_K=4)
       对每个片段算余弦，降序，截取 Top-4
  -> _build_messages(question, hits)
       system：只依据上下文回答，不足则拒答，引用标注 [文件名 p页码]
       user：带编号的上下文 + 问题
  -> OllamaClient.chat(messages)
       POST /api/chat {"model":"qwen2.5:3b","stream":false}
  -> 返回 answer + sources（index/doc_id/filename/page/score/snippet）
```

### 删除

`DELETE /api/documents/{doc_id}` → 同时移除 `documents` 与 `chunks` 中该文档的记录 → 原子写盘 → 204；不存在返回 404。

## 4. 表结构（JSON 索引）

`data/index.json`：

```json
{
  "version": 1,
  "documents": [
    {
      "id": "uuid-hex",
      "filename": "sample.pdf",
      "page_count": 1,
      "chunk_count": 1,
      "created_at": "2026-11-27T06:45:26.989483+00:00"
    }
  ],
  "chunks": [
    {
      "id": "uuid-hex",
      "doc_id": "uuid-hex",
      "filename": "sample.pdf",
      "page": 1,
      "index": 0,
      "start": 0,
      "end": 300,
      "text": "Retrieval augmented generation ...",
      "embedding": [0.01, 0.02]
    }
  ]
}
```

字段口径：

- `page`：从 1 开始。
- `index`：同一文档内的片段顺序，从 0 开始。
- `start/end`：片段在**该页原始文本**中的字符偏移。
- `embedding`：Ollama 返回的浮点数组，维度由模型决定（BGE-M3 通常为 1024）。
- `created_at`：UTC ISO 8601 字符串。

写入策略：

- `asyncio.Lock` 串行化 `add/list/delete/search/counts`。
- 写盘使用同目录 `mkstemp` + `json.dump` + `flush` + `fsync` + `os.replace`。
- 启动后首次访问才加载文件；文件不存在视为空库；JSON 损坏直接抛错，不静默清空。

## 5. 口径与不变量

### 切分

- 默认 `size=800`、`overlap=100`，步长 `700`。
- 相邻片段重叠恰好 100 字符；最后一段可能不足 800。
- `overlap >= size`、`size <= 0`、`overlap < 0` 均抛 `ValueError`。
- 只在一页内切分，不跨页拼接。
- 片段 `strip()` 后为空则丢弃，因此极端空白页可能不产生片段。

### 检索

- 余弦：`dot / (||a|| * ||b||)`；任一零向量返回 `0.0`；维度不一致抛 `ValueError`。
- 得分降序，返回 `min(TOP_K, 片段总数)`。
- `score` 保留 4 位小数；`snippet` 取片段前 120 字符。

### 错误

| 场景 | HTTP | detail 前缀 |
| --- | --- | --- |
| 非 PDF | 400 | `unsupported_file` |
| 超过 `MAX_UPLOAD_MB` | 400 | `file_too_large` |
| 加密/损坏 PDF | 400 | `parse_failed` |
| 无可提取文本 | 400 | `empty_document` |
| 空问题 | 400 | `empty_question` |
| 知识库为空 | 400 | `empty_index` |
| Ollama 不可达/超时 | 502 | `ollama_unreachable` |
| Ollama 非 200/结构异常 | 502 | `ollama_bad_response` |
| 删除不存在的文档 | 404 | `document_not_found` |

### 一致性

- embed 返回数量必须等于输入数量；维度必须一致；否则不写入任何片段。
- 写入成功后 `index.json` 必须可被 `json.loads` 完整解析。
- 删除文档必须同时删除其全部片段，避免“幽灵片段”参与检索。

## 6. 接口与调度

| 方法 | 路径 | 请求 | 响应 |
| --- | --- | --- | --- |
| GET | `/api/health` | - | `HealthOut`：`status/ollama_reachable/embed_model/chat_model/documents/chunks` |
| POST | `/api/documents` | multipart `file` | 201 `DocumentOut` |
| GET | `/api/documents` | - | `list[DocumentOut]`，创建时间倒序 |
| DELETE | `/api/documents/{doc_id}` | - | 204 |
| POST | `/api/ask` | `{"question": "..."}` | `AskResponse` |

调度说明：

- 所有接口均为 `async def`；Ollama 调用使用 `httpx.AsyncClient`，每次请求新建客户端（基础版简单优先）。
- `get_service()` 使用 `lru_cache(maxsize=1)`，进程内共享同一个 `JsonVectorStore`，保证内存状态一致。
- 前端由 `StaticFiles(html=True)` 挂在 `/`，与 API 同源，无 CORS。
- 路由先 `include_router`，再挂静态文件，避免静态 catch-all 抢先匹配 `/api`。

## 7. 验证与排障

### 自动化测试

```powershell
cd local-pdf-rag/backend
.\venv\Scripts\python -m pytest -v
```

实测：**20 passed**（Python 3.11.6，pytest 8.4.2，pytest-asyncio 0.26.0）。

覆盖点：

- `test_chunker`：800/100 重叠、短文本、空白文本、非法 overlap。
- `test_cosine`：同向/正交/反向、零向量、维度不一致。
- `test_json_store`：增删查、持久化往返、删除不存在返回 False。
- `test_parser`：真实 `sample.pdf` 提取到 `Retrieval`；非法字节抛 `PdfParseError`。
- `test_ollama_client`：embed 成功、数量不一致、chat 成功、连接错误映射。
- `test_rag_service`：入库片段数、Top-4 截断、Prompt 含来源、空库拒绝。
- `test_api`：健康、上传、列表、问答、删除、空库 400、空白问题 400、非 PDF 400。

### 真实联调（假 Ollama）

启动：

```powershell
# 终端 A
cd local-pdf-rag/backend
.\venv\Scripts\python scripts\fake_ollama.py

# 终端 B（使用临时索引，避免污染）
cd local-pdf-rag/backend
$env:INDEX_PATH="$env:TEMP\local-pdf-rag-smoke.json"
.\venv\Scripts\python -m uvicorn app.main:app --port 8000
```

实测 HTTP 结果：

- `GET /api/health` → 200，`ollama_reachable: true`
- `POST /api/documents`（sample.pdf）→ 201，`page_count: 1`，`chunk_count: 1`
- `GET /api/documents` → 200，1 条记录
- `POST /api/ask`（What is RAG?）→ 200，答案文本 + 1 条来源，`score: 0.8395`
- `DELETE /api/documents/{id}` → 204，随后列表为空

浏览器（Edge）实测：

- 上传后状态「已入库：sample.pdf（1 页 / 1 片段）」，列表正确渲染。
- 提问后答案出现，来源显示 `#1 sample.pdf p1 · score 0.8395` 与摘要。
- 截图：`C:\Users\Admin\AppData\Local\Temp\qoder-computer-use-images\b698e3e9\img-1795762174010985700-987728.png`

### 已修复问题

**前端列表渲染报 `document.createElement is not a function`**：

- 原因：`refreshDocs()` 的循环变量命名为 `document`，遮蔽了全局 `document` 对象。
- 修复：循环变量改为 `doc`，上传回调中的文档变量同步改名。
- 复验：上传成功、列表出现 `sample.pdf · 1 页 · 1 片段`，报错消失。

### 排障表

| 现象 | 优先检查 | 处理 |
| --- | --- | --- |
| 502 `ollama_unreachable` | Ollama 是否启动、`OLLAMA_BASE_URL` | 启动 Ollama 或改用 `scripts/fake_ollama.py` |
| 502 `ollama_bad_response` | 模型是否已 pull、Ollama 版本是否支持 `/api/embed` | `ollama pull bge-m3` / `ollama pull qwen2.5:3b`；或改用 `/api/embeddings` |
| 上传 400 `empty_document` | PDF 是否扫描版/加密 | 换带文本层的 PDF；当前不做 OCR |
| 上传 400 `parse_failed` | 文件是否损坏、是否真的是 PDF | 用阅读器打开验证 |
| 问答 400 `empty_index` | `data/index.json` 是否为空、`INDEX_PATH` 是否指向别处 | 先上传文档；检查环境变量 |
| 分数普遍很低 | 是否在用假 Ollama 的哈希向量 | 假服务只验证链路；真实语义需 BGE-M3 |
| 改了 `.env` 不生效 | 是否重启进程 | `.env` 仅在 `Settings()` 实例化时读取一次 |
| 前端仍显示旧页面 | 浏览器缓存 | 强制刷新；`StaticFiles` 每次从磁盘读取 |

### 切换到真实 Ollama

无需改代码：

```powershell
ollama pull bge-m3
ollama pull qwen2.5:3b
# 停掉假 Ollama，确认 OLLAMA_BASE_URL 指向 http://localhost:11434
cd local-pdf-rag/backend
.\venv\Scripts\python -m uvicorn app.main:app --port 8000
```

健康检查应显示 `ollama_reachable: true`；上传与问答将使用真实 BGE-M3 与 Qwen2.5。
