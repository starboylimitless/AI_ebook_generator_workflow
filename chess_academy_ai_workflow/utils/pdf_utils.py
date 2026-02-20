from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from pypdf import PdfReader


@dataclass
class PageText:
    page_number: int
    text: str


@dataclass
class ReferenceLayoutInfo:
    page_width: float
    page_height: float
    page_count: int


def ensure_directories() -> Dict[str, Path]:
    base_dir = Path(__file__).resolve().parent.parent
    input_dir = base_dir / "input_docs"
    output_dir = base_dir / "output"
    agents_dir = base_dir / "agents"
    workflows_dir = base_dir / "workflows"
    prompts_dir = base_dir / "prompts"
    utils_dir = base_dir / "utils"

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)
    workflows_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    utils_dir.mkdir(parents=True, exist_ok=True)

    return {
        "base": base_dir,
        "input": input_dir,
        "output": output_dir,
        "agents": agents_dir,
        "workflows": workflows_dir,
        "prompts": prompts_dir,
        "utils": utils_dir,
    }


def check_input_files(input_dir: Path) -> Dict[str, Path]:
    ebook_ads = input_dir / "ebook_ads.pdf"
    next_move_reference = input_dir / "next_move_reference.pdf"

    missing: List[str] = []
    if not ebook_ads.exists():
        missing.append(str(ebook_ads))
    if not next_move_reference.exists():
        missing.append(str(next_move_reference))

    if missing:
        raise FileNotFoundError(
            "Missing required input files. Please ensure the following files exist:\n"
            + "\n".join(missing)
        )

    return {
        "ebook_ads": ebook_ads,
        "next_move_reference": next_move_reference,
    }


def extract_text_pages(pdf_path: Path) -> List[PageText]:
    reader = PdfReader(str(pdf_path))
    pages: List[PageText] = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append(PageText(page_number=i + 1, text=text))

    return pages


def _clean_title_candidate(value: str) -> str:
    # 1. Remove file extensions
    cleaned = re.sub(r"\.(pdf|docx|doc|txt|ppt|pptx|xlsx)\b", "", value, flags=re.IGNORECASE)
    # 2. Standard cleaning (convert underscores to spaces early)
    cleaned = cleaned.replace("_", " ")
    # 3. Remove prefixes like "Ebook 01", "Book 1", "Vol 1" anywhere at the start
    cleaned = re.sub(r"^\s*(Ebook|Book|Vol|Part|Volume)\s*\d+\s*[:\-]?\s*", "", cleaned, flags=re.IGNORECASE)
    # 4. Replace multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_\t\n\r")
    return cleaned.title() if cleaned else ""


def extract_pdf_title(pdf_path: Path, pages: List[PageText]) -> str:
    reader = PdfReader(str(pdf_path))
    metadata_title = (reader.metadata.title or "").strip() if reader.metadata else ""
    cleaned_metadata = _clean_title_candidate(metadata_title)
    if cleaned_metadata:
        return cleaned_metadata

    first_page_text = pages[0].text if pages else ""
    for raw_line in first_page_text.splitlines():
        line = _clean_title_candidate(raw_line)
        if len(line) >= 4:
            return line

    return _clean_title_candidate(pdf_path.stem) or "Untitled Ebook"


def extract_reference_layout(pdf_path: Path) -> ReferenceLayoutInfo:
    reader = PdfReader(str(pdf_path))
    if not reader.pages:
        raise ValueError("Reference PDF has no pages.")

    first_page = reader.pages[0]
    media_box = first_page.mediabox
    width = float(media_box.width)
    height = float(media_box.height)

    return ReferenceLayoutInfo(
        page_width=width,
        page_height=height,
        page_count=len(reader.pages),
    )


def save_json(data: Any, path: Path) -> None:
    if hasattr(data, "__dataclass_fields__"):
        serializable = asdict(data)
    else:
        serializable = data

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
