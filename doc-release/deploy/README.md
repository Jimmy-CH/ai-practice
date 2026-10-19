# DocRelease 部署脚手架

内网 Linux 部署（设计文档：仓库根 `docs/superpowers/specs/2026-10-15-doc-release-deploy-design.md`、
`docs/superpowers/specs/2026-10-16-doc-release-nonroot-deploy-design.md`）。
单端口同源托管：uvicorn :8080 同时服务页面、API、SSE。交付形态为源码包，依赖由部署机在线 pip 安装。

## 一、开发机构建部署包（Windows）

```powershell
cd doc-release
.\deploy\build_package.ps1
```

产物：`out/docrelease-package-<日期>.zip`（backend 源码 + static 前端产物 + deploy 脚手架，不含 wheels）。
生成 MANIFEST.md 记录源码 commit。

## 二、上传与解压（部署机）

```bash
# 系统级（root）
sudo mkdir -p /opt/docrelease/packages
sudo unzip docrelease-package-<日期>.zip -d /opt/docrelease/packages/
# 用户级（非 root，任意可写位置）
mkdir -p ~/docrelease/packages
unzip docrelease-package-<日期>.zip -d ~/docrelease/packages/
```

## 三、安装 / 升级（同一入口）

前置：`python3.11`、`git`、`rsync`，部署机可访问 pip 源（内网源可用 `PIP_INDEX_URL` 覆盖）。
星语网关不通仅警告，不阻断安装。

```bash
cd <包目录>/deploy
sudo bash install.sh   # 系统级：/opt/docrelease + 系统服务 + 系统用户 docrelease
bash install.sh        # 用户级：~/docrelease + systemctl --user，全程无需 root
# 可覆盖默认值：DEPLOY_ROOT=... PORT=... APP_USER=...（APP_USER 仅 root 模式生效）
```

脚本行为：前置检查 →（升级时先停旧服务释放端口，首次安装直接检查端口）→
rsync 源码与 static（排除 venv/.env/docrelease.db/archive/sample_repo，现场数据保留）→
venv 缺失则创建（Python 3.11）→ 在线安装依赖 → .env 缺失则从模板初始化 →
安装并启动 systemd 服务 → lingering 提示（用户级）→ 健康检查（30 秒硬超时）。

用户级说明：
- 服务随用户会话存活；登出/重启后自动拉起，需管理员一次性执行 `sudo loginctl enable-linger <用户>`
- 常用命令：`systemctl --user status docrelease`、`journalctl --user -u docrelease -n 50`
- 不支持跨模式升级（如 root 安装后用非 root 升级）；旧服务占用端口会被端口检查拦截

## 四、部署后验证清单

1. `systemctl status docrelease`（用户级 `systemctl --user status docrelease`）→ active (running)
2. `curl http://<host>:8080/api/health` → `{"status":"ok"}`
3. 浏览器 `http://<host>:8080/` 工作台加载、仓库列表含 order-center；直刷 `/history` 不 404
4. 示例仓 v2.13.3→v2.13.4 跑一次：SSE 步骤/日志/进度实时推送，产物可预览下载，
   `archive/docs/release/v2.13.4/` 生成三个产物文件

## 五、升级与回滚

- 升级：新包解压到 `packages/` 后重跑 `install.sh`（db/archive/sample_repo/.env 全保留）
- 回滚（用旧包覆盖部署目录后重启；系统级需 sudo——部署目录属主是 docrelease）：

```bash
# 系统级（root 身份操作 /opt/docrelease）
sudo rsync -a --exclude "venv/" --exclude ".env" --exclude "docrelease.db" \
  --exclude "archive/" --exclude "sample_repo/" --exclude "static/" \
  /opt/docrelease/packages/<旧包>/backend/ /opt/docrelease/backend/
sudo rsync -a /opt/docrelease/packages/<旧包>/static/ /opt/docrelease/backend/static/
sudo systemctl restart docrelease
# 用户级（无需 root，部署根 ~/docrelease）
rsync -a --exclude "venv/" --exclude ".env" --exclude "docrelease.db" \
  --exclude "archive/" --exclude "sample_repo/" --exclude "static/" \
  ~/docrelease/packages/<旧包>/backend/ ~/docrelease/backend/
rsync -a ~/docrelease/packages/<旧包>/static/ ~/docrelease/backend/static/
systemctl --user restart docrelease
```
