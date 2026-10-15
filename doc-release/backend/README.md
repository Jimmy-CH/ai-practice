# 释文 DocRelease · 后端

从代码变更自动生成发布文档的后端服务：读取本地 git 仓库的变更范围（base..head），
经五步流水线（定位范围 → 收集变更 → tree-sitter AST 解析 → 星语 LLM 业务化改写 → 产物归档），
通过 SSE 实时推送进度，产出 `checklist.csv` / `product-doc.md` / `trace.json` 三类产物。

## 环境

- Python 3.11（Windows x64 已验证，tree-sitter 有预编译 wheel）
- 内网环境可直接访问星语网关；脱离内网时运行会在 LLM 步骤失败/降级

## 初始化

```powershell
cd doc-release\backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env    # 按需修改
```

## 启动

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

首次启动会自动：建表 → 幂等生成示例仓库 `sample_repo/order-center`（含 v2.13.3/v2.13.4/v2.14.0/v3.0.0 四个标签与三大场景）→ 注册为 `is_sample=True` 的仓库。

## 测试

```powershell
.\venv\Scripts\python.exe -m pytest tests -q
```

全部测试离线可跑（conftest 全局打桩 LLM，不会调用真实星语）。

## 冒烟

```powershell
.\venv\Scripts\python.exe e2e_smoke.py           # 打桩 LLM（离线）
.\venv\Scripts\python.exe e2e_smoke.py --real    # 真实星语（内网）
```

## 种子脚本

```powershell
.\venv\Scripts\python.exe seed_sample_repo.py            # 默认生成到 sample_repo/order-center
.\venv\Scripts\python.exe seed_sample_repo.py D:\tmp\demo  # 指定目录
```

## API 摘要（前缀 /api）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /health | 健康检查 |
| GET | /repos | 仓库列表 |
| POST | /repos | 注册本地仓库（body: path, name?） |
| DELETE | /repos/{id} | 删除仓库（有运行记录时 400） |
| GET | /repos/{id}/refs | 分支与标签列表 |
| GET | /repos/{id}/scenarios | 内置场景（仅示例仓） |
| GET | /repos/{id}/preview?base=&head= | 变更预览（截断至 300 行/文件） |
| POST | /runs | 创建并启动运行（body: repo_id, base_ref, head_ref, version_label?, tone?, mask?） |
| GET | /runs | 运行列表（分页 total/items） |
| GET | /runs/{id} | 运行详情（含 steps/logs/stats/result/artifacts） |
| GET | /runs/{id}/events | SSE 事件流（snapshot/step/log/progress/done/error + 15s 心跳） |
| POST | /runs/{id}/cancel | 取消运行 |
| DELETE | /runs/{id} | 删除运行（含归档，trace.runId 匹配才删） |
| GET | /runs/{id}/artifacts/{kind} | 渲染产物（kind: checklist/document/trace；query: tone, mask） |
| GET | /runs/{id}/artifacts/{kind}/download | 下载产物 |

## 归档

产物写入 `archive/docs/release/<version>/`（同版本覆盖；删除时校验 trace.runId 防误删）。
