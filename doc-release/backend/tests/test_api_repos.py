import pytest

from tests.gitfix import commit, init_repo, tag, write_files


@pytest.fixture
def sample_dir(tmp_path):
    r = init_repo(tmp_path)
    write_files(r, {"src/a.ts": "export const A = 1;\n"})
    commit(r, "init")
    tag(r, "v1.0.0")
    write_files(r, {"src/a.ts": "export const A = 2;\n"})
    commit(r, "change", date="2026-08-22 09:00:00 +0800")
    tag(r, "v1.1.0")
    return r


async def test_repo_crud_and_refs(client, sample_dir):
    resp = await client.post("/api/repos", json={"path": str(sample_dir)})
    assert resp.status_code == 201
    repo = resp.json()
    assert repo["name"] == "repo" and repo["is_sample"] is False

    dup = await client.post("/api/repos", json={"path": str(sample_dir)})
    assert dup.status_code == 409

    bad = await client.post("/api/repos", json={"path": str(sample_dir.parent / "nope")})
    assert bad.status_code == 400

    lst = await client.get("/api/repos")
    assert len(lst.json()) == 1

    refs = await client.get(f"/api/repos/{repo['id']}/refs")
    assert refs.status_code == 200
    assert [t["name"] for t in refs.json()["tags"]] == ["v1.0.0", "v1.1.0"]

    scen = await client.get(f"/api/repos/{repo['id']}/scenarios")
    assert scen.json() == []          # 非示例仓库没有内置场景


async def test_preview_and_empty_range(client, sample_dir):
    repo_id = (await client.post("/api/repos", json={"path": str(sample_dir)})).json()["id"]
    ok = await client.get(f"/api/repos/{repo_id}/preview", params={"base": "v1.0.0", "head": "v1.1.0"})
    assert ok.status_code == 200
    data = ok.json()
    assert data["stats"]["commits"] == 1
    assert data["files"][0]["path"] == "src/a.ts"

    empty = await client.get(f"/api/repos/{repo_id}/preview", params={"base": "v1.1.0", "head": "v1.1.0"})
    assert empty.status_code == 422

    bad = await client.get(f"/api/repos/{repo_id}/preview", params={"base": "nope", "head": "v1.1.0"})
    assert bad.status_code == 422


async def test_delete_repo(client, sample_dir):
    repo_id = (await client.post("/api/repos", json={"path": str(sample_dir)})).json()["id"]
    assert (await client.delete(f"/api/repos/{repo_id}")).status_code == 200
    assert (await client.get("/api/repos")).json() == []
    assert (await client.delete(f"/api/repos/{repo_id}")).status_code == 404
