# 内容生产发布工作台

输入活动主题、产品文档、操作手册等，一键产出公告、FAQ、海报文案，经人工审核后下载或创建模拟发布任务。

## 启动

```powershell
cd content-workbench/backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
# 配置环境变量：拷贝 .env.example 为 .env，填入 DEEPSEEK_API_KEY
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

cd ../frontend
npm install
npm run dev
```

前端访问 http://localhost:5173/，后端 API 文档 http://127.0.0.1:8000/docs。

测试账号：
- editor / editor123（编辑者：创建项目、贴资料、生成、编辑、下载、发布）
- reviewer / review123（审核者：查看引用、通过/驳回、查看审计日志）

## 验证

```powershell
cd content-workbench/backend
.\venv\Scripts\python.exe -m pytest tests -v

cd ../frontend
npm run build
```
