import hashlib
import json

import pytest
from sqlalchemy import select
from app.services import generated_material_service as svc
from app.models.generated_material import GeneratedMaterial, compute_analysis_hash

ANALYSIS_HASH = "abc123"


def test_analysis_hash_is_deterministic_across_shapes():
    """纯四类要点与前端包装对象应得出相同哈希，且算法本身跨进程确定。"""
    result = {
        "新增功能": ["异常件一键上报"],
        "变更与优化": ["统一使用新版对账单"],
        "注意事项": ["需升级至 V3.2.0 以上版本"],
        "风险提示": ["派费数据缺失勿重复申诉"],
    }
    wrapped = {"analysis_id": 1, "title": "T", **result, "created_at": "2026-10-14"}

    normalized = json.dumps(
        {
            "新增功能": result["新增功能"],
            "变更与优化": result["变更与优化"],
            "注意事项": result["注意事项"],
            "风险提示": result["风险提示"],
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    expected = hashlib.md5(normalized.encode("utf-8")).hexdigest()

    assert compute_analysis_hash(result) == expected
    assert compute_analysis_hash(wrapped) == expected


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
