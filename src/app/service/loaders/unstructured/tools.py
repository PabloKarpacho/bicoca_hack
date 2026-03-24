from typing import Any, List
from langchain_core.documents import Document
from loguru import logger


async def parse_to_markdown(
    documents: List[Document],
    page_break_placeholder: str = "<!-- page break -->",
    image_placeholder: str = "<!-- image -->",
) -> str:
    res: list[str] = []

    last_idx = len(documents) - 1
    for idx, item in enumerate(documents):
        metadata = item.metadata or {}
        cat = metadata.get("category")
        text = (item.page_content or "").strip()

        if not text and cat != "PageBreak":
            continue

        # Title
        if cat in {"Title"}:
            res.append(f"# {text}\n")

        # Plain text
        elif cat in {"NarrativeText", "UncategorizedText", "Address", "EmailAddress"}:
            res.append(f"{text}\n")

        # Lists
        elif cat in {"ListItem"}:
            res.append(f"- {text}\n")

        # Code
        elif cat in {"CodeSnippet"}:
            res.append(f"```text\n{text}\n```\n")

        # Tables
        elif cat in {"Table"}:
            res.append(f"```text\n{text}\n```\n")

        # Formulas
        elif cat in {"Formula"}:
            if "\n" in text:
                res.append(f"$$\n{text}\n$$\n")
            else:
                res.append(f"${text}$\n")

        # Images
        elif cat in {"Image"}:
            res.append(f"{image_placeholder}\n")

        # FigureCaption
        elif cat in {"FigureCaption"}:
            res.append(f"*{text}*\n")

        # PageBreak
        elif cat == "PageBreak" and idx != last_idx:  # избегаем лишний брейк в конце
            res.append(f"{page_break_placeholder}\n\n")

        # Fallback: просто текст
        else:
            res.append(f"{text}\n")

    # Склеиваем и чуть нормализуем пустые строки
    out = "".join(s.rstrip() for s in res).strip()
    return out
