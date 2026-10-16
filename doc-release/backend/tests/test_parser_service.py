from app.services import parser_service as ps


def test_extract_ts_export_symbols():
    src = (
        "export const A = 7;\n"
        "export function f(a: number) { return a; }\n"
        "export interface I { x: number }\n"
        "export type T = string;\n"
    )
    syms = {s.name: s for s in ps.extract_symbols(src, "typescript")}
    assert syms["A"].kind == "const" and syms["A"].value == "7"
    assert syms["f"].kind == "function"
    assert syms["I"].kind == "interface"
    assert syms["T"].kind == "type"


def test_extract_go_exported_only():
    src = (
        "package p\n\n"
        "func Exported() {}\n"
        "func hidden() {}\n\n"
        "const MaxRows = 500\n\n"
        "func (s *S) ExportedMethod() {}\n"
    )
    names = {s.name for s in ps.extract_symbols(src, "go")}
    assert names == {"Exported", "MaxRows", "ExportedMethod"}
    by_name = {s.name: s for s in ps.extract_symbols(src, "go")}
    assert by_name["MaxRows"].kind == "const" and by_name["MaxRows"].value == "500"


def test_extract_python_symbols():
    src = "MAX_N = 5\n\n\ndef do():\n    pass\n\n\nclass Big:\n    pass\n"
    syms = {s.name: s for s in ps.extract_symbols(src, "python")}
    assert syms["MAX_N"].kind == "const" and syms["MAX_N"].value == "5"
    assert syms["do"].kind == "function" and syms["Big"].kind == "class"


def test_compare_and_const_change_signal():
    base = ps.extract_symbols("export const W = 7;\n", "typescript")
    head = ps.extract_symbols("export const W = 15;\n", "typescript")
    diff = ps.compare_symbols(base, head)
    assert len(diff["changed"]) == 1
    signals = ps.detect_contract_signals("p.ts", diff)
    assert any(s["kind"] == "const_change" and "7" in s["message"] and "15" in s["message"] for s in signals)


def test_symbol_removed_signal():
    base = ps.extract_symbols("export function gone() {}\nexport function kept() {}\n", "typescript")
    head = ps.extract_symbols("export function kept() {}\n", "typescript")
    signals = ps.detect_contract_signals("p.ts", ps.compare_symbols(base, head))
    assert any(s["kind"] == "symbol_removed" and "gone" in s["message"] for s in signals)


def test_degraded_for_unknown_language():
    result = ps.parse_file_pair("a.rb", "def x; end", "def y; end", [])
    assert result["degraded"] is True and result["language"] is None


def test_route_signals_from_diff_lines():
    lines = [
        {"t": "del", "s": "// CreateOrderV1 老版下单接口（POST /v1/order/create）"},
        {"t": "add", "s": "// 存量客户端请迁移至 POST /v2/orders"},
    ]
    signals = ps.detect_route_signals("api/legacy/order.go", lines)
    assert any(s["kind"] == "route_removed" and "/v1/order/create" in s["message"] for s in signals)
    assert any(s["kind"] == "route_added" and "/v2/orders" in s["message"] for s in signals)


def test_parse_file_pair_tsx_real_pair():
    base = "export function PriceBlock(props) {\n  return <div>{props.price}</div>;\n}\n"
    head = base + "\nexport const LABEL = \"到手价\";\n"
    result = ps.parse_file_pair("src/price.tsx", base, head, [])
    assert result["degraded"] is False
    assert [s["name"] for s in result["symbols"]["added"]] == ["LABEL"]
