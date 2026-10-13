from app.export.renderers import render_html, render_markdown


def test_render_announcement():
    content = {"title": "T", "summary": "S", "body": "B", "actions": ["A1"]}
    assert "# T" in render_markdown("announcement", content)
    assert "<h1>T</h1>" in render_html("announcement", content)


def test_render_faq():
    content = {"items": [{"question": "Q", "answer": "A"}]}
    assert "Q" in render_markdown("faq", content)
    assert "<dt>Q</dt>" in render_html("faq", content)


def test_render_poster():
    content = {"headline": "H", "subhead": "S", "selling_points": ["P"], "cta": "C"}
    assert "H" in render_markdown("poster", content)
    assert "H</h1>" in render_html("poster", content)
