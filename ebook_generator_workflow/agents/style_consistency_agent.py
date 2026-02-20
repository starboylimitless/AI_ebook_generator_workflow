from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict

from ebook_generator_workflow.agents.base_agent import BaseAgent

SAFE_FONTS = {"Helvetica", "Helvetica-Bold", "Times-Roman", "Times-Bold", "Courier"}


@dataclass
class StyleSpec:
    fonts: Dict[str, Any]
    colors: Dict[str, Any]
    spacing: Dict[str, Any]
    headings: Dict[str, Any]
    body_text: Dict[str, Any]


class StyleConsistencyAgent(BaseAgent):
    OUTPUT_FILE = "style_spec.json"

    def run(
        self,
        reference_layout_info: Dict[str, Any],
        layout_structure: Dict[str, Any],
        aligned_layout: Dict[str, Any],
    ) -> Path:
        def _execute() -> StyleSpec:
            return StyleSpec(
                fonts={"primary": "Helvetica", "secondary": "Helvetica-Bold"},
                colors={
                    "background": "#FFFFFF",
                    "primary_text": "#0F172A",
                    "secondary_text": "#334155",
                    "accent": "#C9A227",
                    "accent_soft": "#F5EFD3",
                },
                spacing={
                    "page_margin_top": 58,
                    "page_margin_bottom": 46,
                    "page_margin_left": 54,
                    "page_margin_right": 54,
                    "paragraph_spacing": 8,
                    "line_spacing": 14,
                },
                headings={
                    "h1": {"font_name": "Helvetica-Bold", "font_size": 24, "color": "#0B0F19"},
                    "h2": {"font_name": "Helvetica-Bold", "font_size": 18, "color": "#1E293B"},
                    "h3": {"font_name": "Helvetica-Bold", "font_size": 14, "color": "#334155"},
                },
                body_text={"font_name": "Helvetica", "font_size": 11, "color": "#1F2937", "line_height": 15},
            )

        spec = self._run_with_retries(_execute, "StyleConsistencyAgent")
        return self._save_json(asdict(spec), self.OUTPUT_FILE)

    def validate(self, result: StyleSpec | Any) -> None:
        headings = result.get("headings", {}) if isinstance(result, dict) else result.headings
        body_text = result.get("body_text", {}) if isinstance(result, dict) else result.body_text
        for name in ("h1", "h2", "h3"):
            if name not in headings:
                raise ValueError(f"Missing heading style: {name}")
            if headings[name].get("font_name") not in SAFE_FONTS:
                raise ValueError(f"Unsupported font in {name}")
        if body_text.get("font_name") not in SAFE_FONTS:
            raise ValueError("Unsupported body font")
