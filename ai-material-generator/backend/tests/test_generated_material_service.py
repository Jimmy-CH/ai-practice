import pytest
from app.services import generated_material_service as svc


@pytest.mark.asyncio
async def test_upsert_creates(db_session):
    gm = await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", content="# 标题\n正文",
    )
    assert gm.id is not None
    assert gm.content == "# 标题\n正文"


@pytest.mark.asyncio
async def test_get_by_composite_key(db_session):
    await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", content="old",
    )
    found = await svc.get_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement",
    )
    assert found is not None
    assert found.content == "old"


@pytest.mark.asyncio
async def test_upsert_overwrites(db_session):
    await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", content="old",
    )
    gm = await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", content="new",
    )
    assert gm.content == "new"
    found = await svc.get_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement",
    )
    assert found.content == "new"
