import json

import pytest
from pydantic import ValidationError

from app.schemas.run import RunCreate
from app.services import archive_service
from app.services.errors import ServiceError


def test_archive_dir_accepts_normal_version(tmp_path):
    d = archive_service.archive_dir_for(tmp_path, "v2.13.4")
    assert d.name == "v2.13.4"


def test_normalize_version_keeps_single_segment():
    assert archive_service.normalize_version(" v2.13.4 ") == "v2.13.4"
    assert archive_service.normalize_version("release/2026-10") == "release-2026-10"
    assert archive_service.normalize_version('v1:2*3?|<>"') == "v1-2-3"
    assert archive_service.normalize_version("   ") == "unversioned"
    assert archive_service.normalize_version("..") == "unversioned"
    assert len(archive_service.normalize_version("x" * 200)) == 120


def test_archive_dir_rejects_traversal(tmp_path):
    for bad in ("../outside", "..\\outside", "a/../..", ".", ".."):
        with pytest.raises(ServiceError):
            archive_service.archive_dir_for(tmp_path, bad)


def test_delete_archive_rejects_traversal(tmp_path):
    assert archive_service.delete_archive_if_owned(tmp_path, "../../etc", "r1") is False


def test_delete_archive_keeps_unmanaged_files(tmp_path):
    target = archive_service.write_artifacts(tmp_path, "v1.0.0", {
        "trace.json": json.dumps({"runId": "r1"}),
        "checklist.csv": "x", "product-doc.md": "y"})
    extra = target["trace.json"].parent / "user-note.txt"
    extra.write_text("keep me", encoding="utf-8")
    assert archive_service.delete_archive_if_owned(tmp_path, "v1.0.0", "r1") is True
    assert extra.exists()          # 非受管文件保留
    assert extra.parent.exists()   # 目录因残留文件保留


def test_run_create_rejects_path_like_version():
    with pytest.raises(ValidationError):
        RunCreate(repo_id=1, base_ref="v1", head_ref="v2", version_label="../evil")
    with pytest.raises(ValidationError):
        RunCreate(repo_id=1, base_ref="v1", head_ref="v2", version_label=r"a\\b")
    ok = RunCreate(repo_id=1, base_ref="v1", head_ref="v2", version_label="v2.13.4")
    assert ok.version_label == "v2.13.4"
