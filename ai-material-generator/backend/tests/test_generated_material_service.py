import pytest
from sqlalchemy import select
from app.services import generated_material_service as svc
from app.models.generated_material import GeneratedMaterial

ANALYSIS_HASH = "abc123"


@pytest.mark.asyncio
async def test_upsert_creates(db_session):
    gm = await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", analysis_hash=ANALYSIS_HASH, content="# 标题\n正文",
    )
    assert gm.id is not None
    assert gm.content == "# 标题\n正文"


@pytest.mark.asyncio
async def test_get_by_composite_key(db_session):
    await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", analysis_hash=ANALYSIS_HASH, content="old",
    )
    found = await svc.get_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", analysis_hash=ANALYSIS_HASH,
    )
    assert found is not None
    assert found.content == "old"


@pytest.mark.asyncio
async def test_upsert_overwrites(db_session):
    await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", analysis_hash=ANALYSIS_HASH, content="old",
    )
    gm = await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", analysis_hash=ANALYSIS_HASH, content="new",
    )
    assert gm.content == "new"
    found = await svc.get_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", analysis_hash=ANALYSIS_HASH,
    )
    assert found.content == "new"


@pytest.mark.asyncio
async def test_different_analysis_hash_creates_new_record(db_session):
    await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", analysis_hash=ANALYSIS_HASH, content="old",
    )
    gm = await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", analysis_hash="different", content="new",
    )
    assert gm.content == "new"
    records = await db_session.execute(select(GeneratedMaterial))
    assert len(records.scalars().all()) == 2
