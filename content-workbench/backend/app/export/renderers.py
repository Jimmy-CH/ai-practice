from html import escape


def render_markdown(kind: str, content: dict) -> str:
    if kind == "announcement":
        lines = [f"# {content['title']}", "", content["summary"], "", content["body"], "", "## 行动项"]
        lines += [f"- {action}" for action in content["actions"]]
        return "\n".join(lines)
    if kind == "faq":
        lines = ["# FAQ", ""]
        for item in content["items"]:
            lines += [f"## {item['question']}", item["answer"], ""]
        return "\n".join(lines)
    lines = [f"# {content['headline']}", "", content["subhead"], ""]
    lines += [f"- {point}" for point in content["selling_points"]]
    lines += ["", content["cta"]]
    return "\n".join(lines)


def render_html(kind: str, content: dict) -> str:
    if kind == "announcement":
        actions = "".join(f"<li>{escape(a)}</li>" for a in content["actions"])
        return f"<h1>{escape(content['title'])}</h1><p>{escape(content['summary'])}</p><p>{escape(content['body']).replace(chr(10), '<br>')}</p><h2>行动项</h2><ul>{actions}</ul>"
    if kind == "faq":
        items = "".join(f"<dt>{escape(i['question'])}</dt><dd>{escape(i['answer'])}</dd>" for i in content["items"])
        return f"<h1>FAQ</h1><dl>{items}</dl>"
    points = "".join(f"<li>{escape(p)}</li>" for p in content["selling_points"])
    return f"<div style='border:1px solid #ccc;padding:16px'><h1>{escape(content['headline'])}</h1><p>{escape(content['subhead'])}</p><ul>{points}</ul><p><strong>{escape(content['cta'])}</strong></p></div>"
