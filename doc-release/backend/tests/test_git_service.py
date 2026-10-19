import pytest

from app.services import git_service
from app.services.errors import GitError
from tests.gitfix import commit, git, init_repo, tag, write_files


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


def test_split_rename_variants():
    assert git_service._split_rename("src/{a.ts => b.ts}") == ("src/a.ts", "src/b.ts")
    assert git_service._split_rename("old/{x/y.ts => z/y.ts}") == ("old/x/y.ts", "old/z/y.ts")
    assert git_service._split_rename("a.ts => b.ts") == ("a.ts", "b.ts")
    assert git_service._split_rename("src/plain.ts") == ("src/plain.ts", "src/plain.ts")


def test_collect_diff_expands_rename(repo):
    git(repo, "mv", "src/a.ts", "src/renamed.ts")
    commit(repo, "rename a", date="2026-08-23 09:00:00 +0800")
    tag(repo, "v1.2.0")
    data = git_service.collect_diff(str(repo), "v1.1.0", "v1.2.0")
    assert len(data["files"]) == 1
    f = data["files"][0]
    assert f["path"] == "src/renamed.ts"
    assert f.get("old_path") == "src/a.ts"
    assert f["added"] == 0 and f["removed"] == 0
    # R100 纯重命名：patch 应无内容行，而非把新路径当整文件新增
    assert f["lines"] == [] and f["truncated"] is False


def test_collect_diff_splits_multi_file_patch(repo):
    """一次 diff 按文件切分后，每个文件都应拿到自己的内容行。"""
    write_files(repo, {
        "src/b.ts": "export const B = 1;\n",
        "docs/说明 文档.md": "# 需求说明\n",
    })
    commit(repo, "add files", date="2026-08-23 09:00:00 +0800")
    tag(repo, "v1.2.0")

    data = git_service.collect_diff(str(repo), "v1.1.0", "v1.2.0")
    by_path = {f["path"]: f for f in data["files"]}
    assert set(by_path) == {"src/b.ts", "docs/说明 文档.md"}
    assert by_path["src/b.ts"]["lines"][0] == {"t": "add", "s": "export const B = 1;"}
    assert by_path["docs/说明 文档.md"]["lines"][0] == {"t": "add", "s": "# 需求说明"}


def test_read_files_batch(repo):
    got = git_service.read_files(str(repo), "v1.1.0",
                                 ["src/a.ts", "src/missing.ts", "README.md"])
    assert "export function run" in got["src/a.ts"]
    assert got["src/missing.ts"] == ""
    assert got["README.md"].startswith("# demo")
    assert git_service.read_files(str(repo), "v1.1.0", []) == {}


def test_check_ref_rejects_unsafe_input(repo):
    for bad in ("--all", "HEAD --output=x", "a b", "main..dev", "refs/heads/x;rm"):
        with pytest.raises(GitError):
            git_service.resolve_ref(str(repo), bad)
