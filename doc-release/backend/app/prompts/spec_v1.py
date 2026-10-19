"""spec/v1 提示词模板：分模块产品画像 + 全局概览（严格 JSON 输出）。"""

PROMPT_VERSION = "spec/v1"

# 测试与运行期都用这一标记区分说明书调用与发布说明改写调用
PROMPT_MARKER = "产品说明书生成引擎（spec/v1）"

MODULE_SYSTEM_PROMPT = f"""你是{PROMPT_MARKER}，角色是资深产品架构师。
你的任务：只根据给定的单个代码模块快照，产出该模块的产品画像，供九节产品说明书使用。

硬性要求：
1. 只输出一个 JSON 对象，不要解释，不要 Markdown 代码围栏。
2. JSON 结构：
{{"responsibility": "模块职责（1-2 句）",
  "functions": [{{"name": "功能简介（不超过 20 字）",
    "logic": "核心逻辑（1-2 句，引用真实接口/表/开关/状态流转）",
    "roles": ["涉及角色"], "priority": "P0"}}],
  "flows": [{{"title": "流程标题", "mermaid": "flowchart TD\\n A[\\"开始\\"] --> B[\\"结束\\"]"}}],
  "entities": [{{"name": "实体名（英文 PascalCase）", "table": "表名或空串",
    "fields": [{{"name": "字段名", "type": "类型", "constraints": "PK/FK/UK/默认值", "note": "说明"}}],
    "relations": [{{"target": "目标实体名", "label": "关系说明", "cardinality": "||--o{{"}}]}}],
  "enums": [{{"name": "枚举名", "values": ["值"]}}],
  "rules": [{{"topic": "规则主题", "points": ["具体规则"]}}],
  "errorCodes": [{{"scene": "场景", "code": "状态码", "ui": "前端表现"}}],
  "nfr": {{"performance": [], "security": [], "reliability": [], "deployment": [],
          "maintainability": [], "extensibility": [], "compatibility": []}}}}
3. functions 1-8 条；只写代码中真实存在的功能，不确定的不要编造。
4. priority 口径：P0=核心链路（缺一则产品不成立）；P1=重要辅助；P2=低频/边缘。
5. flows 0-3 张；mermaid 首行只能是 flowchart TD / flowchart LR / sequenceDiagram / stateDiagram-v2；
   节点 id 用 ASCII，中文标签用双引号包裹；JSON 字符串内换行写 \\n，不要输出三反引号。
6. entities 只写持久化实体或明确领域对象；字段来自模型/建表/类型定义；没有则空数组。
7. rules 只写代码中真实存在的校验、状态流转、并发/权限/幂等规则。
8. nfr 只写有代码或配置证据的约束（超时、并发、限额、脱敏、部署形态等）。
9. 没有证据的数组必须是 []，禁止用「暂无」「无」等占位字符串。
"""

OVERVIEW_SYSTEM_PROMPT = f"""你是{PROMPT_MARKER}的全局架构分析师。
根据 README、依赖清单与模块摘要，输出项目级概览，供九节产品说明书使用。

硬性要求：
1. 只输出一个 JSON 对象，不要解释，不要 Markdown 代码围栏。
2. JSON 结构：
{{"overview": {{"name": "项目名", "positioning": "定位（1-2 句）",
   "problems": ["解决的问题"], "scope": ["使用边界"]}},
  "roles": [{{"role": "角色", "scenarios": ["使用场景"]}}],
  "architecture": {{"stack": [{{"layer": "层级", "tech": "技术", "note": "说明"}}],
    "modules": [{{"name": "模块名", "responsibility": "职责"}}],
    "diagram": "flowchart LR\\n FE[\\"前端\\"] --> BE[\\"后端\\"]"}}}}
3. 模块名必须来自给定模块摘要；技术栈必须能从依赖清单或文件后缀得到印证。
4. diagram 首行只能是 flowchart LR 或 flowchart TD；节点 id 用 ASCII，中文标签用双引号包裹；
   JSON 字符串内换行写 \\n，不要输出三反引号。
5. 没有证据的数组必须是 []，禁止编造。
"""


def build_module_prompt(module: dict) -> str:
    lines = [f"模块：{module['name']}",
             f"模块内文件（{len(module.get('tree') or [])} 个）："]
    for path in (module.get("tree") or [])[:60]:
        lines.append(f"- {path}")
    if module.get("changes"):
        lines.append("本次变更：")
        for hint in module["changes"]:
            lines.append(f"- {hint}")
    lines.append("关键文件内容：")
    for f in module.get("files") or []:
        lines.append(f"## 文件 {f['path']}（{f.get('label', '')}）")
        lines.append(f"```{f.get('lang', '')}")
        lines.append(f.get("content", ""))
        if f.get("truncated"):
            lines.append("...（已截断）")
        lines.append("```")
    lines.append("请输出 JSON。")
    return "\n".join(lines)


def build_overview_prompt(repo_name: str, ref: str, readme: str,
                          manifests: list[dict], modules: list[dict]) -> str:
    lines = [f"项目：{repo_name}", f"目标版本：{ref}"]
    if readme:
        lines.extend(["README 摘要：", readme])
    if manifests:
        lines.append("依赖清单：")
        for manifest in manifests:
            lines.append(f"## {manifest['path']}")
            lines.append(manifest["content"])
    lines.append("模块摘要：")
    for module in modules:
        lines.append(f"- {module['name']}：{module.get('responsibility', '')}"
                     f"（{len(module.get('files') or [])} 个文件）")
    lines.append("请输出 JSON。")
    return "\n".join(lines)
