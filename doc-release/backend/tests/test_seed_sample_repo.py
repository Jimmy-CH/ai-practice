import pytest

import seed_sample_repo
from tests.gitfix import git


@pytest.fixture(scope="module")
def sample_repo(tmp_path_factory):
    target = tmp_path_factory.mktemp("seed") / "order-center"
    return seed_sample_repo.generate(target)


def _rev_count(repo, rng: str) -> int:
    return int(git(repo, "rev-list", "--count", rng).strip())


def test_tags_created(sample_repo):
    assert sorted(git(sample_repo, "tag", "--list").split()) == ["v2.13.3", "v2.13.4", "v2.14.0", "v3.0.0"]


def test_ranges_have_expected_commit_counts(sample_repo):
    assert _rev_count(sample_repo, "v2.13.3..v2.13.4") == 3
    assert _rev_count(sample_repo, "v2.13.4..v2.14.0") == 4
    assert _rev_count(sample_repo, "v2.14.0..v3.0.0") == 5


def test_patch_range_files_and_status(sample_repo):
    lines = git(sample_repo, "diff", "--name-status", "v2.13.3..v2.13.4").strip().splitlines()
    statuses = {l.split("\t")[1]: l.split("\t")[0] for l in lines}
    assert sorted(statuses) == ["api/report/export.go", "src/report/export/index.ts",
                                "src/report/export/retry.ts", "src/report/export/stream.ts"]
    assert statuses["src/report/export/stream.ts"] == "A"
    assert statuses["src/report/export/index.ts"] == "M"


def test_contract_signal_scenarios(sample_repo):
    # major 范围：v1 下单接口被删除（导出符号删除信号的依据）
    legacy_head = git(sample_repo, "show", "v3.0.0:api/legacy/order.go")
    assert "CreateOrderV1" not in legacy_head
    # feature 范围：退款窗口常量值变化（常量变更信号的依据）
    assert "REFUND_WINDOW_DAYS = 7" in git(sample_repo, "show", "v2.13.3:src/aftersale/policy.ts")
    assert "REFUND_WINDOW_DAYS = 15" in git(sample_repo, "show", "v2.14.0:src/aftersale/policy.ts")


def test_generate_is_idempotent(sample_repo):
    assert seed_sample_repo.generate(sample_repo) == sample_repo
    assert _rev_count(sample_repo, "v2.13.3..v3.0.0") == 12
