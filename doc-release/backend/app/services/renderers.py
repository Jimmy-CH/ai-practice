"""三类产物确定性渲染（纯函数）：功能点清单 CSV / 产品文档 MD / 溯源文件 JSON。

tone（业务/技术）与 mask（脱敏）只在渲染期应用，不改变结构化结果。
"""

import json

GENERATOR_NAME = "释文 DocRelease"


def _mask_path(path: str) -> str:
    parts = (path or "").replace("\\", "/").split("/")
    if len(parts) <= 2:
        return path
    return "/".join(["…"] + parts[-2:])


def _mask_commit(short: str) -> str:
    short = short or ""
    return f"{short[:3]}****" if len(short) > 3 else short


def _paths(f: dict, mask: bool) -> list[str]:
    return [(_mask_path(p) if mask else p) for p in (f.get("paths") or [])]


def _mask_signals(signals: list, mask: bool) -> list:
    """脱敏时对契约信号中的文件路径应用掩码，与功能点 paths 口径一致。"""
    if not mask:
        return signals
    out = []
    for sig in signals or []:
        if not isinstance(sig, dict):
            continue
        s = dict(sig)
        if s.get("path"):
            s["path"] = _mask_path(s["path"])
        out.append(s)
    return out


def _explain(f: dict, tone: str) -> str:
    return f.get("tech", "") if tone == "tech" else f.get("biz", "")


def _csv_cell(value) -> str:
    s = "" if value is None else str(value)
    if any(ch in s for ch in [",", '"', "\n", "\r"]):
        return '"' + s.replace('"', '""') + '"'
    return s


def render_checklist(result: dict, opts: dict) -> str:
    meta = result["meta"]
    tone = opts.get("tone", "business")
    mask = bool(opts.get("mask", False))
    header = ["序号", "版本", "标签", "风险", "破坏性", "功能点", "说明",
              "影响范围", "验收要点", "上线动作", "负责角色", "涉及文件"]
    rows = [header]
    for i, f in enumerate(result.get("features", []), start=1):
        rows.append([
            str(i), meta["version"], f.get("tag", ""), f.get("risk", ""),
            "是" if f.get("breaking") else "否", f.get("title", ""), _explain(f, tone),
            f.get("scope", ""), f.get("acceptance", ""), f.get("action", ""),
            f.get("role", ""), "；".join(_paths(f, mask)),
        ])
    lines = [",".join(_csv_cell(c) for c in row) for row in rows]
    return "\ufeff" + "\r\n".join(lines) + "\r\n"


def render_document(result: dict, opts: dict) -> str:
    meta = result["meta"]
    stats = meta.get("stats", {})
    llm = result.get("llm", {})
    tone = opts.get("tone", "business")
    mask = bool(opts.get("mask", False))
    features = result.get("features", [])
    commit = _mask_commit(meta["headShort"]) if mask else meta["headShort"]

    L: list[str] = []
    L.append(f"# {meta['version']} 发布说明")
    L.append("")
    L.append("## 一、版本概览")
    L.append("")
    L.append(f"- 仓库：{meta['repoName']}（分支 {meta['branch']}）")
    L.append(f"- 变更范围：`{meta['range']}`，头部提交 `{commit}`")
    L.append(f"- 变更规模：{stats.get('commits', 0)} 个提交 · {stats.get('files', 0)} 个文件 · "
             f"+{stats.get('added', 0)}/-{stats.get('removed', 0)} 行 · 跨度 {stats.get('days', 0)} 天")
    L.append(f"- 生成时间：{meta['generatedAt']}（{meta['trigger']}）")
    L.append(f"- 功能点：{len(features)} 项，其中破坏性变更 {sum(1 for f in features if f.get('breaking'))} 项")
    L.append("")

    L.append("## 二、发布亮点")
    L.append("")
    for h in result.get("highlights") or []:
        L.append(f"- {h}")
    if not result.get("highlights"):
        L.append("- （无）")
    L.append("")

    L.append("## 三、功能清单")
    L.append("")
    for i, f in enumerate(features, start=1):
        L.append(f"### {i}. {f.get('title', '')}")
        L.append("")
        L.append(f"- 标签：{f.get('tag', '')}｜风险：{f.get('risk', '')}｜"
                 f"破坏性变更：{'是' if f.get('breaking') else '否'}｜负责角色：{f.get('role', '')}")
        L.append(f"- 业务说明：{f.get('biz', '')}")
        L.append(f"- 技术说明：{f.get('tech', '')}")
        L.append(f"- 用户可见变化：{f.get('visible', '')}")
        L.append(f"- 影响范围：{f.get('scope', '')}")
        L.append(f"- 上线动作：{f.get('action', '')}")
        paths = _paths(f, mask)
        if paths:
            L.append(f"- 涉及文件：{'、'.join(paths)}")
        L.append("")

    L.append("## 四、破坏性变更与升级指引")
    L.append("")
    breaking = [f for f in features if f.get("breaking")]
    if breaking:
        for f in breaking:
            L.append(f"- **{f.get('title', '')}**：{f.get('biz', '')}（上线动作：{f.get('action', '')}）")
    else:
        L.append("本版本无破坏性变更。")
    L.append("")

    L.append("## 五、涉及模块与文件")
    L.append("")
    for m in meta.get("modules", []):
        L.append(f"- {m}")
    if not meta.get("modules"):
        L.append("- （无）")
    L.append("")

    L.append("## 六、验收清单")
    L.append("")
    for f in features:
        L.append(f"- [ ] {f.get('title', '')}：{f.get('acceptance', '')}")
    L.append("")

    L.append("## 七、上线操作步骤")
    L.append("")
    actions = [f"{f.get('title', '')}：{f.get('action', '')}"
               for f in features if f.get("action") and f.get("action") != "无需操作"]
    if actions:
        for i, a in enumerate(actions, start=1):
            L.append(f"{i}. {a}")
    else:
        L.append("无需额外操作。")
    L.append("")

    L.append("## 八、溯源说明")
    L.append("")
    L.append(f"- 运行 ID：`{meta['runId']}`（生成器：{GENERATOR_NAME}）")
    L.append(f"- 改写引擎：{llm.get('provider', '')} / {llm.get('model', '')}，提示词版本 {llm.get('prompt', '')}")
    L.append(f"- 输入 {llm.get('inputChars', 0)} 字符，输出 {llm.get('outputChars', 0)} 字符，"
             f"术语命中 {llm.get('glossaryHits', 0)} 处，置信度 {llm.get('confidence', 0)}")
    if result.get("lowConfidence"):
        L.append("- 需人工复核：")
        for item in result["lowConfidence"]:
            L.append(f"  - {item}")
    L.append(f"- 展示口径：{'技术视角' if tone == 'tech' else '业务视角'}"
             f"{'，已开启脱敏' if mask else ''}")
    L.append("")
    return "\n".join(L)


def render_trace(result: dict, opts: dict, sizes: dict | None = None) -> str:
    meta = result["meta"]
    llm = result.get("llm", {})
    mask = bool(opts.get("mask", False))
    sizes = sizes or {}
    data = {
        "traceVersion": "1.0",
        "runId": meta["runId"],
        "generator": GENERATOR_NAME,
        "generatedAt": meta["generatedAt"],
        "trigger": {"mode": "manual", "label": meta["trigger"]},
        "range": {
            "repo": meta["repoName"],
            "base": meta["range"].split("..")[0],
            "head": meta["range"].split("..")[-1],
            "branch": meta["branch"],
            "commit": _mask_commit(meta["headShort"]) if mask else meta["headShort"],
        },
        "pipeline": meta.get("pipeline", []),
        "llm": {
            "provider": llm.get("provider", ""),
            "model": llm.get("model", ""),
            "prompt": llm.get("prompt", ""),
            "inputChars": llm.get("inputChars", 0),
            "outputChars": llm.get("outputChars", 0),
            "glossaryHits": llm.get("glossaryHits", 0),
        },
        "confidence": llm.get("confidence", 0),
        "changes": meta.get("stats", {}),
        "modules": meta.get("modules", []),
        "features": [
            {"id": f"F{i}", "title": f.get("title", ""), "tag": f.get("tag", ""),
             "risk": f.get("risk", ""), "breaking": bool(f.get("breaking")),
             "paths": _paths(f, mask)}
            for i, f in enumerate(result.get("features", []), start=1)
        ],
        "contractSignals": _mask_signals(result.get("contractSignals", []), mask),
        "lowConfidence": result.get("lowConfidence", []),
        "artifacts": [
            {"kind": "checklist", "file": "checklist.csv", "bytes": sizes.get("checklist", 0)},
            {"kind": "document", "file": "product-doc.md", "bytes": sizes.get("document", 0)},
            {"kind": "trace", "file": "trace.json", "bytes": sizes.get("trace", 0)},
        ],
        "tone": opts.get("tone", "business"),
        "masked": mask,
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def render_trace_stable(result: dict, opts: dict,
                        base_sizes: dict | None = None, rounds: int = 3) -> tuple[str, dict]:
    """trace 内嵌自身字节数：两遍迭代到稳定（位数变化最多再迭代一次）。"""
    sizes = dict(base_sizes or {})
    sizes.setdefault("trace", 0)
    text = ""
    for _ in range(rounds):
        text = render_trace(result, opts, sizes)
        actual = len(text.encode("utf-8"))
        if actual == sizes["trace"]:
            break
        sizes["trace"] = actual
    return text, sizes
