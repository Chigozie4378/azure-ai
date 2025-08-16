from pathlib import Path
from typing import Tuple
from pypdf import PdfReader
from docx import Document

def load_text(path: str) -> Tuple[str, str]:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        txt = []
        r = PdfReader(p)
        for page in r.pages:
            txt.append(page.extract_text() or "")
        return "\n".join(txt), p.name
    if ext in {".docx"}:
        doc = Document(p)
        return "\n".join(par.text for par in doc.paragraphs), p.name
    # .txt, .md fallback
    return p.read_text(encoding="utf-8", errors="ignore"), p.name
