# ai-material-generator 海报配图（脚本 → 海报图）设计

日期：2026-10-16
状态：已与用户逐项确认

## 1. 背景与目标

海报脚本（poster_script）目前只是 LLM 生成的 Markdown 文案，用户无法据此得到海报图片。星语平台已提供文生图接口 `POST /api/chat/image`，且已实测打通（图片专用机器人 ROBOT_00000418，uat 网关 http://10.130.13.74:8060，同步模式约 14 秒出图）。

目标：在海报脚本页新增「海报配图」能力——从脚本文本提炼视觉描述，经用户确认后调用星语文生图，图片落地为用户可管理的资产（预览/下载/删除）。

## 2. 星语文生图接口实测要点（集成依据）

| 项 | 实测结论 |
|---|---|
| 调用方式 | `POST /api/chat/image`，payload：`{robotCode, async: false, prompt, requestId}`；**只能同步**（async=true 秒级 400「请求阿里云后端文生图服务失败」） |
| requestId | 文档标非必填，**实际必传**（缺失返回空响应） |
| 图片 URL 位置 | 在 `data.contents[0].content`（chatType=5），**不在**文档所称 `data.results`（实际为 null）；解析时兼容两种位置，优先 contents |
| 机器人 | ROBOT_00000418 为文生图专用；chat 机器人（ROBOT_00000149）调此接口 401。robotCode 按能力隔离，prod 编码需另行确认，先占位 |
| URL 时效 | 阿里云 OSS 签名临时链接，约 24 小时过期 → **必须服务端立即下载转存** |
| 图片规格 | 实测单图约 6MB PNG |
| 耗时 | 同步出图约 14 秒 → 前端需 loading 提示 |

## 3. 已确认决策

| 决策点 | 结论 | 说明 |
|---|---|---|
| prompt 来源 | 脚本 → chat 提炼视觉描述 → **用户确认/可编辑** → 文生图 | 在两步链路中间加用户确认环节（用户指定） |
| 描述提炼缓存 | 按「owner + 脚本内容哈希」缓存提炼结果 | 同脚本不重复提炼；脚本改动自动失效 |
| 生图结果 | 每次确认都生成新图，**不做生图缓存** | 支持多张备选挑图 |
| 存储与访问 | 本地磁盘 + 鉴权接口 | OSS URL 立即下载转存 `backend/poster_images/`，DB 存元数据；访问走带 token 的 API |
| 审核流 | **图片不进审核流** | 图片是会话内素材（生成/预览/下载/删除）；被审核的仍是脚本文本 |
| 代码组织 | **独立海报域模块** | 新建 api/posters.py + services/poster_writer.py + models/poster_image.py，不动现有生成/审核链路 |
| 权限 | 提炼/生图 editor 专属；图片查看/下载/删除仅本人 | 沿用 `Depends(get_current_user)` + 函数体判 role |

被否决的备选：脚本全文直接作文生图 prompt（文案非视觉描述，出图不可控）；用户从零手写 prompt（多一步操作，失去自动化价值）；DB 存 BLOB（单图 6MB，库膨胀读写慢）；公开静态目录挂载（绕过鉴权）；图片进审核流（状态机改动面大，首版不需要）。

## 4. 总体链路

```
海报脚本文本 ──①提炼──> 视觉描述 prompt ──②前端对话框：用户确认/编辑──> 文生图（星语 ROBOT_00000418）
                                                        │
                            OSS 临时 URL ──③同步下载转存──> 本地 poster_images/{owner_id}/{uuid}.png
                                                        │
                                          ④DB 记元数据 ──> 鉴权接口：列表 / 文件 / 删除
```

- ①② 为两个独立 API，用户确认在前端对话框内完成
- 提炼（约 10 秒）与生图（约 15-20 秒）均为同步请求，前端全程 loading

## 5. 后端设计

### 5.1 星语文生图封装（app/services/xingyu_api.py 追加）

跟随现有 `env` 分支风格新增模块变量：

```python
if env == "dev":
    xingyu_url = "http://10.130.13.74:8060/api/chat/chat"   # 既有
    image_robot_code = "ROBOT_00000418"        # 文生图专用
    image_url = "http://10.130.13.74:8060/api/chat/image"
else:
    xingyu_url = "http://nlup-llm-inter.yto56.com.cn:8060/api/chat/chat"   # 既有
    image_robot_code = "ROBOT_00000418"        # 占位，prod 上线前必须替换
    image_url = "http://nlup-llm-inter.yto56.com.cn:8060/api/chat/image"
```

- `xingyu_text_to_image_api(prompt) -> str | None`：同步 `POST image_url`，payload `{robotCode: image_robot_code, async: False, prompt, requestId: uuid4}`，timeout 120s；解析优先 `data.contents[0].content`、回退 `data.results[0]`；status!=0 记日志返回 None
- `generate_poster_image_url(prompt) -> str`：`asyncio.to_thread` 异步包装 xingyu_text_to_image_api，返回图片 OSS URL；无有效内容抛 RuntimeError（与 poster_writer 的 generate_poster_image 分工：前者只拿 URL，后者负责下载）

### 5.2 数据模型（新建 app/models/poster_image.py，两张表）

**PosterPrompt**（提炼结果缓存）`poster_prompts`：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | |
| owner_id | Integer FK(users.id) | |
| script_hash | String(64) | 脚本内容 md5（`compute_analysis_hash` 同款 hashlib 方式，避免 PYTHONHASHSEED 漂移） |
| prompt | Text | 提炼出的视觉描述 |
| created_at / updated_at | DateTime | |

唯一约束：`(owner_id, script_hash)`——同用户同脚本只有一份提炼结果，覆盖式更新。

**PosterImage**（图片资产）`poster_images`：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | |
| owner_id | Integer FK(users.id) | |
| source_title | String(255) | 来源文档标题（列表过滤用） |
| audience | String(64) | 受众（列表过滤用） |
| prompt | Text | 生图时的 prompt 快照（用户确认/编辑后的版本） |
| file_path | String(512) | 相对 backend 的存储路径 |
| file_size | Integer | 字节数 |
| created_at | DateTime | |

建表由 lifespan `create_all` 自动完成，无需迁移。

### 5.3 服务层

**app/services/poster_writer.py**（新建）：

- `REFINE_PROMPT` 模板：输入海报脚本文本，要求输出「一段可直接用于文生图的中文视觉描述」，覆盖主体、场景、氛围、配色、风格，不含广告语/文字排版要求（文生图模型对画面内文字渲染不可靠，描述里不要求出现文字）
- 前置小改造：`material_writer._chat` 的星语分支 system_prompt 硬编码为「你是一名资深运营文案。」，提炼需要「视觉设计」人设——改为优先取 messages 中 system 角色内容，无 system 消息时保留现有默认（既有调用方只传 user 消息，行为不变，现有测试作安全网）
- `refine_poster_prompt(script_content: str) -> str`：组 `[system(视觉设计师人设), user(REFINE_PROMPT + 脚本)]` → 调 `material_writer._chat`（复用 provider 路由：xingyu 走 generate_by_xingyu，deepseek 走 _chat_deepseek）
- `generate_poster_image(prompt: str) -> tuple[str, bytes]`：调 `xingyu_api.generate_poster_image_url` 拿 URL → 下载（httpx/requests）→ 校验非空与 PNG 魔数 → 返回 (URL, bytes)；失败抛 RuntimeError
- `save_poster_image(owner_id: int, data: bytes) -> str`：写 `backend/poster_images/{owner_id}/{uuid4}.png`，目录按 `__file__` 推导（systemd WorkingDirectory 无关），mkdir parents，返回相对路径（DB 的 source_title/audience/prompt 字段由 service 层入库时写入，落盘只关心文件）

**app/services/poster_image_service.py**（新建，DB CRUD）：

- `get_poster_prompt(db, owner_id, script_hash)` / `upsert_poster_prompt(db, ...)`
- `create_poster_image(db, ...)` / `list_poster_images(db, owner_id, source_title, audience)` / `get_poster_image_by_id(db, image_id)` / `delete_poster_image(db, image)`（删除时同步 unlink 磁盘文件，missing_ok）

### 5.4 API（新建 app/api/posters.py，router 挂 prefix="/api/posters"）

| 端点 | 方法 | 权限 | 行为 |
|---|---|---|---|
| `/api/posters/prompt` | POST | editor | body `{script_content}` → 算 script_hash → 命中缓存直接返回 `{prompt, cached: true}`；否则提炼并 upsert，返回 `{prompt, cached: false}`。失败 502 |
| `/api/posters/images` | POST | editor | body `{source_title, audience, prompt}` → 生图+下载+落盘+入库 → 200 返回图片记录 dict（与现有 materials POST 一致，不设 201）。失败 502 带原因 |
| `/api/posters/images` | GET | 登录 | query `source_title`、`audience` → 当前用户该组合的图片列表（新→旧） |
| `/api/posters/images/{image_id}/file` | GET | 本人 | FileResponse 返回 PNG（media_type image/png）；非本人或不存在 404 |
| `/api/posters/images/{image_id}` | DELETE | 本人 | 删记录+磁盘文件；非本人或不存在 404 |

权限实现沿用既有模式：`user: UserOut = Depends(get_current_user)`，函数体内 `user.role != "editor"` 抛 403；图片访问比对 `image.owner_id == user.id`。

注册：app/api/router.py 追加 `include_router(posters_router, prefix="/api/posters")`，头部接口总览注释 21 → 26。

### 5.5 日志

poster_writer 生图链路对齐 material_writer 风格：记录 prompt 长度、duration、图片大小；API 层异常由现有 HTTP 中间件统一记录。

## 6. 前端设计（GeneratorView.vue + 新增 api/posters.ts）

**入口**：海报脚本 tab（activeMaterialType === 'poster_script'）且 currentMaterial 存在时，物料内容区下方渲染「海报配图」区块。

**交互流**：

1. 点击「生成海报图」→ 调 POST `/api/posters/prompt`（按钮 loading，提示「正在提炼画面描述…」）
2. 成功 → 打开 el-dialog：textarea（rows≈6）展示提炼的描述，**用户可直接编辑**；底部「确认生成」「取消」
3. 点击「确认生成」→ 调 POST `/api/posters/images`（按钮 loading，提示「正在生成海报图，约需 15-20 秒…」；对话框不关闭直到成功/失败）
4. 成功 → 关闭对话框 + ElMessage.success + 刷新图片列表
5. 失败 → ElMessage.error 展示后端 detail

**图片列表**：

- 进入海报脚本 tab 或切换受众/脚本时，按 `source_title + audience` 拉取列表
- 网格卡片：缩略图用 `fetch` 带 Authorization → blob → objectURL 渲染（复用 api client 的 token 注入模式）；卡片操作：**下载原图**（fetch blob + a[download] + 文件名 `{source_title}-海报图-{id}.png`）、**删除**（ElMessageBox.confirm 后调 DELETE）
- 空态文案：「点击「生成海报图」，把脚本变成海报」

**api/posters.ts**：`refinePosterPrompt(scriptContent)`、`createPosterImage(payload)`、`listPosterImages(query)`、`fetchPosterImageFile(id)`（blob）、`deletePosterImage(id)`。

## 7. 错误处理

| 场景 | 行为 |
|---|---|
| 提炼失败（chat 超时/异常） | POST /prompt → 502「画面描述提炼失败: {原因}」 |
| 文生图失败（星语 status!=0/超时） | POST /images → 502「海报图生成失败: {原因}」 |
| OSS 下载失败/非图片内容 | 同上 502，写日志，不产生半成品记录 |
| 落盘失败 | 抛异常 → 502；无 DB 记录（先写文件后写库，失败文件残留仅磁盘垃圾，可重试覆盖场景少） |
| 越权访问/删除他人图片 | 404（不泄露存在性） |
| 未登录 | 401（现有 get_current_user 行为） |
| reviewer 调提炼/生图 | 403 |

写文件成功但入库失败时：unlink 已写文件再抛异常（不留孤儿文件）。

## 8. 测试计划（TDD）

新增 `tests/test_posters_api.py`（API 层）与 `tests/test_poster_writer.py`（服务层），全部 mock 星语网络调用，不打真实模型：

1. POST /prompt：未登录 401；reviewer 403；首次提炼调 chat 一次并落缓存；二次同内容命中缓存（chat mock 断言 call_count==1）；不同 owner 不共享缓存
2. POST /images：mock generate_poster_image 返回 (url, bytes) → 200，文件落盘、DB 有记录；mock 抛错 → 502；reviewer 403
3. GET /images?source_title&audience：按 owner 隔离，只返回本人该组合
4. GET /images/{id}/file：本人 200 + image/png + 内容一致；他人 404；不存在 404
5. DELETE /images/{id}：本人删除后记录消失 + 磁盘文件不存在；他人 404
6. 落盘→入库失败回滚 unlink 的用例
7. 服务层：save_poster_image 写入路径/大小正确；script_hash 稳定（同内容同哈希）

patch 目标约定：提炼链路 patch `app.services.poster_writer` 内实际解析的名字；生图链路 patch `app.services.poster_writer.generate_poster_image`。**全量 pytest 耗时显著超出既有基线即说明有替身失效打到真实模型（历史教训：会从几十秒涨到分钟级），必须排查。**

回归：全量 `pytest tests -q`（当前 70 passed）+ 前端 `npm run build`。

## 9. 真实环境验证

mock 测试之外，端到端冒烟须走真实链路（星语可达）：

1. editor 登录 → 对已生成的海报脚本调 POST /prompt → 返回视觉描述文本
2. 确认 prompt 调 POST /images → 约 15-20 秒返回记录
3. GET /images/{id}/file 拉回 PNG，校验魔数与大小
4. 前端页面走完整交互：生成 → 对话框编辑描述 → 确认 → 缩略图出现 → 下载 → 删除
5. 验证 prod 占位 robotCode 不会被误用（uat 配置下全链路在 uat 网关完成）

## 10. 非目标（YAGNI）

- 不做图片压缩/格式转换（6MB PNG 原样保存，内网磁盘成本可接受）
- 不做批量生图、多分辨率、生图结果缓存
- 不做图片进审核流
- 不做提示词模板管理/风格预设库
- prod robotCode 不在本次范围（占位，待平台提供后替换）
- 不改动现有 6 类文本物料的生成/缓存/审核链路

## 11. 交付物清单

| 文件 | 类型 |
|---|---|
| `backend/app/services/xingyu_api.py` | 追加文生图封装（image_robot_code + 2 函数） |
| `backend/app/models/poster_image.py` | 新建（PosterPrompt + PosterImage） |
| `backend/app/services/poster_writer.py` | 新建（提炼模板 + 生图 + 落盘） |
| `backend/app/services/poster_image_service.py` | 新建（DB CRUD） |
| `backend/app/api/posters.py` | 新建（5 端点） |
| `backend/app/api/router.py` | 追加注册 + 总览注释更新 |
| `backend/tests/test_posters_api.py`、`test_poster_writer.py` | 新建 |
| `frontend/src/api/posters.ts` | 新建 |
| `frontend/src/views/GeneratorView.vue` | 追加海报配图区块 |
| `.gitignore`（backend 或项目级） | 追加 poster_images/ 忽略 |
