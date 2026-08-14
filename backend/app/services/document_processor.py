import os
import re
from pathlib import Path
from typing import List, Optional

import fitz
from docx import Document as DocxDocument
from openpyxl import load_workbook
from pptx import Presentation


SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".xlsx": "xlsx",
    ".pptx": "pptx",
}


def clean_extracted_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def extract_pdf_text(file_path: str) -> str:
    doc = fitz.open(file_path)
    chunks = []
    for page in doc:
        text = page.get_text("text")
        if text:
            chunks.append(text)
    doc.close()
    return clean_extracted_text("\n\n".join(chunks))


def extract_docx_text(file_path: str) -> str:
    document = DocxDocument(file_path)
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    return clean_extracted_text("\n".join(paragraphs))


def extract_txt_text(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="replace") as file:
        return clean_extracted_text(file.read())


def extract_xlsx_text(file_path: str) -> str:
    workbook = load_workbook(file_path, read_only=True, data_only=True)
    sheet_text = []
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(values_only=True):
            values = [str(v).strip() for v in row if v is not None and str(v).strip()]
            if values:
                sheet_text.append(" | ".join(values))
    workbook.close()
    return clean_extracted_text("\n".join(sheet_text))


def extract_pptx_text(file_path: str) -> str:
    presentation = Presentation(file_path)
    slide_text = []
    for slide in presentation.slides:
        texts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                texts.append(shape.text)
        if texts:
            slide_text.append("\n".join(texts))
    return clean_extracted_text("\n\n".join(slide_text))


def extract_text_by_file_type(file_path: str, file_type: str) -> str:
    type_map = {
        "pdf": extract_pdf_text,
        "docx": extract_docx_text,
        "txt": extract_txt_text,
        "xlsx": extract_xlsx_text,
        "pptx": extract_pptx_text,
    }
    handler = type_map.get(file_type)
    if not handler:
        raise ValueError(f"Unsupported file type for processing: {file_type}")
    return handler(file_path)


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks
