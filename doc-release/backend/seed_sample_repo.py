"""按 SEED_SEQUENCE 生成示例 git 仓库（幂等，绝不删除已有目录）。"""

import os
import subprocess
import sys
from pathlib import Path

from seed_data import SEED_SEQUENCE

REPO_DIR_NAME = "order-center"
REQUIRED_TAGS = {"v2.13.3", "v2.13.4", "v2.14.0", "v3.0.0"}


def _git(cwd: Path, *args: str, env: dict | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env or os.environ, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{(proc.stderr or '').strip()}")
    return proc.stdout


def _is_ready(target: Path) -> bool:
    if not (target / ".git").is_dir():
        return False
    try:
        tags = set(_git(target, "tag", "--list").split())
    except RuntimeError:
        return False
    return REQUIRED_TAGS.issubset(tags)


def generate(target: Path) -> Path:
    """在 target 目录生成示例仓库；已就绪时直接返回，不重复生成。"""
    target = Path(target)
    if _is_ready(target):
        return target
    if (target / ".git").exists():
        raise RuntimeError(f"{target} 存在未完成生成的 git 仓库，请手动删除后重试")

    target.mkdir(parents=True, exist_ok=True)
    _git(target, "init", "-b", "main")
    _git(target, "config", "user.name", "order-center-bot")
    _git(target, "config", "user.email", "bot@order-center.internal")

    for step in SEED_SEQUENCE:
        if step["kind"] == "commit":
            for rel, content in step["files"].items():
                path = target / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            _git(target, "add", "-A")
            env = {**os.environ, "GIT_AUTHOR_DATE": step["date"], "GIT_COMMITTER_DATE": step["date"]}
            _git(target, "commit", "-m", step["message"], env=env)
        elif step["kind"] == "tag":
            _git(target, "tag", step["name"])
    return target


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample_repo") / REPO_DIR_NAME
    result = generate(target)
    print(f"示例仓库就绪：{result.resolve()}")


if __name__ == "__main__":
    main()
