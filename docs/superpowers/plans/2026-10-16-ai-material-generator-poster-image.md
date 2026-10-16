# 海报配图（脚本生成海报图）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 ai-material-generator 海报脚本页新增「海报配图」能力：脚本 → LLM 提炼视觉描述 → 用户确认/编辑 → 星语文生图 → 本地转存 → 鉴权浏览/下载/删除。

**Architecture:** 独立海报域模块（api/posters.py + services/poster_writer.py + services/poster_image_service.py + models/poster_image.py 两张表）。提炼结果按 owner+脚本哈希缓存；生图每次都出新图；图片存 `backend/poster_images/{owner_id}/`，通过带鉴权的 API 提供文件访问；不进审核流。

**Tech Stack:** FastAPI + SQLAlchemy async（SQLite，无 alembic，create_all 建表）、requests（同步星语调用 + asyncio.to_thread）、Vue3 + Element Plus + axios。

**设计文档:** `docs/superpowers/specs/2026-10-16-ai-material-generator-poster-image-design.md`（已确认，commit 98edf93）

**关键实测约束（星语文生图接口）:**
- 仅同步模式可用（async=false），约 14 秒出图；async=true 秒级 400
- 图片 URL 在 `data.contents[0].content`，不在文档所称 `data.results`（为 null）——解析须兼容两者，优先 contents
- `requestId` 实际必传（缺失返回空响应）
- OSS URL 约 24 小时过期，必须服务端立即下载转存
- uat robotCode=`ROBOT_00000418`；prod 编码待确认，先占位

**工作目录约定:** 后端命令均在 `D:\StudyProjects\ai-practice\ai-material-generator\backend` 下执行，Python 用 `.\venv\Scripts\python.exe`。git 在仓库根 `D:\StudyProjects\ai-practice`。

**提交约定:** 每个 Task 一次 commit 到本地 dev 分支，消息用 `feat(posters):`/`test(posters):`/`feat(ui):` 前缀。**不要推送**（用户惯例：仅本地）。

---

## 文件结构总览

| 文件 | 操作 | 职责 |
|---|---|---|
| `backend/app/services/xingyu_api.py` | 修改 | 追加 image_url/image_robot_code 变量 + xingyu_text_to_image_api + generate_poster_image_url |
| `backend/app/services/material_writer.py` | 修改 | _chat 星语分支 system prompt 透传（取 messages 中 system 角色） |
| `backend/app/models/poster_image.py` | 新建 | PosterPrompt / PosterImage 两表 + compute_script_hash |
| `backend/app/services/poster_writer.py` | 新建 | 提炼模板 + refine_poster_prompt + generate_poster_image + save/remove_poster_image |
| `backend/app/services/poster_image_service.py` | 新建 | 两表的 DB CRUD |
| `backend/app/api/posters.py` | 新建 | 5 个端点 |
| `backend/app/api/router.py` | 修改 | 注册 posters_router + 接口总览注释 21→26 |
| `backend/tests/test_poster_writer.py` | 新建 | 封装解析/_chat 透传/提炼/生图落盘 单测 |
| `backend/tests/test_posters_api.py` | 新建 | 5 端点 API 测试 |
| `backend/e2e_poster_smoke.py` | 新建 | 真实链路端到端冒烟（跑完保留，供以后回归） |
| `ai-material-generator/.gitignore` | 修改 | 追加 poster_images/ |
| `frontend/src/api/posters.ts` | 新建 | 5 个 API 封装 |
| `frontend/src/views/GeneratorView.vue` | 修改 | 海报配图区块（script + template + style） |
| `ai-material-generator/README.md` | 修改 | 功能说明 |

---

### Task 1: 星语文生图封装（xingyu_api.py）

**Files:**
- Modify: `ai-material-generator/backend/app/services/xingyu_api.py`
- Test: `ai-material-generator/backend/tests/test_poster_writer.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_poster_writer.py`：

```python
"""海报配图服务层测试：星语文生图封装 / _chat 透传 / 提炼 / 生图落盘。全部 mock 网络调用。"""
import pytest

from app.services import xingyu_api


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _image_payload(content="http://oss/img.png"):
    return {
        "status": 0,
        "data": {
            "contents": [{"index": 0, "content": content, "reasoningContent": None}],
            "results": None,
        },
    }


def test_text_to_image_prefers_contents(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, data=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return FakeResponse(payload=_image_payload("http://oss/from-contents.png"))

    monkeypatch.setattr(xingyu_api.requests, "post", fake_post)
    url = xingyu_api.xingyu_text_to_image_api("一只橙猫")
    assert url == "http://oss/from-contents.png"
    assert captured["url"] == xingyu_api.image_url
    assert '"async": false' in captured["data"]
    assert xingyu_api.image_robot_code in captured["data"]


def test_text_to_image_falls_back_to_results(monkeypatch):
    payload = {"status": 0, "data": {"contents": [], "results": ["http://oss/from-results.png"]}}

    def fake_post(url, headers=None, data=None, timeout=None):
        return FakeResponse(payload=payload)

    monkeypatch.setattr(xingyu_api.requests, "post", fake_post)
    assert xingyu_api.xingyu_text_to_image_api("p") == "http://oss/from-results.png"


def test_text_to_image_returns_none_on_error_status(monkeypatch):
    payload = {"status": 400, "message": "请求阿里云后端文生图服务失败!", "data": None}

    def fake_post(url, headers=None, data=None, timeout=None):
        return FakeResponse(payload=payload, text='{"status": 400}')

    monkeypatch.setattr(xingyu_api.requests, "post", fake_post)
    assert xingyu_api.xingyu_text_to_image_api("p") is None


def test_text_to_image_returns_none_on_network_exc(monkeypatch):
    def fake_post(url, headers=None, data=None, timeout=None):
        raise xingyu_api.requests.ConnectionError("boom")

    monkeypatch.setattr(xingyu_api.requests, "post", fake_post)
    assert xingyu_api.xingyu_text_to_image_api("p") is None


@pytest.mark.asyncio
async def test_generate_poster_image_url_async_wrapper(monkeypatch):
    async def fake_sync_wrapper(prompt):
        return "http://oss/ok.png"

    monkeypatch.setattr(xingyu_api, "xingyu_text_to_image_api", lambda p: "http://oss/ok.png")
    assert await xingyu_api.generate_poster_image_url("p") == "http://oss/ok.png"


@pytest.mark.asyncio
async def test_generate_poster_image_url_raises_without_url(monkeypatch):
    monkeypatch.setattr(xingyu_api, "xingyu_text_to_image_api", lambda p: None)
    try:
        await xingyu_api.generate_poster_image_url("p")
        assert False, "应抛 RuntimeError"
    except RuntimeError:
        pass
```

- [ ] **Step 2: 运行确认失败**

```
.\venv\Scripts\python.exe -m pytest tests/test_poster_writer.py -v
```
预期：6 个用例全部 FAIL（`AttributeError: ... has no attribute 'image_url'` / `xingyu_text_to_image_api` 不存在）。

- [ ] **Step 3: 实现**

在 `backend/app/services/xingyu_api.py` 的 env 分支改为（保留既有 xingyu_url/robot_code/request_id/flow_code 行不动，仅新增两行）：

```python
if env == "dev":
    xingyu_url = "http://10.130.13.74:8060/api/chat/chat"
    robot_code = "ROBOT_00000149"
    request_id = "248fef55-a329-477f-8b76-23354bd16c7f"
    flow_code = "Flow_00000156"
    # 文生图专用机器人（chat 机器人调 /api/chat/image 会 401，robotCode 按能力隔离）
    image_robot_code = "ROBOT_00000418"
    image_url = "http://10.130.13.74:8060/api/chat/image"
else:
    xingyu_url = "http://nlup-llm-inter.yto56.com.cn:8060/api/chat/chat"
    # robot_code = "ROBOT_00000065"
    robot_code = "ROBOT_00000090"
    flow_code = ""
    # 占位：prod 文生图机器人编码待平台提供后替换
    image_robot_code = "ROBOT_00000418"
    image_url = "http://nlup-llm-inter.yto56.com.cn:8060/api/chat/image"
```

在文件末尾追加两个函数：

```python
def xingyu_text_to_image_api(prompt: str) -> Optional[str]:
    """同步调用星语文生图接口，返回图片 OSS 临时 URL；失败返回 None。

    实测要点：仅 async=false 可用；URL 优先在 data.contents[0].content
    （chatType=5），文档所称 data.results 实测为 null，两者都兼容。
    """
    payload = {
        "robotCode": image_robot_code,
        "async": False,
        "prompt": prompt,
        "requestId": f"{uuid.uuid4()}",
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(
            url=image_url, headers=headers, data=json.dumps(payload), timeout=120
        )
    except requests.RequestException as exc:
        logger.error(f"xingyu_text_to_image_api(prompt={prompt[:50]}...) failed=>EXC({exc})")
        return None
    if response.status_code != 200:
        logger.error(
            f"xingyu_text_to_image_api failed=>StatusCode({response.status_code})"
        )
        return None
    result = response.json()
    if f"{result.get('status')}" != "0":
        logger.error(
            f"xingyu_text_to_image_api failed=>Result({response.text[:300]})"
        )
        return None
    data = result.get("data") or {}
    contents = data.get("contents") or []
    if contents and isinstance(contents[0], dict) and contents[0].get("content"):
        return contents[0]["content"]
    results = data.get("results") or []
    if results:
        return results[0]
    logger.error(f"xingyu_text_to_image_api failed=>NoImageUrl({response.text[:300]})")
    return None


async def generate_poster_image_url(prompt: str) -> str:
    """异步包装 xingyu_text_to_image_api，返回图片 OSS 临时 URL；失败抛 RuntimeError。"""
    import asyncio

    url = await asyncio.to_thread(xingyu_text_to_image_api, prompt)
    if not url:
        raise RuntimeError("星语文生图未返回图片 URL")
    return url
```

- [ ] **Step 4: 运行确认通过**

```
.\venv\Scripts\python.exe -m pytest tests/test_poster_writer.py -v
```
预期：6 passed。

- [ ] **Step 5: 提交**

```bash
git add ai-material-generator/backend/app/services/xingyu_api.py ai-material-generator/backend/tests/test_poster_writer.py
git commit -m "feat(posters): 星语文生图接口封装（同步模式，兼容 contents/results 两种返回位置）"
```

---

### Task 2: material_writer._chat 透传 system prompt

**Files:**
- Modify: `ai-material-generator/backend/app/services/material_writer.py`（_chat 函数，约 L62-67）
- Test: `ai-material-generator/backend/tests/test_poster_writer.py`（追加）

- [ ] **Step 1: 追加失败测试**

在 `tests/test_poster_writer.py` 末尾追加：

```python
async def _fake_xingyu_capture(captured, system_prompt, user_prompt):
    captured["system"] = system_prompt
    captured["user"] = user_prompt
    return "ok"


@pytest.mark.asyncio
async def test_chat_passes_system_role_to_xingyu(monkeypatch):
    from app.config import settings
    from app.services import material_writer

    captured = {}
    monkeypatch.setattr(material_writer.settings, "llm_provider", "xingyu")
    monkeypatch.setattr(
        material_writer,
        "generate_by_xingyu",
        lambda s, u: _fake_xingyu_capture(captured, s, u),
    )
    result = await material_writer._chat(
        [
            {"role": "system", "content": "你是视觉设计师。"},
            {"role": "user", "content": "描述一只猫"},
        ]
    )
    assert result == "ok"
    assert captured["system"] == "你是视觉设计师。"
    assert captured["user"] == "描述一只猫"


@pytest.mark.asyncio
async def test_chat_keeps_default_system_without_system_msg(monkeypatch):
    from app.config import settings
    from app.services import material_writer

    captured = {}
    monkeypatch.setattr(material_writer.settings, "llm_provider", "xingyu")
    monkeypatch.setattr(
        material_writer,
        "generate_by_xingyu",
        lambda s, u: _fake_xingyu_capture(captured, s, u),
    )
    await material_writer._chat([{"role": "user", "content": "写一篇宣发稿"}])
    assert captured["system"] == "你是一名资深运营文案。"
```

- [ ] **Step 2: 运行确认失败**

```
.\venv\Scripts\python.exe -m pytest tests/test_poster_writer.py -v
```
预期：新增 2 个用例 FAIL（`captured["system"]` 为硬编码的「你是一名资深运营文案。」），原 6 个仍 PASS。

- [ ] **Step 3: 实现**

`backend/app/services/material_writer.py` 中 `_chat` 改为：

```python
async def _chat(messages: list[dict]) -> str:
    if settings.llm_provider == "xingyu":
        # 优先取调用方传入的 system 人设；无 system 消息时保留历史默认
        system_prompt = next(
            (m["content"] for m in messages if m.get("role") == "system"),
            "你是一名资深运营文案。",
        )
        user_prompt = messages[-1]["content"] if messages else ""
        return await generate_by_xingyu(system_prompt, user_prompt)
    return await _chat_deepseek(messages)
```

- [ ] **Step 4: 运行确认通过 + 回归既有用例**

```
.\venv\Scripts\python.exe -m pytest tests/test_poster_writer.py tests/test_generate_cache.py -v
```
预期：全部 PASS（既有调用方只传 user 消息，行为不变）。

- [ ] **Step 5: 提交**

```bash
git add ai-material-generator/backend/app/services/material_writer.py ai-material-generator/backend/tests/test_poster_writer.py
git commit -m "feat(posters): _chat 星语分支透传 system 人设（无 system 时保留默认）"
```

---

### Task 3: 海报数据模型与 DB 服务

**Files:**
- Create: `ai-material-generator/backend/app/models/poster_image.py`
- Create: `ai-material-generator/backend/app/services/poster_image_service.py`
- Test: `ai-material-generator/backend/tests/test_poster_writer.py`（追加）

- [ ] **Step 1: 追加失败测试**

`tests/test_poster_writer.py` 顶部 import 区追加（必须模块级导入：conftest 的 db_session 在 fixture 阶段才 create_all，模型须在收集阶段注册进 Base.metadata）：

```python
import pytest_asyncio
from app.models import poster_image  # noqa: F401  注册两张海报表进 Base.metadata
from app.services import poster_image_service  # noqa: F401
```

末尾追加：

```python
@pytest.mark.asyncio
async def test_compute_script_hash_stable():
    from app.models.poster_image import compute_script_hash

    assert compute_script_hash("abc") == compute_script_hash("abc")
    # md5 跨进程稳定（不受 PYTHONHASHSEED 影响）
    assert compute_script_hash("x") == "9dd4e461268c8034f5c8564e155c67a6"


@pytest.mark.asyncio
async def test_poster_prompt_upsert_and_owner_isolation(db_session):
    from app.models.poster_image import compute_script_hash
    from app.services import poster_image_service as poster_svc

    h = compute_script_hash("脚本A")
    first = await poster_svc.upsert_poster_prompt(db_session, 1, h, "描述v1")
    got = await poster_svc.get_poster_prompt(db_session, 1, h)
    assert got is not None and got.id == first.id and got.prompt == "描述v1"
    # 同 owner 同脚本：覆盖更新（同一条记录）
    updated = await poster_svc.upsert_poster_prompt(db_session, 1, h, "描述v2")
    assert updated.id == first.id and updated.prompt == "描述v2"
    # 不同 owner 不共享缓存
    assert await poster_svc.get_poster_prompt(db_session, 2, h) is None


@pytest.mark.asyncio
async def test_poster_image_crud_and_to_dict(db_session):
    from app.services import poster_image_service as poster_svc

    image = await poster_svc.create_poster_image(
        db_session, 1, "标题T", "网点管理员", "一只橙猫", "poster_images/1/a.png", 123
    )
    got = await poster_svc.get_poster_image_by_id(db_session, image.id)
    assert got is not None and got.prompt == "一只橙猫"
    d = got.to_dict()
    assert d["image_url"] == f"/api/posters/images/{got.id}/file"
    assert "file_path" not in d  # 内部路径不外露
    items = await poster_svc.list_poster_images(db_session, 1, "标题T", "网点管理员")
    assert [i.id for i in items] == [image.id]
    assert await poster_svc.list_poster_images(db_session, 2, "标题T", "网点管理员") == []
    await poster_svc.delete_poster_image(db_session, got)
    assert await poster_svc.get_poster_image_by_id(db_session, image.id) is None
```

- [ ] **Step 2: 运行确认失败**

```
.\venv\Scripts\python.exe -m pytest tests/test_poster_writer.py -v
```
预期：新增 3 个用例 FAIL（ModuleNotFoundError: poster_image / poster_image_service）。

- [ ] **Step 3: 实现模型**

创建 `backend/app/models/poster_image.py`：

```python
import hashlib
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def compute_script_hash(script_content: str) -> str:
    """脚本内容的稳定哈希（提炼缓存键）。md5 跨进程稳定，不受 PYTHONHASHSEED 影响。"""
    return hashlib.md5(script_content.encode("utf-8")).hexdigest()


class PosterPrompt(Base):
    """画面描述提炼结果缓存：同 owner 同脚本只保留一份，覆盖式更新。"""

    __tablename__ = "poster_prompts"
    __table_args__ = (UniqueConstraint("owner_id", "script_hash", name="uix_poster_prompt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    script_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "script_hash": self.script_hash,
            "prompt": self.prompt,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PosterImage(Base):
    """生成的海报图片资产：不进审核流，归属生成者本人。"""

    __tablename__ = "poster_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    source_title: Mapped[str] = mapped_column(String(255), nullable=False)
    audience: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        # file_path 为内部路径不外露；前端经鉴权的 image_url 取文件
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "source_title": self.source_title,
            "audience": self.audience,
            "prompt": self.prompt,
            "file_size": self.file_size,
            "image_url": f"/api/posters/images/{self.id}/file",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

- [ ] **Step 4: 实现 DB 服务**

创建 `backend/app/services/poster_image_service.py`：

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.poster_image import PosterImage, PosterPrompt


async def get_poster_prompt(
    session: AsyncSession,
    owner_id: int,
    script_hash: str,
) -> PosterPrompt | None:
    stmt = select(PosterPrompt).where(
        PosterPrompt.owner_id == owner_id,
        PosterPrompt.script_hash == script_hash,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_poster_prompt(
    session: AsyncSession,
    owner_id: int,
    script_hash: str,
    prompt: str,
) -> PosterPrompt:
    record = await get_poster_prompt(session, owner_id, script_hash)
    if record is None:
        record = PosterPrompt(owner_id=owner_id, script_hash=script_hash)
        session.add(record)
    record.prompt = prompt
    await session.commit()
    await session.refresh(record)
    return record


async def create_poster_image(
    session: AsyncSession,
    owner_id: int,
    source_title: str,
    audience: str,
    prompt: str,
    file_path: str,
    file_size: int,
) -> PosterImage:
    image = PosterImage(
        owner_id=owner_id,
        source_title=source_title,
        audience=audience,
        prompt=prompt,
        file_path=file_path,
        file_size=file_size,
    )
    session.add(image)
    await session.commit()
    await session.refresh(image)
    return image


async def get_poster_image_by_id(session: AsyncSession, image_id: int) -> PosterImage | None:
    return await session.get(PosterImage, image_id)


async def list_poster_images(
    session: AsyncSession,
    owner_id: int,
    source_title: str,
    audience: str,
) -> list[PosterImage]:
    stmt = (
        select(PosterImage)
        .where(
            PosterImage.owner_id == owner_id,
            PosterImage.source_title == source_title,
            PosterImage.audience == audience,
        )
        .order_by(PosterImage.id.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_poster_image(session: AsyncSession, image: PosterImage) -> None:
    await session.delete(image)
    await session.commit()
```

- [ ] **Step 5: 运行确认通过**

```
.\venv\Scripts\python.exe -m pytest tests/test_poster_writer.py -v
```
预期：全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add ai-material-generator/backend/app/models/poster_image.py ai-material-generator/backend/app/services/poster_image_service.py ai-material-generator/backend/tests/test_poster_writer.py
git commit -m "feat(posters): PosterPrompt 提炼缓存与 PosterImage 图片资产模型及 DB 服务"
```

---

### Task 4: 画面描述提炼（poster_writer.refine_poster_prompt）

**Files:**
- Create: `ai-material-generator/backend/app/services/poster_writer.py`
- Test: `ai-material-generator/backend/tests/test_poster_writer.py`（追加）

- [ ] **Step 1: 追加失败测试**

`tests/test_poster_writer.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_refine_poster_prompt_composes_messages_and_strips(monkeypatch):
    from app.services import poster_writer

    captured = {}

    async def fake_chat(messages):
        captured["messages"] = messages
        return "  一只橙猫坐在草地上，扁平插画风格，阳光明媚  "

    monkeypatch.setattr(poster_writer.material_writer, "_chat", fake_chat)
    result = await poster_writer.refine_poster_prompt("# 网点管家升级海报\n卖点：一键上报")
    assert result == "一只橙猫坐在草地上，扁平插画风格，阳光明媚"
    assert captured["messages"][0]["role"] == "system"
    assert "视觉设计" in captured["messages"][0]["content"]
    assert "海报脚本" in captured["messages"][1]["content"]
    assert "一键上报" in captured["messages"][1]["content"]
```

- [ ] **Step 2: 运行确认失败**

```
.\venv\Scripts\python.exe -m pytest tests/test_poster_writer.py -v
```
预期：ModuleNotFoundError: No module named 'app.services.poster_writer'。

- [ ] **Step 3: 实现**

创建 `backend/app/services/poster_writer.py`：

```python
"""海报配图生成链路：脚本文本 → 画面描述提炼 → 星语文生图 → 本地落盘。

提炼走 material_writer._chat（provider 路由）；生图走 xingyu_api 文生图封装。
图片落盘目录按 __file__ 推导，不受进程 WorkingDirectory 影响。
"""
import asyncio
import logging
import time
import uuid
from pathlib import Path

import requests

from app.services import material_writer
from app.services.xingyu_api import generate_poster_image_url

logger = logging.getLogger("app.services.poster_writer")

REFINE_PROMPT = """你是一名资深视觉设计师。下面是一份海报脚本文案，请把它改写成一段可直接用于 AI 文生图工具的中文视觉描述。

要求：
- 画面描述需覆盖：主体形象、场景环境、氛围情绪、配色方案、画面风格
- 不要输出广告语、标语、文字排版要求（文生图模型无法可靠渲染文字）
- 只输出一段连贯的视觉描述，不超过 200 字，不要任何前缀和解释

海报脚本：
{script}"""


async def refine_poster_prompt(script_content: str) -> str:
    """把海报脚本文案提炼成文生图视觉描述。"""
    prompt = REFINE_PROMPT.format(script=script_content)
    messages = [
        {"role": "system", "content": "你是一名资深视觉设计师，擅长把文案创意转化为画面描述。"},
        {"role": "user", "content": prompt},
    ]
    start = time.perf_counter()
    description = await material_writer._chat(messages)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"refine_poster_prompt script_len={len(script_content)} "
        f"duration={duration_ms:.2f}ms response_length={len(description)}"
    )
    return description.strip()
```

- [ ] **Step 4: 运行确认通过**

```
.\venv\Scripts\python.exe -m pytest tests/test_poster_writer.py -v
```
预期：全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add ai-material-generator/backend/app/services/poster_writer.py ai-material-generator/backend/tests/test_poster_writer.py
git commit -m "feat(posters): 海报脚本提炼画面描述（复用 provider 路由）"
```

---

### Task 5: 生图下载与本地落盘（poster_writer）

**Files:**
- Modify: `ai-material-generator/backend/app/services/poster_writer.py`
- Test: `ai-material-generator/backend/tests/test_poster_writer.py`（追加）

- [ ] **Step 1: 追加失败测试**

`tests/test_poster_writer.py` 末尾追加：

```python
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32


@pytest.mark.asyncio
async def test_generate_poster_image_downloads_and_validates(monkeypatch):
    from app.services import poster_writer

    async def fake_url(prompt):
        return "http://oss/img.png"

    class FakeResp:
        status_code = 200
        content = PNG_BYTES

    monkeypatch.setattr(poster_writer, "generate_poster_image_url", fake_url)
    monkeypatch.setattr(poster_writer.requests, "get", lambda url, timeout: FakeResp())
    url, data = await poster_writer.generate_poster_image("橙猫草地")
    assert url == "http://oss/img.png"
    assert data == PNG_BYTES


@pytest.mark.asyncio
async def test_generate_poster_image_rejects_non_png(monkeypatch):
    from app.services import poster_writer

    async def fake_url(prompt):
        return "http://oss/img.png"

    class FakeResp:
        status_code = 200
        content = b"<html>not an image</html>"

    monkeypatch.setattr(poster_writer, "generate_poster_image_url", fake_url)
    monkeypatch.setattr(poster_writer.requests, "get", lambda url, timeout: FakeResp())
    try:
        await poster_writer.generate_poster_image("p")
        assert False, "非 PNG 应抛 RuntimeError"
    except RuntimeError as exc:
        assert "PNG" in str(exc)


def test_save_and_remove_poster_image(tmp_path, monkeypatch):
    from app.services import poster_writer

    monkeypatch.setattr(poster_writer, "POSTER_IMAGE_DIR", tmp_path / "poster_images")
    rel_path = poster_writer.save_poster_image(7, PNG_BYTES)
    assert rel_path.replace("\\", "/").startswith("poster_images/7/")
    absolute = tmp_path / rel_path
    assert absolute.is_file() and absolute.read_bytes() == PNG_BYTES
    # 删除（含不存在路径不报错）
    poster_writer.remove_poster_image(rel_path)
    assert not absolute.exists()
    poster_writer.remove_poster_image(rel_path)
```

- [ ] **Step 2: 运行确认失败**

```
.\venv\Scripts\python.exe -m pytest tests/test_poster_writer.py -v
```
预期：新增 3 个用例 FAIL（poster_writer 无 generate_poster_image / POSTER_IMAGE_DIR 属性）。

- [ ] **Step 3: 实现**

在 `backend/app/services/poster_writer.py` 中，import 区追加 `import asyncio`（若未导入），常量区（REFINE_PROMPT 之后）追加：

```python
# backend/app/services/poster_writer.py → parent×3 = backend/，图片目录 backend/poster_images/
POSTER_IMAGE_DIR = Path(__file__).resolve().parent.parent.parent / "poster_images"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
```

文件末尾追加：

```python
async def generate_poster_image(prompt: str) -> tuple[str, bytes]:
    """调星语文生图并下载图片，返回 (图片URL, 图片字节)。任一环节失败抛 RuntimeError。"""
    start = time.perf_counter()
    url = await generate_poster_image_url(prompt)
    response = await asyncio.to_thread(requests.get, url, timeout=60)
    if response.status_code != 200 or not response.content:
        raise RuntimeError(f"海报图下载失败: HTTP {response.status_code}")
    if not response.content.startswith(PNG_MAGIC):
        raise RuntimeError("海报图下载内容不是有效 PNG")
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"generate_poster_image prompt_len={len(prompt)} duration={duration_ms:.2f}ms "
        f"image_size={len(response.content)}"
    )
    return url, response.content


def save_poster_image(owner_id: int, data: bytes) -> str:
    """图片字节写入 backend/poster_images/{owner_id}/，返回相对 backend 的路径。"""
    dir_path = POSTER_IMAGE_DIR / str(owner_id)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{uuid.uuid4()}.png"
    file_path.write_bytes(data)
    return str(file_path.relative_to(POSTER_IMAGE_DIR.parent))


def remove_poster_image(file_path: str) -> None:
    """删除落盘文件（用户删图与入库失败回滚共用）；路径不存在时静默。"""
    absolute = POSTER_IMAGE_DIR.parent / file_path
    absolute.unlink(missing_ok=True)
```

- [ ] **Step 4: 运行确认通过 + 回归**

```
.\venv\Scripts\python.exe -m pytest tests/test_poster_writer.py -v
```
预期：全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add ai-material-generator/backend/app/services/poster_writer.py ai-material-generator/backend/tests/test_poster_writer.py
git commit -m "feat(posters): 生图下载校验与本地落盘（PNG 魔数校验，owner 子目录隔离）"
```

---

### Task 6: POST /api/posters/prompt（提炼端点）

**Files:**
- Create: `ai-material-generator/backend/app/api/posters.py`
- Test: `ai-material-generator/backend/tests/test_posters_api.py`（新建）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_posters_api.py`：

```python
"""海报配图 API 测试：5 端点。全部 mock 星语网络调用与生图链路。"""
import pytest

from app.services import poster_writer

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731


@pytest.mark.asyncio
async def test_refine_prompt_requires_login(client):
    r = await client.post("/api/posters/prompt", json={"script_content": "x"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refine_prompt_requires_editor(client, reviewer_token):
    r = await client.post(
        "/api/posters/prompt", json={"script_content": "x"}, headers=AUTH(reviewer_token)
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_refine_prompt_refines_then_caches(client, editor_token, monkeypatch):
    calls = []

    async def fake_refine(content):
        calls.append(content)
        return "一只橙猫在草地上，扁平插画风格"

    monkeypatch.setattr("app.services.poster_writer.refine_poster_prompt", fake_refine)
    payload = {"script_content": "# 海报\n卖点：一键上报"}
    r1 = await client.post("/api/posters/prompt", json=payload, headers=AUTH(editor_token))
    assert r1.status_code == 200
    assert r1.json() == {"prompt": "一只橙猫在草地上，扁平插画风格", "cached": False}
    r2 = await client.post("/api/posters/prompt", json=payload, headers=AUTH(editor_token))
    assert r2.status_code == 200
    assert r2.json() == {"prompt": "一只橙猫在草地上，扁平插画风格", "cached": True}
    assert len(calls) == 1  # 第二次命中缓存，不再调 chat


@pytest.mark.asyncio
async def test_refine_prompt_empty_content(client, editor_token):
    r = await client.post("/api/posters/prompt", json={"script_content": "  "}, headers=AUTH(editor_token))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_refine_prompt_502_on_refine_error(client, editor_token, monkeypatch):
    async def broken(content):
        raise RuntimeError("星语超时")

    monkeypatch.setattr("app.services.poster_writer.refine_poster_prompt", broken)
    r = await client.post(
        "/api/posters/prompt", json={"script_content": "x"}, headers=AUTH(editor_token)
    )
    assert r.status_code == 502
    assert "画面描述提炼失败" in r.json()["detail"]
```

- [ ] **Step 2: 运行确认失败**

```
.\venv\Scripts\python.exe -m pytest tests/test_posters_api.py -v
```
预期：全部 FAIL（404 Not Found——路由未注册）。

- [ ] **Step 3: 实现**

创建 `backend/app/api/posters.py`：

```python
"""海报配图接口：提炼画面描述 / 生图 / 列表 / 文件 / 删除。

权限：提炼与生图仅 editor（沿用 get_current_user + 函数体判 role 的既有模式，
勿用返回 Pydantic 模型的自定义依赖，会被并入请求体 schema 导致 422）。
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import UserOut
from app.api.auth import get_current_user
from app.services import poster_image_service as poster_svc
from app.services import poster_writer
from app.models.poster_image import compute_script_hash

router = APIRouter()


class PosterPromptRequest(BaseModel):
    script_content: str


class PosterImageCreate(BaseModel):
    source_title: str
    audience: str
    prompt: str


def _require_editor(user: UserOut) -> None:
    if user.role != "editor":
        raise HTTPException(status_code=403, detail="需要 editor 角色")


@router.post("/prompt")
async def refine_prompt_endpoint(
    data: PosterPromptRequest,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_editor(user)
    if not data.script_content.strip():
        raise HTTPException(status_code=400, detail="海报脚本内容为空")
    script_hash = compute_script_hash(data.script_content)
    cached = await poster_svc.get_poster_prompt(db, user.id, script_hash)
    if cached is not None:
        return {"prompt": cached.prompt, "cached": True}
    try:
        description = await poster_writer.refine_poster_prompt(data.script_content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"画面描述提炼失败: {exc}") from exc
    saved = await poster_svc.upsert_poster_prompt(db, user.id, script_hash, description)
    return {"prompt": saved.prompt, "cached": False}
```

（本 Task 仅创建文件与 /prompt 端点；/images 相关端点在 Task 7/8 追加。）

- [ ] **Step 4: 运行确认通过**

注意：本 Task 尚未注册路由到 app，HTTP 测试仍 404。先做临时验证：跳过 HTTP 断言，确认模块可导入：

```
.\venv\Scripts\python.exe -c "from app.api.posters import router; print([r.path for r in router.routes])"
```
预期：输出 `['/prompt']`。（HTTP 用例的通过验证推迟到 Task 8 路由注册后统一跑。）

- [ ] **Step 5: 提交**

```bash
git add ai-material-generator/backend/app/api/posters.py ai-material-generator/backend/tests/test_posters_api.py
git commit -m "feat(posters): 提炼画面描述端点 POST /api/posters/prompt（owner+脚本哈希缓存）"
```

---

### Task 7: POST/GET /api/posters/images（生图与列表）

**Files:**
- Modify: `ai-material-generator/backend/app/api/posters.py`（追加端点）
- Test: `ai-material-generator/backend/tests/test_posters_api.py`（追加）

- [ ] **Step 1: 追加失败测试**

`tests/test_posters_api.py` 顶部 import 区追加：

```python
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def _mock_poster_generation(monkeypatch, tmp_path):
    """把生图链路整体 mock 掉：generate 返回固定字节，落盘目录指向 tmp。"""
    monkeypatch.setattr(poster_writer, "POSTER_IMAGE_DIR", tmp_path / "poster_images")

    async def fake_generate(prompt):
        return "http://oss/x.png", PNG_BYTES

    monkeypatch.setattr("app.services.poster_writer.generate_poster_image", fake_generate)
```

末尾追加：

```python
@pytest.mark.asyncio
async def test_create_poster_image_generates_and_stores(client, editor_token, monkeypatch, tmp_path):
    _mock_poster_generation(monkeypatch, tmp_path)
    r = await client.post(
        "/api/posters/images",
        json={"source_title": "标题T", "audience": "网点管理员", "prompt": "一只橙猫"},
        headers=AUTH(editor_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["prompt"] == "一只橙猫"
    assert body["file_size"] == len(PNG_BYTES)
    assert body["image_url"] == f"/api/posters/images/{body['id']}/file"
    # 文件已真实落盘（在 tmp 内，不污染仓库）；to_dict 刻意不外露 file_path，用 rglob 校验
    stored_files = list((tmp_path / "poster_images").rglob("*.png"))
    assert len(stored_files) == 1 and stored_files[0].is_file()


@pytest.mark.asyncio
async def test_create_poster_image_requires_editor(client, reviewer_token, monkeypatch, tmp_path):
    _mock_poster_generation(monkeypatch, tmp_path)
    r = await client.post(
        "/api/posters/images",
        json={"source_title": "T", "audience": "A", "prompt": "p"},
        headers=AUTH(reviewer_token),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_poster_image_502_on_generation_error(client, editor_token, monkeypatch, tmp_path):
    _mock_poster_generation(monkeypatch, tmp_path)

    async def broken(prompt):
        raise RuntimeError("星语文生图未返回图片 URL")

    monkeypatch.setattr("app.services.poster_writer.generate_poster_image", broken)
    r = await client.post(
        "/api/posters/images",
        json={"source_title": "T", "audience": "A", "prompt": "p"},
        headers=AUTH(editor_token),
    )
    assert r.status_code == 502
    assert "海报图生成失败" in r.json()["detail"]


@pytest.mark.asyncio
async def test_list_poster_images_owner_and_combo_isolated(client, editor_token, monkeypatch, tmp_path):
    _mock_poster_generation(monkeypatch, tmp_path)
    for title, audience in [("T1", "网点管理员"), ("T1", "业务员"), ("T2", "网点管理员")]:
        await client.post(
            "/api/posters/images",
            json={"source_title": title, "audience": audience, "prompt": "p"},
            headers=AUTH(editor_token),
        )
    r = await client.get(
        "/api/posters/images",
        params={"source_title": "T1", "audience": "网点管理员"},
        headers=AUTH(editor_token),
    )
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["source_title"] == "T1"
    # reviewer 看不到 editor 的图
    r2 = await client.get(
        "/api/posters/images",
        params={"source_title": "T1", "audience": "网点管理员"},
        headers=AUTH(reviewer_token),
    )
    assert r2.json() == []
```

- [ ] **Step 2: 运行确认失败**

```
.\venv\Scripts\python.exe -m pytest tests/test_posters_api.py -v
```
预期：新增用例 FAIL（404——/images 路由未注册）。

- [ ] **Step 3: 实现**

在 `backend/app/api/posters.py` 的 import 区追加 `from app.services.poster_image_service import PosterImage` 不需要——直接追加两个端点（放在 refine_prompt_endpoint 之后）：

```python
@router.post("/images")
async def create_image_endpoint(
    data: PosterImageCreate,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_editor(user)
    if not data.prompt.strip():
        raise HTTPException(status_code=400, detail="画面描述为空")
    try:
        _, image_bytes = await poster_writer.generate_poster_image(data.prompt)
        file_path = poster_writer.save_poster_image(user.id, image_bytes)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"海报图生成失败: {exc}") from exc
    try:
        saved = await poster_svc.create_poster_image(
            db, user.id, data.source_title, data.audience, data.prompt,
            file_path, len(image_bytes),
        )
    except Exception:
        poster_writer.remove_poster_image(file_path)  # 入库失败回滚，不留孤儿文件
        raise
    return saved.to_dict()


@router.get("/images")
async def list_images_endpoint(
    source_title: str,
    audience: str,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    images = await poster_svc.list_poster_images(db, user.id, source_title, audience)
    return [image.to_dict() for image in images]
```

- [ ] **Step 4: 运行确认新增用例仍失败（路由未注册）、模块可导入**

```
.\venv\Scripts\python.exe -c "from app.api.posters import router; print([r.path for r in router.routes])"
```
预期：输出 `['/prompt', '/images', '/images']`。（HTTP 用例统一在 Task 8 路由注册后验证。）

- [ ] **Step 5: 提交**

```bash
git add ai-material-generator/backend/app/api/posters.py ai-material-generator/backend/tests/test_posters_api.py
git commit -m "feat(posters): 生图端点与图片列表（入库失败回滚落盘文件，owner+组合隔离）"
```

---

### Task 8: 文件访问/删除端点 + 路由注册 + gitignore

**Files:**
- Modify: `ai-material-generator/backend/app/api/posters.py`（追加 2 端点）
- Modify: `ai-material-generator/backend/app/api/router.py`
- Modify: `ai-material-generator/.gitignore`
- Test: `ai-material-generator/backend/tests/test_posters_api.py`（追加）

- [ ] **Step 1: 追加失败测试**

`tests/test_posters_api.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_image_file_access_owner_only(client, editor_token, reviewer_token, monkeypatch, tmp_path):
    _mock_poster_generation(monkeypatch, tmp_path)
    r = await client.post(
        "/api/posters/images",
        json={"source_title": "T", "audience": "A", "prompt": "p"},
        headers=AUTH(editor_token),
    )
    image_id = r.json()["id"]
    # 本人可取文件，内容与魔数一致
    r_ok = await client.get(f"/api/posters/images/{image_id}/file", headers=AUTH(editor_token))
    assert r_ok.status_code == 200
    assert r_ok.headers["content-type"] == "image/png"
    assert r_ok.content == PNG_BYTES
    # 他人 404；不存在 404；未登录 401
    assert (await client.get(f"/api/posters/images/{image_id}/file", headers=AUTH(reviewer_token))).status_code == 404
    assert (await client.get("/api/posters/images/99999/file", headers=AUTH(editor_token))).status_code == 404
    assert (await client.get(f"/api/posters/images/{image_id}/file")).status_code == 401


@pytest.mark.asyncio
async def test_delete_poster_image_removes_record_and_file(client, editor_token, reviewer_token, monkeypatch, tmp_path):
    _mock_poster_generation(monkeypatch, tmp_path)
    r = await client.post(
        "/api/posters/images",
        json={"source_title": "T", "audience": "A", "prompt": "p"},
        headers=AUTH(editor_token),
    )
    image_id = r.json()["id"]
    # 他人不能删
    r_forbidden = await client.delete(f"/api/posters/images/{image_id}", headers=AUTH(reviewer_token))
    assert r_forbidden.status_code == 404
    # 本人删除后记录与文件都消失
    r_del = await client.delete(f"/api/posters/images/{image_id}", headers=AUTH(editor_token))
    assert r_del.status_code == 200
    assert (await client.get(f"/api/posters/images/{image_id}/file", headers=AUTH(editor_token))).status_code == 404
    matches = list((tmp_path / "poster_images").rglob("*.png"))
    assert matches == []
```

- [ ] **Step 2: 实现**

`backend/app/api/posters.py` 末尾追加：

```python
@router.get("/images/{image_id}/file")
async def get_image_file_endpoint(
    image_id: int,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    image = await poster_svc.get_poster_image_by_id(db, image_id)
    if image is None or image.owner_id != user.id:
        raise HTTPException(status_code=404, detail="图片不存在")
    absolute = Path(poster_writer.POSTER_IMAGE_DIR.parent / image.file_path)
    if not absolute.is_file():
        raise HTTPException(status_code=404, detail="图片文件缺失")
    return FileResponse(absolute, media_type="image/png", filename=f"poster-{image_id}.png")


@router.delete("/images/{image_id}")
async def delete_image_endpoint(
    image_id: int,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    image = await poster_svc.get_poster_image_by_id(db, image_id)
    if image is None or image.owner_id != user.id:
        raise HTTPException(status_code=404, detail="图片不存在")
    await poster_svc.delete_poster_image(db, image)
    poster_writer.remove_poster_image(image.file_path)
    return {"ok": True}
```

`backend/app/api/router.py`：import 区追加一行，`register_routers` 中 `generator_router` 之后追加一行，接口总览注释在「生成物料 generated_materials」与「健康检查」之间插入海报段落：

```python
from app.api.posters import router as posters_router
```

```python
    app.include_router(posters_router, prefix="/api/posters")
```

总览注释追加（保持与既有格式一致）：

```
海报配图 posters
  POST   /api/posters/prompt                   海报脚本提炼画面描述（owner+脚本哈希缓存）
  POST   /api/posters/images                   生成海报图并本地转存（editor）
  GET    /api/posters/images                   当前用户指定来源+受众的图片列表
  GET    /api/posters/images/{id}/file         取回图片文件（本人）
  DELETE /api/posters/images/{id}              删除图片记录与文件（本人）
```

`ai-material-generator/.gitignore` 末尾追加：

```
backend/poster_images/
```

- [ ] **Step 3: 全量运行两个新测试文件确认通过**

```
.\venv\Scripts\python.exe -m pytest tests/test_posters_api.py tests/test_poster_writer.py -v
```
预期：全部 PASS（含 Task 6/7 推迟的 HTTP 用例）。

- [ ] **Step 4: 全量回归（确认未破坏既有 70 个用例）**

```
.\venv\Scripts\python.exe -m pytest tests -q
```
预期：96 passed（70 既有 + 26 新增：writer 15 + api 11）。**若耗时显著超过基线（历史：打真实星语会到分钟级），必须排查新测试的 mock 是否失效。**

- [ ] **Step 5: 提交**

```bash
git add ai-material-generator/backend/app/api/posters.py ai-material-generator/backend/app/api/router.py ai-material-generator/.gitignore ai-material-generator/backend/tests/test_posters_api.py
git commit -m "feat(posters): 图片文件访问与删除端点，路由集中注册，忽略图片目录"
```

---

### Task 9: E2E 冒烟脚本（API 层真实链路）

**Files:**
- Create: `ai-material-generator/backend/e2e_poster_smoke.py`

- [ ] **Step 1: 写脚本**

创建 `backend/e2e_poster_smoke.py`（与既有 e2e_*.py 同风格，跑完保留供回归）：

```python
"""海报配图端到端冒烟（真实链路：真星语提炼 + 真文生图），跑完保留供回归。

前置：
- 后端已启动：.\\venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
- editor 账号可用；uat 星语网关（10.130.13.74:8060）可达
- 真实调用耗时：提炼约 5-10 秒，生图约 15-40 秒
"""
import time
from uuid import uuid4

import httpx

BASE = "http://127.0.0.1:8001"
CLIENT_TIMEOUT = 300.0
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def login(username: str, password: str) -> str:
    with httpx.Client(timeout=CLIENT_TIMEOUT) as client:
        r = client.post(f"{BASE}/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["access_token"]


def main():
    token = login("editor", "editor123")
    title = f"E2E-POSTER-{uuid4().hex[:8]}"
    script = (
        "# 网点管家 V3.2.0 升级海报\n\n"
        "主标题：一键上报，省时省心\n"
        "副标题：异常件拍照即报，运单号自动带出\n"
        "卖点：扫码上报、进度可查、24 小时反馈"
    )
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(timeout=CLIENT_TIMEOUT) as client:
        # 1. 提炼画面描述（首次：真实 chat 调用）
        r = client.post(f"{BASE}/api/posters/prompt", json={"script_content": script}, headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["prompt"], "refined prompt is empty"
        assert body["cached"] is False
        print(f"refine prompt ok ({len(body['prompt'])} chars)")

        # 2. 同一脚本再提炼：命中缓存且内容一致
        r2 = client.post(f"{BASE}/api/posters/prompt", json={"script_content": script}, headers=headers)
        assert r2.status_code == 200
        assert r2.json()["cached"] is True
        assert r2.json()["prompt"] == body["prompt"]
        print("refine prompt cache hit ok")

        # 3. 生成海报图（真实文生图）
        t0 = time.perf_counter()
        r3 = client.post(
            f"{BASE}/api/posters/images",
            json={"source_title": title, "audience": "网点管理员", "prompt": body["prompt"]},
            headers=headers,
        )
        assert r3.status_code == 200, r3.text
        image = r3.json()
        assert image["file_size"] > 0
        assert image["image_url"] == f"/api/posters/images/{image['id']}/file"
        print(f"generate poster ok ({time.perf_counter() - t0:.1f}s, {image['file_size']} bytes)")

        # 4. 列表：当前用户+来源+受众组合可见 1 张
        r4 = client.get(
            f"{BASE}/api/posters/images",
            params={"source_title": title, "audience": "网点管理员"},
            headers=headers,
        )
        assert r4.status_code == 200 and len(r4.json()) == 1
        print("list poster images ok")

        # 5. 文件可取回且为合法 PNG
        r5 = client.get(f"{BASE}{image['image_url']}", headers=headers)
        assert r5.status_code == 200, r5.text
        assert r5.content.startswith(PNG_MAGIC), "returned file is not a PNG"
        print(f"fetch poster file ok ({len(r5.content)} bytes)")

        # 6. 删除后记录与文件均消失
        r6 = client.delete(f"{BASE}/api/posters/images/{image['id']}", headers=headers)
        assert r6.status_code == 200
        r7 = client.get(f"{BASE}{image['image_url']}", headers=headers)
        assert r7.status_code == 404
        print("delete poster ok")

    print("E2E poster smoke test passed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 启动服务并运行**

终端 1（backend 目录，保持运行）：

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

终端 2：

```powershell
.\venv\Scripts\python.exe e2e_poster_smoke.py
```

预期输出（提炼 5-10 秒、生图 15-40 秒）：

```
refine prompt ok (NN chars)
refine prompt cache hit ok
generate poster ok (N.Ns, NNNNN bytes)
list poster images ok
fetch poster file ok (NNNNNN bytes)
delete poster ok
E2E poster smoke test passed
```

注意：需要 uat 星语网关（10.130.13.74:8060）可达；若网络不可达，本 Task 标记跳过，改在 Task 12 补跑。

- [ ] **Step 3: 提交**

```bash
git add ai-material-generator/backend/e2e_poster_smoke.py
git commit -m "test(posters): 海报配图 API 真实链路冒烟脚本"
```

---

### Task 10: 前端 API 封装 posters.ts

**Files:**
- Create: `ai-material-generator/frontend/src/api/posters.ts`

- [ ] **Step 1: 写文件**

创建 `frontend/src/api/posters.ts`（风格对齐 materials.ts）：

```ts
import client from './client'

export interface PosterImage {
  id: number
  owner_id: number
  source_title: string
  audience: string
  prompt: string
  file_size: number
  image_url: string
  created_at: string
}

export function refinePosterPrompt(scriptContent: string) {
  return client.post('/posters/prompt', { script_content: scriptContent })
}

export function createPosterImage(data: {
  source_title: string
  audience: string
  prompt: string
}) {
  return client.post('/posters/images', data)
}

export function listPosterImages(sourceTitle: string, audience: string) {
  return client.get('/posters/images', { params: { source_title: sourceTitle, audience } })
}

export function fetchPosterImageFile(id: number) {
  // 文件接口需带 Authorization，<img> 直连不可行，调用方用 blob 转 object URL
  return client.get(`/posters/images/${id}/file`, { responseType: 'blob' })
}

export function deletePosterImage(id: number) {
  return client.delete(`/posters/images/${id}`)
}
```

- [ ] **Step 2: 类型检查 + 构建验证**

```powershell
Set-Location "D:\StudyProjects\ai-practice\ai-material-generator\frontend"
cmd /c "npm run build 2>&1"
echo $LASTEXITCODE
```

预期：`vue-tsc --noEmit` 无错误、vite build 完成、`$LASTEXITCODE` 为 0。（必须 `cmd /c` 合并流——PowerShell 下 npm 的 stderr 输出会被误判为失败，历史教训。）

- [ ] **Step 3: 提交**

```bash
git add ai-material-generator/frontend/src/api/posters.ts
git commit -m "feat(ui): 海报配图前端 API 封装"
```

---

### Task 11: GeneratorView.vue 海报配图区块

**Files:**
- Modify: `ai-material-generator/frontend/src/views/GeneratorView.vue`

插入位置（按修改前行号标注，实际按锚点内容定位）：
- L6（materials import 行）后：posters API import
- L396-397（`regenerate()` 结束与 `</script>` 之间）：状态与函数
- L660-661（`<el-empty v-else ... />` 之后、`</section>` 之前）：海报区块。**不能**插在 L636 `v-if` 与 L660 `v-else` 之间——v-else 必须紧邻配对的 v-if，中间插入元素会编译报错
- L661-662（`</section>` 之后、`</main>` 之前）：两个 dialog
- L753-754（`.save-analysis-btn` 规则后、`</style>` 前）：CSS

- [ ] **Step 1: import 追加**

L6 行后追加：

```ts
import {
  refinePosterPrompt,
  createPosterImage,
  listPosterImages,
  deletePosterImage,
  fetchPosterImageFile,
  type PosterImage,
} from '@/api/posters'
```

- [ ] **Step 2: 状态与函数**

`</script>` 前追加：

```ts
// —— 海报配图（仅 poster_script 物料显示）——
const posterDialogVisible = ref(false)
const posterPreviewVisible = ref(false)
const posterPrompt = ref('')
const posterPromptCached = ref(false)
const posterRefining = ref(false)
const posterGenerating = ref(false)
const posterImages = ref<PosterImage[]>([])
const posterImagesLoading = ref(false)
const posterThumbUrls = ref<Record<number, string>>({})
const posterPreviewUrl = ref('')

const isPosterScript = computed(
  () => activeMaterialType.value === 'poster_script' && !!currentMaterial.value,
)

watch(isPosterScript, (visible) => {
  if (visible) loadPosterImages()
})

async function openPosterDialog() {
  posterDialogVisible.value = true
  posterRefining.value = true
  try {
    const res = await refinePosterPrompt(currentMaterial.value!.content)
    posterPrompt.value = res.data.prompt
    posterPromptCached.value = res.data.cached
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '画面描述提炼失败')
  } finally {
    posterRefining.value = false
  }
}

async function doGeneratePoster() {
  if (!posterPrompt.value.trim()) {
    ElMessage.warning('请先填写画面描述')
    return
  }
  posterGenerating.value = true
  try {
    await createPosterImage({
      source_title: title.value,
      audience: audience.value,
      prompt: posterPrompt.value,
    })
    ElMessage.success('海报图已生成')
    await loadPosterImages()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '海报图生成失败')
  } finally {
    posterGenerating.value = false
  }
}

async function loadPosterImages() {
  posterImagesLoading.value = true
  try {
    const res = await listPosterImages(title.value, audience.value)
    posterImages.value = res.data
    // 文件接口需 Authorization，<img> 直连不可行，逐张取 blob 生成预览地址
    for (const img of posterImages.value) {
      if (!posterThumbUrls.value[img.id]) {
        try {
          const blobRes = await fetchPosterImageFile(img.id)
          posterThumbUrls.value[img.id] = URL.createObjectURL(blobRes.data)
        } catch {
          // 单张取图失败不阻塞列表
        }
      }
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '海报图列表加载失败')
  } finally {
    posterImagesLoading.value = false
  }
}

function openPreview(img: PosterImage) {
  if (posterPreviewUrl.value) URL.revokeObjectURL(posterPreviewUrl.value)
  posterPreviewUrl.value = posterThumbUrls.value[img.id] || ''
  posterPreviewVisible.value = true
}

async function doDownloadPoster(img: PosterImage) {
  try {
    const res = await fetchPosterImageFile(img.id)
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `poster-${img.id}.png`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('海报图下载失败')
  }
}

async function doDeletePoster(img: PosterImage) {
  try {
    await ElMessageBox.confirm('删除后不可恢复，确认删除该海报图？', '删除海报图', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deletePosterImage(img.id)
    URL.revokeObjectURL(posterThumbUrls.value[img.id] || '')
    delete posterThumbUrls.value[img.id]
    posterImages.value = posterImages.value.filter((i) => i.id !== img.id)
    ElMessage.success('已删除')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}
```

- [ ] **Step 3: 海报区块（template）**

`<el-empty v-else description="点击「重新解析文档」生成物料" />` 行之后、`</section>` 之前追加：

```html
        <div v-if="isPosterScript" class="poster-section">
          <div class="poster-header">
            <span class="poster-title">海报配图</span>
            <el-button type="primary" size="small" :loading="posterRefining" @click="openPosterDialog">
              生成海报图
            </el-button>
          </div>
          <p class="poster-hint">根据海报脚本提炼画面描述并生成配图（约 15 秒/张），图片仅本人可见</p>
          <div v-loading="posterImagesLoading" class="poster-grid">
            <el-empty
              v-if="!posterImages.length && !posterImagesLoading"
              description="暂无海报图"
              :image-size="60"
            />
            <div v-for="img in posterImages" :key="img.id" class="poster-card">
              <img
                v-if="posterThumbUrls[img.id]"
                :src="posterThumbUrls[img.id]"
                class="poster-thumb"
                @click="openPreview(img)"
              />
              <div class="poster-card-actions">
                <el-button text size="small" @click="doDownloadPoster(img)">下载</el-button>
                <el-button text size="small" type="danger" @click="doDeletePoster(img)">删除</el-button>
              </div>
            </div>
          </div>
        </div>
```

- [ ] **Step 4: 两个弹窗（template）**

`</section>`（generate-section 结束）之后、`</main>` 之前追加：

```html
      <el-dialog v-model="posterDialogVisible" title="海报配图" width="560px">
        <div v-loading="posterRefining">
          <p class="poster-dialog-tip">
            画面描述由 AI 从海报脚本提炼<template v-if="posterPromptCached">（命中缓存）</template>，可编辑后生成：
          </p>
          <el-input
            v-model="posterPrompt"
            type="textarea"
            :rows="5"
            placeholder="正在提炼画面描述…"
          />
          <p class="poster-dialog-warn">生成约需 15 秒；图片为 PNG，仅生成者本人可见，可多次生成挑选</p>
        </div>
        <template #footer>
          <el-button @click="posterDialogVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="posterGenerating"
            :disabled="posterRefining || !posterPrompt.trim()"
            @click="doGeneratePoster"
          >
            {{ posterGenerating ? '生成中…' : '生成海报图' }}
          </el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="posterPreviewVisible" title="海报预览" width="720px">
        <img v-if="posterPreviewUrl" :src="posterPreviewUrl" class="poster-preview-img" />
      </el-dialog>
```

- [ ] **Step 5: CSS**

`</style>` 前追加：

```css
.poster-section { margin-top: 16px; border-top: 1px dashed #ebeef5; padding-top: 16px; }
.poster-header { display: flex; justify-content: space-between; align-items: center; }
.poster-title { font-weight: 600; font-size: 14px; color: #303133; }
.poster-hint { color: #909399; font-size: 12px; margin: 8px 0 12px; }
.poster-grid { display: flex; flex-wrap: wrap; gap: 12px; min-height: 60px; }
.poster-card { width: 140px; border: 1px solid #ebeef5; border-radius: 8px; padding: 8px; }
.poster-thumb { width: 100%; height: 100px; object-fit: cover; border-radius: 6px; cursor: zoom-in; display: block; }
.poster-card-actions { display: flex; justify-content: space-between; margin-top: 4px; }
.poster-preview-img { width: 100%; display: block; }
.poster-dialog-tip { font-size: 13px; color: #606266; margin: 0 0 8px; }
.poster-dialog-warn { font-size: 12px; color: #e6a23c; margin: 8px 0 0; }
```

- [ ] **Step 6: 构建验证**

```powershell
Set-Location "D:\StudyProjects\ai-practice\ai-material-generator\frontend"
cmd /c "npm run build 2>&1"
echo $LASTEXITCODE
```

预期：`$LASTEXITCODE` 为 0。

- [ ] **Step 7: 提交**

```bash
git add ai-material-generator/frontend/src/views/GeneratorView.vue
git commit -m "feat(ui): 海报脚本页新增海报配图区块（提炼弹窗/生成/预览/下载/删除）"
```

---

### Task 12: README + 全量回归 + 浏览器 UI 真实验证

**Files:**
- Modify: `ai-material-generator/README.md`

- [ ] **Step 1: README 更新（两处）**

「## 功能」列表末尾（`- 编辑与审核工作流：…` 行后）追加一行：

```markdown
- 海报配图：海报脚本可一键提炼画面描述并生成配图（星语文生图），图片仅本人可见，支持预览/下载/删除
```

「## 测试」章节之前插入新章节：

```markdown
## 海报配图

1. 切换到「海报脚本」物料后，内容区底部出现「海报配图」区块。
2. 点击「生成海报图」：系统先用大模型把脚本提炼成画面描述（按 owner+脚本内容哈希缓存，改脚本自动失效），可在弹窗中编辑后再生成。
3. 通过星语文生图生成 PNG（约 15 秒/张），服务端下载转存到 `backend/poster_images/{owner_id}/`，不使用 24 小时过期的 OSS 临时链接。
4. 图片不进审核流程，仅生成者本人可见，支持预览、下载、删除；每次生成产出新图，可多次生成挑选。
5. 相关接口集中在 `/api/posters`（见 `backend/app/api/router.py` 总览）。
```

- [ ] **Step 2: 全量回归**

```powershell
Set-Location "D:\StudyProjects\ai-practice\ai-material-generator\backend"
.\venv\Scripts\python.exe -m pytest tests -q
```

预期：96 passed（70 既有 + 26 新增）。

- [ ] **Step 3: 浏览器 UI 端到端验证（真实链路）**

启动三个进程：

```powershell
# 终端 1：后端 8000（vite 代理指向它）
Set-Location "D:\StudyProjects\ai-practice\ai-material-generator\backend"
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 终端 2：前端 dev
Set-Location "D:\StudyProjects\ai-practice\ai-material-generator\frontend"
cmd /c "npm run dev 2>&1"

# 终端 3：独立 profile 的调试 Edge（不污染日常浏览器）
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir="$env:TEMP\edge-cdp-poster" --no-first-run
```

（msedge 路径不存在时改用 `C:\Program Files\Microsoft\Edge\Application\msedge.exe`。）

创建 `backend/tmp_ui_poster_check.mjs`（跑完即删；Node 24 原生 fetch/WebSocket，无需装依赖）：

```js
// 海报配图 UI 端到端验证（真实星语链路，总耗时 2-4 分钟）
const CDP_HTTP = 'http://127.0.0.1:9222'
const APP_URL = 'http://localhost:5173/' // vite 监听 IPv6 ::1，必须用 localhost

const targets = await (await fetch(`${CDP_HTTP}/json/list`)).json()
const page = targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target')
const ws = new WebSocket(page.webSocketDebuggerUrl)
let seq = 0
const pending = new Map()
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++seq
    pending.set(id, { resolve, reject })
    ws.send(JSON.stringify({ id, method, params }))
  })
}
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data)
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id)
    pending.delete(msg.id)
    msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result)
  }
}
await new Promise((r) => (ws.onopen = r))

async function evaljs(expr) {
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })
  if (r.exceptionDetails) {
    throw new Error('page exception: ' + JSON.stringify(r.exceptionDetails.exception?.description || r.exceptionDetails.text))
  }
  return r.result.value
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
async function waitFor(expr, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await evaljs(expr)) return
    await sleep(2000)
  }
  throw new Error(`waitFor timeout: ${label}`)
}

await send('Page.enable')
await send('Page.navigate', { url: APP_URL })
await sleep(3000)

// 1. 登录 editor（v-model 必须用原生 value setter + input 事件驱动）
await evaljs(`(() => {
  const setVal = (el, v) => {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    setter.call(el, v)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }
  const inputs = document.querySelectorAll('input')
  setVal(inputs[0], 'editor')
  setVal(inputs[1], 'editor123')
  document.querySelector('button.el-button--primary').click()
  return true
})()`)
await waitFor(`!!document.querySelector('.parse-btn')`, 30000, '登录后进入主页')
console.log('login: PASS')

// 2. 触发解析 + 全量生成（真实星语调用，最长等 5 分钟）
await evaljs(`document.querySelector('.parse-btn').click()`)
await waitFor(`!!document.querySelector('.material-content')`, 300000, '解析并生成物料')
console.log('parse and generate: PASS')

// 3. 初始为版本宣发稿：海报区块不可见
const hiddenBefore = await evaljs(`!document.querySelector('.poster-section')`)
if (!hiddenBefore) throw new Error('poster section should not show on version_announcement')
console.log('poster hidden on non-poster tab: PASS')

// 4. 切到海报脚本：区块出现
await evaljs(`[...document.querySelectorAll('.material-tag')].find((t) => t.textContent.includes('海报脚本')).click()`)
await waitFor(`!!document.querySelector('.poster-section')`, 120000, '海报脚本物料出现')
console.log('poster section visible: PASS')

// 5. 打开提炼弹窗：等待真实提炼完成（textarea 有内容）
await evaljs(`[...document.querySelectorAll('.poster-section button')].find((b) => b.textContent.includes('生成海报图')).click()`)
await waitFor(`(() => { const ta = document.querySelector('.el-dialog textarea'); return !!ta && ta.value.trim().length > 0 })()`, 120000, '画面描述提炼完成')
const promptLen = await evaljs(`document.querySelector('.el-dialog textarea').value.length`)
console.log('refined prompt chars:', promptLen, 'PASS')

// 6. 弹窗内点生成：等待缩略图出现（真实文生图 15-60 秒）
await evaljs(`[...document.querySelectorAll('.el-dialog__footer button')].find((b) => b.textContent.includes('生成海报图')).click()`)
await waitFor(`!!document.querySelector('.poster-thumb')`, 180000, '海报图生成并回显')
console.log('poster thumbnail visible: PASS')

// 7. 删除：确认框（确认按钮是弹窗按钮组最后一个）→ 缩略图消失
await evaljs(`[...document.querySelectorAll('.poster-card-actions button')].find((b) => b.textContent.includes('删除')).click()`)
await sleep(1000)
await evaljs(`[...document.querySelectorAll('.el-message-box__btns button')].pop().click()`)
await waitFor(`!document.querySelector('.poster-thumb')`, 30000, '删除后缩略图消失')
console.log('poster deleted: PASS')

console.log('UI poster smoke PASSED')
ws.close()
process.exit(0)
```

运行（backend 目录）：

```powershell
node tmp_ui_poster_check.mjs
```

预期：逐行打印 `... PASS`，最后一行 `UI poster smoke PASSED`。断言覆盖：①非海报 tab 不显示区块 ②海报 tab 显示区块 ③弹窗自动填入真实提炼的描述 ④真实文生图后缩略图回显 ⑤确认删除后消失。

关键约束（历史教训）：
- vite 监听 IPv6 ::1：必须用 `http://localhost:5173/`，不能用 127.0.0.1
- v-model 表单必须用原生 value setter + `input` 事件驱动，直接改 value 无效
- 本脚本全部用 `Runtime.evaluate` 的 JS `.click()`（后台窗口也能投递事件）；若改用 CDP `Input.dispatchMouseEvent` 必须先 `Page.bringToFront`
- 真实链路总耗时 2-4 分钟，超时按脚本中给定值设置，不要随意调小

验证通过后删除临时脚本与临时 profile（用文件删除工具删 tmp_ui_poster_check.mjs，勿用 shell 删文件）：

```powershell
Remove-Item -Recurse -Force "$env:TEMP\edge-cdp-poster" -ErrorAction SilentlyContinue
```

- [ ] **Step 4: 提交**

```bash
git add ai-material-generator/README.md
git commit -m "docs: README 增补海报配图功能说明"
```
