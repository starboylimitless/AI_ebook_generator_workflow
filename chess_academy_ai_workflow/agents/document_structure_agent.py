from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from chess_academy_ai_workflow.agents.base_agent import BaseAgent
from chess_academy_ai_workflow.utils.pdf_utils import PageText


@dataclass
class Section:
    id: str
    title: str
    start_page: int
    end_page: int
    level: int


@dataclass
class StructuredDocument:
    document_title: str
    chapters: List[Section]
    sections: List[Section]
    pages: List[Dict[str, Any]]


class DocumentStructureAgent(BaseAgent):
    OUTPUT_FILE = "structured_document.json"
    SOURCE_TOC_RE = re.compile(r"^Table\s+of\s+Contents\b", re.IGNORECASE)
    CHAPTER_RE = re.compile(
        r"^(Chapter|Part)\s+(\d+|[IVXLC]+)\s*:?\s+.+$",
        re.IGNORECASE,
    )
    BULLET_PREFIX_RE = re.compile(r"^[\-\*\u2022\u25AA\u25CF\u25BA]|^[^A-Za-z0-9]*[A-Za-z0-9]?\)")
    IMAGE_HINT_RE = re.compile(r"\[\s*.*?Image:.*?\]", re.IGNORECASE)
    BAD_HEADING_RE = re.compile(r"(www\.|http|@|mailto:)", re.IGNORECASE)
    EXCLUDED_HEADINGS = {"without:"}
    BULLET_TOKEN_RE = re.compile(r"(?:^|\s)(?:\u2022|â—)\s+")

    def run(self, pages: List[PageText], document_title: str) -> Path:
        def _execute() -> StructuredDocument:
            chapters: List[Section] = []
            sections: List[Section] = []
            page_payload: List[Dict[str, Any]] = []

            chapter_index = 0
            section_index = 0
            current_chapter_id = "front_matter"
            current_section_id = "section_0"
            current_heading = ""
            current_heading_level = 0

            for page in pages:
                blocks = self._split_blocks(page.text)
                if not blocks:
                    continue

                if self.SOURCE_TOC_RE.match(blocks[0].strip()):
                    self.logger.info("Skipping source TOC page %s", page.page_number)
                    continue

                chapter_heading, chapter_heading_blocks = self._detect_chapter_heading(blocks)
                heading = ""
                heading_level = 0

                if chapter_heading:
                    chapter_index += 1
                    section_index += 1
                    current_chapter_id = f"chapter_{chapter_index}"
                    current_section_id = f"section_{section_index}"
                    heading = chapter_heading
                    heading_level = 1

                    chapters.append(
                        Section(
                            id=current_chapter_id,
                            title=heading,
                            start_page=page.page_number,
                            end_page=page.page_number,
                            level=1,
                        )
                    )
                    sections.append(
                        Section(
                            id=current_section_id,
                            title=heading,
                            start_page=page.page_number,
                            end_page=page.page_number,
                            level=2,
                        )
                    )
                else:
                    section_heading, section_level = self._detect_section_heading(blocks)
                    if section_heading:
                        section_index += 1
                        current_section_id = f"section_{section_index}"
                        heading = section_heading
                        heading_level = section_level
                        sections.append(
                            Section(
                                id=current_section_id,
                                title=heading,
                                start_page=page.page_number,
                                end_page=page.page_number,
                                level=section_level,
                            )
                        )

                if chapter_heading_blocks:
                    blocks = blocks[chapter_heading_blocks:]
                elif heading:
                    blocks = self._strip_leading_heading(blocks, heading)

                # Keep front-matter pages attached to a synthetic chapter id, but do not
                # create an H1 chapter entry unless explicitly marked in source text.
                if chapter_index == 0:
                    current_chapter_id = "front_matter"

                current_heading = heading
                current_heading_level = heading_level

                page_payload.append(
                    {
                        "page_number": page.page_number,
                        "chapter_id": current_chapter_id,
                        "section_id": current_section_id,
                        "heading": current_heading or None,
                        "heading_level": current_heading_level,
                        "content_blocks": blocks,
                        "raw_text": page.text,
                    }
                )

            self._extend_ranges(chapters, page_payload, "chapter_id")
            self._extend_ranges(sections, page_payload, "section_id")

            return StructuredDocument(
                document_title=document_title,
                chapters=chapters,
                sections=sections,
                pages=page_payload,
            )

        structured = self._run_with_retries(_execute, description="DocumentStructureAgent")
        return self._save_json(asdict(structured), self.OUTPUT_FILE)

    def validate(self, result: StructuredDocument | Any) -> None:
        if isinstance(result, dict):
            pages = result.get("pages", [])
            title = result.get("document_title", "")
        else:
            pages = result.pages
            title = result.document_title

        if not title:
            raise ValueError("document_title is required")
        if not pages:
            raise ValueError("Structured document must contain pages")

    def _split_blocks(self, text: str) -> List[str]:
        text = re.sub(r"[ \t]+", " ", text)
        blocks = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        return self._coalesce_blocks(blocks)

    def _detect_chapter_heading(self, blocks: List[str]) -> tuple[str | None, int]:
        if not blocks:
            return None, 0

        first = self._clean_heading_candidate(blocks[0])
        if not first:
            return None, 0
        if not re.match(r"^(Chapter|Part)\s+(\d+|[IVXLC]+)\b", first, flags=re.IGNORECASE):
            return None, 0

        # Only use the first block as the heading. Do NOT merge continuation
        # blocks — they are body text and should stay separate.
        candidate = self._clean_heading_candidate(first)
        # Trim heading at first sentence boundary to avoid body text leaking in
        candidate = self._trim_heading_at_sentence_end(candidate)
        if self.CHAPTER_RE.match(candidate):
            return candidate, 1
        return None, 0

    def _detect_section_heading(self, blocks: List[str]) -> tuple[str | None, int]:
        # Conservative: only promote clear section-like headings.
        for block in blocks[:3]:
            candidate = self._clean_heading_candidate(block)
            if not candidate:
                continue
            if not self._is_valid_section_heading(candidate):
                continue
            level = 3 if self._is_subsection_heading(candidate) else 2
            return candidate, level
        return None, 0

    # Words that almost always start a new body sentence, not a heading phrase.
    _BODY_START_WORDS = re.compile(
        r'\b(?:If|One|Many|By|You|We|This|That|When|So|But|And|Or|Most|'
        r'Some|However|Whether|Running|People|Everyone|For|Let|Think|'
        r'Here|Now|Once|What|Why|How|Because|It|They|She|He|Our|Your|'
        r'In|On|At|The|A|An|As|Do|Did|Has|Have|Had|Are|Is|Was|Were|'
        r'Not|No|From|To|With|About|After|Before|During|Until|Since)\b',
    )

    def _trim_heading_at_sentence_end(self, heading: str) -> str:
        """Stop heading text at the first complete sentence boundary
        or where body text clearly begins after the title phrase."""
        # 1. Broad sentence-end boundary: ". " / "! " / "? " 
        m = re.search(r'[.!?]\s+[A-Z]', heading)
        if m:
            return heading[:m.start()+1].strip()

        # 2. Detect body-text continuation after the "Chapter N: Title" part.
        colon = heading.find(':')
        # Start searching for body words after the colon + initial title part (at least 15 chars)
        search_start = (colon + 15) if colon != -1 else 20
        
        if search_start < len(heading):
            # Look for common body-starting words that are likely not part of a title
            body_m = self._BODY_START_WORDS.search(heading, search_start)
            if body_m:
                # If we found a body word, check if there's a space or boundary before it
                return heading[:body_m.start()].strip()

        return heading

    def _clean_heading_candidate(self, value: str) -> str:
        cleaned = self.IMAGE_HINT_RE.sub("", value).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    def _strip_leading_heading(self, blocks: List[str], heading: str) -> List[str]:
        if not blocks:
            return blocks
        first = self._clean_heading_candidate(blocks[0])
        if first and self._normalise(first).startswith(self._normalise(heading)):
            return blocks[1:]
        return blocks

    def _is_valid_section_heading(self, text: str) -> bool:
        norm = text.strip()
        if not norm:
            return False
        if norm.lower() in self.EXCLUDED_HEADINGS:
            return False
        if "•" in norm or "â—" in norm:
            return False
        if self.CHAPTER_RE.match(norm):
            return False
        if self.BULLET_PREFIX_RE.match(norm):
            return False
        if self.BAD_HEADING_RE.search(norm):
            return False
        if len(norm) < 12 or len(norm) > 90:
            return False
        if norm.endswith((".", "!", "?")):
            return False

        words = re.findall(r"[A-Za-z][A-Za-z'\-]*", norm)
        if len(words) < 3:
            return False
        # Reject likely body sentences.
        lower_ratio = sum(1 for w in words if w.islower()) / max(1, len(words))
        if lower_ratio > 0.75:
            return False
        # Reject headings that are mostly single-token fragments.
        if len(words) <= 3 and norm.endswith(":"):
            return False
        return True

    @staticmethod
    def _is_subsection_heading(text: str) -> bool:
        return bool(re.match(r"^([A-Z]\.|[0-9]+\.)\s+", text))

    @staticmethod
    def _normalise(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().lower()

    def _coalesce_blocks(self, blocks: List[str]) -> List[str]:
        merged: List[str] = []
        for raw in blocks:
            block = re.sub(r"[ \t]+", " ", raw).strip()
            if not block:
                continue
            if not merged:
                merged.append(block)
                continue

            # Keep bullet blocks and chapter labels explicit.
            if self.BULLET_TOKEN_RE.search(block) or self.CHAPTER_RE.match(block):
                merged.append(block)
                continue

            # Keep blocks that start with common bullet symbols separate.
            if block.lstrip().startswith(("●", "•", "▪", "►", "-", "*")):
                merged.append(block)
                continue

            word_count = len(block.split())
            prev = merged[-1]
            prev_ends_sentence = bool(re.search(r"[.!?:\"]\s*$", prev))

            # Join short extraction fragments into the previous paragraph.
            if word_count <= 3:
                merged[-1] = f"{prev} {block}".strip()
                continue

            # If previous block is not sentence-complete, this is likely continuation.
            if not prev_ends_sentence and not self.BULLET_TOKEN_RE.search(prev):
                merged[-1] = f"{prev} {block}".strip()
                continue

            merged.append(block)
        return merged

    @staticmethod
    def _extend_ranges(items: List[Section], pages: List[Dict[str, Any]], page_key: str) -> None:
        by_id: Dict[str, List[int]] = {}
        for page in pages:
            entity_id = page.get(page_key)
            if entity_id:
                by_id.setdefault(entity_id, []).append(page["page_number"])

        for item in items:
            mapped = by_id.get(item.id, [item.start_page])
            item.start_page = min(mapped)
            item.end_page = max(mapped)
