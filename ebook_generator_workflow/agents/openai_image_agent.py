from __future__ import annotations

import os
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

from ebook_generator_workflow.agents.base_agent import BaseAgent
from ebook_generator_workflow.utils.openai_image_client import OpenAIImageClient


class OpenAIImageAgent(BaseAgent):
    """
    Agent that generates images using OpenAI DALL-E 3 for planned image slots.
    """

    OUTPUT_FILE = "image_placement.json"

    def __init__(self, name: str, prompts_dir: Path, output_dir: Path, api_key: str | None = None) -> None:
        super().__init__(name, prompts_dir, output_dir)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            self.logger.warning("OPENAI_API_KEY not set. OpenAIImageAgent will skip generation.")
            self.client = None
        else:
            self.client = OpenAIImageClient(self.api_key)

    def run(self, image_placement: Dict[str, Any]) -> Path:
        def _execute() -> Dict[str, Any]:
            if not self.client:
                self.logger.warning("OPENAI_API_KEY missing. Skipping image generation.")
                return image_placement

            # PHASE 9: PROMPT OVERRIDES FOR WEAK IMAGES (Preserved from Fal implementation)
            PROMPT_OVERRIDES = {
                "page33_semantic1": "Professional infographic of a daily ad budget plan (300-500 INR), clean modern minimalist design, vector style, white background, high resolution.",
                "page39_semantic1": "Photorealistic mobile phone mockup showing a WhatsApp chat screen with 'Chess Academy' contact, quick replies, clean UI, high quality product photography.",
                "page46_semantic1": "High fidelity dashboard UI mockup on a laptop screen, dark mode, showing 'Ad Performance' graphs and 'Cost Per Lead' metrics, futuristic clean interface, 8k resolution.",
                "page53_semantic1": "Professional business process flowchart, 'Common Mistakes' diagram with red warning icons and clear arrows, modern corporate flat design, white background.",
            }

            pages = image_placement.get("pages", [])
            for page in pages:
                images = page.get("images", [])
                for img in images:
                    slot_id = img.get("slot_id")
                    
                    # Force override if matches
                    if slot_id in PROMPT_OVERRIDES:
                        img["description"] = PROMPT_OVERRIDES[slot_id]

                    if img.get("render_status") in ["planned", "failed"]:
                        prompt = img.get("description", "Conceptual Illustration")
                        
                        # CACHE CHECK: If file already exists in output, just use it
                        filename = f"oa_{abs(hash(prompt))}.png"
                        target_path = self.output_dir / filename
                        
                        if target_path.exists():
                            self.logger.info("Using cached OpenAI image for slot %s", img.get("slot_id"))
                            img["render_status"] = "rendered"
                            img["local_path"] = str(target_path)
                            continue

                        self.logger.info("Generating OpenAI image for slot %s: %s", img.get("slot_id"), prompt)
                        
                        try:
                            # Use OpenAI client to generate image
                            image_path = self.client.generate_image(prompt)
                            
                            # Move generated image to output directory for consistency
                            gen_path = Path(image_path)
                            # target_path is already defined above
                            
                            # Handle potential collision on Windows
                            if target_path.exists():
                                target_path.unlink()
                            
                            shutil.move(str(gen_path), str(target_path))
                            
                            # Update slot metadata
                            img["render_status"] = "rendered"
                            img["local_path"] = str(target_path)
                            self.logger.info("Successfully generated OpenAI image and saved to %s", target_path)
                        except Exception as e:
                            self.logger.error("Failed to generate OpenAI image for %s: %s", img.get("slot_id"), e)
                            img["render_status"] = "failed"

            return image_placement

        result = self._run_with_retries(_execute, "OpenAIImageAgent")
        return self._save_json(result, self.OUTPUT_FILE)

    def validate(self, result: Any) -> None:
        if not isinstance(result, dict) or not result.get("pages"):
            raise ValueError("OpenAIImageAgent result must contain pages")
