import io
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfParseError(Exception):
    """PDF 无法读取、加密或结构损坏。"""


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


class PdfParser:
    """使用 pypdf 逐页提取文本，页码从 1 开始。"""

    def parse_bytes(self, data: bytes) -> list[PageText]:
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted and not reader.decrypt(""):
                raise PdfParseError("PDF 已加密，无法解析")
            pages: list[PageText] = []
            for index, page in enumerate(reader.pages, start=1):
                pages.append(PageText(page=index, text=(page.extract_text() or "").strip()))
            return pages
        except PdfParseError:
            raise
        except PdfReadError as exc:
            raise PdfParseError(f"PDF 解析失败: {exc}") from exc
        except Exception as exc:
            raise PdfParseError(f"PDF 解析失败: {exc}") from exc
