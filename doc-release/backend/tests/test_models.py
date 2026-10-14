from sqlalchemy import func, select

from app.models import Artifact, Repo, Run


async def test_create_repo_run_artifact(db_session):
    repo = Repo(name="order-center", path=r"D:\tmp\order-center", is_sample=True)
    db_session.add(repo)
    await db_session.commit()

    run = Run(repo_id=repo.id, base_ref="v2.13.3", head_ref="v2.13.4", version_label="v2.13.4")
    run.steps = [{"index": 0, "name": "定位仓库与变更范围", "status": "pending"}]
    run.stats = {"commits": 3}
    db_session.add(run)
    await db_session.commit()

    art = Artifact(run_id=run.id, kind="checklist", filename="checklist.csv",
                   path=r"D:\tmp\archive\checklist.csv", bytes=123)
    db_session.add(art)
    await db_session.commit()

    assert len(run.id) == 36
    assert run.status == "pending"
    assert run.tone == "business"
    assert run.mask is False
    assert run.result is None

    got = (await db_session.execute(select(func.count()).select_from(Artifact))).scalar_one()
    assert got == 1
