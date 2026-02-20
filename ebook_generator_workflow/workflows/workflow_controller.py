from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from ebook_generator_workflow.utils.logging_utils import setup_logger
from ebook_generator_workflow.utils.pdf_utils import check_input_files, ensure_directories, save_json
from ebook_generator_workflow.workflows.master_agent import MasterAgent


@dataclass
class WorkflowResult:
    structured_document: str
    layout_structure: str
    image_placement: str
    aligned_layout: str
    style_spec: str
    final_metadata: str
    final_pdf: str
    success: bool
    verification_attempts: int


class WorkflowController:
    def __init__(self) -> None:
        self.paths = ensure_directories()
        self.logger = setup_logger("workflow.controller")

    def run(self) -> WorkflowResult:
        self.logger.info("Initializing workflow controller")
        
        # Load environment variables from .env if possible
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        input_files = check_input_files(self.paths["input"])

        debug_mode = os.getenv("WORKFLOW_DEBUG", "1") == "1"
        max_pages = int(os.getenv("WORKFLOW_MAX_PAGES", "999"))
        safe_mode = os.getenv("SAFE_CREDIT_MODE", "0") == "1"
        openai_key = os.getenv("OPENAI_API_KEY")

        master = MasterAgent(
            base_dir=self.paths["base"],
            input_files=input_files,
            output_dir=self.paths["output"],
            prompts_dir=self.paths["prompts"],
            debug_mode=debug_mode,
            max_pages=max_pages,
            safe_credit_mode=safe_mode,
            openai_key=openai_key,
        )

        outputs = master.run()

        result = WorkflowResult(
            structured_document=str(outputs["structured_document"]),
            layout_structure=str(outputs["layout_structure"]),
            image_placement=str(outputs["image_placement"]),
            aligned_layout=str(outputs["aligned_layout"]),
            style_spec=str(outputs["style_spec"]),
            final_metadata=str(outputs["final_metadata"]),
            final_pdf=str(outputs["final_pdf"]),
            success=bool(outputs.get("success", True)),
            verification_attempts=int(outputs.get("verification_attempts", 1)),
        )

        summary_path = self.paths["output"] / "workflow_result_summary.json"
        save_json(asdict(result), summary_path)
        self.logger.info("Workflow completed successfully")
        return result
