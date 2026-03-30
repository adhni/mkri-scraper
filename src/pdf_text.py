from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PdfText:
    text: str
    page_count: int
    engine: str = "pypdf"


def extract_pdf_text(pdf_path: str | Path) -> PdfText:
    PdfReader = None
    try:
        from pypdf import PdfReader as _PdfReader

        PdfReader = _PdfReader
    except ModuleNotFoundError:
        try:
            from PyPDF2 import PdfReader as _PdfReader

            PdfReader = _PdfReader
        except ModuleNotFoundError as exc:  # pragma: no cover - environment specific.
            raise RuntimeError(
                "A PDF reader library is required. Install pypdf or PyPDF2 before parsing PDF files."
            ) from exc

    path = Path(pdf_path)
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages.append(page_text)
    return PdfText(text="\n\n".join(pages), page_count=len(reader.pages))
