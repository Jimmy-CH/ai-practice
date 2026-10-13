# AI 运营物料智能生成助手

输入版本迭代文档（纯文本或 .docx），AI 自动解析出功能点、变更优化、注意事项、风险提示四类要点，并一键生成面向不同受众的六类运营物料初稿。

## 功能

- 左侧输入文档：支持文本粘贴或 .docx 文件上传
- AI 解析结果：四类要点卡片展示
- 物料生成：支持 6 种物料类型 × 3 种受众
  - 版本宣发稿
  - 网点操作指引
  - FAQ 问答库
  - 行者推送话术
  - 海报脚本
  - 培训课件大纲
- 一键复制、下载单页、导出全部 Markdown

## 技术栈

- 后端：Python 3.11、FastAPI、python-docx、httpx、DeepSeek API
- 前端：Vue 3 + TypeScript + Vite + Element Plus + Axios + marked

## 启动

### 后端

```powershell
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173/

## 测试

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests -v

cd ../frontend
npm run build
```

## 环境变量

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```
