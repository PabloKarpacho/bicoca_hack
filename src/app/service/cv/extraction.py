import asyncio
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


class TextExtractionError(RuntimeError):
    pass


async def extract_text(*, filename: str, data: bytes) -> tuple[str, str]:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        return await asyncio.to_thread(_extract_pdf, data)
    if extension == ".docx":
        return await asyncio.to_thread(_extract_docx, data)
    raise TextExtractionError(f"Unsupported file type: {extension.lstrip('.')}")

def _extract_pdf(data: bytes) -> tuple[str, str]:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise TextExtractionError("PDF extraction dependency is not installed") from exc

    reader = PdfReader(BytesIO(data))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text:
            text_parts.append(page_text.strip())
    raw_text = "\n\n".join(part for part in text_parts if part).strip()
    return raw_text, "pypdf"


def _extract_docx(data: bytes) -> tuple[str, str]:
    try:
        with ZipFile(BytesIO(data)) as archive:
            xml_bytes = archive.read("word/document.xml")
    except Exception as exc:
        raise TextExtractionError("Invalid DOCX file") from exc

    root = ElementTree.fromstring(xml_bytes)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        text_nodes = [
            node.text or "" for node in paragraph.findall(".//w:t", namespace)
        ]
        joined = "".join(text_nodes).strip()
        if joined:
            paragraphs.append(joined)
    raw_text = "\n".join(paragraphs).strip()
    return raw_text, "docx-xml"
