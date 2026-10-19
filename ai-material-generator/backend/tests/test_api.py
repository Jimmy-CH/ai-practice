import io
from unittest.mock import AsyncMock

import pytest
from docx import Document


def _make_docx(*paragraphs: str) -> bytes:
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_parse_text(client, monkeypatch):
    async def fake_analyze(*args, **kwargs):
        return {"新增功能": ["A"], "变更与优化": [], "注意事项": [], "风险提示": []}
    monkeypatch.setattr("app.api.generator.analyze_document", fake_analyze)
    monkeypatch.setattr("app.api.generator.pregenerate_materials", AsyncMock())
    login = await client.post("/api/auth/login", data={"username": "editor", "password": "editor123"})
    token = login.json()["access_token"]
    response = await client.post(
        "/api/parse",
        data={"title": "T", "content": "C"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["新增功能"] == ["A"]


@pytest.mark.asyncio
async def test_extract_text_from_docx(client, editor_token):
    response = await client.post(
        "/api/extract-text",
        files={
            "file": (
                "demo.docx",
                _make_docx("第一段正文", "第二段正文"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "demo.docx"
    assert body["content"] == "第一段正文\n第二段正文"


@pytest.mark.asyncio
async def test_extract_text_rejects_non_docx(client, editor_token):
    response = await client.post(
        "/api/extract-text",
        files={"file": ("demo.txt", b"plain text", "text/plain")},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_generate(client, monkeypatch):
    async def fake_generate(*args, **kwargs):
        return {"title": "R", "content": "C", "audience": "网点管理员", "material_type": "version_announcement", "meta": {"audience": "网点管理员", "material_type": "版本宣发稿", "generator": "DeepSeek"}}
    monkeypatch.setattr("app.api.generator.generate_material", fake_generate)
    login = await client.post("/api/auth/login", data={"username": "editor", "password": "editor123"})
    token = login.json()["access_token"]
    response = await client.post(
        "/api/generate",
        json={
            "title": "T",
            "analysis": {"新增功能": ["A"]},
            "audience": "网点管理员",
            "material_type": "version_announcement",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "R"
