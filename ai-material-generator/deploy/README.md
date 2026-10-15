# MaterialGen 部署脚手架

内网 Linux 部署（设计文档：仓库根 `docs/superpowers/specs/2026-10-15-ai-material-generator-deploy-design.md`）。
单端口同源托管：uvicorn :8081 同时服务页面与 API。依赖经部署机 pip 源在线安装（无需离线 wheel）。

## 一、开发机构建部署包（Windows）

```powershell
cd ai-material-generator
.\deploy\build_package.ps1
```

产物：`out/materialgen-package-<日期>.zip`（前端 dist 产物 + 后端源码 + 脚手架 + MANIFEST.md）。

## 二、上传与解压（部署机）

```bash
sudo mkdir -p /opt/material-gen/packages
sudo unzip materialgen-package-<日期>.zip -d /opt/material-gen/packages/
```

## 三、安装 / 升级（同一入口）

前置：`python3.11`、`rsync`；pip 源可达（内网源用 `PIP_INDEX_URL` 指定）。星语网关不通仅警告，不阻断安装。

```bash
cd /opt/material-gen/packages/materialgen-package-<日期>/deploy
sudo bash install.sh
# 可覆盖默认值：sudo DEPLOY_ROOT=/opt/material-gen PORT=8081 APP_USER=materialgen bash install.sh
```

脚本行为：前置检查 →（升级时先停旧服务释放端口，首次安装直接检查端口）→
rsync 源码与 static（排除 venv/.env/materials.db，现场数据保留）→
venv 缺失则创建（Python 3.11）→ 在线安装依赖 → .env 缺失则从模板初始化 →
安装并启动 systemd 服务 → 健康检查。

端口说明：端口是 uvicorn 命令行参数，不能用 .env 配置；临时换端口用
`sudo PORT=xxxx bash install.sh` 覆盖重跑。

## 四、部署后验证清单

1. `systemctl status material-gen` → active (running)
2. `curl http://<host>:8081/api/health` → `{"status":"ok"}`
3. 浏览器 `http://<host>:8081/` → 登录页加载；直刷 `/materials`、`/review` 不 404
4. editor/editor123 登录 → 粘贴文本解析（星语网关可达）→ 生成物料 → 保存草稿；
   reviewer/reviewer123 登录 → 审核通过 → 「已审核」页下载 Markdown

## 五、升级与回滚

- 升级：新包解压到 `packages/` 后重跑 `install.sh`（db/.env/venv 全保留，
  新列由启动期幂等迁移自动补齐）
- 回滚（用旧包覆盖部署目录后重启）：

```bash
sudo rsync -a --exclude "venv/" --exclude ".env" --exclude "materials.db" \
  --exclude "static/" \
  /opt/material-gen/packages/<旧包>/backend/ /opt/material-gen/backend/
sudo rsync -a /opt/material-gen/packages/<旧包>/static/ /opt/material-gen/backend/static/
sudo systemctl restart material-gen
```
