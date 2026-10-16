import json
import pytest
from app.services import analysis_service as svc


@pytest.mark.asyncio
async def test_upsert_analysis_creates(db_session):
    analysis = await svc.upsert_analysis(
        db_session,
        owner_id=1,
        source_title="版本说明",
        data={"新增功能": ["a"], "变更与优化": ["b"], "注意事项": ["c"], "风险提示": ["d"]},
    )
    assert analysis.id is not None
    assert analysis.source_title == "版本说明"
    assert analysis.owner_id == 1
    assert json.loads(analysis.new_features) == ["a"]


@pytest.mark.asyncio
async def test_upsert_analysis_overwrites(db_session):
    await svc.upsert_analysis(
        db_session,
        owner_id=1,
        source_title="版本说明",
        data={"新增功能": ["a"], "变更与优化": [], "注意事项": [], "风险提示": []},
    )
    analysis = await svc.upsert_analysis(
        db_session,
        owner_id=1,
        source_title="版本说明",
        data={"新增功能": ["b"], "变更与优化": [], "注意事项": [], "风险提示": []},
    )
    loaded = await svc.get_analysis_by_title(db_session, owner_id=1, source_title="版本说明")
    assert loaded is not None
    assert json.loads(loaded.new_features) == ["b"]
    assert analysis.id == loaded.id


@pytest.mark.asyncio
async def test_update_analysis(db_session):
    created = await svc.upsert_analysis(
        db_session,
        owner_id=1,
        source_title="版本说明",
        data={"新增功能": ["a"], "变更与优化": [], "注意事项": [], "风险提示": []},
    )
    updated = await svc.update_analysis(
        db_session,
        created,
        {"new_features": ["x"], "changes": ["y"], "notices": ["z"], "risks": ["w"]},
    )
    assert json.loads(updated.new_features) == ["x"]
    assert json.loads(updated.changes) == ["y"]
    assert json.loads(updated.notices) == ["z"]
    assert json.loads(updated.risks) == ["w"]
