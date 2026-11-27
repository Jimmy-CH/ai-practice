from pathlib import Path

import pytest

from app.ingestion.pdf_parser import PdfParseError, PdfParser

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_parse_sample_pdf():
    pages = PdfParser().parse_bytes(FIXTURE.read_bytes())
    assert len(pages) >= 1
    assert pages[0].page == 1
    assert "Retrieval" in pages[0].text


def test_invalid_pdf_raises():
    with pytest.raises(PdfParseError):
        PdfParser().parse_bytes(b"not a pdf")
