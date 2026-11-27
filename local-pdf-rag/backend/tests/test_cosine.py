import pytest

from app.ingestion.chunker import cosine_similarity


def test_cosine_basic_values():
    assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)


def test_zero_vector_returns_zero():
    assert cosine_similarity([0, 0], [1, 0]) == 0.0


def test_dimension_mismatch():
    with pytest.raises(ValueError):
        cosine_similarity([1, 0], [1, 0, 0])
