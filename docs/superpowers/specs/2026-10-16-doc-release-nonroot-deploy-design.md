# doc-release 部署改造设计（双模式 + 在线 pip）

- 日期：2026-10-16
- 状态：已与用户确认
- 基线：`docs/superpowers/specs/2026-10-15-doc-release-deploy-design.md`（本设计为其增量改造，
  原有单端口同源托管、systemd 服务化、rsync 现场数据保留策略全部不变）
- 同仓先例：`ai-material-generator/deploy/install.sh`（已验证的双模式实现，本设计直接复用其结构）

## 1. 背景与目标

原部署方案要求 `sudo bash install.sh`（root 系统级：`/opt/docrelease` + `/etc/systemd/system`
+ 系统用户 `docrelease`）。现部署机以普通用户操作，需要支持**非 root 安装**；同时交付形态由
离线 wheel 包改为**源码包 + 部署机在线 pip**（部署机 pip 可直接联网，与 ai-material-generator
交付形态对齐）。

目标：

1. `install.sh` 双模式：root 走系统级（行为与原版一致）；非 root 走用户级
   （`~/docrelease` + `systemctl --user`），全程无需 sudo；
2. 构建脚本删除 wheel 下载/校验逻辑，产物改名 `docrelease-package-<日期>.zip`；
3. 文档同步（deploy/README.md、backend/README.md 部署节、MANIFEST）。

## 2. 已确认的范围决策

| 决策点 | 结论 |
| --- | --- |
| 部署形态 | 双模式：`sudo bash install.sh`（系统级）/ `bash install.sh`（用户级），uid 自动判定 |
| 交付方式 | 源码包（backend 源码 + static 前端产物 + deploy 脚手架），**不含 wheels**，依赖部署机在线 pip 安装 |
| root 模式 | 行为不变：`/opt/docrelease` + 系统用户 `docrelease` + `/etc/systemd/system` |
| 非 root 模式 | `~/docrelease` + 当前用户 + `~/.config/systemd/user` + `systemctl --user` |
| 服务单元模板 | `docrelease.service` 模板不改（占位符 `__APP_USER__/__DEPLOY_ROOT__/__PORT__` 保留），两模式差异由 install.sh sed 处理 |
| 跨模式升级 | 不支持（root 装的后用非 root 升级等），旧服务占端口时由端口检查自然拦截并给出明确报错 |
| 健康检查 | 保留 deadline 驱动 30 秒硬超时模式（对齐 ai-material-generator 修复版） |

## 3. install.sh 改造要点

结构复刻 `ai-material-generator/deploy/install.sh`（已在 WSL 真实验证），关键差异：本脚本保留
`git` 前置检查（示例仓库生成与"注册本地仓库"功能依赖 git）。

### 3.1 模式判定与变量作用域（吸取先例踩坑教训）

模式相关变量（`DEPLOY_ROOT`、`APP_USER`、`UNIT_DIR`）**必须在 if/else 分支内各自完整赋值**，
分支外不留任何跨模式默认值——否则非 root 分支静默沿用错误路径，向 `/etc` 写单元文件报
Permission denied（ai-material-generator 实测踩坑，`bash -n` 无法暴露）：

```bash
IS_ROOT=0
if [ "$(id -u)" -eq 0 ]; then IS_ROOT=1; fi
if [ "$IS_ROOT" -eq 1 ]; then
  DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/docrelease}"
  APP_USER="${APP_USER:-docrelease}"
  UNIT_DIR="/etc/systemd/system"
else
  DEPLOY_ROOT="${DEPLOY_ROOT:-$HOME/docrelease}"
  APP_USER="$(id -un)"
  UNIT_DIR="$HOME/.config/systemd/user"
  # su/部分环境缺少该变量时 systemctl --user 无法连接用户总线
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
fi
```

服务操作封装：`svc()` —— root 走 `systemctl`，非 root 走 `systemctl --user`。

### 3.2 删除离线 wheels 逻辑、新增在线 pip

- 包完整性检查删去 `wheels/`（保留 backend/、static/、deploy/）；
- 删去 wheels 目录 rsync；
- `pip install --no-index --find-links ...` → `pip install -r requirements.txt`（走部署机
  pip 源，支持 `PIP_INDEX_URL` 覆盖），安装前探测 pip 源可达性，不通仅警告；
- 借鉴先例健壮性改进：venv 创建失败时清理半成品目录并输出
  `apt install python3.11-venv` 提示，避免残留半成品 venv 使二次安装静默卡死；
- 脚本内文案同步：头部注释改双模式用法说明；包完整性检查错误提示中
  “离线包/请先执行 build_offline_package.ps1”改为“部署包/build_package.ps1”。

### 3.3 systemd 安装（两分支）

- root：三占位符 sed 渲染 → 写 `$UNIT_DIR/docrelease.service` → `chown -R $APP_USER`；
- 非 root：同 sed **额外** `/^User=/d`（用户单元下 User= 指向自身即冗余）+
  `WantedBy=multi-user.target → default.target`；无 chown（目录本属当前用户）；
- 共同：`svc daemon-reload && svc enable && svc restart`。

### 3.4 升级停服务检测

原硬编码 `/etc/systemd/system/${SERVICE_NAME}.service` 改为 `$UNIT_DIR/${SERVICE_NAME}.service`
（首次安装无单元则跳过；跨模式旧服务占端口由既有 `ss -ltn` 端口检查拦截）。

### 3.5 lingering 与健康检查

- **lingering 检查放健康检查之前**（先例脚本中该检查位于 `exit 1` 之后属死代码，本设计修正）：
  非 root 模式下检测 `loginctl show-user` 的 `Linger=`，未启用则提示管理员一次性执行
  `sudo loginctl enable-linger <user>`——决定登出/重启后用户级服务是否存活；
- 健康检查保留 deadline 驱动 30 秒硬超时（单次 curl 受剩余时间约束）；
  失败提示区分 `journalctl -u`（root）/ `journalctl --user -u`（非 root）。

### 3.6 不变项

前置检查的 python3.11、git、rsync、星语网关探测（警告不阻断）；rsync 铺设文件与现场数据
排除清单（venv/.env/docrelease.db/archive/sample_repo/static）；.env 模板初始化逻辑。

## 4. 构建脚本改造（build_offline_package.ps1 → build_package.ps1）

- 重命名并删除：`-WheelSource` 参数与 platform/wsl 双下载路径、wheel 平台校验
  （win_amd64 检查、tree_sitter 等关键二进制在场检查）、wheels/ 目录骨架、wheel 数量输出；
- 产物名：`out/docrelease-package-<日期>.zip`（同日重跑自动加 HHmmss 后缀，沿用现状）；
- 源码收集逻辑不动（robocopy 排除清单、前端 npm run build 含 vue-tsc 类型检查）；
- MANIFEST.md：删 wheel 来源行；包结构行去掉 wheels/；部署提示改为双模式描述。

## 5. 文档同步

- `deploy/README.md`：构建节单命令（无 -WheelSource）；解压路径分 root（`/opt/docrelease/packages`）
  与非 root（家目录任意可写位置）两场景；安装节双模式入口；验证/回滚命令补
  `systemctl --user`、`journalctl --user -u` 变体；
- `backend/README.md` 部署节：措辞由"内网 Linux 离线部署"改为源码包 + 在线 pip 描述（单行改动）。

## 6. 新增 .gitattributes

`doc-release/.gitattributes`：`*.sh text eol=lf`——防止 Windows 重新 checkout 后 install.sh
变 CRLF 导致部署机 bash 报错（ai-material-generator 先例已验证必要性）。

## 7. 验证方式

1. `bash -n` 语法检查 + LF 行尾确认（gitattributes 生效后 git 侧保证）；
2. WSL 内以非 root 用户**真实执行**验证副本（sed 放宽 Python 版本要求后跑，产品脚本不改）——
   模式变量作用域、单元写入 `~/.config/systemd/user/`、`svc` 走 `--user` 总线为核心验证点；
   WSL Python 3.14 与依赖兼容性导致的健康检查失败属环境预期，不算脚本缺陷；
3. 全量 grep 确认 doc-release 内无 wheels/离线残留引用（backend/tests 的"离线可跑"测试语义
   指不联网跑测试，与部署交付形态无关，不改）。

## 8. 风险与约束

| 风险/约束 | 应对 |
| --- | --- |
| 非 root 安装但部署机 pip 源不可达 | 安装前探测仅告警不阻断；若 `pip install` 实际失败，脚本中止并提示配置内网源后重跑 |
| 模式变量作用域错误（先例实测踩坑） | 变量赋值全部收进分支内 + WSL 真实非 root 执行验证 |
| 用户级服务随会话终止 | 安装时检测 lingering 并给出一次性 enable 命令提示 |
| 跨模式升级（root 装、非 root 升） | 明确不支持；端口占用检查自然拦截并报错 |
| install.sh CRLF 化 | 新增 .gitattributes 固定 eol=lf |
| 树莓派/无 systemd 环境 | 非目标，沿用原方案约束 |
