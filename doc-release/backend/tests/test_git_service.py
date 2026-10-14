import pytest

from app.services import git_service
from app.services.errors import GitError
from tests.gitfix import commit, init_repo, tag, write_files


@pytest.fixture
def repo(tmp_path):
    r = init_repo(tmp_path)
    write_files(r, {"src/a.ts": "export const A = 1;\n", "README.md": "# demo\n"})
    commit(r, "init")
    tag(r, "v1.0.0")
    write_files(r, {"src/a.ts": "export const A = 2;\nexport function run() {\n  return A;\n}\n"})
    commit(r, "feat: update a", date="2026-08-22 09:00:00 +0800")
    tag(r, "v1.1.0")
    return r


def test_list_refs_and_default_branch(repo):
    refs = git_service.list_refs(str(repo))
    assert [t["name"] for t in refs["tags"]] == ["v1.0.0", "v1.1.0"]
    assert refs["default_branch"] == "main"
    assert refs["branches"][0]["name"] == "main"


def test_resolve_ref(repo):
    sha = git_service.resolve_ref(str(repo), "v1.1.0")
    assert len(sha) == 40


def test_resolve_ref_rejects_option_like(repo):
    with pytest.raises(GitError):
        git_service.resolve_ref(str(repo), "--all")


def test_validate_repo_rejects_non_git_dir(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(GitError):
        git_service.validate_repo(str(plain))


def test_collect_diff_basic(repo):
    data = git_service.collect_diff(str(repo), "v1.0.0", "v1.1.0")
    assert data["stats"] == {"commits": 1, "files": 1, "modules": 1, "added": 4, "removed": 1, "days": 1}
    f = data["files"][0]
    assert f["path"] == "src/a.ts" and f["status"] == "m"
    assert any(l["t"] == "add" and "export function run" in l["s"] for l in f["lines"])
    assert data["modules"][0]["name"] == "src"


def test_collect_diff_empty_range_raises(repo):
    with pytest.raises(GitError, match="没有变更提交"):
        git_service.collect_diff(str(repo), "v1.1.0", "v1.1.0")


def test_collect_diff_truncates(repo):
    data = git_service.collect_diff(str(repo), "v1.0.0", "v1.1.0", max_lines=2)
    assert data["files"][0]["truncated"] is True
    assert len(data["files"][0]["lines"]) == 2


def test_show_file(repo):
    assert "const A = 1" in git_service.show_file(str(repo), "v1.0.0", "src/a.ts")
    assert git_service.show_file(str(repo), "v1.0.0", "src/missing.ts") == ""
