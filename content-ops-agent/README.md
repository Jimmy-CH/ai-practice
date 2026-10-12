# Content Ops Agent

基于活动主题、产品资料、CI/CD 事件和 Git 发布上下文生成公告、FAQ、海报的内容运营 Agent。

## 启动

```powershell
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload

cd ../frontend
npm install
npm run dev
```

前端默认访问 `http://localhost:8000/api`。

## 验证

```powershell
cd backend
python -m pytest tests -v

cd ../frontend
npm run build
```

## 首期能力

- 创建活动内容项目，导入文本资料、Git Release 上下文和 CI/CD Webhook。
- 一键生成可追溯的公告、FAQ、海报草稿。
- 审核通过后下载 HTML 结构化内容或创建模拟发布任务。
