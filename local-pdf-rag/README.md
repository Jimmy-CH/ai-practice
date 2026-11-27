# local-pdf-rag

本地 PDF 文档问答系统（RAG 基础版）：上传 PDF，自动完成 **解析 → 切分 → 向量化 → 本地存储 → 相似度检索 → 生成**，回答附带 Top-4 来源片段。

## 技术栈

- **后端**：FastAPI、pypdf、httpx、pydantic-settings
- **本地推理**：Ollama（`bge-m3` 负责 Embedding，`qwen2.5:3b` 负责生成）
- **存储**：本地 JSON 索引（`VectorStore` 协议隔离，便于替换 Redis / PostgreSQL）
- **前端**：原生 HTML/JS，零构建，FastAPI `StaticFiles` 同源托管
- **测试**：pytest、pytest-asyncio、httpx `MockTransport` / `ASGITransport`

## 目录

```
local-pdf-rag/
├── backend/
│   ├── app/
│   │   ├── config.py              # Ollama、切分、TopK、索引路径配置
│   │   ├── schemas.py             # 请求/响应模型
│   │   ├── storage/
│   │   │   ├── base.py            # VectorStore 协议与数据类
│   │   │   └── json_store.py      # JSON 向量库（原子写）
│   │   ├── ingestion/
│   │   │   ├── pdf_parser.py      # pypdf 逐页解析
│   │   │   └── chunker.py         # 800/100 滑窗切分 + 余弦
│   │   ├── services/
│   │   │   ├── ollama_client.py   # /api/embed 与 /api/chat
│   │   │   └── rag_service.py     # 入库与问答编排
│   │   ├── api/routes.py
│   │   └── main.py                # 装配 + 静态托管
│   ├── tests/                     # 20 项 pytest
│   └── scripts/fake_ollama.py     # 无 Ollama 时的假服务
└── frontend/index.html            # 上传 + 文档列表 + 提问 + 来源
```

## 快速开始

### 方式一：真实 Ollama

1. 安装 [Ollama](https://ollama.com/download) 并启动。
2. 拉取模型：

```powershell
ollama pull bge-m3
ollama pull qwen2.5:3b
```

3. 启动后端：

```powershell
cd local-pdf-rag/backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

4. 打开 <http://localhost:8000>。

### 方式二：假 Ollama（无需下载模型）

```powershell
# 终端 A：假 Ollama，监听 11434
cd local-pdf-rag/backend
.\venv\Scripts\python scripts\fake_ollama.py

# 终端 B：后端，监听 8000
cd local-pdf-rag/backend
.\venv\Scripts\python -m uvicorn app.main:app --port 8000
```

假服务返回确定性向量与固定答案，用于验证上传、检索、来源展示与前端交互；真实语义效果仍需 Ollama。

## 使用流程

1. 选择 PDF，点击「上传并入库」。
2. 等待解析、切分、向量化完成，文档出现在「已入库文档」。
3. 输入问题，点击「提问」。
4. 查看答案与 Top-4 来源（文件名、页码、余弦分数、片段摘要）。
5. 可删除文档，其片段会同时从索引移除。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | Ollama 可达性、模型名、文档/片段数 |
| POST | `/api/documents` | multipart `file`，上传并入库 |
| GET | `/api/documents` | 文档列表（创建时间倒序） |
| DELETE | `/api/documents/{doc_id}` | 删除文档及其片段 |
| POST | `/api/ask` | `{question}` → `{answer, sources}` |

示例：

```json
{
  "answer": "RAG 将文档检索与大模型生成结合…… [sample.pdf p1]",
  "sources": [
    {
      "index": 1,
      "document_id": "…",
      "filename": "sample.pdf",
      "page": 1,
      "score": 0.83,
      "snippet": "Retrieval augmented generation (RAG) combines…"
    }
  ]
}
```

## 配置

复制 `.env.example` 为 `.env` 后按需修改：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 地址 |
| `EMBED_MODEL` | `bge-m3` | Embedding 模型 |
| `CHAT_MODEL` | `qwen2.5:3b` | 生成模型 |
| `CHUNK_SIZE` | `800` | 片段字符数 |
| `CHUNK_OVERLAP` | `100` | 相邻片段重叠字符数 |
| `TOP_K` | `4` | 检索片段数 |
| `MAX_UPLOAD_MB` | `20` | 上传大小上限 |
| `OLLAMA_TIMEOUT` | `120` | Ollama 请求超时（秒） |
| `INDEX_PATH` | `./data/index.json` | JSON 索引路径 |

## 测试

```powershell
cd local-pdf-rag/backend
.\venv\Scripts\python -m pytest -v
```

覆盖：滑窗切分与重叠、余弦相似度、JSON 存储往返、真实 PDF 解析、Ollama 客户端错误映射、RAG 编排、上传/列表/删除/问答接口。所有测试使用假 Ollama，不触网。

## 生产化改造

本次保持 JSON 闭环，`VectorStore` 协议已为生产存储预留：

- **Redis**：会话缓存（多轮历史、热点问题），不承载向量。
- **PostgreSQL + pgvector**：文档元数据、片段、向量持久化；`search` 改为 SQL 余弦/内积排序。
- **对象存储**：原始 PDF 放 S3/MinIO，JSON 中只保留引用。
- **异步任务**：大文件入库改为队列（Celery/RQ），接口返回任务 ID。

替换时只需新增一个 `VectorStore` 实现并在 `get_service()` 中装配，路由与前端无需改动。

## 设计文档

- 设计说明：`.qoder/docs/local-pdf-rag-设计说明.md`
- 实施计划：`.qoder/docs/local-pdf-rag-实施计划.md`
- 实现说明：`.qoder/docs/local-pdf-rag-实现说明.md`

## 常见问题

**Q：提问返回 502 `ollama_unreachable`？**
A：Ollama 未启动或地址不对。确认 `OLLAMA_BASE_URL`，或改用假 Ollama。

**Q：上传后 `chunk_count` 为 0 或返回 `empty_document`？**
A：PDF 可能是扫描版（无文本层）或加密。当前版本不做 OCR。

**Q：为什么检索分数不高？**
A：假 Ollama 使用哈希向量，分数仅用于验证链路；真实语义请用 BGE-M3。
