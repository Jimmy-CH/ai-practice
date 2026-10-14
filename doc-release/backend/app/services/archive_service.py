"""产物归档：写入 <archive_root>/docs/release/<version>/ 与 runId 绑定的删除保护。"""

import json
from pathlib import Path

from app.services.errors import ServiceError


def archive_dir_for(archive_root: Path, version: str) -> Path:
    return Path(archive_root) / "docs" / "release" / version


def write_artifacts(archive_root: Path, version: str, files: dict[str, str]) -> dict[str, Path]:
    """写入三类产物（同版本覆盖）；单文件写入失败重试一次。"""
    target = archive_dir_for(archive_root, version)
    target.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for filename, content in files.items():
        path = target / filename
        last_error: Exception | None = None
        for _ in range(2):
            try:
                # newline=""：禁用跨平台换行翻译，保证落盘字节与内存渲染字节一致
                path.write_text(content, encoding="utf-8", newline="")
                last_error = None
                break
            except OSError as exc:
                last_error = exc
        if last_error is not None:
            raise ServiceError(f"归档写入失败：{filename}（{last_error}）")
        written[filename] = path
    return written


def delete_archive_if_owned(archive_root: Path, version: str, run_id: str) -> bool:
    """删除归档目录，但仅当 trace.json.runId 与目标运行一致（防误删同版本归档）。"""
    target = archive_dir_for(archive_root, version)
    trace_path = target / "trace.json"
    if not trace_path.exists():
        return False
    try:
        data = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if data.get("runId") != run_id:
        return False
    for child in target.iterdir():
        if child.is_file():
            child.unlink()
    target.rmdir()
    return True
