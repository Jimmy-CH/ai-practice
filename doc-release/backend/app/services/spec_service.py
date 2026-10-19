"""九节产品说明书：head_ref 全量快照 → 分模块 LLM 画像 → 结构化 spec。

本模块只产出结构化数据（run.result["spec"]），Markdown 由 spec_renderer 确定性渲染。
LLM 失败一律降级为占位画像，不中断流水线；取消仍按 RunCancelled 向上传播。
"""

import asyncio
import re
from pathlib import Path

from app.config import settings
from app.prompts import spec_v1
from app.prompts.docrelease_v1 import _symbols_summary
from app.services import git_service, llm_service
from app.services.errors import RunCancelled

# 依赖/构建/缓存目录一律不进入分析上下文
_SKIP_DIRS = {".git", "node_modules", "dist", "build", "out", "venv", ".venv",
              "__pycache__", ".pytest_cache", ".mypy_cache", ".idea", ".vscode",
              "archive", "static", "coverage", ".next", ".nuxt", "target", "bin", "obj"}
_SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".pdf",
                  ".zip", ".gz", ".tar", ".whl", ".exe", ".dll", ".so", ".dylib",
                  ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".lock"}
_SKIP_NAMES = {".env", ".npmrc", ".netrc", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
_TEXT_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".go", ".java", ".kt",
              ".rs", ".cs", ".rb", ".php", ".sql", ".md", ".json", ".yaml", ".yml",
              ".toml", ".ini", ".cfg", ".sh", ".ps1", ".gradle", ".xml", ".proto"}
_CONTAINER_DIRS = {"backend", "frontend", "server", "client", "web", "src", "app",
                   "packages", "apps"}

PRIORITIES = ("P0", "P1", "P2")
NFR_KEYS = ("performance", "security", "reliability", "deployment",
            "maintainability", "extensibility", "compatibility")
_CARDINALITIES = {"||--o{", "||--||", "||--|{", "}o--o{", "}o--||",
                  "|o--o{", "|o--||", "||--o|", "}o--o|", "|o--o|"}
_FLOW_PREFIXES = ("flowchart", "graph ", "sequenceDiagram", "stateDiagram")
_ARCH_PREFIXES = ("flowchart", "graph ")
_LANG_BY_SUFFIX = {".py": "python", ".ts": "ts", ".tsx": "tsx", ".js": "js",
                   ".jsx": "jsx", ".vue": "vue", ".go": "go", ".java": "java",
                   ".sql": "sql", ".json": "json", ".md": "md", ".yaml": "yaml",
                   ".yml": "yaml", ".sh": "bash", ".ps1": "powershell"}


def is_candidate_file(path: str) -> bool:
    """源码/配置类文本文件才进入快照；依赖目录、敏感文件、二进制一律排除。"""
    parts = Path(path).parts
    if not parts or any(p in _SKIP_DIRS for p in parts):
        return False
    name = parts[-1]
    if name in _SKIP_NAMES or name.startswith(".env"):
        return False
    if name.startswith(".") or name.endswith(".min.js"):
        return False
    if name.startswith("credentials"):
        return False
    if name.endswith(".pem") or name.endswith(".key") or name.startswith("id_rsa"):
        return False
    suffix = Path(name).suffix.lower()
    if suffix in _SKIP_SUFFIXES:
        return False
    return suffix in _TEXT_EXTS


def module_key(path: str) -> str:
    """模块聚类键：剥离首个容器目录后取前两级目录（如 app/services、src/order）。"""
    dirs = list(Path(path).parts[:-1])
    if dirs and dirs[0] in _CONTAINER_DIRS:
        stripped = dirs[1:]
        # src/a.ts 这类只有一层容器目录时保留原目录，避免全部落进「根目录」
        dirs = stripped or dirs
    if not dirs:
        return "根目录"
    return "/".join(dirs[:2])


def build_module_groups(paths: list[str], changed_paths: set[str]) -> list[dict]:
    """按模块聚类全部候选文件，并标记模块内是否含本次变更。"""
    groups: dict[str, dict] = {}
    for path in paths:
        if not is_candidate_file(path):
            continue
        key = module_key(path)
        group = groups.setdefault(key, {"name": key, "files": [], "changed": False})
        group["files"].append(path)
        if path in changed_paths:
            group["changed"] = True
    return sorted(groups.values(), key=lambda g: g["name"])


def select_modules(groups: list[dict], max_modules: int) -> tuple[list[dict], int]:
    """按「含变更 > 文件数」排序截断，返回选中模块与被跳过数量。"""
    ordered = sorted(groups, key=lambda g: (g["changed"], len(g["files"])), reverse=True)
    return ordered[:max_modules], max(0, len(ordered) - max_modules)


def _file_score(path: str) -> int:
    """关键文件优先：路由/模型/服务/页面/配置 > 工具/类型 > 测试/示例。"""
    low = path.lower()
    score = 0
    if any(k in low for k in ("route", "router", "controller", "api", "view", "page",
                              "screen", "model", "entity", "schema", "store", "service",
                              "handler", "usecase", "repository", "dao", "config",
                              "settings", "main", "app", "index")):
        score += 5
    elif any(k in low for k in ("util", "helper", "hook", "type", "constant",
                                "middleware", "auth", "pay", "order", "report")):
        score += 3
    if any(k in low for k in ("test", "spec", "mock", "fixture", "story", "example", "demo")):
        score -= 3
    if low.endswith(".md"):
        score -= 2
    return score


def select_files(group: dict, max_files: int) -> list[str]:
    ranked = sorted(group["files"], key=lambda p: (-_file_score(p), p))
    return ranked[:max_files]


def _change_label(status: str) -> str:
    return {"a": "新增", "d": "删除"}.get(status, "修改")


def _changed_paths(changeset: dict) -> set[str]:
    paths: set[str] = set()
    for f in changeset.get("files") or []:
        for key in ("path", "old_path"):
            if f.get(key):
                paths.add(f[key])
    return paths


def _change_hints(group: dict, changeset: dict) -> list[str]:
    """模块内变更摘要：文件状态/行数 + AST 符号，用于第 4 节标注本次变更。"""
    hints: list[str] = []
    for f in changeset.get("files") or []:
        path = f.get("path", "")
        if module_key(path) != group["name"]:
            continue
        label = _change_label(f.get("status", "m"))
        line = f"{path}（{label}，+{f.get('added', 0)}/-{f.get('removed', 0)}）"
        summary = _symbols_summary(f)
        if summary:
            line += f"；符号变更：{summary}"
        hints.append(line)
    return hints


def build_module_snapshots(repo_path: str, ref: str, groups: list[dict],
                           changeset: dict, max_files: int, max_chars: int) -> list[dict]:
    """读取选中模块的关键文件内容，生成提示词输入快照。"""
    selected_paths: list[str] = []
    per_group: dict[str, list[str]] = {}
    for group in groups:
        paths = select_files(group, max_files)
        per_group[group["name"]] = paths
        selected_paths.extend(paths)
    contents = git_service.read_files(repo_path, ref, selected_paths)
    status_by_path = {f.get("path"): f for f in changeset.get("files") or []}

    snapshots: list[dict] = []
    for group in groups:
        budget = max_chars * 6  # 单模块提示词总量兜底，避免 12×4000 撑爆上下文
        files: list[dict] = []
        for path in per_group.get(group["name"], []):
            raw = contents.get(path, "")
            if not raw.strip():
                continue
            text = raw[:max_chars]
            if budget <= 0:
                break
            text = text[:budget]
            budget -= len(text)
            change = status_by_path.get(path) or {}
            files.append({
                "path": path,
                "content": text,
                "truncated": len(raw) > len(text),
                "label": _change_label(change.get("status", "")) if change else "未变更",
                "lang": _LANG_BY_SUFFIX.get(Path(path).suffix.lower(), ""),
            })
        snapshots.append({
            "name": group["name"],
            "changed": group["changed"],
            # 文件清单只用于附录/提示词概览，截断避免大模块把 result 撑爆
            "tree": sorted(group["files"])[:200],
            "files": files,
            "changes": _change_hints(group, changeset),
        })
    return snapshots


def _read_root_files(repo_path: str, ref: str, tree: list[str]) -> tuple[str, list[dict]]:
    """读取根级 README 与依赖清单，供全局概览提示词使用。"""
    names = ("README.md", "README", "readme.md", "package.json", "requirements.txt",
             "pyproject.toml", "go.mod", "pom.xml", "build.gradle", "Dockerfile",
             "docker-compose.yml")
    picked: list[str] = []
    for name in names:
        for path in tree:
            if path == name and path not in picked:
                picked.append(path)
                break
    contents = git_service.read_files(repo_path, ref, picked)
    readme = ""
    manifests: list[dict] = []
    for path in picked:
        text = (contents.get(path) or "").strip()
        if not text:
            continue
        if path.lower().startswith("readme"):
            readme = text[:4000]
        else:
            manifests.append({"path": path, "content": text[:1500]})
    return readme, manifests


def _str(value, limit: int = 200) -> str:
    return str(value or "").strip()[:limit]


def _str_list(value, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = _str(item, 300)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _clean_mermaid(text, prefixes: tuple[str, ...]) -> str:
    """剥离代码围栏并校验首行；首行不在白名单内的图直接丢弃。"""
    t = str(text or "").strip()
    t = re.sub(r"^```(?:mermaid)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t).strip()
    if not t:
        return ""
    first = t.splitlines()[0].strip()
    if not any(first.startswith(p) for p in prefixes):
        return ""
    return t


def normalize_module_payload(raw: dict) -> dict:
    """把模型输出收敛为固定结构；非法项丢弃，缺失数组补空。"""
    if not isinstance(raw, dict):
        raise ValueError("模块画像不是 JSON 对象")

    functions: list[dict] = []
    for item in raw.get("functions") or []:
        if not isinstance(item, dict):
            continue
        name = _str(item.get("name"), 40)
        if not name:
            continue
        priority = item.get("priority")
        functions.append({
            "name": name,
            "logic": _str(item.get("logic"), 500) or "（代码中未体现明确逻辑）",
            "roles": _str_list(item.get("roles"), 6),
            "priority": priority if priority in PRIORITIES else "P1",
        })
        if len(functions) >= 8:
            break

    flows: list[dict] = []
    for item in raw.get("flows") or []:
        if not isinstance(item, dict):
            continue
        mermaid = _clean_mermaid(item.get("mermaid"), _FLOW_PREFIXES)
        if mermaid:
            flows.append({"title": _str(item.get("title"), 60) or "核心流程",
                          "mermaid": mermaid})
        if len(flows) >= 3:
            break

    entities: list[dict] = []
    for item in raw.get("entities") or []:
        if not isinstance(item, dict):
            continue
        name = _str(item.get("name"), 60)
        if not name:
            continue
        fields: list[dict] = []
        for fd in item.get("fields") or []:
            if not isinstance(fd, dict):
                continue
            field_name = _str(fd.get("name"), 60)
            if not field_name:
                continue
            fields.append({
                "name": field_name,
                "type": _str(fd.get("type"), 40) or "string",
                "constraints": _str(fd.get("constraints"), 80),
                "note": _str(fd.get("note"), 120),
            })
            if len(fields) >= 24:
                break
        relations: list[dict] = []
        for rel in item.get("relations") or []:
            if not isinstance(rel, dict):
                continue
            target = _str(rel.get("target"), 60)
            if not target:
                continue
            cardinality = rel.get("cardinality")
            relations.append({
                "target": target,
                "label": _str(rel.get("label"), 60),
                "cardinality": cardinality if cardinality in _CARDINALITIES else "||--o{",
            })
            if len(relations) >= 12:
                break
        entities.append({"name": name, "table": _str(item.get("table"), 80),
                         "fields": fields, "relations": relations})
        if len(entities) >= 12:
            break

    enums: list[dict] = []
    for item in raw.get("enums") or []:
        if not isinstance(item, dict):
            continue
        name = _str(item.get("name"), 60)
        if name:
            enums.append({"name": name, "values": _str_list(item.get("values"), 20)})
        if len(enums) >= 12:
            break

    rules: list[dict] = []
    for item in raw.get("rules") or []:
        if not isinstance(item, dict):
            continue
        topic = _str(item.get("topic"), 80)
        points = _str_list(item.get("points"), 12)
        if topic or points:
            rules.append({"topic": topic or "规则", "points": points})
        if len(rules) >= 12:
            break

    error_codes: list[dict] = []
    for item in raw.get("errorCodes") or []:
        if not isinstance(item, dict):
            continue
        scene = _str(item.get("scene"), 120)
        code = _str(item.get("code"), 20)
        if scene or code:
            error_codes.append({"scene": scene, "code": code, "ui": _str(item.get("ui"), 120)})
        if len(error_codes) >= 20:
            break

    nfr_raw = raw.get("nfr") if isinstance(raw.get("nfr"), dict) else {}
    nfr = {key: _str_list(nfr_raw.get(key), 12) for key in NFR_KEYS}

    return {
        "responsibility": _str(raw.get("responsibility"), 200),
        "functions": functions,
        "flows": flows,
        "entities": entities,
        "enums": enums,
        "rules": rules,
        "errorCodes": error_codes,
        "nfr": nfr,
    }


def normalize_overview_payload(raw: dict) -> dict:
    """全局概览输出收敛；结构缺失时返回空骨架，由兜底逻辑填充。"""
    if not isinstance(raw, dict):
        raise ValueError("概览不是 JSON 对象")
    ov = raw.get("overview") if isinstance(raw.get("overview"), dict) else {}
    roles: list[dict] = []
    for item in raw.get("roles") or []:
        if not isinstance(item, dict):
            continue
        role = _str(item.get("role"), 40)
        if role:
            roles.append({"role": role, "scenarios": _str_list(item.get("scenarios"), 8)})
    arch = raw.get("architecture") if isinstance(raw.get("architecture"), dict) else {}
    stack: list[dict] = []
    for item in arch.get("stack") or []:
        if not isinstance(item, dict):
            continue
        layer, tech = _str(item.get("layer"), 40), _str(item.get("tech"), 80)
        if layer or tech:
            stack.append({"layer": layer, "tech": tech, "note": _str(item.get("note"), 120)})
    modules: list[dict] = []
    for item in arch.get("modules") or []:
        if not isinstance(item, dict):
            continue
        name = _str(item.get("name"), 80)
        if name:
            modules.append({"name": name, "responsibility": _str(item.get("responsibility"), 200)})
    return {
        "overview": {
            "name": _str(ov.get("name"), 80),
            "positioning": _str(ov.get("positioning"), 400),
            "problems": _str_list(ov.get("problems"), 8),
            "scope": _str_list(ov.get("scope"), 8),
        },
        "roles": roles,
        "architecture": {
            "stack": stack,
            "modules": modules,
            "diagram": _clean_mermaid(arch.get("diagram"), _ARCH_PREFIXES),
        },
    }


def fallback_module(group: dict, reason: str) -> dict:
    """单模块失败：保留模块位置并给出一条待人工确认的功能行。"""
    return {
        "name": group["name"],
        "responsibility": f"{group['name']} 模块（自动画像失败，待人工确认）",
        "changed": group["changed"],
        "degraded": True,
        "files": sorted(group["tree"])[:200],
        "functions": [{
            "name": f"{group['name']} 变更待人工确认",
            "logic": (reason or "模型未返回可用结果")[:160],
            "roles": ["研发"],
            "priority": "P1",
        }],
        "flows": [],
        "entities": [],
        "enums": [],
        "rules": [],
        "errorCodes": [],
        "nfr": {key: [] for key in NFR_KEYS},
    }


def fallback_overview(repo_name: str, modules: list[dict], readme: str,
                      manifests: list[dict]) -> dict:
    """全局概览失败：用 README 首段、模块职责与依赖清单确定性兜底。"""
    positioning = ""
    for line in (readme or "").splitlines():
        text = line.strip().lstrip("#").strip()
        if text and not text.startswith(("!", "[", "<", "|")):
            positioning = text[:300]
            break
    stack: list[dict] = []
    manifest_text = " ".join(m.get("content", "") for m in manifests).lower()
    checks = (
        ("vue", "前端", "Vue"),
        ("react", "前端", "React"),
        ("@angular", "前端", "Angular"),
        ("fastapi", "后端", "FastAPI"),
        ("django", "后端", "Django"),
        ("flask", "后端", "Flask"),
        ("spring", "后端", "Spring"),
        ("express", "后端", "Express"),
        ("go 1.", "后端", "Go"),
        ("model", "数据", "SQLAlchemy/ORM"),
    )
    seen: set[str] = set()
    for keyword, layer, tech in checks:
        if keyword in manifest_text and tech not in seen:
            seen.add(tech)
            stack.append({"layer": layer, "tech": tech, "note": "由依赖清单推断"})
    roles: list[dict] = []
    role_map: dict[str, list[str]] = {}
    for module in modules:
        for fn in module.get("functions") or []:
            for role in fn.get("roles") or []:
                scenes = role_map.setdefault(role, [])
                if fn.get("name") and fn["name"] not in scenes:
                    scenes.append(fn["name"])
    for role, scenes in role_map.items():
        roles.append({"role": role, "scenarios": scenes[:5]})
    return {
        "overview": {"name": repo_name, "positioning": positioning, "problems": [], "scope": []},
        "roles": roles,
        "architecture": {
            "stack": stack,
            "modules": [{"name": m["name"],
                         "responsibility": m.get("responsibility", "")} for m in modules],
            "diagram": "",
        },
    }


def _emit(log, channel: str, tag: str, message: str) -> None:
    if log is not None:
        log(channel, tag, message)


async def _chat_json(system_prompt: str, user_prompt: str, cancel_check, metrics: dict) -> dict:
    """单次调用 + 失败重试 1 次；取消立即向上抛，不进入重试。"""
    last_error = ""
    for attempt in (1, 2):
        if cancel_check is not None and cancel_check():
            raise RunCancelled("运行已取消")
        prompt = user_prompt
        if attempt == 2:
            prompt += "\n\n注意：只输出 JSON 对象本身，不要任何解释文字。"
        metrics["calls"] += 1
        try:
            text = await llm_service._chat(system_prompt, prompt)
            metrics["inputChars"] += len(prompt)
            metrics["outputChars"] += len(text or "")
            data = llm_service.extract_json(text or "")
            metrics["okCalls"] += 1
            return data
        except RunCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 —— 解析/请求失败均重试一次
            last_error = str(exc)
    raise RuntimeError(last_error or "LLM 调用失败")


async def _analyze_module(snapshot: dict, sem: asyncio.Semaphore, metrics: dict,
                          cancel_check=None, log=None) -> dict:
    async with sem:
        try:
            data = await _chat_json(spec_v1.MODULE_SYSTEM_PROMPT,
                                    spec_v1.build_module_prompt(snapshot),
                                    cancel_check, metrics)
            normalized = normalize_module_payload(data)
        except RunCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 —— 单模块失败只降级，不中断整体
            reason = str(exc)
            _emit(log, "warn", "画像", f"{snapshot['name']}：生成失败（{reason[:60]}）")
            return fallback_module(snapshot, reason)
    profile = {"name": snapshot["name"], "changed": snapshot["changed"],
               "degraded": False, "files": snapshot["tree"], **normalized}
    profile["responsibility"] = (profile.get("responsibility")
                                 or f"{snapshot['name']} 模块")
    _emit(log, "step", "画像",
          f"{snapshot['name']}：功能 {len(profile['functions'])} · "
          f"流程 {len(profile['flows'])} · 实体 {len(profile['entities'])}")
    return profile


async def _analyze_overview(repo_name: str, ref: str, readme: str, manifests: list[dict],
                            modules: list[dict], metrics: dict, cancel_check=None,
                            log=None) -> tuple[dict, str]:
    try:
        data = await _chat_json(
            spec_v1.OVERVIEW_SYSTEM_PROMPT,
            spec_v1.build_overview_prompt(repo_name, ref, readme, manifests, modules),
            cancel_check, metrics)
        normalized = normalize_overview_payload(data)
        if not normalized["overview"]["name"]:
            normalized["overview"]["name"] = repo_name
        if not normalized["architecture"]["modules"]:
            normalized["architecture"]["modules"] = [
                {"name": m["name"], "responsibility": m.get("responsibility", "")}
                for m in modules]
        _emit(log, "step", "概览",
              f"项目定位与技术栈已生成（{len(normalized['architecture']['stack'])} 项技术）")
        return normalized, ""
    except RunCancelled:
        raise
    except Exception as exc:  # noqa: BLE001 —— 概览失败用确定性兜底
        reason = str(exc)
        _emit(log, "warn", "概览", f"生成失败，使用确定性兜底（{reason[:60]}）")
        return fallback_overview(repo_name, modules, readme, manifests), reason


async def generate_product_spec(repo_path: str, ref: str, repo_name: str, changeset: dict,
                                cancel_check=None, log=None) -> dict:
    """全量快照 → 分模块画像 → 全局概览；除取消外不向外抛异常。"""
    metrics = {"calls": 0, "okCalls": 0, "inputChars": 0, "outputChars": 0}
    if cancel_check is not None and cancel_check():
        raise RunCancelled("运行已取消")

    tree = await asyncio.to_thread(git_service.list_tree, repo_path, ref)
    candidate_paths = [p for p in tree if is_candidate_file(p)]
    groups = build_module_groups(candidate_paths, _changed_paths(changeset))
    selected, skipped = select_modules(groups, max(1, settings.spec_max_modules))
    _emit(log, "step", "快照",
          f"{ref}：{len(candidate_paths)} 个源文件，{len(selected)} 个模块纳入分析"
          + (f"（跳过 {skipped} 个）" if skipped else ""))
    if cancel_check is not None and cancel_check():
        raise RunCancelled("运行已取消")

    snapshots = await asyncio.to_thread(
        build_module_snapshots, repo_path, ref, selected, changeset,
        settings.spec_max_files_per_module, settings.spec_max_file_chars)
    readme, manifests = await asyncio.to_thread(_read_root_files, repo_path, ref, tree)

    sem = asyncio.Semaphore(max(1, settings.spec_concurrency))
    tasks = [asyncio.create_task(_analyze_module(s, sem, metrics, cancel_check, log))
             for s in snapshots]
    try:
        modules = await asyncio.gather(*tasks) if tasks else []
    except RunCancelled:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise

    overview, overview_error = await _analyze_overview(
        repo_name, ref, readme, manifests, modules, metrics, cancel_check, log)

    low_confidence: list[str] = []
    for module in modules:
        if module.get("degraded"):
            low_confidence.append(
                f"{module['name']}：产品画像生成失败，功能/流程/实体待人工复核")
    if overview_error:
        low_confidence.append(
            f"全局概览：生成失败，已使用确定性兜底（{overview_error[:80]}）")

    return {
        "prompt": spec_v1.PROMPT_VERSION,
        "snapshot": {"ref": ref, "files": len(candidate_paths),
                     "modules": len(modules), "skipped": skipped},
        "overview": overview["overview"],
        "roles": overview["roles"],
        "architecture": overview["architecture"],
        "modules": modules,
        "degradedModules": [m["name"] for m in modules if m.get("degraded")],
        "lowConfidence": low_confidence,
        "llm": metrics,
    }
