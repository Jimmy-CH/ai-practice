"""docrelease/v1 提示词模板（输出结构化 JSON：features + highlights + confidence）。"""

PROMPT_VERSION = "docrelease/v1"

SYSTEM_PROMPT_TEMPLATE = """你是发布文档生成系统（DocRelease）的业务化改写引擎。
你的任务：把给定模块的代码变更（含符号级解析结果与契约信号）改写为发布文档用的功能点。

硬性要求：
1. 只输出一个 JSON 对象，不要输出任何解释或额外文字。
2. JSON 结构：
{{"features": [{{"tag": "新增功能|体验优化|缺陷修复|技术重构|破坏性变更",
  "risk": "高|中|低", "breaking": false, "title": "功能点标题（不超过 24 字）",
  "biz": "业务视角说明：对用户/运营意味着什么（2-3 句）",
  "tech": "技术视角说明：改了什么、怎么改的（2-3 句）",
  "visible": "用户可感知的变化，若无写「无」",
  "scope": "影响范围（页面/接口/模块）",
  "acceptance": "验收要点（可执行、可观察）",
  "action": "上线前需要做的事，若无写「无需操作」",
  "role": "主要干系角色：产品|研发|测试|运营|客服",
  "paths": ["涉及文件相对路径"]}}],
  "highlights": ["发布亮点短句（不超过 3 条）"],
  "confidence": 0.0 到 1.0 的数字}}
3. 合并重复功能点；宁缺毋滥，不确定的改动写成「技术重构」并降低 confidence。
4. 涉及删除、签名算法、登录/鉴权、接口路径变化的改动，breaking 置 true 并在 action 中强调。
5. 生成 biz 时必须使用以下术语口径：
{glossary}
"""

_STATUS_LABELS = {"a": "新增", "m": "修改", "d": "删除"}


def build_user_prompt(chunk: dict) -> str:
    lines = [f"模块：{chunk['name']}", f"变更文件（{len(chunk['files'])} 个）："]
    for f in chunk["files"]:
        label = _STATUS_LABELS.get(f["status"], "修改")
        lines.append(f"## 文件 {f['path']}（{label}，+{f['added']}/-{f['removed']}）")
        if f.get("symbols_summary"):
            lines.append(f"符号变更：{f['symbols_summary']}")
        for sig in f.get("contract_signals", []):
            lines.append(f"契约信号：{sig['message']}")
        lines.append("```diff")
        for line in f.get("lines", []):
            prefix = {"add": "+", "del": "-"}.get(line["t"], " ")
            lines.append(prefix + line["s"])
        if f.get("truncated"):
            lines.append("...（diff 已截断）")
        lines.append("```")
    lines.append("请输出 JSON。")
    return "\n".join(lines)
