"""
File parser — extract text from .txt, .md, .pdf, .docx files.
"""
from pathlib import Path


def parse_file(file_path: str) -> str:
    """
    Parse a file and return its text content.
    Supports: .txt, .md, .pdf, .docx
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _parse_pdf(file_path)
    elif suffix == ".docx":
        return _parse_docx(file_path)
    elif suffix in (".txt", ".md", ""):
        return _parse_text(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")


def _parse_text(file_path: str) -> str:
    with open(file_path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _parse_pdf(file_path: str) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")
    text_parts = []
    with fitz.open(file_path) as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n\n".join(text_parts)


def _parse_docx(file_path: str) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError("请安装 python-docx: pip install python-docx")
    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)
