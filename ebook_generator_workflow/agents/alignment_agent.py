from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from ebook_generator_workflow.agents.base_agent import BaseAgent


VALID_LAYOUT_TYPES = {
    "full_width_text",
    "image_left_text_right",
    "image_right_text_left",
    "image_full_width",
}


@dataclass
class AlignedPage:
    page_number: int
    heading: str
    heading_level: int
    body_blocks: List[str]
    layout_type: str
    images: List[Dict[str, Any]]


@dataclass
class AlignedLayout:
    pages: List[AlignedPage]


class AlignmentAgent(BaseAgent):
    OUTPUT_FILE = "aligned_layout.json"
    MAX_IMAGES_PER_PAGE = 1

    def run(
        self,
        structured_document: Dict[str, Any],
        layout_structure: Dict[str, Any],
        image_plan: Dict[str, Any],
    ) -> Path:
        def _execute() -> AlignedLayout:
            planned_images = {p["page_number"]: p.get("images", []) for p in image_plan.get("pages", [])}
            pages: List[AlignedPage] = []

            for page in structured_document.get("pages", []):
                page_number = int(page.get("page_number", 0))
                heading = (page.get("heading") or "").strip()
                heading_level = int(page.get("heading_level") or 0)
                body_blocks = [str(b).strip() for b in page.get("content_blocks", []) if isinstance(b, str) and b.strip()]
                page_images = planned_images.get(page_number, [])[: self.MAX_IMAGES_PER_PAGE]
                layout_type = self._resolve_layout_type(body_blocks, page_images)

                pages.append(
                    AlignedPage(
                        page_number=page_number,
                        heading=heading,
                        heading_level=heading_level,
                        body_blocks=body_blocks,
                        layout_type=layout_type,
                        images=page_images,
                    )
                )

            return AlignedLayout(pages=pages)

        aligned = self._run_with_retries(_execute, "AlignmentAgent")
        return self._save_json(asdict(aligned), self.OUTPUT_FILE)

    def validate(self, result: AlignedLayout | Any) -> None:
        pages = result.get("pages", []) if isinstance(result, dict) else result.pages
        if not pages:
            raise ValueError("Aligned layout must contain pages")

        for page in pages:
            layout_type = page.get("layout_type") if isinstance(page, dict) else page.layout_type
            if layout_type not in VALID_LAYOUT_TYPES:
                raise ValueError(f"Unsupported layout_type: {layout_type}")

    @staticmethod
    def _resolve_layout_type(body_blocks: List[str], images: List[Dict[str, Any]]) -> str:
        if not images:
            return "full_width_text"

        if not body_blocks:
            return "image_full_width"

        zone = (images[0].get("approximate_zone") or "").lower()
        if "left" in zone:
            return "image_left_text_right"
        return "image_right_text_left"
