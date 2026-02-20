from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

import re

from chess_academy_ai_workflow.agents.base_agent import BaseAgent


@dataclass
class ImageSlot:
    slot_id: str
    page_number: int
    category: str
    description: str
    approximate_zone: str
    priority: int
    render_status: str
    type: str = "generic"
    caption: str = ""


class ChessImageAgent(BaseAgent):
    """Deterministic image planning only (no image generation).

    Produces at most 1 image slot per page, and only on every 3rd content
    page to keep a balanced text-to-image rhythm.  The ``render_status``
    field stays ``"planned"`` so future fal.ai insertion can fill it in.
    """

    OUTPUT_FILE = "image_placement.json"
    IMAGE_EVERY_N_PAGES = 2  # place an image roughly every 2 content pages (Densification)

    def run(self, structured_document: Dict[str, Any], image_hooks: Dict[str, Any] | None = None) -> Path:
        def _execute() -> Dict[str, Any]:
            pages = structured_document.get("pages", [])
            chapter_starts = {c.get("start_page") for c in structured_document.get("chapters", []) if c.get("start_page")}
            
            placements: List[Dict[str, Any]] = []
            total_images_placed = 0

            for page in pages:
                page_number = page["page_number"]
                page_images: List[Dict[str, Any]] = []
                
                # STRICT COST OPTIMIZATION: Only 1 Hero image per chapter start
                if page_number in chapter_starts:
                     # Unique suffix per page to avoid filename collision
                     desc = f"Cinematic, realistic photography of chess academy success, professional lighting, high quality, 8k, contextual to chapter at page {page_number}"
                     slot = ImageSlot(
                        slot_id=f"page{page_number}_hero",
                        page_number=page_number,
                        category="hero",
                        description=desc,
                        approximate_zone="top",
                        priority=0,
                        render_status="planned",
                        type="HERO"
                    )
                     page_images.append(asdict(slot))
                     total_images_placed += 1
                
                placements.append(
                    {
                        "page_number": page_number,
                        "images": page_images,
                    }
                )

            return {"pages": placements}

        result = self._run_with_retries(_execute, "ChessImageAgent")
        return self._save_json(result, self.OUTPUT_FILE)

    def validate(self, result: Any) -> None:
        if not isinstance(result, dict) or not result.get("pages"):
            raise ValueError("Image plan must contain pages")
