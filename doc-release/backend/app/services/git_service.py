"""只读封装 git CLI：引用枚举、提交列表、diff 收集、模块聚类。

所有对外函数在出错时抛 GitError；绝不写入被检查的仓库。
"""

import os
import re
import subprocess
from datetime import date
from pathlib import Path

from app.services.errors import GitError

_MAX_FILES = 200
# 引用名白名单：git 引用不允许空白与 shell 元字符，这里前置拦截，避免奇怪参数传给 git
_REF_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._/@^~:+-]{0,199}$")


def _run_git(repo_path: str, args: list[str], timeout: int = 60) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except FileNotFoundError as exc:
        raise GitError("未找到 git 可执行文件") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("git 命令超时") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise GitError(detail[-1] if detail else "git 命令执行失败")
    return proc.stdout


def _check_ref(ref: str) -> str:
    ref = (ref or "").strip()
    if not ref or ref.startswith("-") or ".." in ref or not _REF_PATTERN.match(ref):
        raise GitError(f"非法的引用名：{ref or '(空)'}")
    return ref


def validate_repo(path: str) -> None:
    if not Path(path).is_dir():
        raise GitError(f"路径不存在或不是目录：{path}")
    _run_git(path, ["rev-parse", "--git-dir"])


def resolve_ref(repo_path: str, ref: str) -> str:
    return _run_git(repo_path, ["rev-parse", "--verify", f"{_check_ref(ref)}^{{commit}}"]).strip()


def list_refs(repo_path: str) -> dict:
    out = _run_git(repo_path, ["for-each-ref", "refs/heads", "refs/tags",
                               "--format=%(refname)|%(refname:short)|%(objectname:short)"])
    branches: list[dict] = []
    tags: list[dict] = []
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue
        full, short, sha = parts
        if full.startswith("refs/heads/"):
            branches.append({"name": short, "short": sha})
        elif full.startswith("refs/tags/"):
            tags.append({"name": short, "short": sha})
    branches.sort(key=lambda x: x["name"])
    tags.sort(key=lambda x: x["name"])
    try:
        default_branch = _run_git(repo_path, ["symbolic-ref", "--short", "HEAD"]).strip()
    except GitError:
        default_branch = branches[0]["name"] if branches else ""
    return {"branches": branches, "tags": tags, "default_branch": default_branch}


def list_commits(repo_path: str, base: str, head: str, limit: int = 200) -> list[dict]:
    base, head = _check_ref(base), _check_ref(head)
    out = _run_git(repo_path, ["log", f"{base}..{head}", f"--max-count={limit}",
                               "--format=%h|%an|%ad|%s", "--date=format:%Y-%m-%d"])
    commits = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({"hash": parts[0], "author": parts[1],
                            "date": parts[2], "subject": parts[3]})
    commits.reverse()  # git log 默认新→旧，翻转成最早在前
    return commits


def show_file(repo_path: str, ref: str, path: str) -> str:
    """返回指定引用下的文件内容；文件不存在时返回空串。"""
    ref = _check_ref(ref)
    try:
        return _run_git(repo_path, ["show", f"{ref}:{path}"])
    except GitError:
        return ""


def _unquote_path(raw: str) -> str:
    """去掉 git 对含空格/特殊字符路径加的引号与常见转义。"""
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        body = raw[1:-1]
        return (body.replace('\\"', '"')
                .replace("\\\\", "\\")
                .replace("\\t", "\t")
                .replace("\\n", "\n"))
    return raw


def _parse_hunks(lines: list[str], max_lines: int) -> tuple[list[dict], bool]:
    """解析单个文件的内容行（文件头已在切分时剔除）。"""
    out: list[dict] = []
    for raw in lines:
        # 多个 hunk 之间的 @@ 头与「\ No newline」标记不是内容
        if raw.startswith("@@") or raw.startswith("\\"):
            continue
        if raw.startswith("+"):
            kind, body = "add", raw[1:]
        elif raw.startswith("-"):
            kind, body = "del", raw[1:]
        else:
            kind, body = "ctx", raw[1:] if raw.startswith(" ") else raw
        out.append({"t": kind, "s": body})
        if len(out) >= max_lines:
            return out, True
    return out, False


def _split_file_patches(patch: str) -> dict[str, list[str]]:
    """把一次 git diff 的输出按文件切分，键为文件路径。

    路径可能包含空格（git 在这种情况下不保证加引号），因此以「+++ b/」行为准；
    删除文件没有新路径，回退到「--- a/」。
    """
    segments: dict[str, list[str]] = {}
    current: list[str] | None = None
    old_path = new_path = ""
    for raw in patch.splitlines():
        if raw.startswith("diff --git "):
            current, old_path, new_path = None, "", ""
            continue
        if current is None:
            if raw.startswith("+++ b/"):
                new_path = raw[6:].rstrip("\t").strip()
            elif raw.startswith("--- a/"):
                old_path = raw[6:].rstrip("\t").strip()
            elif raw.startswith("@@"):
                path = new_path or old_path
                current = segments.setdefault(path, []) if path else []
            continue
        current.append(raw)
    return segments


_RENAME_BRACE = re.compile(r"^(.*)\{(.*) => (.*)\}(.*)$")


def _split_rename(raw: str) -> tuple[str, str]:
    """解析 git rename 路径：src/{a.ts => b.ts}（带公共前后缀）或 a.ts => b.ts。"""
    m = _RENAME_BRACE.match(raw)
    if m:
        prefix, old, new, suffix = m.groups()
        return (prefix + old + suffix), (prefix + new + suffix)
    if " => " in raw:
        old, new = raw.split(" => ", 1)
        return old, new
    return raw, raw


def cluster_modules(files: list[dict], depth: int = 2) -> list[dict]:
    groups: dict[str, list[str]] = {}
    for f in files:
        parts = Path(f["path"]).parts
        key = "/".join(parts[:depth]) if len(parts) > depth else str(Path(f["path"]).parent)
        if key in (".", ""):
            key = parts[0] if parts else f["path"]
        groups.setdefault(key, []).append(f["path"])
    return [{"name": k, "files": v} for k, v in sorted(groups.items())]


def _span_days(commits: list[dict]) -> int:
    if not commits:
        return 0
    first = date.fromisoformat(commits[0]["date"])
    last = date.fromisoformat(commits[-1]["date"])
    return max((last - first).days, 1)


def read_files(repo_path: str, ref: str, paths: list[str]) -> dict[str, str]:
    """批量读取指定引用下的文件内容（单次 git cat-file --batch）；缺失文件返回空串。"""
    ref = _check_ref(ref)
    result = {path: "" for path in paths}
    if not paths:
        return result
    payload = "".join(f"{ref}:{path}\n" for path in paths).encode("utf-8")
    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, "cat-file", "--batch"],
            input=payload, capture_output=True, timeout=60, check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except FileNotFoundError as exc:
        raise GitError("未找到 git 可执行文件") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("git 命令超时") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        raise GitError(detail[-1] if detail else "git 命令执行失败")

    data = proc.stdout
    pos = 0
    for path in paths:
        nl = data.find(b"\n", pos)
        if nl == -1:
            break
        header = data[pos:nl].decode("utf-8", "replace")
        pos = nl + 1
        parts = header.rsplit(" ", 2)
        # 缺失对象输出「<查询> missing」，内容输出「<sha> blob <size>」
        if len(parts) != 3 or not parts[2].isdigit():
            continue
        size = int(parts[2])
        result[path] = data[pos:pos + size].decode("utf-8", "replace")
        pos += size + 1
    return result


def collect_diff(repo_path: str, base: str, head: str, max_lines: int = 400) -> dict:
    """收集 base..head 的提交、逐文件 diff（可截断）与统计。

    diff 只跑一次再按文件切分：逐文件调用 git 会产生上百个子进程，
    在预览接口这种同步热路径上开销明显。
    """
    base, head = _check_ref(base), _check_ref(head)
    resolve_ref(repo_path, base)
    resolve_ref(repo_path, head)
    commits = list_commits(repo_path, base, head)
    if not commits:
        raise GitError(f"范围 {base}..{head} 内没有变更提交")

    quoted = ["-c", "core.quotePath=false"]
    numstat = _run_git(repo_path, [*quoted, "diff", "--numstat", f"{base}..{head}", "--"])
    name_status = _run_git(repo_path, [*quoted, "diff", "--name-status", f"{base}..{head}", "--"])
    statuses: dict[str, str] = {}
    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            _, new_path = _split_rename(_unquote_path(parts[-1]))
            statuses[new_path] = {"A": "a", "D": "d"}.get(parts[0][:1], "m")

    files: list[dict] = []
    total_add = total_del = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        old_path, path = _split_rename(_unquote_path(parts[2]))
        added_raw, del_raw = parts[0], parts[1]
        binary = added_raw == "-"
        added = 0 if binary else int(added_raw)
        removed = 0 if binary else int(del_raw)
        total_add += added
        total_del += removed
        files.append({"status": statuses.get(path, "m"), "path": path,
                      "added": added, "removed": removed, "binary": binary,
                      "truncated": False, "lines": []})
        if old_path != path:
            files[-1]["old_path"] = old_path

    patches = _split_file_patches(_run_git(
        repo_path, [*quoted, "diff", "-U3", "--no-color", "--no-ext-diff",
                    f"{base}..{head}", "--"], timeout=120))
    for entry in files[:_MAX_FILES]:
        if entry["binary"]:
            continue
        entry["lines"], entry["truncated"] = _parse_hunks(
            patches.get(entry["path"], []), max_lines)

    modules = cluster_modules(files)
    stats = {"commits": len(commits), "files": len(files), "modules": len(modules),
             "added": total_add, "removed": total_del, "days": _span_days(commits)}
    return {"base": base, "head": head, "commits": commits, "files": files,
            "stats": stats, "modules": modules}
