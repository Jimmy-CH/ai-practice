from app.services.retrieval import select_evidence, split_and_rank


def test_split_blank_lines_and_sentences():
    text = "智能报表支持拖拽分析。\n\n另外还支持导出 Excel 文件！"
    pieces = split_and_rank(text, "s1", ["智能报表"])
    assert {p.text for p in pieces} == {"智能报表支持拖拽分析。", "另外还支持导出 Excel 文件！"}


def test_short_noise_dropped():
    pieces = split_and_rank("好的。好的。", "s1", ["x"])
    assert pieces == []


def test_score_counts_keyword_hits_and_orders():
    text = "智能报表 2.0 支持拖拽分析，智能报表还能定时推送。"
    pieces = split_and_rank(text, "s1", ["智能报表", "拖拽"])
    assert pieces[0].score == 2


def test_select_dedup_orders_and_filters_zero():
    sources = [("s1", "智能报表支持导出。"), ("s2", "智能报表支持导出。无关键词段落。"), ("s3", "完全无关的内容。")]
    evidence = select_evidence(sources, ["智能报表", "导出"], top_k=2)
    assert len(evidence) == 1 and evidence[0].source_id in {"s1", "s2"}


def test_select_returns_top_k():
    sources = [("s1", "A关键词。B关键词。C关键词。"), ("s2", "D关键词。")]
    evidence = select_evidence(sources, ["A关键词", "B关键词", "C关键词", "D关键词"], top_k=2)
    assert len(evidence) == 2 and evidence[0].score == 1
