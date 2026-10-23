"""Document ingestion: PDF/scanned text -> (pages of text).

PyMuPDF is optional; the MVP can ingest plain text already in hand. For scanned
documents we call an OCR engine through the OcrEngine seam - left unimplemented
so the pipeline stays laptop-runnable without heavy deps, but the seam is real.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ExtractedPage:
    page: int
    text: str


class OcrEngine(Protocol):
    def recognize(self, image_bytes: bytes) -> str: ...


def pdf_to_pages(path: str) -> list[ExtractedPage]:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyMuPDF not installed; use text ingestion or add pymupdf") from exc

    pages: list[ExtractedPage] = []
    with fitz.open(path) as doc:
        for i, page in enumerate(doc):
            pages.append(ExtractedPage(page=i + 1, text=page.get_text()))
    return pages


def text_to_pages(raw: str) -> list[ExtractedPage]:
    # Single "page" for already-digitized text.
    return [ExtractedPage(page=1, text=raw)]
