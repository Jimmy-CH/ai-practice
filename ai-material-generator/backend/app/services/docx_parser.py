from pathlib import Path
from docx import Document


def parse_docx_file(path: Path | str) -> str:
    doc = Document(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)
