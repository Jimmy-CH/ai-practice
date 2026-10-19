import io

import pytest
from pptx import Presentation

OUTLINE = """# 网点管家 V3.2.0 培训课件

## 一、培训目标
- 掌握异常件一键上报
- 理解派费日结的数据口径

## 二、注意事项与风险提示
- 升级至 V3.2.0 以上版本
"""


def _payload(content: str = OUTLINE) -> dict:
    return {
        "title": "网点管家 V3.2.0 培训课件",
        "content": content,
        "audience": "网点管理员",
        "source_title": "网点管家 V3.2.0 版本迭代说明",
    }


@pytest.mark.asyncio
async def test_export_training_outline_pptx(client, editor_token):
    response = await client.post(
        "/api/pptx/training-outline",
        json=_payload(),
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 200
    assert response.content[:2] == b"PK"

    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "filename*=UTF-8''" in disposition
    assert ".pptx" in disposition

    prs = Presentation(io.BytesIO(response.content))
    # 封面 + 目录 + 2 个章节页 + 结束页
    assert len(prs.slides) == 5


@pytest.mark.asyncio
async def test_export_training_outline_rejects_empty_content(client, editor_token):
    response = await client.post(
        "/api/pptx/training-outline",
        json=_payload("   "),
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 400
    assert "内容为空" in response.json()["detail"]


@pytest.mark.asyncio
async def test_export_training_outline_requires_editor_role(client, reviewer_token):
    response = await client.post(
        "/api/pptx/training-outline",
        json=_payload(),
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_export_training_outline_requires_login(client):
    response = await client.post("/api/pptx/training-outline", json=_payload())
    assert response.status_code == 401
