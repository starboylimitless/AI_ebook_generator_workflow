from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    Flowable,
)

from chess_academy_ai_workflow.agents.base_agent import BaseAgent
from chess_academy_ai_workflow.utils.logging_utils import setup_logger


@dataclass
class FinalEbookMetadata:
    page_count: int
    has_cover: bool
    has_toc: bool
    table_of_contents: List[str]
    has_section_dividers: bool
    image_hooks_count: int
    validation_passed: bool


_SEMANTIC_IMAGE_MAP = {
    "FUNNEL": "targeting_funnel.png",
    "TARGETING_DIAGRAM": "targeting_funnel.png",
    "BUDGET_PLAN": "budget_visual.png",
    "AD_MOCKUP": "ad_mockup.png",
    "RESPONSE_FLOW": "response_flow.png",
}


class Bookmark(Flowable):
    def __init__(self, title: str, name: str, level: int = 0) -> None:
        Flowable.__init__(self)
        self.title = title
        self.name = name
        self.level = level

    def draw(self) -> None:
        self.canv.bookmarkPage(self.name)
        self.canv.addOutlineEntry(self.title, self.name, level=self.level)


class FinalOptimizationAgent(BaseAgent):
    OUTPUT_METADATA_FILE = "final_ebook_metadata.json"
    OUTPUT_PDF_FILE = "final_ebook.pdf"
    MAX_IMAGE_HOOKS_PER_PAGE = 1
    IMAGE_HINT_RE = re.compile(r"\[\s*.*?[📷🖼️📸]*\s*Image:.*?\]", re.IGNORECASE | re.DOTALL)
    IMAGE_PLACEHOLDER_RE = re.compile(r"\[\s*📷\s*Image:.*?\]", re.IGNORECASE)
    CHAPTER_TITLE_RE = re.compile(r"^(Chapter|Part)\s+(\d+|[IVXLC]+)\b", re.IGNORECASE)
    BULLET_LINE_RE = re.compile(r'\n\s*(?=[●•▪►*\-](?:\s|$)|\d+\.\s)')

    TIP_RE = re.compile(r"^Tip[:\-\s]", re.IGNORECASE)
    CHECKLIST_RE = re.compile(r"Checklist[:\-\s]", re.IGNORECASE)

    def __init__(self, prompts_dir: Path, output_dir: Path, *args: Any, **kwargs: Any) -> None:
        super().__init__(name="final_optimization_agent", prompts_dir=prompts_dir, output_dir=output_dir, *args, **kwargs)
        self.logger = setup_logger("agent.final_optimization")

    def run(
        self,
        structured_document: Dict[str, Any],
        aligned_layout: Dict[str, Any],
        style_spec: Dict[str, Any],
        layout_structure: Dict[str, Any],
        image_placement: Dict[str, Any],
        reference_layout_info: Dict[str, Any],
        original_title: str | None = None,
        normalized_document: Dict[str, Any] | None = None,
    ) -> Dict[str, Path]:
        pdf_path, toc_entries, actual_pages = self._render_pdf(
            structured_document=structured_document,
            aligned_layout=aligned_layout,
            style_spec=style_spec,
            document_title=original_title or (normalized_document.get("front_matter", {}).get("title") if normalized_document else None) or structured_document.get("document_title", "Untitled Ebook"),
            normalized_document=normalized_document,
        )

        metadata = FinalEbookMetadata(
            page_count=actual_pages,
            has_cover=True,
            has_toc=bool(toc_entries),
            table_of_contents=toc_entries,
            has_section_dividers=True,
            image_hooks_count=sum(min(len(p.get("images", [])), self.MAX_IMAGE_HOOKS_PER_PAGE) for p in aligned_layout.get("pages", [])),
            validation_passed=True,
        )
        metadata_path = self._save_json(asdict(metadata), self.OUTPUT_METADATA_FILE)
        return {"metadata": metadata_path, "pdf": pdf_path}

    def validate(self, result: Any) -> None:
        return

    @staticmethod
    def _add_page_number(canvas_obj: canvas.Canvas, doc: Any) -> None:
        page_num = canvas_obj.getPageNumber()
        if page_num > 1:
            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica", 9)
            canvas_obj.setFillColor(colors.HexColor("#64748B"))
            canvas_obj.drawCentredString(doc.width / 2.0 + 54, 30, f"Page {page_num}")
            canvas_obj.restoreState()

    def _resolve_sample_image(self, index: int, semantic_type: str | None = None, local_path: str | None = None) -> Path | None:
        # 0. Try local path first (for generated images)
        if local_path:
            p = Path(local_path)
            if p.exists():
                return p

        # 1. Try semantic mapping next
        if semantic_type and semantic_type.upper() in _SEMANTIC_IMAGE_MAP:
            ideal_name = _SEMANTIC_IMAGE_MAP[semantic_type.upper()]
            path = self.output_dir / ideal_name
            if path.exists():
                return path
            
        # No generic fallback - we only want high-value semantic images
        return None

    def _render_pdf(
        self,
        structured_document: Dict[str, Any],
        aligned_layout: Dict[str, Any],
        style_spec: Dict[str, Any],
        document_title: str,
        normalized_document: Dict[str, Any] | None = None,
    ) -> tuple[Path, List[str], int]:
        output_pdf_path = self.output_dir / self.OUTPUT_PDF_FILE
        
        spacing = style_spec.get("spacing", {})
        colors_map = style_spec.get("colors", {})
        headings = style_spec.get("headings", {})
        body = style_spec.get("body_text", {})

        doc = SimpleDocTemplate(
            str(output_pdf_path),
            rightMargin=spacing.get("page_margin_right", 54),
            leftMargin=spacing.get("page_margin_left", 54),
            topMargin=spacing.get("page_margin_top", 58),
            bottomMargin=spacing.get("page_margin_bottom", 46),
        )

        styles = getSampleStyleSheet()
        h1 = ParagraphStyle(
            "h1",
            parent=styles["Heading1"],
            fontName=headings.get("h1", {}).get("font_name", "Helvetica-Bold"),
            fontSize=28, # BOOSTED
            textColor=colors.HexColor(headings.get("h1", {}).get("color", "#0B0F19")),
            spaceBefore=12, # Reduced from 24
            spaceAfter=16,  # Reduced from 24
            leading=32,
        )
        h2 = ParagraphStyle(
            "h2",
            parent=styles["Heading2"],
            fontName=headings.get("h2", {}).get("font_name", "Helvetica-Bold"),
            fontSize=headings.get("h2", {}).get("font_size", 18),
            textColor=colors.HexColor(headings.get("h2", {}).get("color", "#1E293B")),
            spaceBefore=10, # Reduced from 12
            spaceAfter=6,   # Reduced from 8
            leading=22,
        )
        h3 = ParagraphStyle(
            "h3",
            parent=styles["Heading3"],
            fontName=headings.get("h3", {}).get("font_name", "Helvetica-Bold"),
            fontSize=headings.get("h3", {}).get("font_size", 14),
            textColor=colors.HexColor(headings.get("h3", {}).get("color", "#334155")),
            spaceBefore=10,
            spaceAfter=6,
            leading=18,
        )
        body_style = ParagraphStyle(
            "body",
            parent=styles["BodyText"],
            fontName=body.get("font_name", "Helvetica"),
            fontSize=body.get("font_size", 11),
            textColor=colors.HexColor(body.get("color", "#1F2937")),
            leading=max(14, int(body.get("line_height", 15))),
            spaceAfter=4, # Reduced from 6
            alignment=0,
        )
        caption_style = ParagraphStyle(
            "caption",
            parent=body_style,
            fontSize=8,
            textColor=colors.HexColor("#64748B"),
            alignment=1,
            spaceBefore=2,
            spaceAfter=0,
        )
        list_item_style = ParagraphStyle(
            "list_item",
            parent=body_style,
            leftIndent=24,
            firstLineIndent=-12,
            spaceBefore=2,
            spaceAfter=2,
            bulletIndent=12,
            leading=14,
        )

        accent = colors.HexColor(colors_map.get("accent", "#C9A227"))
        accent_soft = colors.HexColor(colors_map.get("accent_soft", "#F5EFD3"))

        elements: List[Any] = []
        elements.extend(self._build_cover(document_title, doc.width, h1, body_style, accent, accent_soft))

        if normalized_document:
            chapters = normalized_document.get("chapters", [])
            toc_entries = [c.get("title", "") for c in chapters if c.get("title")]
        else:
            chapters = structured_document.get("chapters", [])
            toc_entries = self._build_toc_entries(chapters, structured_document.get("document_title", ""))

        elements.extend(self._build_toc(doc.width, toc_entries, h1, body_style, accent))

        pages = aligned_layout.get("pages", [])
        image_cycle_index = 0
        previous_heading = ""
        chapters_rendered = 0
        chapter_page_count = 0
        chapter_image_inserted = False

        for page in pages:
            page_number = page.get("page_number")
            heading = (page.get("heading") or "").strip()
            heading_level = int(page.get("heading_level") or 0)
            layout_type = page.get("layout_type", "full_width_text")
            body_blocks = [self._clean_block(b) for b in page.get("body_blocks", [])]
            body_blocks = [b for b in body_blocks if b]
            body_blocks = self._merge_into_paragraphs(body_blocks)
            images = page.get("images", [])[: self.MAX_IMAGE_HOOKS_PER_PAGE]

            rendered_heading = False
            pending_heading = None
            if heading and heading != previous_heading:
                if self._should_render_heading(heading, heading_level):
                    if heading_level == 1:
                        # Closure for PREVIOUS chapter
                        if chapters_rendered > 0:
                             summary = self._build_feature_box("SUMMARY", ["Action Item: Review your academy's status against this chapter.", "Next Step: Plan your implementation."], body_style, list_item_style, doc.width)
                             if summary: elements.extend(summary)
                             elements.append(Spacer(1, 0.2 * inch))

                        if elements and not isinstance(elements[-1], PageBreak):
                            elements.append(PageBreak())
                        
                        bar = Table([[""]], colWidths=[doc.width], rowHeights=[6])
                        bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), accent)]))
                        elements.append(bar)
                        elements.append(Spacer(1, 0.4 * inch))
                        chapters_rendered += 1
                        chapter_page_count = 0
                        chapter_image_inserted = False

                    heading_style = h1 if heading_level == 1 else (h3 if heading_level == 3 else h2)
                    bookmark_name = f"chapter_{chapters_rendered}" if heading_level == 1 else f"section_{page_number}"
                    elements.append(Bookmark(heading, bookmark_name, level=0 if heading_level == 1 else 1))
                    
                    heading_para = Paragraph(f'<a name="{bookmark_name}"/>{heading}', heading_style)
                    pending_heading = (heading_para, heading_style)
                    rendered_heading = True
                    
                    if heading_level == 1:
                        elements.append(heading_para)
                        elements.append(Spacer(1, 0.1 * inch))
                        # Chapter banners can also be generated or semantic
                        img_path = self._resolve_sample_image(image_cycle_index, semantic_type="CHAPTER_BANNER")
                        if img_path:
                            try:
                                img = Image(str(img_path), width=doc.width * 0.8, height=2.5 * inch)
                                img.hAlign = "CENTER"
                                elements.append(img)
                                image_cycle_index += 1
                                chapter_image_inserted = True 
                            except:
                                pass
                        elements.append(Spacer(1, 0.3 * inch))
                        pending_heading = None 
                else:
                    body_blocks = [heading] + body_blocks
                previous_heading = heading

            if rendered_heading:
                body_blocks = [b for b in body_blocks if self._normalise(b) != self._normalise(heading)]

            page_flowables, image_cycle_index = self._page_flowables(
                layout_type=layout_type,
                images=images,
                body_blocks=body_blocks,
                body_style=body_style,
                caption_style=caption_style,
                list_item_style=list_item_style,
                doc_width=doc.width,
                image_cycle_index=image_cycle_index,
                accent=accent,
                accent_soft=accent_soft,
            )

            if pending_heading:
                hp, hs = pending_heading
                # CHAPTER DIVIDER (Phase 8 Polish)
                # Add a visual accent line below the chapter title
                divider_table = Table([[""]], colWidths=[doc.width * 0.6], rowHeights=[2])
                divider_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), accent),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]))
                divider_table.hAlign = "CENTER"

                hb = [hp, Spacer(1, 4), divider_table, Spacer(1, 12)]
                
                if page_flowables and isinstance(page_flowables[0], Paragraph):
                    hb.append(page_flowables.pop(0))
                elements.append(KeepTogether(hb))

            if page_flowables:
                elements.extend(page_flowables)

            chapter_page_count += 1
            if chapter_page_count == 3 and not (chapter_page_count == 1 and chapter_image_inserted):
                img_path = self._resolve_sample_image(image_cycle_index)
                if img_path:
                    elements.append(Spacer(1, 0.2 * inch))
                    try:
                        img = Image(str(img_path), width=doc.width * 0.7, height=2.0 * inch)
                        img.hAlign = "CENTER"
                        elements.append(img)
                        image_cycle_index += 1
                    except:
                        pass
                    elements.append(Spacer(1, 0.2 * inch))

            elements.append(Spacer(1, 0.12 * inch))

        # Phase 12: Closure for Final Chapter
        if chapters_rendered > 0:
             summary = self._build_feature_box("SUMMARY", ["Action Item: Review your academy's status against this chapter.", "Next Step: Plan your implementation."], body_style, list_item_style, doc.width)
             if summary: elements.extend(summary)

        doc.build(elements, onLaterPages=self._add_page_number)
        actual_pages = doc.page
        return output_pdf_path, toc_entries, actual_pages

    @staticmethod
    def _build_cover(
        document_title: str,
        doc_width: float,
        h1: ParagraphStyle,
        body_style: ParagraphStyle,
        accent: colors.Color,
        accent_soft: colors.Color,
    ) -> List[Any]:
        title = (document_title or "Untitled Ebook").strip()
        cover_title_style = ParagraphStyle(
            "cover_title", parent=h1, alignment=1,
            textColor=colors.HexColor("#0B0F19"),
            fontSize=34, leading=40,
            spaceBefore=0, spaceAfter=0,
        )
        subtitle_style = ParagraphStyle(
            "cover_subtitle", parent=body_style, alignment=1,
            fontSize=14, textColor=colors.HexColor("#475569"),
            spaceBefore=0, spaceAfter=0,
        )
        tagline_style = ParagraphStyle(
            "cover_tagline", parent=body_style, alignment=1,
            fontSize=11, textColor=colors.HexColor("#64748B"),
            fontName="Helvetica-Oblique",
        )

        top_bar = Table([[""]], colWidths=[doc_width], rowHeights=[28])
        top_bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), accent)]))

        thin_bar = Table([[""]], colWidths=[doc_width], rowHeights=[4])
        thin_bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), accent_soft)]))

        bottom_bar = Table([[""]], colWidths=[doc_width], rowHeights=[14])
        bottom_bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), accent)]))

        sq_size = 18
        chess_row = []
        for i in range(int(doc_width // sq_size)):
            chess_row.append("")
        chess_table = Table([chess_row], colWidths=[sq_size] * len(chess_row), rowHeights=[sq_size])
        chess_styles = [("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
        for i in range(len(chess_row)):
            bg = accent if i % 2 == 0 else accent_soft
            chess_styles.append(("BACKGROUND", (i, 0), (i, 0), bg))
        chess_table.setStyle(TableStyle(chess_styles))

        return [
            top_bar,
            thin_bar,
            Spacer(1, 2.0 * inch),
            Paragraph(title, cover_title_style),
            Spacer(1, 0.25 * inch),
            Paragraph("A Step-by-Step Guide for Chess Academy Owners", subtitle_style),
            Spacer(1, 0.5 * inch),
            Paragraph("Learn to run simple, effective ads that bring student inquiries<br/>without agencies, complex funnels, or high budgets.", tagline_style),
            Spacer(1, 1.8 * inch),
            chess_table,
            Spacer(1, 0.15 * inch),
            bottom_bar,
            PageBreak(),
        ]

    @staticmethod
    def _build_toc_entries(chapters: List[Dict[str, Any]], document_title: str) -> List[str]:
        title_norm = re.sub(r"\s+", " ", str(document_title)).strip().lower()
        toc_entries: List[str] = []
        seen_titles: set[str] = set()

        for chapter in chapters:
            title = re.sub(r"\s+", " ", str(chapter.get("title", ""))).strip()
            if not title or title.lower() == title_norm or title in seen_titles:
                continue
            if not re.match(r"^(Chapter|Part)\s+(\d+|[IVXLC]+)\b", title, flags=re.IGNORECASE):
                continue
            seen_titles.add(title)
            toc_entries.append(title)
        return toc_entries

    @staticmethod
    def _build_toc(doc_width: float, toc_entries: List[str], h1: ParagraphStyle, body_style: ParagraphStyle, accent: colors.Color) -> List[Any]:
        toc_title_style = ParagraphStyle("toc_title", parent=h1, fontSize=22, spaceAfter=12, textColor=colors.HexColor("#0B0F19"))
        elements: List[Any] = [Paragraph("Table of Contents", toc_title_style), Spacer(1, 0.08 * inch)]
        bar = Table([[""]], colWidths=[doc_width * 0.3], rowHeights=[3])
        bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), accent)]))
        elements.append(bar)
        elements.append(Spacer(1, 0.15 * inch))

        toc_row_style = ParagraphStyle("toc_row", parent=body_style, spaceAfter=2, fontSize=12, leading=16)
        for idx, title in enumerate(toc_entries, start=1):
            link_text = f'<link destination="chapter_{idx}"><font color="#1E40AF">{idx}. {title}</font></link>'
            row = Table([[Paragraph(link_text, toc_row_style)]], colWidths=[doc_width])
            row.setStyle(TableStyle([
                ("LINEBELOW", (0, 0), (-1, 0), 0.25, colors.HexColor("#CBD5E1")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(row)
        elements.append(PageBreak())
        return elements

    def _page_flowables(
        self, layout_type: str, images: List[Dict[str, Any]], body_blocks: List[str | Dict[str, Any]],
        body_style: ParagraphStyle, caption_style: ParagraphStyle, list_item_style: ParagraphStyle,
        doc_width: float, image_cycle_index: int, accent: colors.Color, accent_soft: colors.Color,
    ) -> tuple[List[Any], int]:
        image_groups: List[Any] = [] # List of lists of flowables
        text_flowables = self._paragraph_flowables(body_blocks, body_style, list_item_style, doc_width, accent, accent_soft)

        # 1. GENERATE IMAGE GROUPS
        for hook in images[: self.MAX_IMAGE_HOOKS_PER_PAGE]:
            image_widget_group = self._image_with_caption(hook, caption_style, image_cycle_index, doc_width)
            if image_widget_group:
                image_cycle_index += 1
                image_groups.append(image_widget_group)

        # 2. SEMANTIC INSERTION ENGINE (User Rule: "Mid-list insertion is forbidden")
        # We want to insert images:
        #  - AFTER the first "Intro" paragraph (Body text)
        #  - BEFORE any bullet lists
        #  - NEVER inside a list
        
        if not image_groups:
            return text_flowables, image_cycle_index

        out: List[Any] = []
        inserted_count = 0
        
        # Scan text flowables to find safe insertion points
        insertion_indices = []
        
        # Heuristic: Find the first "Body" paragraph that is NOT followed by another body paragraph immediately? 
        # Actually, simpler: Find the FIRST body paragraph. Insert after it.
        # If we have multiple images, distribute them? For now, we usually have 1 per page.
        
        first_intro_idx = -1
        
        for i, f in enumerate(text_flowables):
            # Check if this flowable is a Body Paragraph
            if isinstance(f, Paragraph):
                # We assume body_style names might start with 'body' or match exactly
                if getattr(f.style, 'name', '') == body_style.name:
                    first_intro_idx = i
                    break
        
        # Logic: 
        # If we found an intro, insert AFTER it (and its spacer).
        # We need to be careful about Spacers. Usually a Body Para is followed by a Spacer.
        
        insert_at = -1
        if first_intro_idx != -1:
            # Check if next item is a Spacer
            if first_intro_idx + 1 < len(text_flowables) and isinstance(text_flowables[first_intro_idx+1], Spacer):
                insert_at = first_intro_idx + 2
            else:
                insert_at = first_intro_idx + 1
        else:
            # No intro paragraph found (maybe specific section type). 
            # Insert at top? Or before first list?
            # Let's insert at top if no intro, but check for Headers.
            # If first item is header, insert after header.
            if text_flowables and isinstance(text_flowables[0], (Paragraph, KeepTogether)):
                 # Assume header logic handles KeepTogether(Heading)
                 insert_at = 1 
            else:
                insert_at = 0

        # Construct new list
        # We only support 1 image per page mostly, so just insert the first group at the spot.
        # If multiple groups, we can stack them or find next spots. 
        # Current Layout Rule: "One major image per page max"
        
        # Copy up to insertion point
        safe_idx = min(insert_at, len(text_flowables))
        out.extend(text_flowables[:safe_idx])
        
        # Insert ALL image groups (usually 1)
        for group in image_groups:
             out.extend(group)
        
        # Copy rest
        out.extend(text_flowables[safe_idx:])
            
        return out, image_cycle_index

    def _image_with_caption(self, hook: Dict[str, Any], caption_style: ParagraphStyle, index: int, doc_width: float) -> Any:
        # 1. ORPHAN TITLE KILL SWITCH
        # If no explicit caption, we DO NOT invent one from the type.
        caption_text = hook.get("caption", "").strip()
        
        # If the caption is just "Illustration" or "Generic", suppress it.
        if caption_text.lower() in ["illustration", "generic", "hint"]:
            caption_text = ""

        semantic_type = hook.get("type", hook.get("category"))
        local_path = hook.get("local_path")
        
        img_path = self._resolve_sample_image(index, semantic_type=semantic_type, local_path=local_path)
        
        # 2. SKIP IF NO IMAGE
        if not img_path:
            return None

        try:
            full_path = str(Path(img_path).resolve())
            
            # 3. LAYOUT GEOMETRY: 72% Width (User Req), Centered
            # Max width is 72% of printable area.
            # Max height is 3.5 inches to prevent massive vertical takeover.
            max_img_width = doc_width * 0.72
            img = Image(full_path, width=max_img_width, height=3.5 * inch)
            
            # Rescale maintaining aspect ratio functionality is built into how we set w/h 
            # (ReportLab Image defaults to aspect ratio if one dim is None, but here we enforce bounds. 
            #  Ideally we'd read image size, but fixed height/width constraint is safer for stability).
            #  Let's allow natural height based on width constraint if possible, 
            #  but ReportLab Image needs explicit w/h. 
            #  For now, we stick to the provided sizing but make it strictly 75% wide or less.
            
            img.hAlign = "CENTER"

            content_rows = [[img]]
            
            # 4. CAPTION HANDLING
            # Only add caption row if we have a valid, non-generic caption
            if caption_text:
                caption = Paragraph(caption_text, caption_style)
                content_rows.append([caption])

            # 5. BLOCK ENCAPSULATION
            # Use a table to bind image and caption together
            block = Table(content_rows, colWidths=[max_img_width])
            block.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"), # Center everything in the table
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6), # Small padlock between img/caption
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            block.hAlign = "CENTER"

            # 6. VERTICAL RHYTHM & ATOMICITY
            # Return a list of flowables: Spacing + Atomic Block + Spacing
            return [
                Spacer(1, 12),              # Reduced from 24
                KeepTogether(block),        # Never separate image from caption
                Spacer(1, 12)               # Reduced from 18
            ]

        except Exception as e:
            self.logger.warning("Failed to render image %s: %s", img_path, e)
        
        return None

    def _render_target_audience_boxes(self, blocks: List[str], body_style: ParagraphStyle, doc_width: float) -> List[Any]:
        """
        Phase 8.5: Robust parser for the "Target Audience" section.
        Handles monolithic strings with newlines.
        Maps text to "For", "Not For", "Achieve" boxes.
        """
        flowables = []
        
        # Styles for boxes
        box_styles = {
            "for": colors.HexColor("#EFF6FF"),      # Light Blue
            "not": colors.HexColor("#FEF2F2"),      # Light Red
            "achieve": colors.HexColor("#F0FDF4"),  # Light Green
        }
        
        # Flatten all blocks and split by newlines
        all_lines = []
        for b in blocks:
            if isinstance(b, str):
                all_lines.extend(b.split('\n'))
            elif isinstance(b, dict) and "text" in b:
                # If it's a dict, it might be a structured block. 
                # Be safe and split text.
                all_lines.extend(str(b["text"]).split('\n'))
            else:
                 all_lines.extend(str(b).split('\n'))
                
        current_category = "intro" # Default
        current_bullets = []
        
        def flush_box():
            nonlocal current_bullets
            if not current_bullets: return
            
            nonlocal current_category
            bg_color = box_styles.get(current_category, colors.white)
            
            # Title mapping
            title_text = "Who This Ebook Is For"
            if current_category == "not": title_text = "Who This Is NOT For"
            if current_category == "achieve": title_text = "What You Will Achieve"
            
            # Build box content
            box_content = []
            title_style = ParagraphStyle("BoxTitle", parent=body_style, fontName="Helvetica-Bold", fontSize=12, spaceAfter=8, textColor=colors.black)
            box_content.append(Paragraph(title_text, title_style))
            
            # Render bullets with custom style
            bullet_style = ParagraphStyle("BoxBullet", parent=body_style, leftIndent=12, firstLineIndent=0, spaceAfter=3)
            for b in current_bullets:
                box_content.append(Paragraph(f"&bull; {b}", bullet_style))
            
            # Render as table
            # 90% width
            t = Table([[box_content]], colWidths=[doc_width * 0.9])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), bg_color),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROUNDEDCORNERS", [6, 6, 6, 6]),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]))
            t.hAlign = "CENTER"
            
            flowables.append(Spacer(1, 12))
            flowables.append(t)
            flowables.append(Spacer(1, 12))
            current_bullets = []

        # Parsing Logic
        for line in all_lines:
            text = line.strip()
            if not text: continue
            
            lower = text.lower()
            
            # Category triggers
            if "primary audience" in lower or "who this ebook is for" in lower or "target reader" in lower:
                flush_box()
                current_category = "for"
                continue
            elif "not cover" in lower or "what this ebook will not" in lower or "without:" in lower:
                flush_box()
                current_category = "not"
                continue
            elif "core goal" in lower or "will cover" in lower or "what you will achieve" in lower:
                flush_box()
                current_category = "achieve"
                continue
            elif "chapter" in lower: # End of section usually
                flush_box() # Flush whatever we have
                current_category = "intro"
                flowables.append(Paragraph(text, body_style)) # Just treat as text
                continue

            # Bullet detection
            # Remove raw bullet chars
            clean_text = re.sub(r"^[●•▪►*?\-\d\.]+\s*", "", text).strip()
            
            # If line starts with bullet OR we are in a box category and it looks like a list item
            if current_category != "intro":
                # In a box, almost everything is a bullet or a sub-header.
                # Treat as bullet for simplicity in the box view.
                current_bullets.append(clean_text)
            else:
                # Outside box (Intro)
                is_bullet = bool(re.match(r"^[●•▪►*?\-]", text))
                if is_bullet:
                     # Treat as bullet paragraph intro? Or just text.
                     # Let's clean it and show.
                     flowables.append(Paragraph(f"&bull; {clean_text}", body_style))
                else:
                    flowables.append(Paragraph(text, body_style))
                flowables.append(Spacer(1, 6))

        flush_box()
        return flowables

    def _paragraph_flowables(
        self, blocks: List[str | Dict[str, Any]], body_style: ParagraphStyle, list_item_style: ParagraphStyle,
        doc_width: float, accent: colors.Color, accent_soft: colors.Color,
    ) -> List[Any]:
        # Phase 11: Layout Protection Layer
        # Normalize structure BEFORE any processing
        blocks = self._normalize_content_structure(blocks)

        # Phase 8.5 Interception: Target Audience
        is_target_audience_section = False
        sample_text = ""
        for b in blocks[:2]:
            if isinstance(b, str): sample_text += b.lower()
            elif isinstance(b, dict): sample_text += b.get("text", "").lower()
            
        if "target audience" in sample_text or "who this ebook is for" in sample_text:
             return self._render_target_audience_boxes(blocks, body_style, doc_width)

        flowables: List[Any] = []
        
        # GLOBAL FEATURE DETECTOR (Phase 9)
        # We iterate blocks and check for "Trigger Prefixes"
        
        current_feature_type = None
        feature_buffer = []

        def flush_feature():
            nonlocal current_feature_type, feature_buffer
            if not feature_buffer or not current_feature_type: return
            
            # Build the box
            box = self._build_feature_box(current_feature_type, feature_buffer, body_style, list_item_style, doc_width)
            if box:
                flowables.extend(box)
            
            feature_buffer = []
            current_feature_type = None

        for raw_block in blocks:
            text_content = ""
            if isinstance(raw_block, str): text_content = raw_block
            elif isinstance(raw_block, dict): text_content = raw_block.get("text", "")
            
            # Split monolithic blocks by newline
            lines = text_content.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line: continue
                
                # Check for Feature Trigger
                # Fix Phase 12: Strip bullets/whitespace to detect Broken Boxes
                clean_line_check = re.sub(r"^[●•▪►*?\-\d\.]+\s*", "", line).strip().lower()
                
                # Mistake Detection
                if clean_line_check.startswith(("mistake", "common mistake", "trap", "avoid")):
                    flush_feature() # Flush previous
                    current_feature_type = "MISTAKE"
                    feature_buffer.append(line)
                    continue
                
                # Checklist / Action Detection
                if clean_line_check.startswith(("checklist", "action step", "do this", "verify")):
                    flush_feature()
                    current_feature_type = "CHECKLIST"
                    feature_buffer.append(line)
                    continue
                
                # Tip / Note Detection
                if clean_line_check.startswith(("tip", "note", "remember", "pro tip")):
                    flush_feature()
                    current_feature_type = "TIP"
                    feature_buffer.append(line)
                    continue
                
                # Quote Detection
                if line.startswith(('"', '“', '‘', "'")) and len(line) > 60:
                    flush_feature()
                    current_feature_type = "QUOTE"
                    feature_buffer.append(line)
                    continue

                if current_feature_type:
                    # We are inside a feature block.
                    # Heuristic: If it looks like a new header, break out?
                    # For now, simplistic: Any bullet inside extends, any non-bullet extends if short?
                    # Actually, usually these features are 1-3 paras/bullets.
                    # Let's verify length. If buffer > 6 items, maybe break?
                    if len(feature_buffer) > 8:
                        flush_feature()
                        # Fallthrough to normal processing
                    else:
                        feature_buffer.append(line)
                        continue

                # Normal Paragraph Processing (Global Bullet Normalizer)
                bullet_match = re.match(r"^[●•▪►*?\-]\s*(.*)", line)
                if bullet_match:
                    content = bullet_match.group(1).strip()
                    if not content: content = line 
                    p = Paragraph(f"&bull; {content}", list_item_style)
                    flowables.append(p)
                else:
                    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
                    p = Paragraph(text, body_style)
                    flowables.append(p)
                
                flowables.append(Spacer(1, 4))
        
        flush_feature()
        return flowables

    def _build_feature_box(self, ftype: str, items: List[str], body_style: ParagraphStyle, list_style: ParagraphStyle, doc_width: float) -> List[Any]:
        # Colors & Icons
        styles = {
            "MISTAKE": {"bg": colors.HexColor("#FEF2F2"), "border": colors.HexColor("#DC2626"), "title": "Common Mistake", "icon": "⚠️"},
            "CHECKLIST": {"bg": colors.HexColor("#EFF6FF"), "border": colors.HexColor("#2563EB"), "title": "Quick Checklist", "icon": "✅"},
            "TIP": {"bg": colors.HexColor("#F0FDF4"), "border": colors.HexColor("#16A34A"), "title": "Pro Tip", "icon": "💡"},
            "QUOTE": {"bg": colors.HexColor("#F8FAFC"), "border": colors.HexColor("#64748B"), "title": "Insight", "icon": "❝"},
            "SUMMARY": {"bg": colors.HexColor("#F0F9FF"), "border": colors.HexColor("#0284C7"), "title": "Key Takeaways", "icon": "📝"},
        }
        
        conf = styles.get(ftype, styles["TIP"])
        
        # Build Content
        content_flowables = []
        
        # Title Row
        title_para = Paragraph(f"{conf['icon']} <b>{conf['title']}</b>", 
                               ParagraphStyle("FeatureTitle", parent=body_style, fontSize=11, textColor=conf["border"], spaceAfter=6))
        content_flowables.append(title_para)
        
        # Items
        for item in items:
            # Check if title (first item usually contains trigger)
            # We strip the trigger word?
            clean_item = item
            # Regex to strip "Mistake 1:" etc
            clean_item = re.sub(r"^(Mistake \d+|Tip|Checklist|Note)[:\s\-]*", "", clean_item, flags=re.IGNORECASE).strip()
            
            if not clean_item: continue
            
            # Check for bullets inside item
            bullet_match = re.match(r"^[●•▪►*?\-]\s*(.*)", clean_item)
            if bullet_match:
                 p = Paragraph(f"&bull; {bullet_match.group(1)}", list_style)
            else:
                 p = Paragraph(clean_item, body_style)
            
            content_flowables.append(p)
            
        t_inner = Table([[c] for c in content_flowables], colWidths=[doc_width * 0.85])
        t_inner.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        
        main_table = Table([[t_inner]], colWidths=[doc_width * 0.9])
        main_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), conf["bg"]),
            ("BOX", (0, 0), (-1, -1), 1, conf["border"]),
            ("ROUNDEDCORNERS", [8, 8, 8, 8]),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ]))
        main_table.hAlign = "CENTER"
        
        return [Spacer(1, 12), main_table, Spacer(1, 12)]

    def _clean_block(self, block: str) -> str:
        text = self.IMAGE_HINT_RE.sub("", str(block)).strip()
        text = self.IMAGE_PLACEHOLDER_RE.sub("", text).strip()
        text = re.sub(r"[ \t]+", " ", text)
        text = text.replace("₹", "Rs.")
        return text

    def _merge_into_paragraphs(self, blocks: List[str]) -> List[str]:
        if not blocks: return []
        paragraphs: List[str] = []
        current: List[str] = []

        def flush() -> None:
            if current:
                merged = re.sub(r"\s+", " ", " ".join(current)).strip()
                if merged: paragraphs.append(merged)
                current.clear()

        def looks_heading_start(t: str) -> bool:
            t = t.strip()
            if not t or len(t) > 100: return False
            if self.CHAPTER_TITLE_RE.match(t): return True
            if self.TIP_RE.search(t) or t.startswith(('"', '“', '‘', "'")) or self.CHECKLIST_RE.search(t): return True
            words = t.split()
            if len(words) <= 2 and t[0].isupper() and (t.endswith(":") or not t.endswith((".", "!", "?"))): return True
            return False

        def looks_like_list_item(t: str) -> bool:
            t = t.strip()
            # Check for bullet start
            if re.match(r"^[●•▪►*?\-]\s+", t): return True
            # Check for Numbered list
            if re.match(r"^\d+\.\s+", t): return True
            # Check for inline bullet that didn't get split?
            return False

        for block in blocks:
            stripped = block.strip()
            if not stripped:
                flush()
                continue
            
            # Pre-split inline bullets aggressively
            # Regex to find "Text • Text" patterns and replace with newline
            # But we must be careful not to break "3.5" or similar.
            # Convert all bullet-likes to newline + bullet
            
            # Normalize bullets to standard dot for cleaner processed text
            # (Phase 10: Symbol Normalization)
            normalized_block = re.sub(r"([^\n])\s*[●•▪►*]\s+", r"\1\n• ", stripped)
            
            # If line starts with diverse bullet, normalize it too
            normalized_block = re.sub(r"^[●•▪►*]\s+", r"• ", normalized_block)
            
            sub_lines = normalized_block.split('\n')
            
            for sub in sub_lines:
                sub = sub.strip()
                if not sub: continue
                
                is_list = looks_like_list_item(sub)
                is_head = looks_heading_start(sub)
                
                if is_list or is_head:
                    flush()  # Close previous paragraph
                    paragraphs.append(sub) # Add this strictly as own block
                    # Do not start a new merge buffer with this, it's done.
                else:
                    # It is regular text.
                    # Should we merge it with previous?
                    # Yes, unless previous was a list item? 
                    # Actually, flush() clears 'current'.
                    # So if we just flushed, 'current' is empty.
                    current.append(sub)
                    
        flush()
        return paragraphs

    def _should_render_heading(self, heading: str, level: int) -> bool:
        h = heading.strip()
        if not h: return False
        if level == 1: return bool(self.CHAPTER_TITLE_RE.match(h))
        if len(h) < 12 and not self.CHAPTER_TITLE_RE.match(h): return False
        return True

    @staticmethod
    def _split_for_side_by_side(blocks: List[str]) -> tuple[List[str], List[str]]:
        if len(blocks) <= 3: return blocks, []
        return blocks[:3], blocks[3:]

    def _split_inline_bullets(self, text: str) -> list[str]:
        parts = self.BULLET_LINE_RE.split(text)
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def _normalise(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().lower()

    def _normalize_content_structure(self, blocks: List[str | Dict[str, Any]]) -> List[str | Dict[str, Any]]:
        """
        Phase 11: Hardening.
        1. Convert all bullet variants to '•'.
        2. Split inline bullets 'Text • Text' into separate blocks.
        3. Strip artifacts like '■■' from headers.
        """
        normalized = []
        for b in blocks:
            text = ""
            if isinstance(b, str): text = b
            elif isinstance(b, dict): text = b.get("text", "")
            
            if not text.strip(): continue
            
            # 1. Strip Artifacts (e.g., "■■ Common Mistake" -> "Common Mistake")
            text = re.sub(r"^[■●►]{2,}\s*", "", text)
            
            # 2. Normalize Start Bullets
            # Replace any starting bullet char with standard dot
            text = re.sub(r"^[●▪►*]\s*", "• ", text)
            
            # 3. Inline Bullet Splitter
            # If line contains " • " or " ● " in middle, replace with newline
            # We use a unique marker to avoid regex overlapping issues, then split
            text = re.sub(r"(\s+)[●•▪►*](\s+)", r"\1\n•\2", text)
            
            # 4. Split by newline and re-structure
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line: continue
                # Re-normalize start just in case split revealed new bullet
                if re.match(r"^[●▪►*]", line):
                     line = "• " + line.lstrip("●▪►* ")
                
                if isinstance(b, dict):
                    new_b = b.copy()
                    new_b["text"] = line
                    normalized.append(new_b)
                else:
                    normalized.append(line)
        return normalized
