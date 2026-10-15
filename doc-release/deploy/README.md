# DocRelease 部署脚手架

内网 Linux 离线部署（设计文档：仓库根 `docs/superpowers/specs/2026-10-15-doc-release-deploy-design.md`）。
单端口同源托管：uvicorn :8000 同时服务页面、API、SSE。

## 一、开发机构建离线包（Windows）

```powershell
cd doc-release
.\deploy\build_offline_package.ps1                    # 默认：pip --platform 下载 manylinux wheel
.\deploy\build_offline_package.ps1 -WheelSource wsl   # 备选：WSL 内 Python 3.11 下载（platform 法缺 wheel 时用）
```

产物：`out/docrelease-offline-<日期>.zip`。脚本自动校验：wheels 中不得出现 win_amd64 包；
`tree_sitter-` / `tree_sitter_language_pack-` / `pydantic_core-` 关键 wheel 必须在场；生成 MANIFEST.md（源码 commit）。

## 二、上传与解压（部署机）

```bash
sudo mkdir -p /opt/docrelease/packages
sudo unzip docrelease-offline-<日期>.zip -d /opt/docrelease/packages/
```

## 三、安装 / 升级（同一入口）

前置：`python3.11`、`git`、`rsync`。星语网关不通仅警告，不阻断安装。

```bash
cd /opt/docrelease/packages/docrelease-offline-<日期>/deploy
sudo bash install.sh
# 可覆盖默认值：sudo DEPLOY_ROOT=/opt/docrelease PORT=8000 APP_USER=docrelease bash install.sh
```

脚本行为：前置检查 →（升级时先停旧服务释放端口，首次安装直接检查端口）→
rsync 源码与 static（排除 venv/.env/db/archive/sample_repo，现场数据保留）→
venv 缺失则创建（Python 3.11）→ 离线安装依赖 → .env 缺失则从模板初始化 → 安装并启动 systemd 服务 → 健康检查。

## 四、部署后验证清单

1. `systemctl status docrelease` → active (running)
2. `curl http://<host>:8000/api/health` → `{"status":"ok"}`
3. 浏览器 `http://<host>:8000/` 工作台加载、仓库列表含 order-center；直刷 `/history` 不 404
4. 示例仓 v2.13.3→v2.13.4 跑一次：SSE 步骤/日志/进度实时推送，产物可预览下载，
   `archive/docs/release/v2.13.4/` 生成三个产物文件

## 五、升级与回滚

- 升级：新包解压到 `packages/` 后重跑 `install.sh`（db/archive/sample_repo/.env 全保留）
- 回滚（用旧包覆盖部署目录后重启）：

```bash
sudo rsync -a --exclude "venv/" --exclude ".env" --exclude "docrelease.db" \
  --exclude "archive/" --exclude "sample_repo/" --exclude "static/" \
  /opt/docrelease/packages/<旧包>/backend/ /opt/docrelease/backend/
sudo rsync -a /opt/docrelease/packages/<旧包>/static/ /opt/docrelease/backend/static/
sudo systemctl restart docrelease
```
