from seed_data import SCENARIOS, SEED_SEQUENCE


def test_sequence_structure():
    assert SEED_SEQUENCE[0]["kind"] == "commit"
    tags = [s["name"] for s in SEED_SEQUENCE if s["kind"] == "tag"]
    assert tags == ["v2.13.3", "v2.13.4", "v2.14.0", "v3.0.0"]


def test_scenarios_cover_all_tags():
    tags = {s["name"] for s in SEED_SEQUENCE if s["kind"] == "tag"}
    assert {sc["id"] for sc in SCENARIOS} == {"patch", "feature", "major"}
    for sc in SCENARIOS:
        assert sc["base"] in tags and sc["head"] in tags


def test_all_file_contents_non_empty():
    for step in SEED_SEQUENCE:
        if step["kind"] != "commit":
            continue
        assert step["files"], step["message"]
        for path, content in step["files"].items():
            assert content.strip(), f"{path} 内容为空"
