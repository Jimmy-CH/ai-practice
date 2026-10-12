from app.services.retrieval import split_and_rank


def test_select_evidence_prefers_theme_terms() -> None:
    chunks = split_and_rank("搜索功能上线。\n\n公司团建通知。", ["搜索"])

    assert chunks[0].text == "搜索功能上线。"
