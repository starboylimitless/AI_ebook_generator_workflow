from __future__ import annotations

import os
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

from chess_academy_ai_workflow.agents.base_agent import BaseAgent
from chess_academy_ai_workflow.utils.fal_image_client import FalImageClient


class FalImageAgent(BaseAgent):
    """
    Agent that generates images using Fal.ai (Flux) for planned image slots.
    """

    OUTPUT_FILE = "image_placement.json"

    def __init__(self, name: str, prompts_dir: Path, output_dir: Path, api_key: str | None = None) -> None:
        super().__init__(name, prompts_dir, output_dir)
        self.api_key = api_key or os.environ.get("FAL_KEY")
        if not self.api_key:
            self.logger.warning("FAL_KEY not set. FalImageAgent will skip generation.")
            self.client = None
        else:
            self.client = FalImageClient(self.api_key)

    def run(self, image_placement: Dict[str, Any]) -> Path:
        def _execute() -> Dict[str, Any]:
            if not self.client:
                self.logger.warning("FAL_KEY missing. Skipping image generation.")
                return image_placement

            pages = image_placement.get("pages", [])
            for page in pages:
                images = page.get("images", [])
                for img in images:
                    if img.get("render_status") in ["planned", "failed"]:
                        prompt = img.get("description", "Conceptual Illustration")
                        
                        # CACHE CHECK: If file already exists in output, just use it
                        filename = f"fal_{abs(hash(prompt))}.png"
                        target_path = self.output_dir / filename
                        
                        if target_path.exists():
                            self.logger.info("Using cached Fal image for slot %s", img.get("slot_id"))
                            img["render_status"] = "rendered"
                            img["local_path"] = str(target_path)
                            continue

                        self.logger.info("Generating Fal image for slot %s: %s", img.get("slot_id"), prompt)
                        
                        try:
                            # Use Fal client to generate image
                            image_path = self.client.generate_image(prompt)
                            
                            # Move generated image to output directory for consistency
                            gen_path = Path(image_path)
                            
                            # Handle potential collision on Windows
                            if target_path.exists():
                                target_path.unlink()
                            
                            shutil.move(str(gen_path), str(target_path))
                            
                            # Update slot metadata
                            img["render_status"] = "rendered"
                            img["local_path"] = str(target_path)
                            self.logger.info("Successfully generated Fal image and saved to %s", target_path)
                        except Exception as e:
                            self.logger.error("Failed to generate Fal image for %s: %s", img.get("slot_id"), e)
                            img["render_status"] = "failed"

            return image_placement

        result = self._run_with_retries(_execute, "FalImageAgent")
        return self._save_json(result, self.OUTPUT_FILE)

    def validate(self, result: Any) -> None:
        if not isinstance(result, dict) or not result.get("pages"):
            raise ValueError("FalImageAgent result must contain pages")
