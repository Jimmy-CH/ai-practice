"""tree-sitter 符号级解析：导出符号对比与契约信号提取。

支持 .ts/.tsx/.go/.py；未知语言或解析异常时降级为文件级信号（degraded=True）。
"""

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from tree_sitter_language_pack import get_parser

LANG_BY_EXT = {".ts": "typescript", ".tsx": "tsx", ".go": "go", ".py": "python"}

_ROUTE_PATTERN = re.compile(r"(?:GET|POST|PUT|DELETE|PATCH)\s+(/v\d[\w/{}\-\.]*)|(/v\d[\w/{}\-\.]*)")


@dataclass
class Symbol:
    name: str
    kind: str                 # function / class / interface / type / const / func / method / var
    signature: str            # 规范化的首行文本
    value: str | None = None  # 字面值文本（仅 const/var）


def detect_language(path: str) -> str | None:
    return LANG_BY_EXT.get(Path(path).suffix.lower())


def _first_line(node) -> str:
    return node.text.decode("utf-8", errors="replace").split("\n")[0]


def _norm(line: str) -> str:
    return " ".join(line.split())


def _name_text(node) -> str | None:
    n = node.child_by_field_name("name")
    return n.text.decode("utf-8", errors="replace") if n is not None else None


def _extract_ts(node) -> list[Symbol]:
    out: list[Symbol] = []
    if node.type != "export_statement":
        return out
    for child in node.children:
        if child.type in ("function_declaration", "class_declaration",
                          "interface_declaration", "type_alias_declaration"):
            name = _name_text(child)
            if name:
                kind = {"function_declaration": "function", "class_declaration": "class",
                        "interface_declaration": "interface", "type_alias_declaration": "type"}[child.type]
                out.append(Symbol(name, kind, _norm(_first_line(child))))
        elif child.type == "lexical_declaration":
            for decl in child.children:
                if decl.type != "variable_declarator":
                    continue
                name = _name_text(decl)
                if not name:
                    continue
                value_node = decl.child_by_field_name("value")
                value = _norm(_first_line(value_node)) if value_node is not None else None
                out.append(Symbol(name, "const", _norm(_first_line(decl)), value))
    return out


def _is_exported(name: str) -> bool:
    return bool(name) and name[0].isupper()


def _extract_go(node) -> list[Symbol]:
    out: list[Symbol] = []
    if node.type in ("function_declaration", "method_declaration"):
        name = _name_text(node)
        if name and _is_exported(name):
            out.append(Symbol(name, "func" if node.type == "function_declaration" else "method",
                              _norm(_first_line(node))))
    elif node.type == "type_declaration":
        for spec in node.children:
            if spec.type == "type_spec":
                name = _name_text(spec)
                if name and _is_exported(name):
                    out.append(Symbol(name, "type", _norm(_first_line(spec))))
    elif node.type in ("const_declaration", "var_declaration"):
        for spec in node.children:
            if spec.type in ("const_spec", "var_spec"):
                name = _name_text(spec)
                if not name or not _is_exported(name):
                    continue
                value_node = spec.child_by_field_name("value")
                value = _norm(_first_line(value_node)) if value_node is not None else None
                out.append(Symbol(name, "const" if spec.type == "const_spec" else "var",
                                  _norm(_first_line(spec)), value))
    return out


def _extract_py(node) -> list[Symbol]:
    out: list[Symbol] = []
    if node.type in ("function_definition", "class_definition"):
        name = _name_text(node)
        if name:
            kind = "function" if node.type == "function_definition" else "class"
            out.append(Symbol(name, kind, _norm(_first_line(node))))
    elif node.type == "expression_statement":
        for child in node.children:
            if child.type != "assignment":
                continue
            left = child.child_by_field_name("left")
            right = child.child_by_field_name("right")
            if left is None or left.type != "identifier":
                continue
            name = left.text.decode("utf-8", errors="replace")
            if not name.isupper():
                continue
            value = _norm(_first_line(right)) if right is not None else None
            out.append(Symbol(name, "const", _norm(_first_line(child)), value))
    return out


def extract_symbols(source: str, lang: str) -> list[Symbol]:
    parser = get_parser(lang)
    tree = parser.parse(source.encode("utf-8"))
    out: list[Symbol] = []
    for node in tree.root_node.children:
        if lang in ("typescript", "tsx"):
            out.extend(_extract_ts(node))
        elif lang == "go":
            out.extend(_extract_go(node))
        elif lang == "python":
            out.extend(_extract_py(node))
    return out


def compare_symbols(base: list[Symbol], head: list[Symbol]) -> dict:
    base_map = {s.name: s for s in base}
    head_map = {s.name: s for s in head}
    added = [s for n, s in head_map.items() if n not in base_map]
    removed = [s for n, s in base_map.items() if n not in head_map]
    changed = []
    for name, bs in base_map.items():
        hs = head_map.get(name)
        if hs is not None and bs.signature != hs.signature:
            changed.append({"name": name, "kind": hs.kind, "before": bs.signature, "after": hs.signature,
                            "value_before": bs.value, "value_after": hs.value})
    return {"added": [asdict(s) for s in added], "removed": [asdict(s) for s in removed], "changed": changed}


def detect_contract_signals(path: str, symbols: dict) -> list[dict]:
    signals: list[dict] = []
    for c in symbols["changed"]:
        if (c["kind"] == "const" and c["value_before"] and c["value_after"]
                and c["value_before"] != c["value_after"]):
            signals.append({"kind": "const_change", "path": path,
                            "message": f"常量 {c['name']} 由 {c['value_before']} 变为 {c['value_after']}"})
    for s in symbols["removed"]:
        signals.append({"kind": "symbol_removed", "path": path,
                        "message": f"导出符号 {s['name']}（{s['kind']}）已删除"})
    return signals


def detect_route_signals(path: str, lines: list[dict]) -> list[dict]:
    added_routes: set[str] = set()
    removed_routes: set[str] = set()
    for line in lines:
        if line["t"] not in ("add", "del"):
            continue
        bucket = added_routes if line["t"] == "add" else removed_routes
        for m in _ROUTE_PATTERN.finditer(line["s"]):
            bucket.add(m.group(1) or m.group(2))
    signals = []
    for r in sorted(removed_routes - added_routes):
        signals.append({"kind": "route_removed", "path": path, "message": f"接口路径 {r} 已移除或变更"})
    for r in sorted(added_routes - removed_routes):
        signals.append({"kind": "route_added", "path": path, "message": f"新增接口路径 {r}"})
    return signals


def parse_file_pair(path: str, base_src: str, head_src: str, diff_lines: list[dict]) -> dict:
    """解析一对文件（基线/头版）并输出符号对比与契约信号；失败时降级。"""
    lang = detect_language(path)
    result = {
        "language": lang,
        "degraded": False,
        "symbols": {"added": [], "removed": [], "changed": []},
        "contract_signals": detect_route_signals(path, diff_lines),
    }
    if lang is None:
        result["degraded"] = True
        return result
    try:
        base_symbols = extract_symbols(base_src, lang) if base_src else []
        head_symbols = extract_symbols(head_src, lang) if head_src else []
        symbols = compare_symbols(base_symbols, head_symbols)
        result["symbols"] = symbols
        result["contract_signals"].extend(detect_contract_signals(path, symbols))
    except Exception:  # noqa: BLE001 —— 任何解析异常均降级为文件级信号
        result["degraded"] = True
    return result
