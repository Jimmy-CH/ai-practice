"""九节产品说明书确定性渲染（纯函数）：结构化 spec → Markdown。

tone 对说明书不再生效（固定技术口径）；mask 仅作用于模块/文件路径与提交哈希。
"""

import re

from app.services.renderers import GENERATOR_NAME, _mask_commit, _mask_path

_NFR_TITLES = [
    ("performance", "性能"),
    ("security", "安全"),
    ("reliability", "可靠性与容错"),
    ("deployment", "可用性与部署"),
    ("maintainability", "可维护性与可测试性"),
    ("extensibility", "可扩展性"),
    ("compatibility", "兼容性"),
]
_CARDINALITIES = {"||--o{", "||--||", "||--|{", "}o--o{", "}o--||",
                  "|o--o{", "|o--||", "||--o|", "}o--o|", "|o--o|"}


def _path_text(path: str, mask: bool) -> str:
    return _mask_path(path) if mask else path


def _cell(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", "<br>")


def _table(headers: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(_cell(c) for c in row) + " |")
    return out


def _ident(name: str) -> str:
    """mermaid 标识符：只保留 ASCII 字母数字下划线，数字开头补前缀。"""
    text = re.sub(r"[^0-9A-Za-z_]", "_", (name or "").strip())
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        return ""
    return "E_" + text if text[0].isdigit() else text


def _quote(text: str) -> str:
    return (text or "").replace('"', "'").replace("\n", " ").strip()


def _mermaid(lines: list[str], code: str) -> None:
    lines.append("```mermaid")
    lines.extend(code.splitlines())
    lines.append("```")


def _aggregate_entities(modules: list[dict]) -> list[dict]:
    """跨模块合并同名实体：字段按名称合并，关系去重。"""
    merged: dict[str, dict] = {}
    for module in modules:
        for entity in module.get("entities") or []:
            key = _ident(entity.get("name") or entity.get("table") or "")
            if not key:
                continue
            target = merged.setdefault(key, {"name": key, "table": "",
                                             "fields": {}, "relations": []})
            if not target["table"] and entity.get("table"):
                target["table"] = entity["table"]
            for field in entity.get("fields") or []:
                field_key = _ident(field.get("name") or "")
                if field_key and field_key not in target["fields"]:
                    target["fields"][field_key] = field
            for relation in entity.get("relations") or []:
                rel_target = _ident(relation.get("target") or "")
                if not rel_target:
                    continue
                cardinality = relation.get("cardinality")
                if cardinality not in _CARDINALITIES:
                    cardinality = "||--o{"
                item = (rel_target, _quote(relation.get("label", "")), cardinality)
                if item not in target["relations"]:
                    target["relations"].append(item)
    return list(merged.values())


def _er_diagram(entities: list[dict]) -> str:
    lines = ["erDiagram"]
    names = {entity["name"] for entity in entities}
    for entity in entities:
        for target, label, cardinality in entity["relations"]:
            if target not in names:
                continue
            suffix = f' : "{label}"' if label else ""
            lines.append(f"    {entity['name']} {cardinality} {target}{suffix}")
    for entity in entities:
        if not entity["fields"]:
            lines.append(f"    {entity['name']}")
            continue
        lines.append(f"    {entity['name']} {{")
        for field_name, field in entity["fields"].items():
            type_name = _ident(field.get("type") or "string") or "string"
            constraints = str(field.get("constraints") or "").upper()
            key = ""
            if "PK" in constraints:
                key = " PK"
            elif "FK" in constraints:
                key = " FK"
            elif "UK" in constraints:
                key = " UK"
            note = _quote(field.get("note", ""))
            lines.append(f'        {type_name} {field_name}{key} "{note}"')
        lines.append("    }")
    return "\n".join(lines)


def render_product_spec(result: dict, opts: dict) -> str:
    spec = result.get("spec") or {}
    meta = result.get("meta") or {}
    modules = spec.get("modules") or []
    overview = spec.get("overview") or {}
    architecture = spec.get("architecture") or {}
    snapshot = spec.get("snapshot") or {}
    mask = bool(opts.get("mask", False))
    stats = meta.get("stats") or {}

    def p(path: str) -> str:
        return _path_text(path, mask)

    lines: list[str] = []
    repo_name = meta.get("repoName") or overview.get("name") or "项目"
    lines.append(f"# {repo_name} 产品说明书（{meta.get('version', '')}）")
    lines.append("")
    commit = _mask_commit(meta.get("headShort", "")) if mask else meta.get("headShort", "")
    lines.append(f"> 基于 `{meta.get('range', '')}` 目标版本 `{commit}` 的代码快照自动生成 · "
                 f"{meta.get('generatedAt', '')} · {GENERATOR_NAME}")
    scope = (f"> 提示词版本 `{spec.get('prompt', '')}` · 覆盖 "
             f"{snapshot.get('modules', len(modules))} 个模块 / "
             f"{snapshot.get('files', 0)} 个源文件")
    if snapshot.get("skipped"):
        scope += f" · {snapshot['skipped']} 个模块未纳入自动分析"
    lines.append(scope)
    lines.append("")

    # 1. 项目概述
    lines.extend(["## 1. 项目概述", ""])
    lines.append(f"**项目名称**：{overview.get('name') or repo_name}")
    lines.append("")
    lines.append(f"**定位**：{overview.get('positioning') or '（未识别到明确的项目定位，建议人工补充）'}")
    lines.append("")
    problems = overview.get("problems") or []
    lines.append("**解决的问题**：")
    lines.extend([f"- {item}" for item in problems] or ["- （未识别）"])
    lines.append("")
    boundaries = overview.get("scope") or []
    lines.append("**使用边界**：")
    lines.extend([f"- {item}" for item in boundaries] or ["- （未识别）"])
    lines.append("")
    changed_modules = [m.get("name", "") for m in modules if m.get("changed")]
    changed_text = "、".join(p(name) for name in changed_modules) if changed_modules else "无"
    lines.append(f"**本版本范围**：`{meta.get('range', '')}`，{stats.get('commits', 0)} 个提交 · "
                 f"{stats.get('files', 0)} 个文件 · +{stats.get('added', 0)}/"
                 f"-{stats.get('removed', 0)} 行；变更模块：{changed_text}")
    lines.append("")

    # 2. 用户角色与使用场景
    lines.extend(["## 2. 用户角色与使用场景", ""])
    role_rows = [[role.get("role", ""), "；".join(role.get("scenarios") or [])]
                 for role in spec.get("roles") or [] if role.get("role")]
    if not role_rows:
        derived: dict[str, list[str]] = {}
        for module in modules:
            for fn in module.get("functions") or []:
                for role in fn.get("roles") or []:
                    scenes = derived.setdefault(role, [])
                    if fn.get("name") and fn["name"] not in scenes:
                        scenes.append(fn["name"])
        role_rows = [[role, "；".join(scenes[:5])] for role, scenes in derived.items()]
    if role_rows:
        lines.extend(_table(["角色", "使用场景"], role_rows))
    else:
        lines.append("（未识别到明确的用户角色）")
    lines.append("")

    # 3. 系统架构与技术栈
    lines.extend(["## 3. 系统架构与技术栈", "", "### 3.1 技术栈", ""])
    stack = architecture.get("stack") or []
    if stack:
        lines.extend(_table(["层级", "技术", "说明"],
                            [[item.get("layer", ""), item.get("tech", ""),
                              item.get("note", "")] for item in stack]))
    else:
        lines.append("（未识别到明确的技术栈）")
    lines.append("")
    lines.extend(["### 3.2 模块划分", ""])
    arch_modules = architecture.get("modules") or [
        {"name": module.get("name", ""), "responsibility": module.get("responsibility", "")}
        for module in modules]
    if arch_modules:
        lines.extend(_table(["模块", "职责"],
                            [[p(item.get("name", "")), item.get("responsibility", "")]
                             for item in arch_modules]))
    else:
        lines.append("（未识别到模块划分）")
    lines.append("")
    if architecture.get("diagram"):
        lines.extend(["### 3.3 架构图", ""])
        _mermaid(lines, architecture["diagram"])
        lines.append("")

    # 4. 功能清单及核心逻辑
    lines.extend(["## 4. 功能清单及核心逻辑", "",
                  "> 优先级口径：P0=核心链路；P1=重要辅助；P2=低频/边缘。", ""])
    number = 0
    sub = 0
    for module in modules:
        functions = module.get("functions") or []
        if not functions:
            continue
        sub += 1
        suffix = "（本次变更）" if module.get("changed") else ""
        if module.get("degraded"):
            suffix += "（自动解析降级）"
        lines.append(f"### 4.{sub} {p(module.get('name', ''))}{suffix}")
        lines.append("")
        rows = []
        for fn in functions:
            number += 1
            rows.append([str(number), fn.get("name", ""), fn.get("logic", ""),
                         "、".join(fn.get("roles") or []), fn.get("priority", "P1")])
        lines.extend(_table(["序号", "功能简介", "核心逻辑", "涉及角色", "优先级"], rows))
        lines.append("")
    if number == 0:
        lines.extend(["（未识别到明确的功能点）", ""])

    # 5. 核心流程
    lines.extend(["## 5. 核心流程（各模块流程图）", ""])
    sub = 0
    for module in modules:
        for flow in module.get("flows") or []:
            sub += 1
            lines.append(f"### 5.{sub} {flow.get('title', '核心流程')}"
                         f"（{p(module.get('name', ''))}）")
            lines.append("")
            _mermaid(lines, flow.get("mermaid", ""))
            lines.append("")
    if sub == 0:
        lines.extend(["（未识别到可绘制的核心流程）", ""])

    # 6. ER 图
    entities = _aggregate_entities(modules)
    lines.extend(["## 6. 领域实体关系图（ER 图）", ""])
    if entities:
        _mermaid(lines, _er_diagram(entities))
    else:
        lines.append("（未识别到领域实体）")
    lines.append("")

    # 7. 领域实体清单
    lines.extend(["## 7. 领域实体清单（分模块）", ""])
    sub = 0
    enum_rows: list[list] = []
    for module in modules:
        module_entities = module.get("entities") or []
        if module_entities:
            sub += 1
            lines.append(f"### 7.{sub} {p(module.get('name', ''))}")
            lines.append("")
            for entity in module_entities:
                headline = f"**{entity.get('name', '')}**"
                if entity.get("table"):
                    headline += f"（表 `{entity['table']}`）"
                lines.extend([headline, ""])
                fields = entity.get("fields") or []
                if fields:
                    lines.extend(_table(
                        ["字段", "类型", "约束/默认", "说明"],
                        [[field.get("name", ""), field.get("type", ""),
                          field.get("constraints", ""), field.get("note", "")]
                         for field in fields]))
                else:
                    lines.append("（未识别到字段定义）")
                lines.append("")
        for item in module.get("enums") or []:
            if item.get("name"):
                enum_rows.append([item["name"], " / ".join(item.get("values") or [])])
    if sub == 0 and not enum_rows:
        lines.extend(["（未识别到领域实体）", ""])
    if enum_rows:
        lines.append(f"### 7.{sub + 1} 枚举字典")
        lines.append("")
        lines.extend(_table(["枚举", "取值"], enum_rows))
        lines.append("")

    # 8. 详细规则说明
    lines.extend(["## 8. 详细规则说明", ""])
    sub = 0
    error_rows: list[list] = []
    for module in modules:
        rules = module.get("rules") or []
        if rules:
            sub += 1
            lines.append(f"### 8.{sub} {p(module.get('name', ''))}")
            lines.append("")
            for rule in rules:
                lines.append(f"**{rule.get('topic', '规则')}**")
                lines.append("")
                lines.extend([f"- {point}" for point in rule.get("points") or []])
                lines.append("")
        for item in module.get("errorCodes") or []:
            if item.get("scene") or item.get("code"):
                error_rows.append([item.get("scene", ""), item.get("code", ""),
                                   item.get("ui", "")])
    if sub == 0:
        lines.extend(["（未识别到明确的业务规则）", ""])
    if error_rows:
        lines.append(f"### 8.{sub + 1} 错误码矩阵")
        lines.append("")
        lines.extend(_table(["场景", "状态码", "前端表现"], error_rows))
        lines.append("")

    # 9. 非功能性需求
    lines.extend(["## 9. 非功能性需求", ""])
    sub = 0
    for key, title in _NFR_TITLES:
        items: list[str] = []
        for module in modules:
            for item in (module.get("nfr") or {}).get(key) or []:
                text = str(item).strip()
                if text and text not in items:
                    items.append(text)
        if not items:
            continue
        sub += 1
        lines.extend([f"### 9.{sub} {title}", ""])
        lines.extend([f"- {item}" for item in items])
        lines.append("")
    if sub == 0:
        lines.extend(["（未识别到明确的非功能性约束，建议人工补充）", ""])

    # 附录：代码依据与待复核项
    lines.extend(["## 附录：代码依据", ""])
    rows = [[p(module.get("name", "")),
             "、".join(p(path) for path in (module.get("files") or [])[:8])]
            for module in modules]
    if rows:
        lines.extend(_table(["模块", "关键文件"], rows))
    else:
        lines.append("（无）")
    lines.append("")
    review: list[str] = []
    for item in spec.get("lowConfidence") or []:
        text = str(item)
        if mask:
            # 复核项里带模块名时与正文保持一致脱敏
            for module in modules:
                name = module.get("name") or ""
                if name:
                    text = text.replace(name, p(name))
        review.append(text)
    for module in modules:
        if module.get("degraded"):
            review.append(f"{p(module.get('name', ''))}：产品画像生成失败，"
                          "功能/流程/实体待人工复核")
    if review:
        lines.append("**待人工复核**：")
        lines.append("")
        lines.extend([f"- {item}" for item in dict.fromkeys(review)])
        lines.append("")

    return "\n".join(lines)
