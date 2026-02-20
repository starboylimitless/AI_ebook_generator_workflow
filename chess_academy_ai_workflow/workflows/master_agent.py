from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from chess_academy_ai_workflow.agents.alignment_agent import AlignmentAgent
from chess_academy_ai_workflow.agents.chess_image_agent import ChessImageAgent
from chess_academy_ai_workflow.agents.document_normalizer_agent import DocumentNormalizerAgent
from chess_academy_ai_workflow.agents.document_structure_agent import DocumentStructureAgent
from chess_academy_ai_workflow.agents.fal_image_agent import FalImageAgent
from chess_academy_ai_workflow.agents.final_optimization_agent import FinalOptimizationAgent
from chess_academy_ai_workflow.agents.image_semantic_agent import ImageSemanticAgent
from chess_academy_ai_workflow.agents.style_consistency_agent import StyleConsistencyAgent
from chess_academy_ai_workflow.agents.visual_layout_agent import VisualLayoutAgent
from chess_academy_ai_workflow.utils.logging_utils import setup_logger
from chess_academy_ai_workflow.utils.pdf_utils import (
    extract_pdf_title,
    extract_reference_layout,
    extract_text_pages,
    load_json,
    save_json,
)


class MasterAgent:
    def __init__(
        self,
        base_dir: Path,
        input_files: Dict[str, Path],
        output_dir: Path,
        prompts_dir: Path,
        debug_mode: bool = True,
        max_pages: int = 500,
        safe_credit_mode: bool = False,
        openai_key: str | None = None,
    ) -> None:
        self.base_dir = base_dir
        self.input_files = input_files
        self.output_dir = output_dir
        self.prompts_dir = prompts_dir
        self.debug_mode = debug_mode
        self.max_pages = max_pages
        self.safe_credit_mode = safe_credit_mode
        self.logger = setup_logger("workflow.master_agent")

        self.document_structure_agent = DocumentStructureAgent("document_structure_agent", prompts_dir, output_dir)
        self.visual_layout_agent = VisualLayoutAgent("visual_layout_agent", prompts_dir, output_dir)
        self.image_semantic_agent = ImageSemanticAgent("image_semantic_agent", prompts_dir, output_dir)
        self.chess_image_agent = ChessImageAgent("chess_image_agent", prompts_dir, output_dir)
        self.fal_image_agent = FalImageAgent("fal_image_agent", prompts_dir, output_dir, api_key=os.environ.get("FAL_KEY"))
        self.alignment_agent = AlignmentAgent("alignment_agent", prompts_dir, output_dir)
        self.style_agent = StyleConsistencyAgent("style_consistency_agent", prompts_dir, output_dir)
        self.document_normalizer_agent = DocumentNormalizerAgent("document_normalizer_agent", prompts_dir, output_dir)
        self.final_agent = FinalOptimizationAgent(prompts_dir, output_dir)

    def _cross_verify_with_reference(self, aligned_layout: Dict[str, Any], reference_layout: Any) -> Dict[str, Any]:
        pages = aligned_layout.get("pages", [])
        # Loosen limit significantly to avoid trapping legitimate longer ebooks
        limit = 500 
        if len(pages) > limit:
            self.logger.warning("Page explosion detected (%s). Trimming to %s", len(pages), limit)
            aligned_layout["pages"] = pages[:limit]
        return aligned_layout

    def _debug_dump(self, stage: str, payload: Dict[str, Any]) -> None:
        if not self.debug_mode:
            return
        path = self.output_dir / f"debug_{stage}.json"
        save_json(payload, path)
        pages = len(payload.get("pages", [])) if isinstance(payload, dict) else 0
        print(f"[debug] {stage}: pages={pages} -> {path}")

    def run(self) -> Dict[str, Any]:
        self.logger.info("MasterAgent starting production ebook pipeline with quality verification loop")

        pages = extract_text_pages(self.input_files["ebook_ads"])[: self.max_pages]
        reference_layout = extract_reference_layout(self.input_files["next_move_reference"])
        original_title = extract_pdf_title(self.input_files["ebook_ads"], pages)

        max_attempts = 3
        last_result: Dict[str, Any] = {}
        verification_passed = False
        attempts_used = 0

        for attempt in range(1, max_attempts + 1):
            self.logger.info("Pipeline Attempt %s/%s", attempt, max_attempts)
            attempts_used = attempt

            # 1. Document Structure
            structured_path = self.output_dir / self.document_structure_agent.OUTPUT_FILE
            if self.safe_credit_mode and structured_path.exists():
                self.logger.info("Safe Credit Mode: Skipping DocumentStructureAgent, using %s", structured_path)
            else:
                structured_path = self.document_structure_agent.run(pages=pages, document_title=original_title)
            
            structured_document = load_json(structured_path)
            self._debug_dump("01_structure", structured_document)
            
            # 2. Visual Layout
            layout_path = self.output_dir / self.visual_layout_agent.OUTPUT_FILE
            if self.safe_credit_mode and layout_path.exists():
                self.logger.info("Safe Credit Mode: Skipping VisualLayoutAgent, using %s", layout_path)
            else:
                layout_path = self.visual_layout_agent.run(reference_layout)
            
            layout_structure = load_json(layout_path)
            self._debug_dump("02_layout", layout_structure)
            
            # 3. Image Semantic Hooks
            hooks_path = self.output_dir / self.image_semantic_agent.OUTPUT_FILE
            if self.safe_credit_mode and hooks_path.exists():
                self.logger.info("Safe Credit Mode: Skipping ImageSemanticAgent, using %s", hooks_path)
            else:
                hooks_path = self.image_semantic_agent.run(structured_document)
            
            image_hooks = load_json(hooks_path)
            self._debug_dump("03_hooks", image_hooks)
            
            # 4. Image Planning
            image_path = self.output_dir / self.chess_image_agent.OUTPUT_FILE
            if self.safe_credit_mode and image_path.exists():
                self.logger.info("Safe Credit Mode: Skipping ChessImageAgent, using %s", image_path)
            else:
                image_path = self.chess_image_agent.run(structured_document, image_hooks)
            
            image_plan = load_json(image_path)
            self._debug_dump("04_images", image_plan)
            
            # 4.1 Fal.ai Image Generation
            image_path = self.fal_image_agent.run(image_plan)
            image_plan = load_json(image_path)
            self._debug_dump("04_fal_gen", image_plan)
            
            # 5. Alignment
            aligned_path = self.output_dir / self.alignment_agent.OUTPUT_FILE
            if self.safe_credit_mode and aligned_path.exists():
                self.logger.info("Safe Credit Mode: Skipping AlignmentAgent, using %s", aligned_path)
            else:
                aligned_path = self.alignment_agent.run(structured_document, layout_structure, image_plan)
            
            aligned_layout = load_json(aligned_path)
            aligned_layout = self._cross_verify_with_reference(aligned_layout, reference_layout)
            self._debug_dump("05_alignment", aligned_layout)
            
            # 6. Style Consistency
            style_path = self.output_dir / self.style_agent.OUTPUT_FILE
            if self.safe_credit_mode and style_path.exists():
                self.logger.info("Safe Credit Mode: Skipping StyleConsistencyAgent, using %s", style_path)
            else:
                style_path = self.style_agent.run(
                    reference_layout_info={
                        "page_width": reference_layout.page_width,
                        "page_height": reference_layout.page_height,
                        "page_count": reference_layout.page_count,
                    },
                    layout_structure=layout_structure,
                    aligned_layout={"pages": [{"page_number": p["page_number"]} for p in aligned_layout.get("pages", [])]},
                )
            
            style_spec = load_json(style_path)
            self._debug_dump("06_style", style_spec)
            
            # 7. Normalization
            normalized_path = self.output_dir / self.document_normalizer_agent.OUTPUT_FILE
            if self.safe_credit_mode and normalized_path.exists():
                self.logger.info("Safe Credit Mode: Skipping DocumentNormalizerAgent, using %s", normalized_path)
            else:
                normalized_path = self.document_normalizer_agent.run(
                    structured_document=structured_document,
                    aligned_layout=aligned_layout,
                    image_plan=image_plan,
                )
            
            normalized_document = load_json(normalized_path)
            self._debug_dump("07_normalization", normalized_document)

            final_paths = self.final_agent.run(
                structured_document=structured_document,
                aligned_layout=aligned_layout,
                style_spec=style_spec,
                layout_structure=layout_structure,
                image_placement=image_plan,
                reference_layout_info={
                    "page_width": reference_layout.page_width,
                    "page_height": reference_layout.page_height,
                    "page_count": reference_layout.page_count,
                },
                original_title=original_title,
                normalized_document=normalized_document,
            )

            last_result = {
                "structured_document": structured_path,
                "layout_structure": layout_path,
                "image_placement": image_path,
                "aligned_layout": aligned_path,
                "style_spec": style_path,
                "normalized_document": normalized_path,
                "final_metadata": final_paths["metadata"],
                "final_pdf": final_paths["pdf"],
            }

            if self._verify_output_quality(last_result):
                self.logger.info("Quality verification passed on attempt %s", attempt)
                verification_passed = True
                break
            self.logger.warning("Quality verification FAILED on attempt %s. Retrying...", attempt)

        self.logger.info("MasterAgent completed successfully")
        last_result["success"] = verification_passed
        last_result["verification_attempts"] = attempts_used
        return last_result

    def _verify_output_quality(self, result: Dict[str, Any]) -> bool:
        try:
            struct = load_json(result["structured_document"])
            meta = load_json(result["final_metadata"])
            aligned = load_json(result["aligned_layout"])

            chapters = struct.get("chapters", [])
            if len(chapters) < 2:
                self.logger.warning("Verification Fail: Too few chapters detected (%s)", len(chapters))
                return False

            toc = meta.get("table_of_contents", [])
            if not toc:
                self.logger.warning("Verification Fail: Table of Contents is empty")
                return False

            for entry in toc:
                if len(str(entry).strip()) < 4:
                    self.logger.warning("Verification Fail: TOC entry too short/junk: %s", entry)
                    return False

            valid_layout_types = {
                "full_width_text",
                "image_left_text_right",
                "image_right_text_left",
                "image_full_width",
            }
            for page in aligned.get("pages", []):
                layout_type = page.get("layout_type")
                images = page.get("images", [])
                body_blocks = page.get("body_blocks", [])
                if layout_type not in valid_layout_types:
                    self.logger.warning("Verification Fail: Invalid layout type on page %s", page.get("page_number"))
                    return False
                if layout_type == "image_full_width" and body_blocks:
                    self.logger.warning("Verification Fail: image_full_width has body text on page %s", page.get("page_number"))
                    return False
                if layout_type in {"image_left_text_right", "image_right_text_left"} and (not images or not body_blocks):
                    self.logger.warning("Verification Fail: side-by-side layout missing text/image on page %s", page.get("page_number"))
                    return False

            pages = struct.get("pages", [])
            if not pages:
                self.logger.warning("Verification Fail: Structured document missing pages")
                return False

            first_three_chapters = chapters[:3]
            if not first_three_chapters:
                self.logger.warning("Verification Fail: Missing first three chapters metadata")
                return False

            chapter_ids = {c.get("id") for c in first_three_chapters if c.get("id")}
            page_by_number = {p.get("page_number"): p for p in pages if p.get("page_number") is not None}
            aligned_by_number = {p.get("page_number"): p for p in aligned.get("pages", []) if p.get("page_number") is not None}

            doc_title_norm = str(struct.get("document_title", "")).strip().lower()
            for chap in first_three_chapters:
                chap_id = chap.get("id")
                title = str(chap.get("title", "")).strip()
                level = chap.get("level")
                if level != 1:
                    self.logger.warning("Verification Fail: Chapter %s has non-level-1 heading", chap_id)
                    return False
                if title and title.lower() != doc_title_norm and not any(title in str(entry) for entry in toc):
                    self.logger.warning("Verification Fail: Chapter title not reflected in TOC: %s", title)
                    return False

            for chap in first_three_chapters:
                start_page = chap.get("start_page")
                end_page = chap.get("end_page")
                if start_page is None or end_page is None:
                    continue
                for page_number in range(start_page, end_page + 1):
                    a_page = aligned_by_number.get(page_number)
                    if not a_page:
                        continue
                    has_heading = bool(str(a_page.get("heading", "")).strip())
                    has_body = bool(a_page.get("body_blocks"))
                    if has_heading and not has_body:
                        self.logger.warning("Verification Fail: Heading without adjacent body text on page %s", page_number)
                        return False

            for p in aligned.get("pages", []):
                if p.get("page_number") not in page_by_number:
                    continue
                src_page = page_by_number[p["page_number"]]
                if src_page.get("chapter_id") not in chapter_ids:
                    continue
                if p.get("images") and not p.get("body_blocks"):
                    self.logger.warning("Verification Fail: Image without nearby text context on page %s", p["page_number"])
                    return False

            return True
        except Exception as e:
            self.logger.error("Error during verification: %s", e)
            return False
