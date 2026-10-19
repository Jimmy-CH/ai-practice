"""启动自愈：上次进程遗留的运行必须被收敛，否则会永久阻塞查重、取消与删除。"""

from app.models import Repo, Run
from app.models.run import blank_steps
from app.services import pipeline_service


async def _seed_repo(db_session) -> int:
    repo = Repo(name="demo", path="C:/tmp/docrelease-demo")
    db_session.add(repo)
    await db_session.commit()
    return repo.id


async def test_recover_stale_runs_marks_failed(db_session):
    repo_id = await _seed_repo(db_session)
    stale = Run(repo_id=repo_id, base_ref="v1.0.0", head_ref="v1.1.0",
                version_label="v1.1.0", status="running", steps=blank_steps())
    stale.steps[1]["status"] = "active"
    done = Run(repo_id=repo_id, base_ref="v1.0.0", head_ref="v1.1.0",
               version_label="v1.1.0", status="succeeded", steps=blank_steps())
    pending = Run(repo_id=repo_id, base_ref="v1.0.0", head_ref="v1.1.0",
                  version_label="v1.1.0", status="pending", steps=blank_steps())
    db_session.add_all([stale, done, pending])
    await db_session.commit()

    assert await pipeline_service.recover_stale_runs() == 2

    await db_session.refresh(stale)
    assert stale.status == "failed"
    assert stale.error == "服务重启，运行被中断"
    assert stale.finished_at is not None
    assert stale.steps[1]["status"] == "failed"
    assert stale.steps[0]["status"] == "pending"

    await db_session.refresh(pending)
    assert pending.status == "failed"

    await db_session.refresh(done)
    assert done.status == "succeeded"


async def test_recover_stale_runs_noop_when_clean(db_session):
    assert await pipeline_service.recover_stale_runs() == 0
