# doc-release 部署方案设计（内网 Linux 离线部署）

- 日期：2026-10-15
- 状态：已与用户逐节确认
- 关联规格：`docs/superpowers/specs/2026-10-14-doc-release-design.md`

## 1. 背景与目标

doc-release（释文）为 FastAPI 后端 + Vue 3 前端的全栈工具，依赖内网星语 LLM 网关
（`http://10.130.13.74:8060`）。当前仅支持开发方式运行（uvicorn 8000 + vite dev 5173）。
本方案定义其部署到内网 Linux 服务器的标准方式：离线包交付、单端口同源服务、systemd 服务化，
并提供可重复执行的安装/升级/回滚流程。

## 2. 已确认的范围决策

| 决策点 | 结论 |
| --- | --- |
| 目标环境 | 内网 Linux 服务器（可访问星语网关），裸机部署，不用 Docker |
| 交付方式 | 离线包上传（scp/堡垒机），不依赖部署机访问外网/PyPI/GitHub |
| 服务形态 | 方案 A：FastAPI 单端口同源托管（uvicorn 直接服务前端 dist + API + SSE） |
| 否决方案 | nginx 前置反代（SSE 缓冲配置易踩坑、多一组件、对内网单机工具过度设计）；Docker（用户排除） |
| Python 版本 | **3.11.11**（用户指定）。已核验：全部依赖 `Requires-Python` 下限 ≤ 3.10（tree_sitter 0.26.0、fastapi 0.141.1、pytest 9.1.1、pydantic_core 等），3.11 满足全部下限；开发环境同为 3.11.x，行为一致 |
| 端口 | 8080（开发后端仍为 8000；可通过 PORT 变量或 unit `--port` 调整） |
| 认证 | 无（首期非目标，内网使用） |

派生约束：开发与部署统一 Python 3.11；引入新依赖时核对 `Requires-Python` ≤ 3.11。

## 3. 部署架构与目录布局

部署机目录（`/opt/docrelease`，可调整）：

```
/opt/docrelease/
├── backend/                      # 后端源码 + 运行时数据（WorkingDirectory）
│   ├── app/  prompts/  glossary.json
│   ├── seed_sample_repo.py  seed_data.py  e2e_smoke.py
│   ├── requirements.txt
│   ├── venv/                     # 部署机安装时创建
│   ├── .env                      # 首次安装从模板初始化；升级保留
│   ├── docrelease.db             # SQLite；升级保留
│   ├── archive/                  # 产物归档；升级保留
│   ├── sample_repo/order-center/ # 首次启动 lifespan 幂等自动生成
│   └── static/                   # 前端构建产物（由后端托管）
├── packages/                     # 历次离线包存放处（升级/回滚依据）
├── wheels/                       # 离线 wheel（安装成功后可删）
└── deploy/
    ├── install.sh                # 安装/升级统一入口
    ├── docrelease.service        # systemd 单元
    └── env.template              # .env 模板
```

进程模型：systemd 管理单个 uvicorn 进程，监听 `0.0.0.0:8080`，同端口服务页面、API、SSE。
运行时前置：Python 3.11.11、git（示例仓库生成与“注册本地仓库”功能都需要）、内网可达星语网关。
单 worker 即可：流水线为 asyncio 异步 + `asyncio.to_thread`，SQLite 与本地 git 仓库路径均为单机形态。

## 4. 代码改动（唯一侵入点，约 15 行）

1. `app/config.py` 增加 `static_dir: str = "static"`（相对 WorkingDirectory）。
2. `app/main.py` 在**所有 API 路由注册之后**（静态端点注册顺序约束）：

   - `static/` 目录**不存在则跳过挂载** → 开发模式（5173/8000 双进程）与现有 pytest 全部不受影响；
   - 存在则挂载 `/assets` 静态目录 + SPA catch-all 路由：
     - 请求命中 `static/` 下真实文件 → 返回该文件；
     - 路径以 `api/` 开头 → 返回 404 JSON（避免 API 404 被回退成 index.html 掩盖错误）；
     - 其余路径 → 回退 `index.html`（`createWebHistory()` history 路由刷新必需）。

3. CORS 中间件保留不动：开发模式仍需；同源部署下浏览器不发预检，无副作用。

## 5. 离线包构成与构建流程（开发机 Windows）

包名：`docrelease-offline-YYYYMMDD/`（同目录可带 `-N` 序号区分同日多版）。

```
docrelease-offline-YYYYMMDD/
├── backend/          # 后端源码；排除 venv/ docrelease.db/ archive/ sample_repo/ __pycache__/ .env
├── static/           # 前端 npm run build 产物（含 vue-tsc --noEmit 类型检查）
├── wheels/           # Linux 平台离线 wheel（对应 Python 3.11）
├── deploy/           # install.sh + docrelease.service + env.template
└── MANIFEST.md       # 版本、构建时间、源码 git commit、内容清单
```

**wheel 平台坑（重点）**：Windows 上 `pip download` 默认只拉 `win_amd64` wheel，直接装 Linux 必失败。两条构建路径：

1. **首选：WSL 打包**——WSL 内用 Python 3.11 `pip download -r requirements.txt -d wheels`，平台天然匹配；
2. **备选：Windows 指定平台下载**——
   `pip download -r requirements.txt -d wheels --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all:`。

构建后必须验证：`wheels/` 中 `tree_sitter`（abi3）、`tree_sitter_language_pack`（abi3）、
`pydantic_core`（cp311 manylinux）等含二进制扩展的包均为 Linux 平台 wheel；若个别包缺 wheel，回落 WSL 路径。

打包脚本 `deploy/build_offline_package.ps1`（源码位置 `doc-release/deploy/`，开发机执行）：构建前端 → 收集源码 → 下载 wheel → 生成 MANIFEST → 输出 zip。

## 6. 部署机安装流程（install.sh：安装与升级同一入口）

1. 前置检查：`python3.11` 存在、`git` 存在、`curl` 探测星语网关（不通仅警告，不阻断——允许先装后通网）；
2. rsync `backend/` → `/opt/docrelease/backend/`，排除 `venv/ .env docrelease.db archive/ sample_repo/ static/`；
3. rsync `static/` → `/opt/docrelease/backend/static/`；
4. venv 不存在则 `python3.11 -m venv venv`；
5. `venv/bin/pip install --no-index --find-links /opt/docrelease/wheels -r requirements.txt`；
   安装成功后 `wheels/` 可删除，再次升级重跑 install.sh 时由新包重建；
6. `.env` 不存在则从 `env.template` 初始化（存在则不动，保留现场配置）；
7. 安装 `docrelease.service` 至 `/etc/systemd/system/`，`daemon-reload`、`enable --now`；
8. 健康检查：循环 `curl http://127.0.0.1:8080/api/health`（最多 30s），失败则输出 journalctl 排障指引并以非零码退出。

**升级** = 上传新离线包、重跑 `install.sh`、脚本内自动 `systemctl restart`。运行时数据
（db/archive/sample_repo/.env）全部保留。首次启动时 lifespan 自动建表并幂等生成示例仓库。

## 7. systemd 服务化

`docrelease.service` 关键项：

```ini
[Unit]
Description=DocRelease (释文) backend + frontend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=docrelease
WorkingDirectory=/opt/docrelease/backend
ExecStart=/opt/docrelease/backend/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

- 环境变量不写入 unit：`config.py` 从 WorkingDirectory 下 `.env` 读取，改配置只动 `.env` 后 `restart`；
- 改端口：编辑 unit 中 `--port` 后 `daemon-reload + restart`；
- `install.sh` 负责创建 `docrelease` 系统用户（不存在时）并 `chown` 数据目录。

## 8. 配置管理（.env）

与现 `config.py` 字段一一对应，`env.template` 与 `.env.example` 内容一致：
`XINGYU_URL`、`ROBOT_CODE`、`LLM_PROVIDER=xingyu`、`DEEPSEEK_API_KEY`（可选回退）、
`LLM_TIMEOUT`、`LLM_MAX_CONCURRENCY`。部署机通常只需确认网关地址与网络连通；
`db_url`/`archive_dir`/`sample_repo_dir`/`cors_origins`/`static_dir` 保持默认。

## 9. 升级与回滚

- 升级：见第 6 节；离线包统一解压至 `/opt/docrelease/packages/<包名>/` 保留，作为回滚依据；
- 回滚 = rsync 旧包中 `backend/` + `static/` 覆盖部署目录 + `systemctl restart docrelease`；
- SQLite 安全性：项目用 `Base.metadata.create_all` 幂等建表、无迁移框架，不删列不改列；
  新代码加列后回滚旧代码，SQLAlchemy 显式列查询不受多余列影响——回滚安全；
- 归档产物按 `archive/docs/release/<version>/` 存放，回滚不触碰。

## 10. 部署后验证清单

1. `systemctl status docrelease` → active (running)；
2. `curl http://<host>:8080/api/health` → `{"status":"ok"}`；
3. 浏览器打开 `http://<host>:8080/` → 三栏工作台加载、仓库列表含 order-center（示例仓）；
4. 直刷 `/history` → 不 404（SPA fallback 生效）；
5. 示例仓跑一次 v2.13.3→v2.13.4 运行 → SSE 步骤/日志/进度实时推送 → 三类产物可预览、可下载；
6. `archive/docs/release/v2.13.4/` 生成三个产物文件；
7. （内网可选）`venv/bin/python e2e_smoke.py --real` 走真实星语全链路。

## 11. 风险与约束

| 风险/约束 | 应对 |
| --- | --- |
| tree-sitter 系 wheel 在目标平台缺失 | 构建时清单校验；缺则回落 WSL 打包路径 |
| 部署机 Python 版本漂移（装成 3.8/3.12 等） | install.sh 显式检查 `python3.11`，缺失即失败并提示安装命令 |
| 星语网关不可达（网段/防火墙） | install.sh 探测告警；运行期 LLM 步骤失败/降级已在流水线内处理 |
| 8080 端口被占 | 安装前 `ss -ltn` 检查；改端口只动 unit 一处 |
| uvicorn 单进程性能上限 | 内网单工具够用；将来加 nginx 前置 + 多 worker 与本方案不冲突 |
| 离线包与源码版本错位 | MANIFEST.md 记录 git commit 与构建时间，升级前核对 |
