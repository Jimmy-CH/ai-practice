# ai-material-generator 内网 Linux 部署方案设计

日期：2026-10-15
状态：已与用户逐节确认

## 1. 背景与目标

ai-material-generator（AI 运营物料智能生成助手）当前仅支持开发态运行：后端 `uvicorn` 跑在 127.0.0.1:8000，前端依赖 Vite dev server（:5173）代理 `/api`。需要将其交付到内网 Linux 服务器长期运行。

目标：提供与 doc-release 同构的部署脚手架，实现「开发机构包 → 上传 → 一键安装/升级 → 验证」的完整交付链路。

## 2. 已确认决策

| 决策点 | 结论 | 说明 |
|---|---|---|
| 部署环境 | 内网 Linux，Python 3.11.11 | 与 doc-release 同型环境 |
| 部署位置 | 与 doc-release 同一台内网机 | 端口、路径、服务名需错开 |
| 依赖安装 | **在线 pip 安装**，不做离线 wheel 包 | 用户确认部署机 pip 可直接下载（内网源可达）；wheel 平台由部署机自动解析 |
| 交付物 | 源码部署包 zip（源码 + 前端 dist 产物 + deploy 脚手架） | 前端仍在 Windows 开发机构建 |
| 安全配置 | 保持现状 | 内网可信环境：`secret_key` 默认值、内置账号（editor/editor123、reviewer/reviewer123）、CORS `*` 均不改动 |
| 部署形态 | 单端口同源托管 + systemd 单进程 | 复刻 doc-release 模式（方案 A，用户选定） |

被否决的备选：nginx 前后端分离部署（双服务复杂、内机离线装 nginx 成本高）、Docker 交付（内机 Docker 可用性未验证）。

## 3. 总体架构

```
内网 Linux 部署机（与 doc-release 同机）
├── /opt/docrelease        ← 已有，:8080，互不影响
└── /opt/material-gen      ← 新增部署根（DEPLOY_ROOT 可覆盖）
    ├── backend/           ← FastAPI 源码 + venv/ + materials.db + .env
    ├── static/            ← 前端 dist 构建产物（由 install.sh rsync 到位）
    ├── packages/          ← 部署包暂存
    └── /etc/systemd/system/material-gen.service
```

- 端口：**8081**（错开 docrelease 的 8080；`PORT` 环境变量可覆盖，经 sed 注入 unit）
- 服务名：`material-gen.service`；运行用户：`materialgen`（`APP_USER` 可覆盖）
- uvicorn 单进程同端口服务：前端页面、静态资源、`/api/*` 接口
- LLM：`LLM_PROVIDER=xingyu`（默认），星语网关 10.130.13.74:8060 内网可达；DeepSeek 为可选回退
- 开发态完全不变：后端 8000 + Vite 5173；`static/` 目录不存在时部署代码自动跳过

## 4. 代码改动（唯一侵入业务仓库的点）

| 文件 | 改动 | 要点 |
|---|---|---|
| `backend/app/config.py` | 新增 `static_dir: str = "static"` | 相对路径按工作目录解析，与现有 Settings 风格一致 |
| `backend/app/main.py` | 末尾新增 `register_static(app, Path(settings.static_dir))` | 复刻 doc-release `backend/app/main.py` 的 `register_static()` 实现 |

`register_static()` 行为规格（从 doc-release 同版本代码移植，fastapi 0.141.1 一致）：

1. `static/` 不存在 → 直接返回（开发模式零影响）。
2. `static/assets/` 存在 → 挂载 `StaticFiles` 到 `/assets`。
3. 注册 catch-all 路由 `/{full_path:path}`（全方法、不进 OpenAPI schema）作为 SPA fallback：
   - `api` 与 `api/*` 路径：不回退页面；尾斜杠路径若存在真实路由则 307 重定向补偿；路径已注册但方法不符时返回 405 + `Allow` 头（处理 FastAPI 0.141 `_IncludedRouter` 无 `path`/`methods` 属性的补偿逻辑）；其余 404。
   - 其余路径 GET/HEAD：`static/` 下存在同名文件则返回该文件，否则返回 `index.html`（history 路由直刷不 404）。
   - 非 GET/HEAD：404。
4. 必须在所有 API 路由注册之后调用，避免 catch-all 拦截 `/api`。

业务逻辑、路由、数据库模型**零改动**。

## 5. 部署脚手架 `ai-material-generator/deploy/`

```
deploy/
├── build_package.ps1      # Windows 开发机构包
├── env.template           # 部署 .env 模板
├── material-gen.service   # systemd 单元模板（与安装后 unit 同名，install.sh 仅 sed 注入不重命名）
├── install.sh             # 安装/升级同一入口
└── README.md              # 部署操作手册
```

### 5.1 build_package.ps1（Windows 开发机）

1. 前置：`node`/`npm` 可用；在 `frontend/` 执行 `npm run build`。
2. 组包目录：拷贝 `backend/app`、`backend/requirements.txt`、`deploy/`、`frontend/dist` →（组包内重命名为 `static/`）。
3. 生成 `MANIFEST.md`：源码 commit、构建时间、包内清单。
4. 产物 `out/materialgen-package-<yyyyMMdd>.zip`（`out/` 已 gitignore；同名存在时追加 `HHmmss` 后缀）。

不包含 wheels（依赖在线安装）、不包含 venv/数据库/.env。

### 5.2 env.template

```env
LLM_PROVIDER=xingyu
# 如需回退 DeepSeek，取消注释并填写：
# LLM_PROVIDER=deepseek
# DEEPSEEK_API_KEY=sk-xxx
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# DEEPSEEK_MODEL=deepseek-chat
```

### 5.3 material-gen.service（模板要点）

- `User=materialgen`（install.sh 按 `APP_USER` sed 注入）
- `WorkingDirectory=/opt/material-gen/backend`（按 `DEPLOY_ROOT` 注入）
- `ExecStart=<venv>/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8081`（端口注入）
- `Restart=on-failure`、`RestartSec=3`
- `Environment=PATH=...` 保证 venv 优先

### 5.4 install.sh 执行流程

```
环境变量默认值：DEPLOY_ROOT=/opt/material-gen  PORT=8081  APP_USER=materialgen
1. 前置检查：python3.11、rsync 可用；pip 源连通性探测（失败仅警告）；星语网关探测（失败仅警告）
2. 幂等：systemctl 已存在 material-gen 服务且 running 则先 stop（释放端口）；首装仅检查端口占用
3. rsync 源码与 static → $DEPLOY_ROOT
   排除：venv/  .env  materials.db   ← 现场数据保留
4. venv 缺失则 python3.11 -m venv 创建
5. $DEPLOY_ROOT/backend/venv 内 pip install -r requirements.txt（在线）
6. $DEPLOY_ROOT/backend/.env 不存在则从 env.template 初始化；已存在不动
7. 渲染 materialgen.service（sed 注入 DEPLOY_ROOT/PORT/APP_USER）→ /etc/systemd/system/
   daemon-reload → enable --now
8. 健康检查：curl http://127.0.0.1:$PORT/api/health 重试（上限 30 秒）直至 {"status":"ok"}
```

## 6. 数据生命周期

| 场景 | 行为 |
|---|---|
| 首次安装 | `materials.db` 不存在 → 服务启动 lifespan 自动 `create_all` + `_migrate_schema` + `seed_users`；内置账号 editor/editor123、reviewer/reviewer123 直接可用 |
| 升级 | rsync 排除 db/.env/venv → 现场数据与配置保留；表结构新增列由 `main.py` 已内置的幂等迁移（PRAGMA 检测 + ALTER TABLE）自动补齐 |
| 回滚 | 解压旧包覆盖部署目录（同样排除现场数据）→ `systemctl restart material-gen` |

已知注意事项（继承自开发环境经验，非部署期改动项）：
- `passlib` 必须搭配 `bcrypt==4.0.1`（requirements.txt 已钉定，在线安装自然生效）。
- SQLite 文件被残留进程锁定属开发态问题；systemd 单进程托管下由 Restart 策略兜底。

## 7. 部署后验证清单

1. `systemctl status material-gen` → active (running)
2. `curl http://<host>:8081/api/health` → `{"status":"ok"}`
3. 浏览器 `http://<host>:8081/` → 登录页加载；直刷 `/materials`、`/review` 不 404
4. editor 登录 → 粘贴文本解析（星语网关可达）→ 生成物料 → 保存草稿；reviewer 登录 → 审核通过 → 「已审核」页下载 Markdown
5. `journalctl -u material-gen -n 100` 无异常堆栈

## 8. 测试与回归

- 后端 pytest 新增静态托管用例（TestClient）：
  - `static/` 存在时，GET 未知前端路由返回 `index.html` 内容
  - `static/` 下真实文件可被访问（测试中临时构造 static 目录与文件验证）
  - 未知 `/api/xxx` 返回 404 JSON；已注册路径用错误方法访问返回 405 + `Allow`
  - `static/` 不存在时全部现有用例行为不变
- 全量 `pytest tests -q` 回归（基线约 28 秒 / 51 passed；显著超出说明有用例打到真实星语模型）
- 前端 `npm run build` 通过
- `install.sh`、`build_package.ps1` 语法检查（`bash -n` / PowerShell 解析）
- 端到端：包 → install.sh → 验证清单全过

## 9. 非目标

- 不做 HTTPS/反向代理/域名（内网直连 IP:PORT）
- 不做多实例/水平扩容、不做 Docker 化
- 不改动安全配置（secret_key、内置账号、CORS，见决策表）
- 不引入 alembic；继续使用 lifespan 幂等迁移
- 不做前端产物 CDN/缓存策略调优

## 10. 交付物清单

- `backend/app/config.py`、`backend/app/main.py`（静态托管）
- `backend/tests/` 新增静态托管测试文件
- `ai-material-generator/deploy/` 五个脚手架文件
- 本设计文档（仓库根 `docs/superpowers/specs/`）
