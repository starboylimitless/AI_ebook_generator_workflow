from __future__ import annotations
import os
import requests
from pathlib import Path
from openai import OpenAI
import logging

logger = logging.getLogger("utils.openai_image_client")

class OpenAIImageClient:
    """
    OpenAI DALL-E 3 image generation client.
    Downloads generated image locally and returns path.
    """

    def __init__(self, api_key: str | None = None) -> None:
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")
        self.client = OpenAI(api_key=api_key)

    def generate_image(self, prompt: str) -> str:
        """
        Generate image using DALL-E 3 and save locally.
        """
        try:
            logger.info(f"Generating OpenAI image for prompt: {prompt[:50]}...")
            
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )

            image_url = response.data[0].url
            if not image_url:
                raise ValueError("No image URL returned from OpenAI")

            # Download the image
            image_response = requests.get(image_url, timeout=30)
            image_response.raise_for_status()

            output_dir = Path("generated_images")
            output_dir.mkdir(exist_ok=True)

            # Use a hash of the prompt for a consistent filename
            image_path = output_dir / f"oa_{abs(hash(prompt))}.png"

            with open(image_path, "wb") as f:
                f.write(image_response.content)

            logger.info(f"Successfully saved OpenAI image to: {image_path}")
            return str(image_path)

        except Exception as e:
            logger.error(f"OpenAI Image Generation Error: {e}")
            raise
