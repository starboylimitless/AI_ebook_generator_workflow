from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ebook_generator_workflow.agents.base_agent import BaseAgent


class DocumentNormalizerAgent(BaseAgent):
    """
    Agent responsible for normalizing raw extracted text and metadata into a 
    clean, structured ebook format with clear front matter and chapter hierarchy.
    """

    OUTPUT_FILE = "normalized_document.json"

    def run(
        self,
        structured_document: Dict[str, Any],
        aligned_layout: Dict[str, Any],
        image_plan: Dict[str, Any],
    ) -> Path:
        """
        Runs the normalization process using the LLM to intelligently 
        restructure the document.
        """

        def _execute() -> Dict[str, Any]:
            user_prompt = json.dumps(
                {
                    "structured_document": structured_document,
                    "aligned_layout": aligned_layout,
                    "image_plan": image_plan,
                },
                indent=2,
            )

            # Call LLM with the normalization prompt
            result = self._call_llm_json("document_normalizer_agent.txt", user_prompt)
            return result

        # Run with retries and save output
        normalized_data = self._run_with_retries(_execute, "DocumentNormalizerAgent")
        return self._save_json(normalized_data, self.OUTPUT_FILE)

    def validate(self, result: Dict[str, Any]) -> None:
        """
        Validates the normalized document schema.
        """
        required_fields = ["front_matter", "chapters"]
        self._require_fields(result, required_fields)

        if not isinstance(result["chapters"], list):
            raise ValueError("Field 'chapters' must be a list")

        # Basic depth check: ensure chapters have titles
        for chapter in result["chapters"]:
            if "title" not in chapter:
                raise ValueError("Each chapter must have a 'title'")
