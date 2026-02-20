from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ebook_generator_workflow.agents.base_agent import BaseAgent
from ebook_generator_workflow.utils.logging_utils import setup_logger


class ImageSemanticAgent(BaseAgent):
    """Generates semantic image hooks by analyzing document content.

    Identifies high-value visual opportunities like diagrams, and mockups.
    """

    OUTPUT_FILE = "image_hooks.json"

    def __init__(self, name: str, prompts_dir: Path, output_dir: Path, *args: Any, **kwargs: Any) -> None:
        super().__init__(name=name, prompts_dir=prompts_dir, output_dir=output_dir, *args, **kwargs)
        self.logger = setup_logger("agent.image_semantic")

    def run(self, structured_document: Dict[str, Any]) -> Path:
        def _execute() -> Dict[str, Any]:
            data = self._call_llm_json(
                prompt_file="image_semantic_agent.txt",
                user_prompt=f"DOCUMENT CONTENT (JSON):\n{json.dumps(structured_document, indent=2)}"
            )
            return data

        result = self._run_with_retries(_execute, "ImageSemanticAgent")
        return self._save_json(result, self.OUTPUT_FILE)

    def validate(self, result: Any) -> None:
        if not isinstance(result, dict) or "hooks" not in result:
            raise ValueError("ImageSemanticAgent output must contain 'hooks' list")
