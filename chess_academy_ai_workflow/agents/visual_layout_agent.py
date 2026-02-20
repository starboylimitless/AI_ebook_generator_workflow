from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from chess_academy_ai_workflow.agents.base_agent import BaseAgent
from chess_academy_ai_workflow.utils.pdf_utils import ReferenceLayoutInfo


@dataclass
class LayoutZone:
    id: str
    type: str
    x: float
    y: float
    width: float
    height: float
    alignment: str


@dataclass
class PageLayout:
    page_type: str
    zones: List[LayoutZone]


@dataclass
class LayoutStructure:
    page_width: float
    page_height: float
    margins: Dict[str, float]
    spacing_rhythm: Dict[str, float]
    cover_layout: PageLayout
    section_divider_layout: PageLayout
    content_layout: PageLayout


class VisualLayoutAgent(BaseAgent):
    OUTPUT_FILE = "layout_structure.json"

    def run(self, reference_layout: ReferenceLayoutInfo) -> Path:
        def _execute() -> LayoutStructure:
            w = reference_layout.page_width
            h = reference_layout.page_height
            margin_x = round(w * 0.1, 2)
            margin_y = round(h * 0.09, 2)

            cover = PageLayout(
                page_type="cover",
                zones=[
                    LayoutZone("cover_accent", "shape", margin_x, h * 0.78, w - (2 * margin_x), h * 0.03, "center"),
                    LayoutZone("cover_title", "title", margin_x, h * 0.5, w - (2 * margin_x), h * 0.22, "center"),
                    LayoutZone("cover_subtitle", "text", margin_x, h * 0.42, w - (2 * margin_x), h * 0.06, "center"),
                ],
            )

            section = PageLayout(
                page_type="section_divider",
                zones=[
                    LayoutZone("section_bar", "shape", margin_x, h * 0.7, w - (2 * margin_x), h * 0.018, "left"),
                    LayoutZone("section_title", "title", margin_x, h * 0.54, w - (2 * margin_x), h * 0.14, "left"),
                    LayoutZone("section_caption", "text", margin_x, h * 0.46, w - (2 * margin_x), h * 0.06, "left"),
                ],
            )

            content = PageLayout(
                page_type="content",
                zones=[
                    LayoutZone("header", "text", margin_x, h * 0.78, w - (2 * margin_x), h * 0.12, "left"),
                    LayoutZone("body", "text", margin_x, margin_y + h * 0.2, w - (2 * margin_x), h * 0.52, "left"),
                    LayoutZone("image_right", "image", w * 0.58, margin_y, w * 0.32, h * 0.16, "center"),
                    LayoutZone("image_left", "image", margin_x, margin_y, w * 0.32, h * 0.16, "center"),
                ],
            )

            return LayoutStructure(
                page_width=w,
                page_height=h,
                margins={"left": margin_x, "right": margin_x, "top": margin_y, "bottom": margin_y},
                spacing_rhythm={"base": 8, "heading_gap": 14, "section_gap": 24},
                cover_layout=cover,
                section_divider_layout=section,
                content_layout=content,
            )

        layout = self._run_with_retries(_execute, "VisualLayoutAgent")
        return self._save_json(asdict(layout), self.OUTPUT_FILE)

    def validate(self, result: LayoutStructure | Any) -> None:
        if isinstance(result, dict):
            content = result.get("content_layout", {}).get("zones", [])
        else:
            content = result.content_layout.zones
        image_zones = [z for z in content if (z.get("type") if isinstance(z, dict) else z.type) == "image"]
        if len(image_zones) < 2:
            raise ValueError("Content layout must include at least two image zones")
